c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\gui\main_window.py:94: UserWarning: This figure includes Axes that are not compatible with tight_layout, so results might be incorrect.
  self.figure.tight_layout()
2025-06-18 02:23:28,366 - __main__ - INFO - Starting Bot Application...
2025-06-18 02:23:28,502 - __main__ - INFO - Starting DataFetcher asyncio task (including historical fill)...
2025-06-18 02:23:29,359 - __main__ - INFO - Calculated historical lookback: 7 days ago UTC to get approx 150 of 1H bars using 1m klines.
2025-06-18 02:23:29,420 - trading_bot.data_fetcher.fetcher - INFO - [DataFetcher] Client not initialized. Initializing for historical data fetch...
2025-06-18 02:23:29,425 - trading_bot.data_fetcher.fetcher - INFO - [DataFetcher] Initializing API client (timeout: 30s)...
2025-06-18 02:23:29,425 - trading_bot.data_fetcher.fetcher - ERROR - [DataFetcher] API client initialization failed: AsyncClient.create() got an unexpected keyword argument 'requests_timeout'
Traceback (most recent call last):
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\data_fetcher\fetcher.py", line 65, in _initialize_client
    self.client = await AsyncClient.create(requests_timeout=settings.REQUEST_TIMEOUT)
                        ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AsyncClient.create() got an unexpected keyword argument 'requests_timeout'
2025-06-18 02:23:29,429 - trading_bot.data_fetcher.fetcher - ERROR - [DataFetcher] Failed to initialize client for historical data.
2025-06-18 02:23:29,447 - trading_bot.data_fetcher.fetcher - INFO - [DataFetcher] Initializing API client (timeout: 30s)...
2025-06-18 02:23:29,447 - trading_bot.data_fetcher.fetcher - ERROR - [DataFetcher] API client initialization failed: AsyncClient.create() got an unexpected keyword argument 'requests_timeout'
Traceback (most recent call last):
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\data_fetcher\fetcher.py", line 65, in _initialize_client
    self.client = await AsyncClient.create(requests_timeout=settings.REQUEST_TIMEOUT)
                        ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: AsyncClient.create() got an unexpected keyword argument 'requests_timeout'
2025-06-18 02:23:29,456 - __main__ - ERROR - DataFetcher startup or historical fill crashed: 'NoneType' object has no attribute 'kline_socket'
Traceback (most recent call last):
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\main.py", line 168, in start_fetcher_async
    await self.fetcher.start_fetching()
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\data_fetcher\fetcher.py", line 159, in start_fetching
    self.socket = self.bsm.kline_socket(symbol=self.symbol, interval=self.api_interval)
                  ^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute 'kline_socket'
2025-06-18 02:23:29,964 - __main__ - INFO - DataFetcher asyncio task (start_fetcher_async in main) finished.
2025-06-18 02:23:57,776 - __main__ - INFO - Application closing sequence initiated...
2025-06-18 02:23:57,776 - __main__ - INFO - Destroying GUI.
2025-06-18 02:23:57,896 - __main__ - INFO - Bot application stopped.
trading_bot package loaded.
gui package loaded.
data_fetcher package loaded.
strategy package loaded.
indicators package loaded.
