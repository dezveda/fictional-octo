# 03 Module: Data Fetcher

## 1. Purpose

The `DataFetcher` module (`trading_bot/data_fetcher/fetcher.py`) is responsible for all interactions with the Binance API to acquire market data. This includes:
-   Fetching historical kline (candlestick) data upon application startup.
-   Establishing and managing real-time WebSocket connections for live kline updates.
-   Establishing and managing real-time WebSocket connections for live order book depth updates (partial book snapshots).
-   Processing raw data from Binance into standardized formats for use by other modules.
-   Providing data to the application core (`BotApplication` in `main.py`) via asynchronous callbacks.

It aims to encapsulate all direct Binance API communication related to market data streams.

## 2. Key Class: `DataFetcher`

This module primarily defines the `DataFetcher` class.

### 2.1. `__init__(self, symbol, stop_event, on_kline_callback=None, on_price_update_callback=None, on_status_update=None, on_orderbook_update_callback=None)`

*   **Parameters**:
    *   `symbol` (str): The trading symbol (e.g., "BTCUSDT"), typically from `settings.TRADING_SYMBOL`.
    *   `stop_event` (threading.Event): An event used to signal graceful shutdown of WebSocket loops.
    *   `on_kline_callback`: Callback function triggered with each new complete kline data (historical or live base interval). Used to send data to `GoldenStrategy` via `BotApplication`.
    *   `on_price_update_callback`: Callback triggered with the latest closing price from each live base interval kline. Used for frequent GUI price updates.
    *   `on_status_update`: Callback for sending status or error messages to the GUI.
    *   `on_orderbook_update_callback`: Callback triggered with each new order book snapshot.
*   **Key Attributes Initialized**:
    *   `self.symbol`: Stores the trading symbol.
    *   `self.stop_event`: Stores the shutdown event.
    *   Various callbacks.
    *   `self.client`: Stores the `python-binance` `AsyncClient` instance (initialized by `_initialize_client`).
    *   `self.bsm`: Stores the `python-binance` `BinanceSocketManager` instance.
    *   `self.fetch_interval_str`: Stores `settings.KLINE_FETCH_INTERVAL` (e.g., "1m").
    *   `self.api_interval`: Stores the `python-binance` constant for `fetch_interval_str` (e.g., `AsyncClient.KLINE_INTERVAL_1MINUTE`), derived via `_map_interval_str_to_api_const`.
    *   `self.kline_socket_task`, `self.depth_socket_task`: Placeholders for asyncio tasks managing the WebSockets. (Note: Current implementation starts tasks in `main.py` but `DataFetcher` methods are the coroutines for these tasks).
    *   `self.order_book`: Dictionary (`{'bids': {price: qty}, 'asks': {price: qty}}`) for the local order book cache.
    *   `self.local_ob_max_levels`: Max levels to store from `settings.LOCAL_ORDER_BOOK_MAX_LEVELS`.
    *   `self.latest_price`, `self.latest_kline_data`: Store the most recent kline information.

### 2.2. `_initialize_client(self)` (async)

*   **Purpose**: Creates and initializes the `python-binance` `AsyncClient` and `BinanceSocketManager`.
*   **Logic**:
    *   Idempotent: Checks if `self.client` already exists.
    *   Calls `AsyncClient.create(request_timeout=settings.REQUEST_TIMEOUT)`. The `request_timeout` (note underscore) parameter is crucial for handling potential network delays.
    *   Initializes `self.bsm` with the created client.
    *   Performs an `await self.client.ping()` to verify connectivity.
    *   **Error Handling**: Includes `try-except` for `asyncio.TimeoutError`, `aiohttp.ClientError`, and general `Exception` during creation/ping. Logs errors and sends status updates. Sets `self.client` and `self.bsm` to `None` on failure.
    *   A `finally` block logs the final state of `self.client` and `self.bsm` using `logger.critical` for high visibility during debugging.

### 2.3. `_map_interval_str_to_api_const(self, interval_str)`

*   **Purpose**: Converts human-readable interval strings from `settings.py` (e.g., "1m", "1h") into the `AsyncClient.KLINE_INTERVAL_*` constants required by `python-binance`.
*   **Logic**: Uses a dictionary mapping. Includes a fallback to 1-minute interval with a warning if an unsupported string is provided. (Note: The "1s" mapping was removed as `AsyncClient.KLINE_INTERVAL_1SECOND` caused AttributeErrors; 1s klines, if used by WebSocket, are typically handled by string interval in stream name or specific parameter, not this map for historical klines).

### 2.4. `fetch_historical_klines(self, symbol_to_fetch, interval_for_api, lookback_start_str=None, limit=None)` (async)

*   **Purpose**: Fetches a batch of historical kline data from Binance.
*   **Parameters**:
    *   `symbol_to_fetch`, `interval_for_api` (the `AsyncClient` constant).
    *   `lookback_start_str`: Preferred method for fetching a duration (e.g., "7 days ago UTC"). `python-binance` handles pagination.
    *   `limit`: Number of klines (alternative to `lookback_start_str` for fetching most recent N klines; subject to API single call limits if not paginated by library for this specific call type).
*   **Logic**:
    *   Ensures client is initialized via `_initialize_client()`.
    *   Calls `await self.client.get_historical_klines(...)` using either `start_str=lookback_start_str` or `limit=limit`. The implementation prioritizes `lookback_start_str`. (Note: The `endtime` parameter was removed as it caused `TypeError` and was not needed for "up to now" fetching).
    *   **Data Processing**: Transforms the raw list-of-lists kline data from Binance into a list of standardized dictionaries: `{'t': ms_timestamp, 'o': float, 'h': float, 'l': float, 'c': float, 'v': float}`.
    *   Includes error handling for API calls and data conversion.
    *   Returns the list of processed kline dictionaries.

### 2.5. `start_kline_stream(self)` (async, formerly `start_fetching`)

*   **Purpose**: Initiates and manages the WebSocket connection for live kline data. This method typically runs as a persistent asyncio task.
*   **Logic**:
    *   Ensures client is initialized.
    *   Uses `self.bsm.kline_socket(symbol=self.symbol, interval=self.api_interval)` (where `self.api_interval` is like `AsyncClient.KLINE_INTERVAL_1MINUTE`).
    *   Enters an `async with ... as kline_stream_socket:` block.
    *   Enters a `while True` loop (checking `self.stop_event`):
        *   `msg = await kline_stream_socket.recv()`
        *   Calls `self._process_kline_message(msg)`.
    *   Handles exceptions and ensures cleanup in a `finally` block (calling `self.stop_all_streams()` or parts of it).

### 2.6. `_process_kline_message(self, msg)`

*   **Purpose**: Callback for processing messages received from the kline WebSocket.
*   **Logic**:
    *   Parses the kline data from the message structure (usually under a 'k' key for kline events).
    *   Updates `self.latest_price` and `self.latest_kline_data`.
    *   Calls `self.on_price_update_callback(formatted_price_string)` if set.
    *   Calls `self.on_kline_callback(full_kline_data_dict)` if set.
    *   Includes logging (DEBUG level for price, INFO for full message if enabled).

### 2.7. `start_depth_stream(self)` (async)

*   **Purpose**: Initiates and manages the WebSocket connection for live order book depth data (partial book snapshots). Runs as a persistent asyncio task.
*   **Logic**:
    *   Ensures `self.bsm` (BinanceSocketManager) is initialized.
    *   Uses `settings.ORDER_BOOK_STREAM_DEPTH_LEVEL` (e.g., 20) and `settings.ORDER_BOOK_UPDATE_SPEED_MS` (e.g., "100ms") to configure the stream.
    *   The implementation uses `self.bsm.start_partial_book_depth_socket(symbol=self.symbol, level=depth_level_int, interval=update_speed_str, callback=self._process_depth_message)`. The `python-binance` library then manages calling `_process_depth_message` with depth snapshots.
    *   The method itself contains a `while True: await asyncio.sleep(1)` loop that checks `self.stop_event` to keep the asyncio task (created in `main.py`) alive and allow for graceful shutdown. (Note: If `start_partial_book_depth_socket` is a context manager stream like `kline_socket`, then this method would contain the `async with ... as ds: await ds.recv()` loop instead. The subtask report from turn 121 indicated a callback model was used for this).
    *   Includes CRITICAL logging for entry and BSM call attempt.

### 2.8. `_process_depth_message(self, msg)`

*   **Purpose**: Callback for processing messages from the partial book depth WebSocket.
*   **Logic**:
    *   Handles snapshot messages (expected format: `{'lastUpdateId': ..., 'bids': [['price', 'qty'], ...], 'asks': [...]}`).
    *   Updates `self.order_book['bids']` and `self.order_book['asks']` (as dictionaries `{price_float: qty_float}`), truncating to `self.local_ob_max_levels`.
    *   Calls `self.on_orderbook_update_callback(self.get_order_book_snapshot())` if the callback is set.
    *   Includes CRITICAL/INFO logging for message reception and DEBUG for processed content.

### 2.9. `get_order_book_snapshot(self, num_levels=None)`

*   **Purpose**: Returns a structured, sorted copy of the local order book cache.
*   **Logic**:
    *   Converts the internal `{price:qty}` bid/ask dictionaries into sorted lists of `[price, qty]` tuples.
    *   Bids are sorted highest price first.
    *   Asks are sorted lowest price first.
    *   Returns a dictionary `{'bids': sorted_bids_list, 'asks': sorted_asks_list}`, truncated to `num_levels`.

### 2.10. `stop_all_streams(self)` (async, formerly `stop_fetching`)

*   **Purpose**: Gracefully stops all active WebSocket streams and cleans up resources.
*   **Logic**:
    *   Sets `self.stop_event`.
    *   Cancels `self.kline_socket_task` and `self.depth_socket_task` if they are active (these tasks are created and stored in `main.py` but `DataFetcher` holds references or can manage them internally). The current implementation in `DataFetcher` (turn 103 report) suggests it expects `main.py` to manage the task objects, but it has a `self.depth_socket_task` attribute. The kline task is implicit in `start_kline_stream`'s loop. This method should ensure these loops terminate.
    *   Calls `await self.client.close_connection()` if `self.client` exists.
    *   Resets `self.client`, `self.bsm`, `self.kline_socket_task`, `self.depth_socket_task` to `None`.

## 3. Key Settings Used (`utils/settings.py`)

*   `TRADING_SYMBOL`
*   `KLINE_FETCH_INTERVAL`
*   `REQUEST_TIMEOUT`
*   `ORDER_BOOK_STREAM_DEPTH_LEVEL`
*   `LOCAL_ORDER_BOOK_MAX_LEVELS`
*   `ORDER_BOOK_UPDATE_SPEED_MS`

## 4. Interaction with Other Modules

*   **`main.py` (`BotApplication`)**: Instantiates `DataFetcher`, starts its stream methods as asyncio tasks, and provides callbacks to receive data and status updates. Calls `stop_all_streams` on shutdown.
*   **`GoldenStrategy`**: Receives kline data and order book snapshots from `BotApplication` (which gets them from `DataFetcher`'s callbacks).
*   **`GUI`**: Receives live price updates and status messages directly from `DataFetcher` (via `BotApplication` callbacks).

This module is critical as it's the sole provider of market data to the entire application. Its robustness, especially in handling WebSocket connections and errors, is vital.
