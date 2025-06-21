# 02 Data Flow

This document describes the flow of market data (klines and order book) through the Minimalist Trading Bot, from acquisition to processing and display. It also touches upon the key callback mechanisms ensuring inter-module communication and GUI updates.

## 1. Overview of Data Types and Modules Involved

*   **Kline Data**: Open, High, Low, Close, Volume, Timestamp information for specific intervals (e.g., 1-minute base klines, aggregated to 1-hour strategy klines).
*   **Order Book Data**: Real-time bid and ask levels with their associated quantities.
*   **Key Modules**:
    *   `DataFetcher` (`data_fetcher/fetcher.py`): Acquires raw data from Binance.
    *   `BotApplication` (`main.py`): Orchestrates data flow between `DataFetcher`, `GoldenStrategy`, and `GUI`.
    *   `GoldenStrategy` (`strategy/gold_strategy.py`): Processes klines for aggregation, calculates indicators on aggregated data, performs specialized analyses (Pivots, Fibonacci, Liquidity from order book), and generates trading signals/consolidation info.
    *   `LiquidityAnalysis` (`strategy/liquidity_analysis.py`): Analyzes raw order book data.
    *   `GUI` (`gui/main_window.py`): Displays all relevant information.

## 2. Kline Data Flow

### 2.1. Historical Kline Data (Startup Pre-fill)

1.  **Initiation (`main.py - BotApplication.start_fetcher_async`)**:
    *   Calculates required lookback period based on `settings.STRATEGY_TIMEFRAME`, `settings.KLINE_FETCH_INTERVAL`, and `settings.HISTORICAL_LOOKBACK_AGG_BARS_COUNT`.
    *   Calls `DataFetcher.fetch_historical_klines()` with these parameters.
2.  **Fetching (`DataFetcher.fetch_historical_klines`)**:
    *   Connects to Binance REST API (via `AsyncClient.get_historical_klines`).
    *   Fetches a batch of klines for the `settings.KLINE_FETCH_INTERVAL` (e.g., 1-minute klines) for the calculated lookback duration.
    *   Processes raw API response into a list of standardized kline dictionaries: `{'t': ms_timestamp, 'o': float, 'h': float, 'l': float, 'c': float, 'v': float}`.
    *   Returns this list to `BotApplication`.
3.  **Processing & Aggregation (`main.py` & `GoldenStrategy`)**:
    *   `BotApplication.start_fetcher_async` sets `strategy.is_historical_fill_active = True`.
    *   It iterates through the fetched historical klines:
        *   For each kline, it calls `gui_app.update_price_display` (via `schedule_gui_update`) to show the price of the kline being processed.
        *   It calls `strategy.handle_new_kline_data()` (which is an alias or direct call to `strategy.process_new_kline()`).
    *   `GoldenStrategy.process_new_kline()` calls `_process_incoming_kline()`:
        *   The base kline (e.g., 1-minute) is added to `current_agg_kline_buffer`.
        *   If enough base klines complete an aggregated bar (e.g., a 1-hour bar based on `settings.STRATEGY_TIMEFRAME`):
            *   `_finalize_and_process_aggregated_bar()` is called. This creates the OHLCV for the aggregated bar and stores it in `agg_*` deques.
            *   It then calls `_run_strategy_on_aggregated_data()`.
    *   `GoldenStrategy._run_strategy_on_aggregated_data()`:
        *   Calculates all indicators based on the history of *aggregated bars*.
        *   Performs specialized analyses (Pivots, Fibonacci) using aggregated data.
        *   Calls `_generate_signal()`.
        *   **Crucially**, during historical fill (`is_historical_fill_active == True`), calls to `on_indicators_update` and `on_signal_update` (for actual signals or consolidation) are **suppressed** within `_run_strategy_on_aggregated_data` and `_trigger_provisional_chart_update`. The chart update via `on_chart_update` (called from `_trigger_provisional_chart_update`) is also suppressed by a similar flag check within it.
4.  **Final Update Post-Fill (`main.py`)**:
    *   After processing all historical klines, `BotApplication` sets `strategy.is_historical_fill_active = False`.
    *   It then calls `strategy._run_strategy_on_aggregated_data()` *once* to perform a final calculation based on the complete historical aggregated data and trigger a single update for indicators, signals/consolidation, and the chart to the GUI.

### 2.2. Live Kline Data

1.  **Connection (`DataFetcher.start_kline_stream`)**:
    *   Connects to Binance WebSocket for the kline stream of `settings.KLINE_FETCH_INTERVAL` (e.g., 1-minute klines).
    *   The WebSocket manager (`bsm`) receives messages.
2.  **Message Processing (`DataFetcher._process_kline_message`)**:
    *   For each incoming kline message:
        *   Extracts `latest_price` (close price of the 1-minute kline).
        *   Calls `on_price_update_callback` (connected to `gui_app.update_price_display`) to update the live price in GUI.
        *   Calls `on_kline_callback` (connected to `BotApplication.handle_new_kline_data`) with the full 1-minute kline data.
3.  **Aggregation & Provisional Updates (`main.py` & `GoldenStrategy`)**:
    *   `BotApplication.handle_new_kline_data()` calls `strategy.process_new_kline()`.
    *   `GoldenStrategy.process_new_kline()` calls `_process_incoming_kline()`:
        *   The 1-minute kline is added to `current_agg_kline_buffer`.
        *   `_trigger_provisional_chart_update()` is called (since `is_historical_fill_active` is now `False`):
            *   A provisional aggregated bar (e.g., the forming 1-hour bar) is constructed.
            *   A DataFrame of (historical aggregated bars + this provisional bar) is sent to `on_chart_update` -> GUI chart updates with live last candle.
            *   Provisional 1-hour indicators and consolidation percentages are calculated based on this (history + provisional bar) data.
            *   `on_indicators_update` and `on_signal_update` (with consolidation string) are called -> GUI indicator panel and signal/consolidation panel update with these "live" provisional values.
        *   If the 1-minute kline completes a full aggregated bar (e.g., 1-hour):
            *   `_finalize_and_process_aggregated_bar()` is called:
                *   The aggregated bar is finalized and stored.
                *   `_run_strategy_on_aggregated_data()` is called.
            *   `GoldenStrategy._run_strategy_on_aggregated_data()`:
                *   Calculates indicators based on *completed* aggregated bars.
                *   Performs specialized analyses.
                *   Calls `_generate_signal()`.
                *   Calls `on_indicators_update` and `on_signal_update` (with actual trade signal or final consolidation for the completed bar) -> GUI updates with finalized data for the strategy timeframe.

## 3. Order Book Data Flow (Live Only)

1.  **Connection (`main.py` & `DataFetcher.start_depth_stream`)**:
    *   `BotApplication.start_fetcher_async` creates an asyncio task for `DataFetcher.start_depth_stream()`.
    *   `DataFetcher` connects to Binance WebSocket for partial order book depth stream (e.g., `@depth20@100ms`).
2.  **Message Processing (`DataFetcher._process_depth_message`)**:
    *   For each incoming depth snapshot message:
        *   Updates `self.order_book` (local cache of bids/asks).
        *   Calls `on_orderbook_update_callback` (connected to `BotApplication.handle_new_orderbook_data`) with a snapshot of the current order book.
3.  **Analysis & Strategy Integration (`main.py` & `GoldenStrategy`)**:
    *   `BotApplication.handle_new_orderbook_data()` calls `strategy.process_order_book_update()`.
    *   `GoldenStrategy.process_order_book_update()`:
        *   Stores the `latest_order_book_snapshot`.
        *   Calls `liquidity_analysis.analyze(latest_order_book_snapshot, settings, ...)` to get significant bid/ask levels.
        *   Stores the result in `self.latest_liquidity_analysis`.
        *   If `not self.is_historical_fill_active`, calls `on_liquidity_update_callback` (connected to `gui_app.update_liquidity_display`) -> GUI liquidity panel updates.
    *   `GoldenStrategy._assess_sr_levels()` (called by `_generate_signal` which runs per aggregated bar, and also provisionally by `_trigger_provisional_chart_update`):
        *   Accesses `self.latest_liquidity_analysis` to use the significant order book levels in its S/R assessment.

## 4. Callback Mechanism and Thread Safety

*   **Callbacks**: The system extensively uses callbacks for inter-module communication:
    *   `DataFetcher` -> `BotApplication` (for new klines, new price, new order book snapshot, status updates).
    *   `BotApplication` -> `GoldenStrategy` (for new klines, new order book snapshot).
    *   `GoldenStrategy` -> `BotApplication` (which then routes to GUI for indicators, signals, chart data, liquidity data, status updates).
*   **Thread Safety for GUI**:
    *   `DataFetcher` runs its WebSocket communications in an asyncio event loop managed in a separate thread by `BotApplication`.
    *   Any data that needs to update the GUI from this background thread (or any other non-GUI thread) is passed via a callback that is first wrapped by `BotApplication.schedule_gui_update()`.
    *   `schedule_gui_update(target_gui_method)` returns a new function that, when called, uses `self.gui_app.after(0, lambda: target_gui_method(*args))` to schedule the actual GUI update on Tkinter's main event loop. This ensures all GUI modifications are thread-safe.

This data flow allows for responsive live updates of current price, chart, and provisional indicators, while ensuring that core strategy decisions and their corresponding GUI displays are based on the stable, completed higher timeframe aggregated bars.
