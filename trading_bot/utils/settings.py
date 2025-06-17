# trading_bot/utils/settings.py

# Shared application settings

TRADING_SYMBOL = "BTCUSDT" # Default trading symbol

# Logging configuration (can be expanded)
LOG_LEVEL = "INFO" # e.g., DEBUG, INFO, WARNING, ERROR

# GUI settings (example)
# GUI_THEME = "Dark"
# GUI_COLOR = "blue"

# --- Indicator & Strategy Parameters ---

# Indicator Periods
RSI_PERIOD = 14
MACD_SHORT_PERIOD = 12
MACD_LONG_PERIOD = 26
MACD_SIGNAL_PERIOD = 9
SUPERTREND_ATR_PERIOD = 10 # For Supertrend indicator itself
SUPERTREND_MULTIPLIER = 3.0
KDJ_N_PERIOD = 9
KDJ_M1_PERIOD = 3
KDJ_M2_PERIOD = 3
SAR_INITIAL_AF = 0.02
SAR_MAX_AF = 0.2
SAR_AF_INCREMENT = 0.02
FRACTAL_WINDOW = 5
MOMENTUM_PERIOD = 10
ATR_PERIOD = 14 # General ATR period, used by Supertrend and can be used for TP/SL

# Strategy Parameters
STRATEGY_RSI_OVERSOLD = 30
STRATEGY_RSI_OVERBOUGHT = 70
STRATEGY_ENTRY_THRESHOLD = 3.0 # Score needed to generate a signal
ATR_TP_MULTIPLIER = 2.0 # Example: TP is 2 * ATR
ATR_SL_MULTIPLIER = 1.5 # Example: SL is 1.5 * ATR

# Timeframe for strategy calculations (e.g., '1T' for 1 minute, '5T', '15T', '1H', '4H')
# Note: 'T' is pandas offset alias for minute. Use 'min' for pd.Timedelta, e.g. '1min', '60min'
STRATEGY_TIMEFRAME = "1H"

# Interval for DataFetcher to fetch klines (e.g., '1m', '5m', '1h') - must match Binance API options for websockets and historical data
# For 1s data via WebSocket: fetcher.py currently hardcodes AsyncClient.KLINE_INTERVAL_1SECOND
# This KLINE_FETCH_INTERVAL would be for the historical data fetch to match strategy aggregation, or if WS also changes.
# The prompt implies this is for WS, but 1s is usually fetched for responsiveness if strategy is on higher TF.
# Let's assume this is for the WebSocket kline interval if we make it configurable,
# and historical data fetch will use this too.
# For now, fetcher.py uses 1s for WebSocket. This setting might be for a different purpose or future refactor.
# Let's assume it's for the base kline interval the strategy *could* receive if not 1s.
# The prompt's fetcher code changes `start_fetching` to use this.
KLINE_FETCH_INTERVAL = "1m" # Example: fetch 1-minute klines for WebSocket and historical.

# Number of STRATEGY_TIMEFRAME bars to pre-fill with historical data
HISTORICAL_LOOKBACK_AGG_BARS_COUNT = 150 # e.g., 150 bars of STRATEGY_TIMEFRAME

# Minimum profit/loss percentages
MIN_TP_DISTANCE_PERCENTAGE = 0.005  # 0.5% minimum distance for TP from entry
MIN_SL_DISTANCE_PERCENTAGE = 0.005  # 0.5% minimum distance for SL from entry
MIN_TP_FALLBACK_PERCENTAGE = 0.01   # 1% TP if ATR is not available
MIN_SL_FALLBACK_PERCENTAGE = 0.01   # 1% SL if ATR is not available
