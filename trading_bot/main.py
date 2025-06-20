import asyncio
import threading
import asyncio
import threading
import logging
import pandas as pd # For pd.Timedelta
from datetime import datetime, timezone # For lookback_start_str calculation
from trading_bot.gui.main_window import App
from trading_bot.data_fetcher.fetcher import DataFetcher
from trading_bot.strategy.gold_strategy import GoldenStrategy
from trading_bot.utils import settings

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BotApplication:
    def __init__(self):
        self.gui_app = App()

        # Pass GUI update methods as callbacks to strategy and fetcher
        self.strategy = GoldenStrategy(
            on_status_update=self.schedule_gui_update(self.gui_app.update_status_bar),
            on_indicators_update=self.schedule_gui_update(self.gui_app.update_indicators_display),
            on_signal_update=self.schedule_gui_update(self.gui_app.update_signal_display),
            on_liquidity_update_callback=self.schedule_gui_update(self.gui_app.update_liquidity_display),
            on_chart_update=self.schedule_gui_update(self.gui_app.update_chart) # Add chart update callback
        )


        self.stop_event = threading.Event() # Initialize stop_event first

        self.fetcher = DataFetcher(
            symbol=settings.TRADING_SYMBOL,
            on_kline_callback=self.handle_new_kline_data, # Strategy processes full kline
            on_price_update_callback=self.schedule_gui_update(self.gui_app.update_price_display), # GUI gets quick price string
            on_status_update=self.schedule_gui_update(self.gui_app.update_status_bar),
            stop_event=self.stop_event # Pass the stop event to the fetcher
        )

        self.asyncio_thread = None
        self.fetcher_loop = None # To store the loop of the fetcher thread

    def schedule_gui_update(self, update_function):
        """ Returns a new function that schedules the original update_function on the GUI thread. """
        def scheduled_update(*args):
            self.gui_app.after(0, lambda: update_function(*args))
        return scheduled_update

    def handle_new_kline_data(self, kline_data):
        """
        This is called from the DataFetcher's thread.
        It processes the kline data through the strategy.
        Strategy methods that update GUI are already wrapped by schedule_gui_update.
        """
        # logger.debug(f"MainApp: Received kline, c={kline_data.get('c')}") # Can be too verbose
        self.strategy.process_new_kline(kline_data)

    def handle_new_orderbook_data(self, orderbook_snapshot):
        """ Passes order book updates to the strategy. """
        # logger.debug(f"[MainApp] Received order book snapshot. Top bid: {orderbook_snapshot['bids'][0] if orderbook_snapshot['bids'] else 'N/A'}")
        if self.strategy:
            self.strategy.process_order_book_update(orderbook_snapshot)

    async def start_fetcher_async(self):
        """ Coroutine to run the DataFetcher, including historical fill. """
        try:
            logger.info("Starting DataFetcher asyncio task (including historical fill)...")
            self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Initializing data...")

            # 1. Fetch historical data
            # Ensure client is initialized in fetcher before calling fetch_historical_klines
            # The fetch_historical_klines method now handles client initialization.

            # Process timeframe strings for pd.Timedelta compatibility
            processed_strategy_tf_str = settings.STRATEGY_TIMEFRAME.lower()
            if 't' in processed_strategy_tf_str and not 'min' in processed_strategy_tf_str:
                processed_strategy_tf_str = processed_strategy_tf_str.replace('t', 'min')
            strategy_tf_delta = pd.Timedelta(processed_strategy_tf_str)

            processed_fetch_interval_str = settings.KLINE_FETCH_INTERVAL.lower()
            if 'm' in processed_fetch_interval_str and not 'min' in processed_fetch_interval_str and 'ms' not in processed_fetch_interval_str:
                processed_fetch_interval_str = processed_fetch_interval_str.replace('m', 'min')
            elif 's' in processed_fetch_interval_str and not 'sec' in processed_fetch_interval_str and 'ms' not in processed_fetch_interval_str:
                processed_fetch_interval_str = processed_fetch_interval_str.replace('s', 'sec')
            fetch_interval_delta = pd.Timedelta(processed_fetch_interval_str)

            if strategy_tf_delta < fetch_interval_delta:
                logger.error(f"Strategy timeframe {settings.STRATEGY_TIMEFRAME} cannot be smaller than fetch interval {settings.KLINE_FETCH_INTERVAL}.")
                self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Config Error: Strategy TF < Fetch Interval. Halting.")
                return

            num_agg_bars_needed = settings.HISTORICAL_LOOKBACK_AGG_BARS_COUNT
            lookback_start_str_for_api = None

            if num_agg_bars_needed > 0 :
                # Calculate total duration needed for the strategy timeframe bars
                total_duration_for_strategy_bars = num_agg_bars_needed * strategy_tf_delta

                # Add a small buffer to ensure enough data (e.g., a few fetch intervals)
                buffer_duration = fetch_interval_delta * 10 # Buffer of 10 base fetch intervals
                total_lookback_duration = total_duration_for_strategy_bars + buffer_duration

                # Calculate the actual start date string for the API
                # python-binance start_str uses format like "1 day ago UTC", "10 hours ago UTC", "1 Jan, 2020"
                # We want to fetch data *before* the current moment.
                # For "X units ago UTC", it's relative to the time the call is made.
                # Let's calculate based on total hours.
                total_hours_lookback = total_lookback_duration.total_seconds() / 3600

                if total_hours_lookback > 48: # If more than 2 days, express in days for simplicity
                    lookback_start_str_for_api = f"{int(total_hours_lookback / 24) +1} days ago UTC" # Add 1 for buffer
                else:
                    lookback_start_str_for_api = f"{int(total_hours_lookback) +1} hours ago UTC" # Add 1 for buffer

                logger.info(f"Calculated historical lookback: {lookback_start_str_for_api} to get approx {num_agg_bars_needed} of {settings.STRATEGY_TIMEFRAME} bars using {settings.KLINE_FETCH_INTERVAL} klines.")

                if fetch_interval_delta > pd.Timedelta(0): # Ensure fetch_interval is valid
                    self.schedule_gui_update(self.gui_app.update_status_bar)(
                        f"[MainApp] Fetching historical data using lookback: {lookback_start_str_for_api} for {num_agg_bars_needed} '{settings.STRATEGY_TIMEFRAME}' bars..."
                    )

                    historical_klines = await self.fetcher.fetch_historical_klines(
                        symbol_to_fetch=settings.TRADING_SYMBOL,
                        interval_for_api=self.fetcher.api_interval,
                        lookback_start_str=lookback_start_str_for_api, # Use this instead of limit
                        limit=None # Let start_str define the range; library handles pagination
                    )

                    if historical_klines:
                        self.strategy.is_historical_fill_active = True
                        self.schedule_gui_update(self.gui_app.update_status_bar)(
                            f"[MainApp] Processing {len(historical_klines)} historical '{settings.KLINE_FETCH_INTERVAL}' klines (detailed UI updates suppressed)..."
                        )
                        for k_idx, k_data in enumerate(historical_klines):
                            self.handle_new_kline_data(k_data)
                            # Update GUI with the price of the current historical kline being processed
                            if k_data and 'c' in k_data: # Ensure k_data and 'c' key exist
                                try:
                                    price_val = float(k_data['c'])
                                    self.schedule_gui_update(self.gui_app.update_price_display)(f"{price_val:.2f}")
                                except ValueError:
                                    logger.warning(f"[MainApp] Could not convert historical kline close price to float: {k_data.get('c')}")

                            if (k_idx + 1) % 250 == 0 or (k_idx + 1) == len(historical_klines): # Update every 250 klines or on the last one
                                 self.schedule_gui_update(self.gui_app.update_status_bar)(
                                     f"[MainApp] Processed {k_idx+1}/{len(historical_klines)} historical '{settings.KLINE_FETCH_INTERVAL}' klines for aggregation..."
                                 )

                        self.strategy.is_historical_fill_active = False
                        # Perform one final update to GUI with the state after historical fill
                        if self.strategy.agg_kline_data_deque: # If any aggregated bars were formed
                            try:
                                logger.info('[MainApp] Triggering final GUI update after historical fill.')
                                # This call will now update GUI as flag is false
                                self.strategy._run_strategy_on_aggregated_data()
                            except Exception as e_strat_call:
                                logger.error(f'[MainApp] Error during final strategy call for GUI update: {e_strat_call}', exc_info=True)
                                self.schedule_gui_update(self.gui_app.update_status_bar)(f'[MainApp] Error in final UI refresh: {e_strat_call}')
                        self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Historical data processing complete. UI updated.")
                    else:
                        self.strategy.is_historical_fill_active = False # Ensure flag is reset
                        self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] No historical data fetched. Strategy will populate with live data.")
                else:
                    self.strategy.is_historical_fill_active = False # Ensure flag is reset
                    self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Skipping historical data fetch (0 klines requested or invalid calculation).")
            else:
                 self.strategy.is_historical_fill_active = False # Ensure flag is reset
                 self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Skipping historical data fetch (lookback bars or interval invalid).")


            # 2. Start live WebSocket fetching
            if not self.stop_event.is_set(): # Only start if not already shutting down
                self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Starting live KLINE data stream...")
                # Start kline stream
                # The start_kline_stream method now handles client initialization if not already done.
                await self.fetcher.start_kline_stream() # Renamed from start_fetching

                # Start depth stream as a separate task
                # Ensure client is available (which start_kline_stream should ensure)
                # Also check if depth_socket_task attribute exists and if it's already running
                if self.fetcher.client and \
                   not (hasattr(self.fetcher, 'depth_socket_task') and \
                        self.fetcher.depth_socket_task and \
                        not self.fetcher.depth_socket_task.done()):
                    logger.info("[MainApp] Creating task for DataFetcher depth stream...")
                    self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Starting live ORDER BOOK data stream...")
                    self.fetcher.depth_socket_task = asyncio.create_task(self.fetcher.start_depth_stream())
                elif not self.fetcher.client:
                    logger.warning("[MainApp] Cannot start depth stream: Fetcher client not initialized.")
                    self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Order book stream NOT started (client missing).")
                else:
                    logger.info("[MainApp] Depth stream task already exists or is running.")

        except Exception as e:
            logger.error(f"DataFetcher startup or historical fill crashed: {e}", exc_info=True)
            self.schedule_gui_update(self.gui_app.update_status_bar)(f"[MainApp] Data Pre-fill/Fetcher CRASHED: {e}")
        finally:
            logger.info("DataFetcher asyncio task (start_fetcher_async in main) finished.")
            if not self.stop_event.is_set():
                 self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Live DataFetcher stopped. Check logs.")


    def run_asyncio_loop_in_thread(self):
        """ Runs the asyncio event loop in a separate thread. """
        self.fetcher_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.fetcher_loop)
        try:
            self.fetcher_loop.run_until_complete(self.start_fetcher_async())
        finally:
            self.fetcher_loop.close()

    def start(self):
        logger.info("Starting Bot Application...")
        self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Starting application...")

        self.asyncio_thread = threading.Thread(target=self.run_asyncio_loop_in_thread, daemon=True)
        self.asyncio_thread.start()

        self.gui_app.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.gui_app.mainloop()

    def on_closing(self):
        logger.info("Application closing sequence initiated...")
        self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Shutting down...")
        self.stop_event.set() # Signal async tasks to stop

        # Attempt to stop the fetcher's asyncio tasks and close client
        if self.fetcher: # Check if fetcher object exists
            logger.info("Requesting DataFetcher to stop all streams...")
            if hasattr(self, 'fetcher_loop') and self.fetcher_loop and self.fetcher_loop.is_running():
                # stop_all_streams is an async method, handles client closing and task cancellation
                asyncio.run_coroutine_threadsafe(self.fetcher.stop_all_streams(), self.fetcher_loop)
            else:
                logger.info("Fetcher loop not available or not running for run_coroutine_threadsafe stop_all_streams.")

        if self.asyncio_thread and self.asyncio_thread.is_alive():
            logger.info("Waiting for asyncio_thread to finish...")
            self.asyncio_thread.join(timeout=5.0) # Wait for up to 5 seconds
            if self.asyncio_thread.is_alive():
                logger.warning("Asyncio thread did not finish in time.")
            else:
                logger.info("Asyncio thread finished.")

        logger.info("Destroying GUI.")
        self.gui_app.destroy()
        logger.info("Bot application stopped.")


if __name__ == '__main__':
    app = BotApplication()
    app.start()
