import asyncio
import json
from binance import AsyncClient, BinanceSocketManager
import logging
from trading_bot.utils import settings

# Configure logging for the fetcher
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Configured in main.py

class DataFetcher:
    def __init__(self, symbol=settings.TRADING_SYMBOL, on_kline_callback=None, on_price_update_callback=None, on_status_update=None):
        self.symbol = symbol
        self.client = None
        self.bsm = None
        self.socket = None
        self.latest_price = None
        self.latest_kline_data = None
        self.on_kline_callback = on_kline_callback # For strategy processing
        self.on_price_update_callback = on_price_update_callback # For GUI price updates
        self.on_status_update = on_status_update # For status bar updates

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
        # For 1-second data, Binance uses '1s' interval for klines.
        kline_stream_name = f"{self.symbol.lower()}@kline_1s"

        if self.on_status_update:
            self.on_status_update(f"[DataFetcher] Starting {self.symbol} 1s kline WebSocket ({kline_stream_name})...")

        self.socket = self.bsm.kline_socket(symbol=self.symbol, interval=AsyncClient.KLINE_INTERVAL_1SECOND)

        try:
            async with self.socket as stream:
                while True:
                    msg = await stream.recv()
                    self._process_kline_message(msg)
        except Exception as e:
            logger.error(f"WebSocket connection error or processing error: {e}")
            if self.on_status_update:
                self.on_status_update(f"[DataFetcher] WebSocket Error: {e}. Attempting to reconnect...")
            await self.stop_fetching() # Clean up
            # Implement reconnection logic or notify main application
            # For now, we'll just log and exit the fetch loop.
            # A more robust solution would involve a retry mechanism with backoff.
            raise # Re-raise the exception to be handled by the caller or main loop

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
