# 04 Module: Indicators Calculator

## 1. Purpose

The `indicators/calculator.py` module provides a suite of functions for calculating various common technical trading indicators. A key design principle for this module is self-containment: all indicator calculations are implemented from scratch using fundamental Python libraries like `pandas` and `numpy`, explicitly avoiding external specialized libraries such as TA-Lib. This approach ensures transparency in the calculations and minimizes external dependencies.

These functions are primarily consumed by the `GoldenStrategy` module to assess market conditions.

## 2. Implemented Indicators and Helper Functions

The module includes the following calculations:

### 2.1. Helper Functions

These are not standalone indicators but are used in the calculation of other indicators.

*   **`calculate_sma(prices, period)`**
    *   **Description**: Calculates the Simple Moving Average.
    *   **Parameters**:
        *   `prices` (list/pd.Series): Series of price data.
        *   `period` (int): The lookback period for the SMA.
    *   **Output**: `float` (SMA value) or `None` if not enough data.

*   **`calculate_ema(prices, period)`**
    *   **Description**: Calculates the Exponential Moving Average.
    *   **Parameters**:
        *   `prices` (list/pd.Series): Series of price data.
        *   `period` (int): The lookback period for the EMA (span).
    *   **Output**: `float` (EMA value) or `None` if not enough data. (Note: The implementation uses `pd.Series.ewm()` and returns the last value).

*   **`calculate_atr(high_prices, low_prices, close_prices, period=14)`**
    *   **Description**: Calculates the Average True Range, a measure of market volatility.
    *   **Parameters**:
        *   `high_prices` (pd.Series): Series of high prices.
        *   `low_prices` (pd.Series): Series of low prices.
        *   `close_prices` (pd.Series): Series of close prices.
        *   `period` (int, default 14): The lookback period for ATR (typically using Wilder's smoothing / EMA).
    *   **Output**: `pd.Series` (ATR values) or `None` if not enough data. The `GoldenStrategy` typically uses the last value of this series.
    *   **Settings Used (by `GoldenStrategy`)**: `settings.ATR_PERIOD` (default 14).

### 2.2. Core Indicators

*   **`calculate_macd(prices_series, short_period=12, long_period=26, signal_period=9)`**
    *   **Description**: Calculates Moving Average Convergence Divergence (MACD line, Signal line, Histogram).
    *   **Parameters**:
        *   `prices_series` (list/pd.Series): Series of closing prices.
        *   `short_period` (int, default 12): Period for the short-term EMA.
        *   `long_period` (int, default 26): Period for the long-term EMA.
        *   `signal_period` (int, default 9): Period for the EMA of the MACD line (Signal line).
    *   **Output**: `dict {'macd': float, 'signal': float, 'histogram': float}` or `None`/partial `None` if not enough data.
    *   **Settings Used (by `GoldenStrategy`)**: `settings.MACD_SHORT_PERIOD`, `settings.MACD_LONG_PERIOD`, `settings.MACD_SIGNAL_PERIOD`.

*   **`calculate_rsi(prices_series, period=14)`**
    *   **Description**: Calculates the Relative Strength Index.
    *   **Parameters**:
        *   `prices_series` (list/pd.Series): Series of closing prices.
        *   `period` (int, default 14): The lookback period for RSI.
    *   **Output**: `float` (RSI value) or `None`.
    *   **Settings Used (by `GoldenStrategy`)**: `settings.RSI_PERIOD`.

*   **`calculate_supertrend(high_prices_series, low_prices_series, close_prices_series, atr_period=10, atr_multiplier=3.0)`**
    *   **Description**: Calculates the Supertrend indicator, which identifies trend direction and provides dynamic support/resistance levels. Relies on ATR.
    *   **Parameters**:
        *   `high_prices_series`, `low_prices_series`, `close_prices_series` (list/pd.Series).
        *   `atr_period` (int, default 10): Period for ATR calculation used by Supertrend.
        *   `atr_multiplier` (float, default 3.0): Multiplier for ATR to define bands.
    *   **Output**: `dict {'trend': pd.Series, 'direction': pd.Series, 'last_trend': float, 'last_direction': int (1 for uptrend, -1 for downtrend)}` or `None`.
    *   **Settings Used (by `GoldenStrategy`)**: `settings.SUPERTREND_ATR_PERIOD` (which should align with `settings.ATR_PERIOD` for consistency if ATR is passed separately), `settings.SUPERTREND_MULTIPLIER`.

*   **`calculate_kdj(high_prices_series, low_prices_series, close_prices_series, n_period=9, m1_period=3, m2_period=3)`**
    *   **Description**: Calculates the KDJ Indicator (Random Index), similar to Stochastic Oscillator, showing overbought/oversold conditions and trend direction via K, D, and J lines.
    *   **Parameters**:
        *   `high_prices_series`, `low_prices_series`, `close_prices_series` (list/pd.Series).
        *   `n_period` (int, default 9): Period for RSV (Raw Stochastic Value).
        *   `m1_period` (int, default 3): Smoothing period for K line.
        *   `m2_period` (int, default 3): Smoothing period for D line.
    *   **Output**: `dict {'K': float, 'D': float, 'J': float}` or `None`.
    *   **Settings Used (by `GoldenStrategy`)**: `settings.KDJ_N_PERIOD`, `settings.KDJ_M1_PERIOD`, `settings.KDJ_M2_PERIOD`.

*   **`calculate_sar(high_prices_series, low_prices_series, initial_af=0.02, max_af=0.2, af_increment=0.02)`**
    *   **Description**: Calculates Parabolic Stop and Reverse (SAR), an indicator used to find potential reversals in market direction.
    *   **Parameters**:
        *   `high_prices_series`, `low_prices_series` (list/pd.Series).
        *   `initial_af` (float, default 0.02): Initial acceleration factor.
        *   `max_af` (float, default 0.2): Maximum acceleration factor.
        *   `af_increment` (float, default 0.02): Increment for acceleration factor.
    *   **Output**: `dict {'sar': pd.Series, 'last_sar': float, 'last_direction': int (1 for long, -1 for short)}` or `None`. ('last_direction' indicates the implied trend if price is above/below SAR).
    *   **Settings Used (by `GoldenStrategy`)**: `settings.SAR_INITIAL_AF`, `settings.SAR_MAX_AF`, `settings.SAR_AF_INCREMENT`.

*   **`calculate_williams_fractal(high_prices_series, low_prices_series, window=5)`**
    *   **Description**: Identifies Williams Fractal points (significant highs or lows) based on a pattern of surrounding bars. A 5-bar pattern (2 bars on each side of the fractal bar) is standard.
    *   **Parameters**:
        *   `high_prices_series`, `low_prices_series` (list/pd.Series).
        *   `window` (int, default 5): Number of bars in the fractal pattern.
    *   **Output**: `dict {'bullish': pd.Series (bool), 'bearish': pd.Series (bool), 'last_bullish_price': float/None, 'last_bearish_price': float/None}` or `None`.
    *   **Settings Used (by `GoldenStrategy`)**: `settings.FRACTAL_WINDOW`.

*   **`calculate_momentum(prices_series, period=10)`**
    *   **Description**: Calculates Momentum (Price_today - Price_N_periods_ago).
    *   **Parameters**:
        *   `prices_series` (list/pd.Series): Series of closing prices.
        *   `period` (int, default 10): The lookback period for momentum calculation.
    *   **Output**: `float` (Momentum value) or `None`.
    *   **Settings Used (by `GoldenStrategy`)**: `settings.MOMENTUM_PERIOD`.

## 3. Implementation Notes

*   All functions are designed to take pandas Series as primary input for price data, but can often handle lists which are then converted internally.
*   Return values are typically the latest calculated indicator value(s) or a dictionary containing them. Some indicators like Supertrend or SAR also return the full series if needed, but `GoldenStrategy` primarily uses the latest values.
*   Sufficient data length is required for calculations; functions will return `None` or partial data if the input series is too short for the specified periods.
*   Default periods for indicators are common standard values but are overridden by values from `utils/settings.py` when called by `GoldenStrategy`.

This module forms the analytical backbone for the trading strategy, providing the necessary data points for decision-making.
