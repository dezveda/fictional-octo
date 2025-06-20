# trading_bot/utils/settings.py

# Shared application settings

TRADING_SYMBOL = "BTCUSDT" # Default trading symbol

# Logging configuration (can be expanded)
LOG_LEVEL = "INFO" # e.g., DEBUG, INFO, WARNING, ERROR

# GUI settings (example)
# GUI_THEME = "Dark"
# GUI_COLOR = "blue"

# Chart settings
CHART_MAX_AGG_BARS_DISPLAY = 100 # Max number of aggregated bars to display on chart
PRICE_PRECISION = 2 # Decimal places for price display on chart label
MIN_BARS_FOR_PROVISIONAL_INDICATORS = 15 # Min bars in chart_df for provisional indicators to calculate meaningfully
CHART_PRICE_LABEL_XOFFSET = 0.15 # X-offset for price label from right edge of last candle
CHART_PRICE_LABEL_COLOR = 'white'
CHART_PRICE_LABEL_BOXSTYLE = 'round,pad=0.15'
CHART_PRICE_LABEL_BGCOLOR = '#202020'
CHART_PRICE_LABEL_EDGECOLOR = 'gray'

# Order Book Settings
ORDER_BOOK_STREAM_DEPTH_LEVEL = 20 # For partial book depth (e.g., 5, 10, 20 for @depthX streams)
LOCAL_ORDER_BOOK_MAX_LEVELS = 20   # How many levels of bids/asks to store and display locally
ORDER_BOOK_UPDATE_SPEED_MS = "100ms" # Update speed for partial depth stream, e.g., '100ms' or '1000ms'

# Liquidity Analysis Settings
LIQUIDITY_SIGNIFICANT_QTY_THRESHOLD = 10 # Example: BTC quantity to be considered significant on L1/L2 book
LIQUIDITY_CLUSTER_PRICE_RANGE_FACTOR = 0.001 # e.g., 0.1% of current price for clustering bids/asks
LIQUIDITY_LEVELS_TO_CHECK = 2    # How many top bid/ask liquidity levels to check for S/R
LIQUIDITY_GUI_LEVELS_TO_SHOW = 3 # Number of top bid/ask liquidity levels to show in GUI

# Network Request Settings
REQUEST_TIMEOUT = 30  # Seconds for Binance API requests

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
MIN_RR_RATIO = 1.5 # Minimum Risk/Reward Ratio for a trade

# --- Strategy Helper Parameters ---
MACD_HIST_STRENGTH_THRESHOLD = 0.00005 # For BTCUSDT, adjust based on price volatility; small non-zero
RSI_BULLISH_CONFIRM = 55.0
RSI_BEARISH_CONFIRM = 45.0
KDJ_J_OVERBOUGHT = 90.0
KDJ_J_OVERSOLD = 10.0
KDJ_K_CONFIRM_OVERBOUGHT = 80.0 # K value to confirm J's overbought
KDJ_K_CONFIRM_OVERSOLD = 20.0 # K value to confirm J's oversold
SR_PROXIMITY_FACTOR = 0.003 # 0.3% proximity to S/R levels for bounce/rejection
VOLUME_AVG_PERIOD = 20 # Rolling average period for volume assessment
VOLUME_HIGH_MULTIPLIER = 1.5 # Volume > X * average
VOLUME_LOW_MULTIPLIER = 0.7  # Volume < X * average
SL_PRICE_BUFFER_ATR_FACTOR = 0.1 # Factor of ATR to use as a buffer for SL placement beyond bar low/high


# Timeframe for strategy calculations (e.g., '1T' for 1 minute, '5T', '15T', '1H', '4H')
# Note: 'T' is pandas offset alias for minute. Use 'min' for pd.Timedelta, e.g. '1min', '60min'
STRATEGY_TIMEFRAME = "1H"

# Interval for DataFetcher to fetch klines (e.g., '1m', '5m', '1h') - must match Binance API options for websockets and historical data
KLINE_FETCH_INTERVAL = "1m"

# Number of STRATEGY_TIMEFRAME bars to pre-fill with historical data
HISTORICAL_LOOKBACK_AGG_BARS_COUNT = 150

# Minimum profit/loss percentages
MIN_TP_DISTANCE_PERCENTAGE = 0.005  # 0.5% minimum distance for TP from entry
MIN_SL_DISTANCE_PERCENTAGE = 0.005  # 0.5% minimum distance for SL from entry
MIN_TP_FALLBACK_PERCENTAGE = 0.01   # 1% TP if ATR is not available
MIN_SL_FALLBACK_PERCENTAGE = 0.01   # 1% SL if ATR is not available
