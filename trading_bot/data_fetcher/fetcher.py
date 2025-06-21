import asyncio
import json
import asyncio # For asyncio.TimeoutError
import aiohttp # For aiohttp.ClientError
import os # For path operations
from binance import AsyncClient, BinanceSocketManager
import logging
from trading_bot.utils import settings
from copy import deepcopy # For get_order_book_snapshot

# Configure logging for the fetcher
logger = logging.getLogger(__name__)

# --- Kline Data Storage Functions ---

KLINE_DATA_DIR = "trading_bot/data/kline_data/"

def _get_kline_filepath(symbol: str, interval: str) -> str:
    """
    Constructs the filepath for storing/retrieving kline data.
    e.g., trading_bot/data/kline_data/BTCUSDT_1h.json
    """
    filename = f"{symbol.upper()}_{interval}.json"
    return os.path.join(KLINE_DATA_DIR, filename)

def save_klines(filepath: str, klines_data: list) -> bool:
    """
    Saves kline data to a JSON file.

    Args:
        filepath: The full path to the file.
        klines_data: A list of kline data points (e.g., list of lists or list of dicts).

    Returns:
        True if saving was successful, False otherwise.
    """
    try:
        # Ensure the directory exists
        dir_name = os.path.dirname(filepath)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            logger.info(f"[KlinesStorage] Created directory: {dir_name}")

        with open(filepath, 'w') as f:
            json.dump(klines_data, f, indent=4)
        logger.info(f"[KlinesStorage] Successfully saved {len(klines_data)} klines to {filepath}")
        return True
    except IOError as e:
        logger.error(f"[KlinesStorage] IOError writing to {filepath}: {e}", exc_info=True)
    except TypeError as e:
        logger.error(f"[KlinesStorage] TypeError during JSON serialization for {filepath}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[KlinesStorage] Unexpected error saving klines to {filepath}: {e}", exc_info=True)
    return False

def load_klines(filepath: str) -> list:
    """
    Loads kline data from a JSON file.

    Args:
        filepath: The full path to the file.

    Returns:
        A list of kline data points, or an empty list if the file doesn't exist or an error occurs.
    """
    if not os.path.exists(filepath):
        logger.info(f"[KlinesStorage] File not found: {filepath}. Returning empty list.")
        return []
    try:
        with open(filepath, 'r') as f:
            klines_data = json.load(f)
        logger.info(f"[KlinesStorage] Successfully loaded {len(klines_data)} klines from {filepath}")
        return klines_data
    except json.JSONDecodeError as e:
        logger.error(f"[KlinesStorage] JSONDecodeError reading {filepath}: {e}. Returning empty list.", exc_info=True)
    except IOError as e:
        logger.error(f"[KlinesStorage] IOError reading {filepath}: {e}. Returning empty list.", exc_info=True)
    except Exception as e:
        logger.error(f"[KlinesStorage] Unexpected error loading klines from {filepath}: {e}. Returning empty list.", exc_info=True)
    return []

# --- End Kline Data Storage Functions ---
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Configured in main.py

class DataFetcher:
    _INTERVAL_MAPPING = {
        "1m": AsyncClient.KLINE_INTERVAL_1MINUTE,
        "3m": AsyncClient.KLINE_INTERVAL_3MINUTE,
        "5m": AsyncClient.KLINE_INTERVAL_5MINUTE,
        "15m": AsyncClient.KLINE_INTERVAL_15MINUTE,
        "30m": AsyncClient.KLINE_INTERVAL_30MINUTE,
        "1h": AsyncClient.KLINE_INTERVAL_1HOUR,
        "2h": AsyncClient.KLINE_INTERVAL_2HOUR,
        "4h": AsyncClient.KLINE_INTERVAL_4HOUR,
        "6h": AsyncClient.KLINE_INTERVAL_6HOUR,
        "8h": AsyncClient.KLINE_INTERVAL_8HOUR,
        "12h": AsyncClient.KLINE_INTERVAL_12HOUR,
        "1d": AsyncClient.KLINE_INTERVAL_1DAY,
        # "1s" is often handled differently (e.g., WebSocket only or specific API endpoint)
        # For historical, Binance API does not support "1s" via get_historical_klines
    }
    _REVERSE_INTERVAL_MAPPING = {v: k for k, v in _INTERVAL_MAPPING.items()}

    def _map_interval_str_to_api_const(self, interval_str):
        const = self._INTERVAL_MAPPING.get(interval_str.lower())
        if const is None:
            logger.warning(f"[DataFetcher] Unsupported kline interval string: {interval_str}. Defaulting to 1m.")
            if self.on_status_update:
                 self.on_status_update(f"[DataFetcher] Warning: Unsupported interval {interval_str}, using 1m.")
            return AsyncClient.KLINE_INTERVAL_1MINUTE # Default
        return const

    def _map_api_const_to_interval_str(self, api_const):
        interval_str = self._REVERSE_INTERVAL_MAPPING.get(api_const)
        if interval_str is None:
            logger.warning(f"[DataFetcher] Unsupported API kline constant: {api_const}. Cannot determine interval string for filename.")
            # Fallback or raise error, depending on desired strictness
            # For now, let's return a placeholder that will likely fail file operations,
            # or handle it in the calling function.
            return None # Or raise ValueError
        return interval_str

    def __init__(self, symbol=settings.TRADING_SYMBOL,
                 on_kline_callback=None,
                 on_price_update_callback=None,
                 on_status_update=None,
                 stop_event=None,
                 on_orderbook_update_callback=None): # New callback
        self.symbol = symbol
        self.client = None
        self.bsm = None
        self.kline_socket = None # Renamed from self.socket for clarity
        self.depth_socket = None   # For the depth stream socket object
        self.latest_price = None
        self.latest_kline_data = None
        self.on_kline_callback = on_kline_callback
        self.on_price_update_callback = on_price_update_callback
        self.on_status_update = on_status_update
        self.stop_event = stop_event

        self.fetch_interval_str = settings.KLINE_FETCH_INTERVAL
        self.api_interval = self._map_interval_str_to_api_const(self.fetch_interval_str)

        # Order Book related attributes
        self.order_book = {'bids': {}, 'asks': {}} # Store as {price_float: quantity_float}
        self.local_ob_max_levels = settings.LOCAL_ORDER_BOOK_MAX_LEVELS
        self.on_orderbook_update_callback = on_orderbook_update_callback
        self.depth_socket_task = None # To keep track of the depth stream task

    async def _initialize_client(self):
        if self.client:
            logger.info("[DataFetcher] Client already initialized.")
            return

        if self.on_status_update:
            self.on_status_update(f"[DataFetcher] Initializing API client (timeout: {settings.REQUEST_TIMEOUT}s)...")
        logger.info(f"[DataFetcher] Initializing API client (timeout: {settings.REQUEST_TIMEOUT}s)...")
        # Ensure settings is imported if not already done at module level
        # from trading_bot.utils import settings # This should be at the top of the file

        client_created_successfully = False
        try:
            self.client = await AsyncClient.create(request_timeout=settings.REQUEST_TIMEOUT)
            self.bsm = BinanceSocketManager(self.client) # Initialize BSM here
            await self.client.ping()
            client_created_successfully = True
            if self.on_status_update:
                self.on_status_update("[DataFetcher] API Client initialized and ping successful.")
            logger.info("[DataFetcher] API Client initialized and ping successful.")

        except asyncio.TimeoutError:
            self.client = None; self.bsm = None # Ensure bsm is also None on failure
            logger.error(f"[DataFetcher] API client initialization timed out after {settings.REQUEST_TIMEOUT}s.")
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Error: Connection to Binance timed out ({settings.REQUEST_TIMEOUT}s). Check network/firewall.")
        except aiohttp.ClientError as e:
            self.client = None; self.bsm = None
            logger.error(f"[DataFetcher] API client initialization failed due to a network error: {e}", exc_info=True)
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Error: Network issue connecting to Binance: {e}")
        except Exception as e:
            self.client = None; self.bsm = None
            logger.error(f"[DataFetcher] API client initialization failed: {e}", exc_info=True)
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Error: API client initialization failed: {e}")
        finally:
            # Ensure self.bsm is None if self.client is None after initialization attempt.
            if self.client is None:
                self.bsm = None
            logger.critical(f"[DataFetcher] _initialize_client: self.client is {self.client}, self.bsm is {self.bsm} after create attempt. Success: {client_created_successfully}")
            # No need for the original 'if not client_created_successfully: self.bsm = None'
            # because if client_created_successfully is false, self.client would be None,
            # and the line above (if self.client is None: self.bsm = None) handles it.

    def _process_kline_message(self, msg):
        if msg.get('e') == 'error':
            logger.error(f"WebSocket Error: {msg.get('m')}")
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Error: {msg.get('m')}")
            return

        if msg.get('e') == 'kline':
            kline = msg.get('k', {})
            self.latest_price = float(kline.get('c'))
            self.latest_kline_data = kline

            if self.on_price_update_callback and self.latest_price is not None:
                logger.debug(f"[DataFetcher] Live kline. Latest price: {self.latest_price}. Triggering on_price_update_callback if callback set.")
                try:
                    self.on_price_update_callback(f"{self.latest_price:.2f}")
                except Exception as e: logger.error(f'Error in on_price_update_callback: {e}')

            # Process for on_kline_callback (typically for live strategy updates)
            if self.on_kline_callback and self.latest_kline_data:
                try:
                    self.on_kline_callback(self.latest_kline_data) # self.latest_kline_data is already in dict format from Binance
                except Exception as e: logger.error(f'Error in on_kline_callback: {e}')

            # Save closed kline to persistent storage
            if kline.get('x'): # Check if kline is closed
                logger.info(f"[DataFetcher] Closed kline received for {self.symbol} ({self.fetch_interval_str}). Attempting to save.")

                # Format the kline data into the standard dictionary structure used by historical fetcher
                # Binance kline data: {'t': startTime, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume, 'x': isClosed, ...}
                closed_kline_data = {
                    't': int(kline['t']),
                    'o': float(kline['o']),
                    'h': float(kline['h']),
                    'l': float(kline['l']),
                    'c': float(kline['c']),
                    'v': float(kline['v'])
                }

                filepath = _get_kline_filepath(self.symbol, self.fetch_interval_str)
                existing_klines = load_klines(filepath)

                # Append or update logic
                if existing_klines and existing_klines[-1]['t'] == closed_kline_data['t']:
                    logger.info(f"[DataFetcher] Updating last kline in {filepath} for timestamp {closed_kline_data['t']}.")
                    existing_klines[-1] = closed_kline_data
                else:
                    # If list is empty, or this kline is newer than the last one, append.
                    # We assume klines from websocket arrive in order for a given symbol/interval.
                    # If there's a possibility of out-of-order klines, a sort would be needed,
                    # but that's unlikely for live stream of final klines.
                    if existing_klines and existing_klines[-1]['t'] > closed_kline_data['t']:
                        logger.warning(f"[DataFetcher] New kline for {self.symbol} has older timestamp than last saved. Appending and sorting might be needed if this occurs often.")
                        # For now, just append. If this becomes an issue, need to insert and sort or use map-based merge like in historical.
                    existing_klines.append(closed_kline_data)
                    logger.info(f"[DataFetcher] Appending new kline to {filepath} for timestamp {closed_kline_data['t']}.")

                if save_klines(filepath, existing_klines):
                    logger.info(f"[DataFetcher] Successfully saved updated klines ({len(existing_klines)} total) to {filepath} for {self.symbol} ({self.fetch_interval_str}).")
                else:
                    logger.error(f"[DataFetcher] Failed to save updated klines to {filepath} for {self.symbol} ({self.fetch_interval_str}).")

    def _process_depth_message(self, msg):
        logger.critical("[DataFetcherOB] METHOD ENTRY: _process_depth_message() - A RAW DEPTH MESSAGE WAS RECEIVED FROM WEBSOCKET.")
        logger.info(f"[DataFetcherOB] Full raw depth message received: {msg}")
        logger.debug(f"[DataFetcherOB] Received depth message summary: lastUpdateId={msg.get('lastUpdateId')}, bids_count={len(msg.get('bids',[]))}, asks_count={len(msg.get('asks',[]))}")
        if 'e' in msg and msg['e'] == 'error':
            logger.error(f"[DataFetcherOB] Depth stream error: {msg.get('m')}")
            if self.on_status_update: self.on_status_update(f"[OB Error] {msg.get('m')}")
            return

        try:
            new_bids = {float(price_level): float(qty) for price_level, qty in msg.get('bids', [])[:self.local_ob_max_levels]}
            new_asks = {float(price_level): float(qty) for price_level, qty in msg.get('asks', [])[:self.local_ob_max_levels]}

            self.order_book['bids'] = new_bids
            self.order_book['asks'] = new_asks
            # For more detailed debugging of content, uncomment below. Can be very verbose.
            # logger.debug(f"[DataFetcherOB] Processed - Top 3 Bids: {list(self.order_book['bids'].items())[:3]}, Top 3 Asks: {list(self.order_book['asks'].items())[:3]}")

            logger.debug(f"[DataFetcherOB] Order book processed. Triggering on_orderbook_update_callback if set.")
            if self.on_orderbook_update_callback:
                self.on_orderbook_update_callback(self.get_order_book_snapshot())
        except Exception as e:
            logger.error(f"[DataFetcherOB] Error processing depth message: {e}. Msg: {msg}", exc_info=True)

    async def start_kline_stream(self): # Renamed from start_fetching for clarity
        if not self.client or not self.bsm:
            logger.error("[DataFetcher] Client/BSM not initialized. Cannot start kline stream.")
            if self.on_status_update: self.on_status_update("[KlineStream Error] Client not ready.")
            return

        if self.on_status_update:
            self.on_status_update(f"[DataFetcher] Starting {self.symbol} {self.fetch_interval_str} kline WebSocket...")

        self.kline_socket = self.bsm.kline_socket(symbol=self.symbol, interval=self.api_interval)

        try:
            async with self.kline_socket as stream:
                if self.on_status_update:
                    self.on_status_update(f"[DataFetcher] Kline WebSocket connection established for {self.symbol} {self.fetch_interval_str}.")
                while True:
                    if self.stop_event and self.stop_event.is_set():
                        logger.info("[DataFetcher] Stop event received, exiting kline WebSocket loop.")
                        break
                    msg = await stream.recv()
                    self._process_kline_message(msg)
        except Exception as e:
            logger.error(f"[DataFetcher] Kline WebSocket connection error: {e}", exc_info=True)
            if self.on_status_update: self.on_status_update(f"[KlineStream Error] WebSocket Error: {e}. Check logs.")
        finally:
            logger.info("[DataFetcher] Exited kline WebSocket loop.")
            self.kline_socket = None # Clear socket ref

    async def start_depth_stream(self):
        logger.critical("[DataFetcherOB] METHOD ENTRY: start_depth_stream()")
        if not self.client or not self.bsm:
            logger.error("[DataFetcherOB] Client/BSM not initialized. Cannot start depth stream.")
            if self.on_status_update: self.on_status_update("[OB Error] Client not ready.")
            return

        depth_level_int = settings.ORDER_BOOK_STREAM_DEPTH_LEVEL
        update_speed_str = settings.ORDER_BOOK_UPDATE_SPEED_MS
        # Construct stream name as per python-binance e.g. 'btcusdt@depth20@100ms'
        # OR use specific parameters if start_depth_socket supports them (check library version)
        # For recent versions, it's start_partial_book_depth_socket(symbol, level, speed, callback)
        # Assuming the version where callback is used with start_partial_book_depth_socket:

        # The prompt's example used `bsm.start_depth_socket` which is for *diff* depth stream.
        # For partial book depth (snapshots), it's `start_partial_book_depth_socket`.
        # Let's use partial book depth as it's simpler to manage state (no merging diffs).
        # Stream name: f"{self.symbol.lower()}@depth{depth_level_int}@{update_speed_str}"

        if self.on_status_update:
            self.on_status_update(f"[DataFetcherOB] Starting {self.symbol} partial depth stream (L{depth_level_int}@{update_speed_str})...")
        logger.info(f"[DataFetcherOB] Starting {self.symbol} partial depth stream (L{depth_level_int}@{update_speed_str})...")
        logger.critical(f"[DataFetcherOB] Attempting to start BSM depth socket. Symbol: {self.symbol}, Level: {settings.ORDER_BOOK_STREAM_DEPTH_LEVEL}, Speed: {settings.ORDER_BOOK_UPDATE_SPEED_MS}")

        try:
            # For python-binance >= 1.0.17, use start_partial_book_depth_socket
            self.depth_socket = self.bsm.start_partial_book_depth_socket(
                symbol=self.symbol,
                level=depth_level_int,
                interval=update_speed_str, #This is the 'speed' param, e.g. '100ms'
                callback=self._process_depth_message
            )
            # This method in BSM starts the task; we don't need to run a recv loop here.
            # We need to await BSM.start() in main.py if not already done for other sockets.
            # For now, assume BSM is started elsewhere or this call is enough.
            # The 'socket' returned by BSM when using callbacks is often just a control object or None.
            # The actual socket runs in BSM's context.
            logger.info(f"[DataFetcherOB] Depth socket for {self.symbol} successfully opened/callback registered. Waiting for messages...")
            if self.on_status_update:
                self.on_status_update(f"[DataFetcherOB] Partial depth stream for {self.symbol} initiated.")
            # Keep this task alive until stop_event or error
            while not (self.stop_event and self.stop_event.is_set()):
                # logger.debug(f'[DataFetcherOB] start_depth_stream task alive, stop_event: {self.stop_event.is_set() if self.stop_event else "N/A"}') # Too verbose for 100ms stream
                await asyncio.sleep(1) # Keep alive, check stop_event
            logger.info(f"[DataFetcherOB] Stop event for depth stream {self.symbol}.")

        except Exception as e:
            logger.error(f"[DataFetcherOB] Partial depth stream for {self.symbol} encountered an error: {e}", exc_info=True)
            if self.on_status_update:
                self.on_status_update(f"[OB Error] Partial depth stream failed: {e}")
        finally:
            logger.info(f"[DataFetcherOB] Partial depth stream for {self.symbol} has stopped.")
            # BSM handles socket closure on bsm.close() or when individual socket tasks are cancelled.
            # If a socket object was returned and stored in self.depth_socket, it would be closed.
            # With callback-based BSM sockets, explicit closure here might not be needed if BSM handles it.
            self.depth_socket = None

    async def stop_all_streams(self): # Renamed from stop_fetching for clarity
        if self.on_status_update:
            self.on_status_update(f"[DataFetcher] Stopping all streams...")

        if self.stop_event: # Signal all managed tasks to stop
            self.stop_event.set()

        # If kline_socket was managed by `async with`, it closes on exit.
        # If depth_socket_task holds an asyncio.Task, it needs to be cancelled.
        if self.depth_socket_task and not self.depth_socket_task.done():
            logger.info('[DataFetcher] Cancelling depth socket task...')
            self.depth_socket_task.cancel()
            try: await self.depth_socket_task
            except asyncio.CancelledError: logger.info('[DataFetcher] Depth socket task cancelled successfully.')
            except Exception as e_cancel: logger.error(f'[DataFetcher] Error awaiting cancelled depth task: {e_cancel}')
        self.depth_socket_task = None

        # The kline_socket (self.kline_socket) if run with `async with` will close when its loop exits.
        # The BSM manages its own sockets. A call to bsm.close() would be more general if needed.
        # However, client.close_connection() is the most common way to shut down all connections.
        if self.client:
            logger.info("[DataFetcher] Closing client connection (should stop BSM sockets)...")
            await self.client.close_connection()
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Client connection closed.")
        self.client = None
        self.bsm = None
        self.kline_socket = None
        self.depth_socket = None


    async def fetch_historical_klines(self, symbol_to_fetch: str, interval_for_api: str, lookback_start_str: str = None, limit: int = None) -> list:
        if not self.client:
            logger.info("[DataFetcher] Client not initialized. Initializing for historical data fetch...")
            await self._initialize_client()
            if not self.client: # Check again after attempt
                logger.error("[DataFetcher] Failed to initialize client for historical data.")
                if self.on_status_update: self.on_status_update("[DataFetcher] Error: Failed to initialize client for historical data.")
                return []

        interval_str_for_file = self._map_api_const_to_interval_str(interval_for_api)
        if not interval_str_for_file:
            logger.error(f"[DataFetcher] Could not map API interval {interval_for_api} to string. Cannot proceed with file operations for historical klines.")
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Error: Internal error with interval mapping for {interval_for_api}.")
            return [] # Cannot form a filename

        filepath = _get_kline_filepath(symbol_to_fetch, interval_str_for_file)
        logger.info(f"[DataFetcher] Historical kline filepath: {filepath}")

        existing_klines = load_klines(filepath)
        if existing_klines:
            logger.info(f"[DataFetcher] Loaded {len(existing_klines)} klines from cache: {filepath}")
            # Determine the timestamp of the last kline to fetch new ones.
            # Binance API uses milliseconds for kline timestamps.
            # kline format: {'t': time, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume}
            last_kline_ts = existing_klines[-1]['t'] # Assuming klines are sorted, 't' is timestamp

            # To fetch klines *after* this one, start_str should be last_kline_ts + 1 ms
            # However, Binance's get_historical_klines `start_str` is inclusive.
            # If the last kline is for time T, and interval is 1m, T is the OPEN time of that minute.
            # Fetching from T again would give that same kline.
            # Fetching from T + 1ms would also give that same kline if T was 1678886400000 (start of a minute)
            # We need to fetch from the *next* interval's open time.
            # For a 1-minute interval, if last kline starts at 10:00:00 (ts_open), it closes at 10:00:59.999.
            # The next kline will start at 10:01:00.
            # So, start_str should be the open time of the kline immediately following the last saved one.
            # The kline data from Binance includes [open_time, open, high, low, close, volume, close_time, ...]
            # Our processed kline is {'t': open_time, ...}
            # If interval is 1m (60000 ms), next open time is last_kline_ts['t'] + 60000
            # This needs to be generalized for different intervals.
            # A simpler way: fetch from last_kline_ts. Duplicates will be handled during merge.
            # This ensures we don't miss any klines if the bot stopped right at an interval boundary.

            # Let's adjust start_str to be the open time of the last saved kline.
            # The merge logic will handle duplicates.
            effective_lookback_start_str = str(last_kline_ts)

            # When fetching incrementally, 'limit' should not be used, as we want all data since last point.
            api_limit = None # Override limit
            logger.info(f"[DataFetcher] Fetching new klines for {symbol_to_fetch} ({interval_str_for_file}) since {effective_lookback_start_str} (from last saved kline).")
            if self.on_status_update:
                 self.on_status_update(f"[DataFetcher] Cache found. Fetching new {symbol_to_fetch} ({interval_str_for_file}) klines since timestamp {last_kline_ts}.")
        else:
            logger.info(f"[DataFetcher] No cached klines found for {symbol_to_fetch} ({interval_str_for_file}) at {filepath}.")
            effective_lookback_start_str = lookback_start_str
            api_limit = limit # Use original limit
            if self.on_status_update:
                status_msg = f"[DataFetcher] No cache. Fetching historical klines for {symbol_to_fetch} ({interval_str_for_file})."
                if api_limit and not effective_lookback_start_str: status_msg += f" Last {api_limit} klines."
                elif effective_lookback_start_str: status_msg += f" Starting from {effective_lookback_start_str}."
                else: logger.warning("[DataFetcher] fetch_historical_klines called without lookback_start_str or limit (and no cache)."); return [] # Or default fetch, e.g., last 500
                self.on_status_update(status_msg)

        if not effective_lookback_start_str and not api_limit:
            logger.warning(f"[DataFetcher] Insufficient parameters for fetching historical klines for {symbol_to_fetch} ({interval_str_for_file}). Need start_str or limit if no cache.")
            # Default to fetching a small number of recent klines if no params and no cache
            # For example, fetch last 500 klines.
            # api_limit = 500
            # logger.info(f"[DataFetcher] Defaulting to fetching last {api_limit} klines for {symbol_to_fetch} ({interval_str_for_file}).")
            # Or simply return if strict parameter requirement is desired. For now, let's be strict.
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Error: Need start date or limit for initial fetch of {symbol_to_fetch}.")
            return existing_klines # Return what we have (empty if no cache)

        logger.info(f"Fetching historical data from API: Symbol={symbol_to_fetch}, Interval API Const={interval_for_api}, StartStr={effective_lookback_start_str}, Limit={api_limit}")
        raw_klines_from_api = []
        try:
            if effective_lookback_start_str:
                raw_klines_from_api = await self.client.get_historical_klines(symbol=symbol_to_fetch, interval=interval_for_api, start_str=effective_lookback_start_str, limit=api_limit) # Pass limit only if set
            elif api_limit: # Only limit is provided
                raw_klines_from_api = await self.client.get_historical_klines(symbol=symbol_to_fetch, interval=interval_for_api, limit=api_limit)
            # If both are None, get_historical_klines might have its own default or error out.
            # The check above (not effective_lookback_start_str and not api_limit) should prevent this.
        except Exception as e:
            logger.error(f"[DataFetcher] Error fetching historical klines from API: {e}", exc_info=True)
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Error fetching API data: {e}")
            return existing_klines # Return what we had from cache, if any

        newly_processed_klines = []
        if raw_klines_from_api:
            for k_raw in raw_klines_from_api:
                try:
                    # Standard Binance Kline format:
                    # [ Kline open time, Open price, High price, Low price, Close price, Volume, Kline close time, Quote asset volume, Number of trades, Taker buy base asset volume, Taker buy quote asset volume, Ignore ]
                    processed_kline = {'t': int(k_raw[0]), 'o': float(k_raw[1]), 'h': float(k_raw[2]), 'l': float(k_raw[3]), 'c': float(k_raw[4]), 'v': float(k_raw[5])}
                    newly_processed_klines.append(processed_kline)
                except (IndexError, ValueError) as conversion_e:
                    logger.error(f"[DataFetcher] Error processing raw kline data from API: {conversion_e}. Data: {k_raw}")
                    continue
            logger.info(f"[DataFetcher] Fetched and processed {len(newly_processed_klines)} new klines from API for {symbol_to_fetch} ({interval_str_for_file}).")
        else:
            logger.info(f"[DataFetcher] No new klines returned from API for {symbol_to_fetch} ({interval_str_for_file}) with current parameters.")

        if not newly_processed_klines and not existing_klines:
            logger.info(f"[DataFetcher] No klines available (neither cached nor fetched) for {symbol_to_fetch} ({interval_str_for_file}).")
            if self.on_status_update: self.on_status_update(f"[DataFetcher] No klines found for {symbol_to_fetch} ({interval_str_for_file}).")
            return []

        # Merge existing and new klines
        # Use a dictionary keyed by timestamp to handle overlaps and ensure uniqueness
        merged_klines_map = {k['t']: k for k in existing_klines}
        for k_new in newly_processed_klines:
            merged_klines_map[k_new['t']] = k_new # New data overwrites old if timestamps overlap

        # Convert back to a list and sort by timestamp
        final_klines_list = sorted(list(merged_klines_map.values()), key=lambda k: k['t'])

        logger.info(f"[DataFetcher] Merged klines. Total count for {symbol_to_fetch} ({interval_str_for_file}): {len(final_klines_list)}")

        if save_klines(filepath, final_klines_list):
            logger.info(f"[DataFetcher] Successfully saved {len(final_klines_list)} total klines to {filepath}.")
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Saved {len(final_klines_list)} klines for {symbol_to_fetch} ({interval_str_for_file}).")
        else:
            logger.warning(f"[DataFetcher] Failed to save merged klines to {filepath}.")
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Warning: Failed to save klines for {symbol_to_fetch} to cache.")
            # Still return the klines even if saving failed, as they are in memory.

        return final_klines_list

    def get_latest_price(self):
        return self.latest_price

    def get_latest_kline(self):
        return self.latest_kline_data

    def get_order_book_snapshot(self, num_levels=None):
        if num_levels is None:
            num_levels = self.local_ob_max_levels

        # Use deepcopy to prevent modification of internal state if caller modifies the snapshot
        temp_order_book = deepcopy(self.order_book)

        sorted_bids = sorted(temp_order_book['bids'].items(), key=lambda item: item[0], reverse=True)
        sorted_asks = sorted(temp_order_book['asks'].items(), key=lambda item: item[0])

        return {
            'bids': sorted_bids[:num_levels],
            'asks': sorted_asks[:num_levels]
        }

# Example Usage (for testing purposes, will be removed or refactored)
async def main_test():
    def print_status(message): print(f"STATUS: {message}")
    def handle_new_kline_for_test(kline_data): print(f"KLINE_TEST_CALLBACK: Close: {kline_data['c']}, Time: {kline_data['t']}")
    def handle_new_price_for_test(price_str): print(f"PRICE_TEST_CALLBACK: Price: {price_str}")
    def handle_ob_update_for_test(ob_snapshot):
        print(f"OB_CALLBACK: Top Bid: {ob_snapshot['bids'][0] if ob_snapshot['bids'] else 'N/A'}, Top Ask: {ob_snapshot['asks'][0] if ob_snapshot['asks'] else 'N/A'}")

    stop_event_test = asyncio.Event() # For testing stop
    fetcher = DataFetcher(
        on_kline_callback=handle_new_kline_for_test,
        on_price_update_callback=handle_new_price_for_test,
        on_status_update=print_status,
        on_orderbook_update_callback=handle_ob_update_for_test,
        stop_event=stop_event_test
    )

    try:
        print_status("Attempting to initialize client for tests...")
        await fetcher._initialize_client() # Manually init for some tests
        if not fetcher.client:
            print_status("Client initialization failed. Skipping further tests.")
            return

        print_status("Fetching sample historical klines (last 5 of 1m)...")
        hist_klines = await fetcher.fetch_historical_klines(
            symbol_to_fetch="BTCUSDT",
            interval_for_api=AsyncClient.KLINE_INTERVAL_1MINUTE,
            limit=5
        )
        if hist_klines:
            print_status(f"Fetched {len(hist_klines)} historical klines. First: {hist_klines[0]}, Last: {hist_klines[-1]}")
        else:
            print_status("No historical klines fetched for test.")

        print_status("Starting kline and depth streams for 5 seconds...")
        # Run streams concurrently for testing
        kline_task = asyncio.create_task(fetcher.start_kline_stream())
        depth_task = asyncio.create_task(fetcher.start_depth_stream())
        fetcher.depth_socket_task = depth_task # Assign for stop_fetching to find

        await asyncio.sleep(5) # Let them run for a bit
        print_status("5 seconds passed. Requesting stop.")
        stop_event_test.set() # Signal tasks to stop

        await asyncio.gather(kline_task, depth_task, return_exceptions=True) # Wait for tasks to finish
        print_status("Streams should be stopped.")

    except Exception as e:
        print_status(f"Unhandled error in main_test: {e}")
    finally:
        print_status("Calling final stop_all_streams...")
        await fetcher.stop_all_streams() # Ensure cleanup
        print_status("Fetching stopped.")

if __name__ == '__main__':
    print("Starting DataFetcher test...")
    asyncio.run(main_test())
