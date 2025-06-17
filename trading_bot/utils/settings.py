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

# Minimum profit/loss percentages
MIN_TP_DISTANCE_PERCENTAGE = 0.005  # 0.5% minimum distance for TP from entry
MIN_SL_DISTANCE_PERCENTAGE = 0.005  # 0.5% minimum distance for SL from entry
MIN_TP_FALLBACK_PERCENTAGE = 0.01   # 1% TP if ATR is not available
MIN_SL_FALLBACK_PERCENTAGE = 0.01   # 1% SL if ATR is not available
