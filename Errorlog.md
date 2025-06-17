c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\strategy\gold_strategy.py:31: FutureWarning: 'H' is deprecated and will be removed in a future version. Please use 'h' instead of 'H'.
  self.timeframe_delta = pd.Timedelta(self.strategy_timeframe_str.replace('T', 'min'))
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\main.py", line 214, in <module>
    app = BotApplication()
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\main.py", line 31, in __init__
    self.fetcher = DataFetcher(
                   ~~~~~~~~~~~^
        symbol=settings.TRADING_SYMBOL,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<3 lines>...
        stop_event=self.stop_event # Pass the stop event to the fetcher
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\data_fetcher\fetcher.py", line 50, in __init__
    self.api_interval = self._map_interval_str_to_api_const(self.fetch_interval_str)
                        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\data_fetcher\fetcher.py", line 15, in _map_interval_str_to_api_const
    "1s": AsyncClient.KLINE_INTERVAL_1SECOND, # Added 1s for completeness, though WS might use it directly
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: type object 'AsyncClient' has no attribute 'KLINE_INTERVAL_1SECOND'. Did you mean: 'KLINE_INTERVAL_12HOUR'?
trading_bot package loaded.
gui package loaded.
data_fetcher package loaded.
strategy package loaded.
indicators package loaded.
