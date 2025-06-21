# 09 Logging and Debugging Guide

This document provides an overview of the logging setup in the Minimalist Trading Bot and offers guidance on how to use logs for monitoring and debugging potential issues.

## 1. Logging Setup

*   **Root Logger Configuration**: Basic logging is configured in `trading_bot/main.py` using:
    ```python
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ```
    By default, this sets the logging level for the root logger to `INFO`. Messages of level `INFO`, `WARNING`, `ERROR`, and `CRITICAL` will be printed to the console.

*   **Configurable Log Level**: The overall logging verbosity can be controlled via the `LOG_LEVEL` parameter in `trading_bot/utils/settings.py`.
    *   `LOG_LEVEL = "INFO"` (default): Shows informational messages, warnings, errors, and critical failures.
    *   `LOG_LEVEL = "DEBUG"`: Provides much more detailed output, useful for tracing data flow and diagnosing issues. This will enable all `logger.debug()` messages throughout the application.
    *   Other levels like "WARNING", "ERROR" can also be set to reduce verbosity.
    *   The `main.py` script attempts to set the root logger's level based on this setting.

*   **Module-Specific Loggers**: Most Python modules (`.py` files) in the project initialize their own logger instance using:
    ```python
    logger = logging.getLogger(__name__)
    ```
    This allows messages to be attributed to the module they originated from (e.g., `trading_bot.data_fetcher.fetcher`, `trading_bot.strategy.gold_strategy`).
    *   The GUI module (`gui/main_window.py`) uses a specific logger often named `logger_gui` (e.g., `logging.getLogger(__name__ + '_gui')`) for its messages.

*   **GUI Status Bar**: The status bar at the bottom of the GUI provides a user-friendly view of many important status updates and log messages, especially those sent via the `on_status_update` callbacks. This is often the first place to look for operational messages.

## 2. Key Log Messages and What to Monitor

When troubleshooting or monitoring the bot, look for these types of messages (primarily in the console output, as the GUI status bar might not show DEBUG level logs):

### Startup & Initialization:
*   `[MainApp] Starting Bot Application...`
*   `[DataFetcher] Initializing API client (timeout: Xs)...`
*   `[DataFetcher] API Client initialized and ping successful.` (CRITICAL if fails: `self.client is None ... Success: False`)
*   `[MainApp] Checking client and preparing for depth stream. self.fetcher.client state: <client_obj_or_None>` (CRITICAL)
*   `[MainApp] ABOUT TO CREATE DataFetcher depth stream task.` (CRITICAL)
*   `[MainApp] DataFetcher depth stream task CREATED: <task_obj>` (CRITICAL)
*   `[DataFetcherOB] METHOD ENTRY: start_depth_stream()` (CRITICAL)
*   `[DataFetcherOB] Attempting to start BSM depth socket...` (CRITICAL)
*   `[DataFetcherOB] Depth socket for SYMBOL successfully opened/callback registered...` (CRITICAL for depth stream)

**If these initial CRITICAL logs don't appear or show errors (especially `self.client is None`), the bot cannot connect to Binance.**

### Historical Data Loading:
*   `[MainApp] Calculated historical lookback: X days/hours ago UTC...`
*   `[DataFetcher] Fetching historical klines...`
*   `[DataFetcher] Successfully fetched and processed X historical klines.`
*   `[MainApp] Processing X fetched historical 'Ym' klines (UI updates suppressed)...`
*   Periodic: `[MainApp] Processed A/B historical 'Ym' klines for aggregation...`
*   For each aggregated bar during fill: `[GoldenStrategy] New Z_TF bar aggregated: O:..., H:..., L:..., C:...` (where Z_TF is strategy timeframe like "1H")
*   `[MainApp] Historical data processing complete. Performing final UI update.`

**If historical loading seems stuck or incomplete, check logs for errors from `DataFetcher` or issues in the processing loop in `main.py`.**

### Live Data Operations:
*   **Klines**:
    *   `[DataFetcher] WebSocket connection established for SYMBOL Ym.`
    *   (DEBUG) `[DataFetcher] Live kline. Latest price: P. Triggering on_price_update_callback...` (for live price display)
    *   (DEBUG) `[DataFetcher] Live kline processed. Triggering on_kline_callback...` (for strategy)
*   **Order Book**:
    *   `[DataFetcherOB] METHOD ENTRY: _process_depth_message() - A RAW DEPTH MESSAGE WAS RECEIVED...` (CRITICAL - if this stops, depth stream has an issue)
    *   `[DataFetcherOB] Full raw depth message received: {...}` (INFO - shows the actual data)
    *   (DEBUG) `[DataFetcherOB] Order book processed. Triggering on_orderbook_update_callback...`
*   **MainApp Data Handling**:
    *   (DEBUG) `[MainApp] handle_new_orderbook_data received snapshot...`
    *   (DEBUG) `[MainApp] Calling strategy.process_order_book_update...`
*   **Strategy Aggregation & Provisional Updates (per base kline, e.g., 1m, if not historical fill)**:
    *   GUI update logs for provisional indicators/consolidation: `[GUI Indicators] update_indicators_display received: {'timeframe': '1H (Live)', ...}`
    *   GUI update logs for provisional consolidation: `[GUI Signal] update_signal_display received: '(1H) Consolidation (Live): LONG X% | SHORT Y%'`
*   **Strategy Full Bar Processing (per aggregated bar, e.g., 1H)**:
    *   `[GoldenStrategy] New X_TF bar aggregated...` (from `_finalize_and_process_aggregated_bar`)
    *   `[GoldenStrategy] Collecting more AGGREGATED bars... (A/B)` (if not enough bars for full indicators)
    *   `[StrategyDebug] (X_TF) States: Trend=..., MACD=..., RSI=..., KDJ=..., Fractal=..., S/R=..., Vol=...` (This is key for understanding strategy decisions)
    *   If signal: `[GoldenStrategy] (X_TF) Generated Signal: {'type': 'LONG/SHORT', ...}` (INFO)
    *   If consolidation: `[GoldenStrategy] (X_TF) Consolidation Info: Long X%, Short Y%.` (DEBUG)
    *   If no trade signal: `[GoldenStrategy] (X_TF) No *trade* signal generated on this bar.` (Status update)
*   **Liquidity Analysis Path**:
    *   `[GoldenStrategy] process_order_book_update received snapshot...` (DEBUG)
    *   `[LiquidityAnalysisOB] Received snapshot. Bids: X, Asks: Y` (DEBUG)
    *   `[LiquidityAnalysisOB] Using LIQUIDITY_SIGNIFICANT_QTY_THRESHOLD: Z` (DEBUG)
    *   `[LiquidityAnalysisOB] Analysis complete. Found A significant bids, B significant asks.` (DEBUG)
    *   `[GoldenStrategy] Liquidity analysis result: Sig Bids Count: A, Sig Asks Count: B` (DEBUG)
    *   `[GoldenStrategy] Calling on_liquidity_update_callback...` (DEBUG)
    *   `[GUI Liquidity] update_liquidity_display received. Status='...', SigBids: A, SigAsks: B` (DEBUG)
    *   In `_assess_sr_levels`: `[SR_Assess] Assessing Order Book Liquidity. ... Sig Bids: A, SigAsks: B` (DEBUG)
    *   And potentially: `[SR_Assess] Bounce detected off significant bid...` or `Rejection ... ask...` (DEBUG)

### Error Messages:
*   Look for lines with `ERROR` or `CRITICAL` severity.
*   `DataFetcher` connection errors (timeouts, network issues).
*   Errors during data processing (e.g., `ValueError` if kline data is malformed).
*   Errors in GUI update methods (e.g., `[GUI Error] In update_X_display: ...`).
*   Strategy logic errors (though these should ideally be caught and logged gracefully).

## 3. Debugging Tips

1.  **Set `LOG_LEVEL = "DEBUG"`**: In `trading_bot/utils/settings.py`, change `LOG_LEVEL` to `"DEBUG"` to get the most detailed output in your console. This is the first step for any troubleshooting.
2.  **Follow the Data Flow**: If a piece of information isn't appearing in the GUI (e.g., liquidity data, a specific indicator, price updates), use the log messages outlined above to trace where the data stops flowing. Start from the source (`DataFetcher`) and follow it through `main.py` to `GoldenStrategy` and finally to the GUI update methods.
3.  **Check GUI Status Bar**: This often shows higher-level status messages or errors that are user-facing and can provide initial clues.
4.  **Isolate Issues**:
    *   If no data appears at all (price, chart, order book): The problem is likely in `DataFetcher` initialization or its WebSocket connections. Check CRITICAL logs from `DataFetcher` first.
    *   If price updates but chart/indicators/signals don't: The issue might be in kline data processing in `main.py`, `GoldenStrategy` aggregation, or the callbacks for these specific GUI elements.
    *   If liquidity data is missing from GUI: Focus on logs prefixed with `[DataFetcherOB]`, `[MainApp]` handling order book, `[GoldenStrategy]` processing order book, `[LiquidityAnalysisOB]`, and `[GUI Liquidity]`. Check if `LIQUIDITY_SIGNIFICANT_QTY_THRESHOLD` in settings is too high, resulting in no "significant" levels being found.
5.  **Strategy Decisions (`[StrategyDebug]` logs)**: If the bot isn't producing signals when you expect (or producing unexpected ones), the `[StrategyDebug] (X_TF) States: Trend=..., MACD=...` log is vital. It shows the qualitative assessment for each component that feeds into the signal confluence logic. This can help you understand if, for example, the trend is assessed as 'NEUTRAL' when you think it's 'BULLISH', or if a specific indicator state is preventing confluence.
6.  **Parameter Tuning (`settings.py`)**: Many issues of "no signals" or "too many signals" can be related to the parameters in `settings.py`. The debug logs for indicator states will help you understand if thresholds (e.g., RSI levels, MACD histogram strength, S/R proximity) need adjustment.
7.  **Network & API Issues**:
    *   Persistent `TimeoutError` or `aiohttp.ClientError` during `DataFetcher` initialization usually point to network connectivity problems between your machine and Binance, or potential Binance API issues/rate limits. Check your internet, firewall, and consider if Binance is having known problems.
    *   The `REQUEST_TIMEOUT` in `settings.py` can be increased if your connection is generally slow for the initial connection.

By systematically checking these logs and understanding the data flow, most operational issues can be diagnosed.
