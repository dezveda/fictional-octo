2025-06-17 05:17:45,449 - __main__ - INFO - Starting Bot Application...
2025-06-17 05:17:45,562 - __main__ - INFO - Starting DataFetcher asyncio task (including historical fill)...
c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\main.py:70: FutureWarning: 'H' is deprecated and will be removed in a future version. Please use 'h' instead of 'H'.
  strategy_tf_delta = pd.Timedelta(strategy_tf_str)
2025-06-17 05:17:45,819 - __main__ - INFO - Calculated historical lookback: 7 days ago UTC to get approx 150 of 1H bars using 1m klines.
2025-06-17 05:17:45,856 - trading_bot.data_fetcher.fetcher - INFO - [DataFetcher] Client not initialized. Initializing for historical data fetch...
2025-06-17 05:17:47,843 - trading_bot.data_fetcher.fetcher - INFO - Fetching historical data: Symbol=BTCUSDT, Interval=1m, Start=7 days ago UTC, Limit=None, EndTime=None
2025-06-17 05:17:47,843 - trading_bot.data_fetcher.fetcher - ERROR - [DataFetcher] Error fetching historical klines: AsyncClient.get_historical_klines() got an unexpected keyword argument 'endtime'
Traceback (most recent call last):
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\data_fetcher\fetcher.py", line 216, in fetch_historical_klines
    raw_klines = await self.client.get_historical_klines(
                       ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        symbol=symbol_to_fetch,
        ^^^^^^^^^^^^^^^^^^^^^^^
    ...<2 lines>...
        endtime=end_time_ms # API uses 'endtime' (lowercase)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
TypeError: AsyncClient.get_historical_klines() got an unexpected keyword argument 'endtime'
2025-06-17 05:17:48,865 - asyncio - ERROR - Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x000001D7F71B4AD0>
2025-06-17 05:17:48,866 - asyncio - ERROR - Unclosed connector
connections: ['deque([(<aiohttp.client_proto.ResponseHandler object at 0x000001D7F7080BF0>, 37244.7074601)])']
connector: <aiohttp.connector.TCPConnector object at 0x000001D7F71B4C20>
2025-06-17 05:27:19,975 - __main__ - INFO - Application closing sequence initiated...
2025-06-17 05:27:19,976 - __main__ - INFO - Requesting DataFetcher to stop...
2025-06-17 05:27:19,976 - __main__ - INFO - Calling stop_fetching via run_coroutine_threadsafe.
2025-06-17 05:27:19,976 - __main__ - INFO - Waiting for asyncio_thread to finish...
2025-06-17 05:27:25,014 - __main__ - WARNING - Asyncio thread did not finish in time.
2025-06-17 05:27:25,015 - __main__ - INFO - Destroying GUI.
2025-06-17 05:27:25,078 - __main__ - INFO - Bot application stopped.
trading_bot package loaded.
gui package loaded.
data_fetcher package loaded.
strategy package loaded.
indicators package loaded.
indicators package loaded.
