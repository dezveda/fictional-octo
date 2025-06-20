import asyncio
import json
import asyncio # For asyncio.TimeoutError
import aiohttp # For aiohttp.ClientError
from binance import AsyncClient, BinanceSocketManager
import logging
from trading_bot.utils import settings
from copy import deepcopy # For get_order_book_snapshot

# Configure logging for the fetcher
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Configured in main.py

class DataFetcher:
    def _map_interval_str_to_api_const(self, interval_str):
        # Mapping from settings string to python-binance AsyncClient constants
        mapping = {
            # "1s": AsyncClient.KLINE_INTERVAL_1SECOND, # WebSocket uses direct string for 1s if needed.
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
        }
        const = mapping.get(interval_str.lower())
        if const is None:
            logger.warning(f"[DataFetcher] Unsupported kline interval string: {interval_str}. Defaulting to 1m.")
            if self.on_status_update:
                 self.on_status_update(f"[DataFetcher] Warning: Unsupported interval {interval_str}, using 1m.")
            return AsyncClient.KLINE_INTERVAL_1MINUTE
        return const

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
            return

        if self.on_status_update:
            self.on_status_update(f"[DataFetcher] Initializing API client (timeout: {settings.REQUEST_TIMEOUT}s)...")
        logger.info(f"[DataFetcher] Initializing API client (timeout: {settings.REQUEST_TIMEOUT}s)...")

        try:
            self.client = await AsyncClient.create(request_timeout=settings.REQUEST_TIMEOUT)
            self.bsm = BinanceSocketManager(self.client)
            await self.client.ping()
            if self.on_status_update:
                self.on_status_update("[DataFetcher] API Client initialized and ping successful.")
            logger.info("[DataFetcher] API Client initialized and ping successful.")
        except asyncio.TimeoutError:
            self.client = None
            self.bsm = None
            logger.error(f"[DataFetcher] API client initialization timed out after {settings.REQUEST_TIMEOUT}s.")
            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] Error: Connection to Binance timed out ({settings.REQUEST_TIMEOUT}s). Check network/firewall.")
        except aiohttp.ClientError as e:
            self.client = None
            self.bsm = None
            logger.error(f"[DataFetcher] API client initialization failed due to a network error: {e}", exc_info=True)
            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] Error: Network issue connecting to Binance: {e}")
        except Exception as e:
            self.client = None
            self.bsm = None
            logger.error(f"[DataFetcher] API client initialization failed: {e}", exc_info=True)
            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] Error: API client initialization failed: {e}")

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
            if self.on_kline_callback and self.latest_kline_data:
                try:
                    self.on_kline_callback(self.latest_kline_data)
                except Exception as e: logger.error(f'Error in on_kline_callback: {e}')

    def _process_depth_message(self, msg):
        if 'e' in msg and msg['e'] == 'error':
            logger.error(f"[DataFetcherOB] Depth stream error: {msg.get('m')}")
            if self.on_status_update: self.on_status_update(f"[OB Error] {msg.get('m')}")
            return

        try:
            new_bids = {float(price_level): float(qty) for price_level, qty in msg.get('bids', [])[:self.local_ob_max_levels]}
            new_asks = {float(price_level): float(qty) for price_level, qty in msg.get('asks', [])[:self.local_ob_max_levels]}

            self.order_book['bids'] = new_bids
            self.order_book['asks'] = new_asks

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
            if self.on_status_update:
                self.on_status_update(f"[DataFetcherOB] Partial depth stream for {self.symbol} initiated.")
            # Keep this task alive until stop_event or error
            while not (self.stop_event and self.stop_event.is_set()):
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


    async def fetch_historical_klines(self, symbol_to_fetch, interval_for_api, lookback_start_str=None, limit=None):
        if not self.client:
            logger.info("[DataFetcher] Client not initialized. Initializing for historical data fetch...")
            await self._initialize_client()
            if not self.client:
                logger.error("[DataFetcher] Failed to initialize client for historical data.")
                if self.on_status_update: self.on_status_update("[DataFetcher] Error: Failed to initialize client for historical data.")
                return []

        if self.on_status_update:
            status_msg = f"[DataFetcher] Fetching historical klines for {symbol_to_fetch}, interval {interval_for_api}..."
            if limit and not lookback_start_str: status_msg += f" Last {limit} klines."
            elif lookback_start_str: status_msg += f" Starting from {lookback_start_str}."
            else: logger.warning("[DataFetcher] fetch_historical_klines called without lookback_start_str or limit."); return []
            self.on_status_update(status_msg)

        logger.info(f"Fetching historical data: Symbol={symbol_to_fetch}, Interval={interval_for_api}, Start={lookback_start_str}, Limit={limit}")

        try:
            if lookback_start_str:
                raw_klines = await self.client.get_historical_klines(symbol=symbol_to_fetch, interval=interval_for_api, start_str=lookback_start_str)
            elif limit:
                raw_klines = await self.client.get_historical_klines(symbol=symbol_to_fetch, interval=interval_for_api, limit=limit)
            else: logger.error("[DataFetcher] Invalid parameters for historical kline fetch."); return []
        except Exception as e:
            logger.error(f"[DataFetcher] Error fetching historical klines: {e}", exc_info=True)
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Error fetching historical klines: {e}")
            return []

        processed_klines = []
        if raw_klines:
            for k in raw_klines:
                try:
                    processed_kline = {'t': int(k[0]),'o': float(k[1]),'h': float(k[2]),'l': float(k[3]),'c': float(k[4]),'v': float(k[5])}
                    processed_klines.append(processed_kline)
                except (IndexError, ValueError) as conversion_e:
                    logger.error(f"[DataFetcher] Error processing raw kline data: {conversion_e}. Data: {k}")
                    continue
            if self.on_status_update: self.on_status_update(f"[DataFetcher] Successfully fetched and processed {len(processed_klines)} historical klines.")
            logger.info(f"Fetched {len(processed_klines)} historical klines for {symbol_to_fetch}.")
        else:
            if self.on_status_update: self.on_status_update(f"[DataFetcher] No historical klines returned for {symbol_to_fetch} with given parameters.")
            logger.info(f"No historical klines returned for {symbol_to_fetch} with params: interval={interval_for_api}, start={lookback_start_str}, limit={limit}")
        return processed_klines

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
