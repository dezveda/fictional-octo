***********Status bar Log:
[11:22:58] [MainApp] Data Pre-fill/Fetcher CRASHED: 
[11:22:58] [MainApp] Live DataFetcher stopped. Check logs.

*********Chart log:
Error plotting chart: kwarg "figcolor" validator returned false for value: "(0.16862745098039217, 0.16862745098039271, 0.16862745098039217, 1.0)"
'Validator' : lambda value: isinstance(value,str) }

*********Terminal log:
2025-06-17 11:21:52,791 - trading_bot.gui.main_window_gui - ERROR - [GUI] Error plotting chart with mplfinance: kwarg "figcolor" validator returned False for value: "(0.16862745098039217, 0.16862745098039217, 0.16862745098039217, 1.0)"
    'Validator'   : lambda value: isinstance(value,str) },
Traceback (most recent call last):
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\gui\main_window.py", line 227, in update_chart
    s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc, gridstyle=':',
                           facecolor='#1c1c1c',
                           figcolor=self.figure.get_facecolor()) # Use figure's actual facecolor
  File "C:\Users\Nuevo Usuario\AppData\Roaming\Python\Python313\site-packages\mplfinance\_styles.py", line 139, in make_mpf_style
    config = _process_kwargs(kwargs, _valid_make_mpf_style_kwargs())
  File "C:\Users\Nuevo Usuario\AppData\Roaming\Python\Python313\site-packages\mplfinance\_arg_validators.py", line 350, in _process_kwargs
    raise TypeError('kwarg "'+key+'" validator returned False for value: "'+str(value)+'"\n    '+v)
TypeError: kwarg "figcolor" validator returned False for value: "(0.16862745098039217, 0.16862745098039217, 0.16862745098039217, 1.0)"
    'Validator'   : lambda value: isinstance(value,str) },
2025-06-17 11:22:37,090 - __main__ - ERROR - DataFetcher startup or historical fill crashed: 
Traceback (most recent call last):
  File "C:\Program Files\Python313\Lib\site-packages\aiohttp\client.py", line 703, in _request
    conn = await self._connector.connect(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        req, traces=traces, timeout=real_timeout
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "C:\Program Files\Python313\Lib\site-packages\aiohttp\connector.py", line 548, in connect
    proto = await self._create_connection(req, traces, timeout)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Program Files\Python313\Lib\site-packages\aiohttp\connector.py", line 1056, in _create_connection
    _, proto = await self._create_direct_connection(req, traces, timeout)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Program Files\Python313\Lib\site-packages\aiohttp\connector.py", line 1357, in _create_direct_connection
    hosts = await self._resolve_host(host, port, traces=traces)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Program Files\Python313\Lib\site-packages\aiohttp\connector.py", line 995, in _resolve_host
    return await asyncio.shield(resolved_host_task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
asyncio.exceptions.CancelledError

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\main.py", line 168, in start_fetcher_async
    await self.fetcher.start_fetching()
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\data_fetcher\fetcher.py", line 122, in start_fetching
    await self._initialize_client()
  File "c:\Users\Nuevo Usuario\Downloads\Kaska\trading_bot\data_fetcher\fetcher.py", line 56, in _initialize_client
    self.client = await AsyncClient.create()
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Nuevo Usuario\AppData\Roaming\Python\Python313\site-packages\binance\client.py", line 7533, in create
    await self.ping()
  File "C:\Users\Nuevo Usuario\AppData\Roaming\Python\Python313\site-packages\binance\client.py", line 7655, in ping
    return await self._get('ping', version=self.PRIVATE_API_VERSION)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Nuevo Usuario\AppData\Roaming\Python\Python313\site-packages\binance\client.py", line 7620, in _get
    return await self._request_api('get', path, signed, version, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Nuevo Usuario\AppData\Roaming\Python\Python313\site-packages\binance\client.py", line 7583, in _request_api
    return await self._request(method, uri, signed, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Nuevo Usuario\AppData\Roaming\Python\Python313\site-packages\binance\client.py", line 7564, in _request
    async with getattr(self.session, method)(uri, **kwargs) as response:
               ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "C:\Program Files\Python313\Lib\site-packages\aiohttp\client.py", line 1425, in __aenter__
    self._resp: _RetType = await self._coro
                           ^^^^^^^^^^^^^^^^
  File "C:\Program Files\Python313\Lib\site-packages\aiohttp\client.py", line 607, in _request
    with timer:
         ^^^^^
  File "C:\Program Files\Python313\Lib\site-packages\aiohttp\helpers.py", line 685, in __exit__
    raise asyncio.TimeoutError from exc_val
TimeoutError
2025-06-17 11:22:58,016 - __main__ - INFO - DataFetcher asyncio task (start_fetcher_async in main) finished.
2025-06-17 11:24:37,036 - __main__ - INFO - Application closing sequence initiated...
2025-06-17 11:24:37,037 - __main__ - INFO - Requesting DataFetcher to stop...
2025-06-17 11:24:37,037 - __main__ - INFO - Fetcher loop not available or not running for run_coroutine_threadsafe.
2025-06-17 11:24:37,053 - __main__ - INFO - Destroying GUI.
2025-06-17 11:24:37,477 - __main__ - INFO - Bot application stopped.
trading_bot package loaded.
gui package loaded.
data_fetcher package loaded.
strategy package loaded.
indicators package loaded.
2025-06-17 11:25:07,621 - asyncio - ERROR - Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x000002EBC7F6A3C0>
