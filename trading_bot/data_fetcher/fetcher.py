import asyncio
import json
from binance import AsyncClient, BinanceSocketManager
import logging
from trading_bot.utils import settings

# Configure logging for the fetcher
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Configured in main.py

class DataFetcher:
    def _map_interval_str_to_api_const(self, interval_str):
        # Mapping from settings string to python-binance AsyncClient constants
        mapping = {
            # "1s": AsyncClient.KLINE_INTERVAL_1SECOND, # Typically not available for historical bulk fetch / may cause issues. WebSocket uses direct string for 1s.
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
            if self.on_status_update: # Ensure on_status_update is callable
                 self.on_status_update(f"[DataFetcher] Warning: Unsupported interval {interval_str}, using 1m.")
            return AsyncClient.KLINE_INTERVAL_1MINUTE
        return const

    def __init__(self, symbol=settings.TRADING_SYMBOL, on_kline_callback=None, on_price_update_callback=None, on_status_update=None, stop_event=None):
        self.symbol = symbol
        self.client = None
        self.bsm = None
        self.socket = None
        self.latest_price = None
        self.latest_kline_data = None
        self.on_kline_callback = on_kline_callback # For strategy processing
        self.on_price_update_callback = on_price_update_callback # For GUI price updates
        self.on_status_update = on_status_update # For status bar updates
        self.stop_event = stop_event # For graceful shutdown

        self.fetch_interval_str = settings.KLINE_FETCH_INTERVAL
        self.api_interval = self._map_interval_str_to_api_const(self.fetch_interval_str)


    async def _initialize_client(self):
        if self.on_status_update:
            self.on_status_update(f"[DataFetcher] Initializing Asynchronous Client...")
        self.client = await AsyncClient.create()
        self.bsm = BinanceSocketManager(self.client)
        if self.on_status_update:
            self.on_status_update(f"[DataFetcher] AsyncClient and BinanceSocketManager initialized.")

    def _process_kline_message(self, msg):
        '''
        Processes a kline/candlestick message.
        Example kline message:
        {
            "e": "kline",					// event type
            "E": 1499404907056,				// event time
            "s": "ETHBTC",					// symbol
            "k": {
                "t": 1499404860000, 		// kline start time
                "T": 1499404919999, 		// kline close time
                "s": "ETHBTC",				// symbol
                "i": "1m",					// interval
                "f": 77462,					// first trade id
                "L": 77465,					// last trade id
                "o": "0.10278577",			// open
                "c": "0.10278645",			// close
                "h": "0.10278712",			// high
                "l": "0.10278518",			// low
                "v": "17.47929838",			// volume
                "n": 4,						// number of trades
                "x": false,					// is this kline closed?
                "q": "1.79662878",			// quote asset volume
                "V": "2.34879809",			// taker buy base asset volume
                "Q": "0.24142730",			// taker buy quote asset volume
                "B": "13279784.01349473"	// ignore
            }
        }
        '''
        if msg.get('e') == 'error':
            logger.error(f"WebSocket Error: {msg.get('m')}")
            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] Error: {msg.get('m')}")
            return

        if msg.get('e') == 'kline':
            kline = msg.get('k', {})
            self.latest_price = float(kline.get('c')) # Closing price of the kline
            self.latest_kline_data = kline # kline is a dict like {'t':..., 'o':..., 'h':..., 'l':..., 'c':..., 'v':...}
            # logger.info(f"Symbol: {kline.get('s')}, Interval: {kline.get('i')}, Close: {self.latest_price}, Time: {kline.get('T')}")

            # Callbacks with new data
            if self.on_price_update_callback and self.latest_price is not None:
                logger.debug(f"[DataFetcher] Live kline. Latest price: {self.latest_price}. Triggering on_price_update_callback if callback set.")
                try:
                    self.on_price_update_callback(f"{self.latest_price:.2f}") # Pass formatted string
                except Exception as e:
                    logger.error(f'Error in on_price_update_callback: {e}')
            if self.on_kline_callback and self.latest_kline_data:
                try:
                    self.on_kline_callback(self.latest_kline_data) # Pass full kline dict
                except Exception as e:
                    logger.error(f'Error in on_kline_callback: {e}')

            if self.on_status_update:
                # This might be too verbose for every message, consider updating status less frequently
                # self.on_status_update(f"[DataFetcher] {self.symbol} Price: {self.latest_price}")
                pass


    async def start_fetching(self):
        await self._initialize_client()

        if self.on_status_update:
            self.on_status_update(f"[DataFetcher] Starting {self.symbol} {self.fetch_interval_str} kline WebSocket...")

        self.socket = self.bsm.kline_socket(symbol=self.symbol, interval=self.api_interval)

        try:
            async with self.socket as stream:
                if self.on_status_update:
                    self.on_status_update(f"[DataFetcher] WebSocket connection established for {self.symbol} {self.fetch_interval_str}.")
                while True:
                    if self.stop_event and self.stop_event.is_set():
                        logger.info("[DataFetcher] Stop event received, exiting WebSocket loop.")
                        break
                    msg = await stream.recv()
                    self._process_kline_message(msg)
        except Exception as e:
            logger.error(f"[DataFetcher] WebSocket connection error or processing error: {e}", exc_info=True)
            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] WebSocket Error: {e}. Check logs.")
            # No auto-reconnect here, main app would need to handle restart or fetcher crash
        finally:
            logger.info("[DataFetcher] Exited WebSocket loop.")
            # self.client might be None if _initialize_client failed or stop_fetching was called already
            if self.client and self.bsm: # bsm depends on client
                 logger.info("[DataFetcher] Attempting to close BinanceSocketManager and client connection in start_fetching finally block.")
                 # Closing the bsm explicitly might not always be necessary if client.close_connection handles it.
                 # await self.bsm.close() # This might not be the correct way to close BSM sockets fully.
                                        # The individual socket `self.socket` is closed by `async with`.
                 await self.client.close_connection()
                 logger.info("[DataFetcher] Client connection closed in start_fetching finally.")
                 self.client = None # Ensure client is None after closing
                 self.bsm = None # BSM is unusable without client
                 self.socket = None


    async def stop_fetching(self):
        if self.on_status_update:
            self.on_status_update(f"[DataFetcher] Stopping data fetching...")
        if self.client:
            await self.client.close_connection()
            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] Connection closed.")
        self.client = None
        self.bsm = None
        self.socket = None

    async def fetch_historical_klines(self, symbol_to_fetch, interval_for_api, lookback_start_str=None, limit=None): # Removed end_time_ms
        """
        Fetches historical kline data from Binance.
        symbol_to_fetch: The trading symbol (e.g., "BTCUSDT").
        interval_for_api: The kline interval string compatible with python-binance (e.g., AsyncClient.KLINE_INTERVAL_1MINUTE).
        lookback_start_str: A string like "10 days ago UTC", "200 hours ago UTC". Used if limit is None.
        limit: Number of klines to fetch. If 'lookback_start_str' is also provided, 'limit' might be ignored or used by the library for pagination control.
               If only 'limit' is provided, it fetches the most recent 'limit' klines.

        Returns: A list of processed kline dictionaries, or an empty list if an error occurs or no data.
                 Each kline dict: {'t': ms_timestamp, 'o': float, 'h': float, 'l': float, 'c': float, 'v': float}
        """
        if not self.client:
            logger.info("[DataFetcher] Client not initialized. Initializing for historical data fetch...")
            await self._initialize_client() # Ensure client is ready
            if not self.client:
                logger.error("[DataFetcher] Failed to initialize client for historical data.")
                if self.on_status_update:
                    self.on_status_update("[DataFetcher] Error: Failed to initialize client for historical data.")
                return []

        if self.on_status_update:
            status_msg = f"[DataFetcher] Fetching historical klines for {symbol_to_fetch}, interval {interval_for_api}..."
            if limit and not lookback_start_str:
                status_msg += f" Last {limit} klines."
            elif lookback_start_str:
                status_msg += f" Starting from {lookback_start_str}."
            else: # limit and lookback_start_str are None - this case needs to be handled or prevented
                 logger.warning("[DataFetcher] fetch_historical_klines called without lookback_start_str or limit.")
                 return [] # Or default to a small limit
            self.on_status_update(status_msg)

        logger.info(f"Fetching historical data: Symbol={symbol_to_fetch}, Interval={interval_for_api}, Start={lookback_start_str}, Limit={limit}")

        try:
            if lookback_start_str: # Prioritize lookback_start_str if provided
                raw_klines = await self.client.get_historical_klines(
                    symbol=symbol_to_fetch,
                    interval=interval_for_api,
                    start_str=lookback_start_str
                    # Not passing limit here intentionally; let start_str define the range.
                    # The library handles pagination and will fetch all klines from start_str to now.
                    # If a specific end is needed, it would be 'end_str' or an equivalent timestamp for 'endtime'.
                )
            elif limit: # Fetch last 'limit' klines if no lookback_start_str
                raw_klines = await self.client.get_historical_klines(
                    symbol=symbol_to_fetch,
                    interval=interval_for_api,
                    limit=limit
                )
            else:
                logger.error("[DataFetcher] Invalid parameters for historical kline fetch.")
                return []

        except Exception as e:
            logger.error(f"[DataFetcher] Error fetching historical klines: {e}", exc_info=True)
            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] Error fetching historical klines: {e}")
            return []

        processed_klines = []
        if raw_klines:
            for k in raw_klines:
                # Raw kline format: [timestamp, open, high, low, close, volume, close_time, ...]
                try:
                    processed_kline = {
                        't': int(k[0]),        # Millisecond timestamp (start of kline)
                        'o': float(k[1]),
                        'h': float(k[2]),
                        'l': float(k[3]),
                        'c': float(k[4]),
                        'v': float(k[5])
                    }
                    processed_klines.append(processed_kline)
                except (IndexError, ValueError) as conversion_e:
                    logger.error(f"[DataFetcher] Error processing raw kline data: {conversion_e}. Data: {k}")
                    continue # Skip this kline

            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] Successfully fetched and processed {len(processed_klines)} historical klines.")
            logger.info(f"Fetched {len(processed_klines)} historical klines for {symbol_to_fetch}.")
        else:
            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] No historical klines returned for {symbol_to_fetch} with given parameters.")
            logger.info(f"No historical klines returned for {symbol_to_fetch} with params: interval={interval_for_api}, start={lookback_start_str}, limit={limit}")

        return processed_klines

    def get_latest_price(self):
        return self.latest_price

    def get_latest_kline(self):
        return self.latest_kline_data

# Example Usage (for testing purposes, will be removed or refactored)
async def main_test():

    def print_status(message):
        print(f"STATUS: {message}")

    def handle_new_kline_for_test(kline_data):
        print(f"KLINE_TEST_CALLBACK: Close: {kline_data['c']}, Time: {kline_data['t']}")

    def handle_new_price_for_test(price_str):
        print(f"PRICE_TEST_CALLBACK: Price: {price_str}")

    fetcher = DataFetcher(
        # symbol="BTCUSDT", # Now uses default from settings
        on_kline_callback=handle_new_kline_for_test,
        on_price_update_callback=handle_new_price_for_test,
        on_status_update=print_status
    )

    try:
        print_status("Attempting to start fetching...")
        await fetcher.start_fetching()
    except KeyboardInterrupt:
        print_status("Keyboard interrupt received. Stopping...")
    except Exception as e:
        print_status(f"Unhandled error in main_test: {e}")
    finally:
        await fetcher.stop_fetching()
        print_status("Fetching stopped.")

if __name__ == '__main__':
    # This part is for direct testing of the fetcher.py file.
    # To run: python trading_bot/data_fetcher/fetcher.py
    print("Starting DataFetcher test...")
    asyncio.run(main_test())
