import asyncio
import threading
import logging
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
            on_signal_update=self.schedule_gui_update(self.gui_app.update_signal_display)
        )

        self.fetcher = DataFetcher(
            symbol=settings.TRADING_SYMBOL,
            on_kline_callback=self.handle_new_kline_data, # Strategy processes full kline
            on_price_update_callback=self.schedule_gui_update(self.gui_app.update_price_display), # GUI gets quick price string
            on_status_update=self.schedule_gui_update(self.gui_app.update_status_bar)
        )

        self.stop_event = threading.Event()
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

    async def start_fetcher_async(self):
        """ Coroutine to run the DataFetcher. """
        try:
            logger.info("Starting DataFetcher asyncio task...")
            self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] Attempting to start data fetching...")
            await self.fetcher.start_fetching()
        except Exception as e:
            logger.error(f"DataFetcher crashed: {e}", exc_info=True)
            self.schedule_gui_update(self.gui_app.update_status_bar)(f"[MainApp] DataFetcher CRASHED: {e}")
        finally:
            logger.info("DataFetcher asyncio task finished.")
            if not self.stop_event.is_set(): # If not stopped by user
                 self.schedule_gui_update(self.gui_app.update_status_bar)("[MainApp] DataFetcher stopped unexpectedly. Check logs.")


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

        # Attempt to stop the fetcher's asyncio loop gracefully
        if self.fetcher and hasattr(self.fetcher, 'stop_fetching') and self.fetcher.client and self.fetcher.bsm: # Check if active
            logger.info("Requesting DataFetcher to stop...")
            # The fetcher's loop should handle KeyboardInterrupt or other exceptions on stop_event
            # Or, it needs a dedicated stop method that can be called from here via run_coroutine_threadsafe
            # For now, setting stop_event is the primary mechanism. The thread join will wait.
            if hasattr(self, 'fetcher_loop') and self.fetcher_loop and self.fetcher_loop.is_running():
                logger.info("Calling stop_fetching via run_coroutine_threadsafe.")
                asyncio.run_coroutine_threadsafe(self.fetcher.stop_fetching(), self.fetcher_loop)
            else:
                logger.info("Fetcher loop not available or not running for run_coroutine_threadsafe.")

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
