import pandas as pd
import numpy as np
from collections import deque

# Helper function for Exponential Moving Average (EMA)
def calculate_ema(prices, period):
    """Calculates Exponential Moving Average (EMA)."""
    if len(prices) < period:
        return None  # Not enough data
    # Pandas ewm method is efficient for this.
    # adjust=False makes it behave like most trading platforms' EMAs.
    return pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]

def calculate_sma(prices, period):
    """Calculates Simple Moving Average (SMA)."""
    if len(prices) < period:
        return None # Not enough data
    return np.mean(prices[-period:])


# 1. MACD (Moving Average Convergence Divergence)
def calculate_macd(prices_series, short_period=12, long_period=26, signal_period=9):
    """
    Calculates MACD, MACD Signal, and MACD Histogram.
    Assumes `prices_series` is a list or pandas Series of closing prices.
    Returns a dictionary { 'macd': value, 'signal': value, 'histogram': value } or None if not enough data.
    """
    if not isinstance(prices_series, pd.Series):
        prices_series = pd.Series(prices_series)

    if len(prices_series) < long_period:
        return None # Not enough data to calculate long EMA

    ema_short = prices_series.ewm(span=short_period, adjust=False).mean()
    ema_long = prices_series.ewm(span=long_period, adjust=False).mean()

    macd_line = ema_short - ema_long

    if len(macd_line) < signal_period: # Check if macd_line itself has enough data for signal line
        return {'macd': macd_line.iloc[-1], 'signal': None, 'histogram': None}

    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line

    return {
        'macd': macd_line.iloc[-1],
        'signal': signal_line.iloc[-1],
        'histogram': histogram.iloc[-1]
    }

# 2. RSI (Relative Strength Index)
def calculate_rsi(prices_series, period=14):
    """
    Calculates Relative Strength Index (RSI).
    Assumes `prices_series` is a list or pandas Series of closing prices.
    Returns the RSI value or None if not enough data.
    """
    if not isinstance(prices_series, pd.Series):
        prices_series = pd.Series(prices_series)

    if len(prices_series) <= period: # Needs more than `period` data points
        return None # Not enough data

    delta = prices_series.diff()

    # Ensure delta series is float for calculations
    gain = delta.where(delta > 0, 0).astype(float).fillna(0)
    loss = -delta.where(delta < 0, 0).astype(float).fillna(0)

    # Calculate EMA of gain and loss (Wilder's smoothing)
    # min_periods=period ensures that we only get values after enough data
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    # Check if there's enough data for avg_gain and avg_loss after ewm
    # This check is implicitly handled by how pandas ewm works if enough input data is present
    # but we need to ensure we have valid numbers for the last element.

    current_avg_gain = avg_gain.iloc[-1]
    current_avg_loss = avg_loss.iloc[-1]

    if pd.isna(current_avg_gain) or pd.isna(current_avg_loss):
         # This can happen if the series passed to ewm is too short for any output,
         # or if initial values of gain/loss are all zero for the period.
        return None


    if current_avg_loss == 0:
        return 100.0 # RSI is 100 if average loss is 0

    rs = current_avg_gain / current_avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))

    return rsi

# 3. Supertrend
def calculate_atr(high_prices, low_prices, close_prices, period=14):
    """
    Calculates Average True Range (ATR).
    Expects pandas Series for high, low, and close prices.
    Returns a pandas Series of ATR values.
    """
    if not (isinstance(high_prices, pd.Series) and
            isinstance(low_prices, pd.Series) and
            isinstance(close_prices, pd.Series)):
        raise ValueError("Inputs (high, low, close) must be pandas Series.")

    if not (len(high_prices) == len(low_prices) == len(close_prices)):
        raise ValueError("Input series must have the same length.")

    if len(close_prices) < period:
        return None # Not enough data

    # Calculate True Range (TR)
    tr1 = high_prices - low_prices
    tr2 = abs(high_prices - close_prices.shift(1))
    tr3 = abs(low_prices - close_prices.shift(1))

    true_range = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
    true_range.iloc[0] = high_prices.iloc[0] - low_prices.iloc[0] # First TR is just High - Low for that period

    # ATR is typically calculated using Wilder's smoothing method (an EMA)
    atr_series = true_range.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    return atr_series

def calculate_supertrend(high_prices_series, low_prices_series, close_prices_series, atr_period=10, atr_multiplier=3.0):
    """
    Calculates Supertrend indicator.
    Expects lists or pandas Series for high, low, and close prices.
    Returns a dictionary {'trend': Series, 'direction': Series, 'last_trend': value, 'last_direction': value} or None.
    Direction: 1 for uptrend, -1 for downtrend.
    """
    if not isinstance(high_prices_series, pd.Series):
        high_prices_series = pd.Series(high_prices_series, dtype=float)
    if not isinstance(low_prices_series, pd.Series):
        low_prices_series = pd.Series(low_prices_series, dtype=float)
    if not isinstance(close_prices_series, pd.Series):
        close_prices_series = pd.Series(close_prices_series, dtype=float)

    if len(close_prices_series) < atr_period + 1: # Need enough data for ATR and then Supertrend logic
        return None

    atr = calculate_atr(high_prices_series, low_prices_series, close_prices_series, period=atr_period)
    if atr is None or atr.empty or atr.isna().all():
        return None # Not enough data for ATR

    # Basic Supertrend Calculation
    hl2 = (high_prices_series + low_prices_series) / 2
    upper_band = hl2 + (atr_multiplier * atr)
    lower_band = hl2 - (atr_multiplier * atr)

    supertrend = pd.Series(index=close_prices_series.index, dtype=float)
    direction = pd.Series(index=close_prices_series.index, dtype=int) # 1 for uptrend, -1 for downtrend

    # Initial state: Assume downtrend for the first valid ATR point if close is below upper_band, else uptrend.
    # This initialization can vary. A common way is to wait for a clear cross.
    # For simplicity, let's initialize based on the first point where ATR is available.

    first_valid_atr_index = atr.first_valid_index()
    if first_valid_atr_index is None:
        return None # Should not happen if atr is not None/empty

    # Iterate from the first point where ATR is valid
    # Initialize first Supertrend value
    if close_prices_series[first_valid_atr_index] <= upper_band[first_valid_atr_index]:
        supertrend[first_valid_atr_index] = upper_band[first_valid_atr_index]
        direction[first_valid_atr_index] = -1 # Downtrend
    else:
        supertrend[first_valid_atr_index] = lower_band[first_valid_atr_index]
        direction[first_valid_atr_index] = 1 # Uptrend

    for i in range(first_valid_atr_index + 1, len(close_prices_series)):
        current_close = close_prices_series[i]
        prev_close = close_prices_series[i-1]
        prev_supertrend = supertrend[i-1]
        prev_direction = direction[i-1]

        if prev_direction == 1: # Previous was Uptrend
            supertrend[i] = lower_band[i]
            if current_close < lower_band[i]: # Price crossed below lower band
                direction[i] = -1 # Change to Downtrend
                supertrend[i] = upper_band[i] # Switch band
            else:
                direction[i] = 1 # Continue Uptrend
                # Adjust band: if current lower_band is higher than previous, use it
                supertrend[i] = max(lower_band[i], prev_supertrend)
        else: # Previous was Downtrend
            supertrend[i] = upper_band[i]
            if current_close > upper_band[i]: # Price crossed above upper band
                direction[i] = 1 # Change to Uptrend
                supertrend[i] = lower_band[i] # Switch band
            else:
                direction[i] = -1 # Continue Downtrend
                # Adjust band: if current upper_band is lower than previous, use it
                supertrend[i] = min(upper_band[i], prev_supertrend)

    if supertrend.empty or supertrend.isna().all(): # check if all values are NaN
        return None

    return {
        'trend': supertrend, # Full series
        'direction': direction, # Full series
        'last_trend': supertrend.iloc[-1],
        'last_direction': direction.iloc[-1]
    }

# 4. KDJ Indicator
def calculate_kdj(high_prices_series, low_prices_series, close_prices_series, n_period=9, m1_period=3, m2_period=3):
    """
    Calculates KDJ Indicator (K, D, J lines).
    KDJ is similar to the Stochastic Oscillator.
    Expects pandas Series for high, low, and close prices.
    n_period: The period for calculating RSV (usually 9).
    m1_period: The period for smoothing K (usually 3).
    m2_period: The period for smoothing D (usually 3).
    Returns a dictionary {'K': value, 'D': value, 'J': value} or None if not enough data.
    """
    if not (isinstance(high_prices_series, pd.Series) and
            isinstance(low_prices_series, pd.Series) and
            isinstance(close_prices_series, pd.Series)):
        # Convert if they are lists, otherwise raise error if conversion fails
        try:
            high_prices_series = pd.Series(high_prices_series, dtype=float)
            low_prices_series = pd.Series(low_prices_series, dtype=float)
            close_prices_series = pd.Series(close_prices_series, dtype=float)
        except ValueError:
            raise ValueError("Inputs (high, low, close) must be pandas Series or convertible to them.")

    if not (len(high_prices_series) == len(low_prices_series) == len(close_prices_series)):
        raise ValueError("Input series must have the same length.")

    if len(close_prices_series) < n_period:
        return None # Not enough data for RSV calculation

    # Calculate RSV (Raw Stochastic Value)
    lowest_low_n = low_prices_series.rolling(window=n_period, min_periods=n_period).min()
    highest_high_n = high_prices_series.rolling(window=n_period, min_periods=n_period).max()

    # Avoid division by zero if highest_high_n == lowest_low_n
    # RSV formula: (Close - Lowest Low N) / (Highest High N - Lowest Low N) * 100
    rsv = ((close_prices_series - lowest_low_n) / (highest_high_n - lowest_low_n).replace(0, np.nan)) * 100
    rsv = rsv.fillna(50) # Fill NaNs in RSV (e.g. from division by zero if HH=LL) with a neutral 50, or handle as per strategy.
                         # Some implementations might carry forward previous K/D in this case.

    # Calculate K, D, J lines using EMA-like smoothing (common practice)
    # Initial K and D are often set to 50.
    # K = (2/3) * Previous K + (1/3) * RSV
    # D = (2/3) * Previous D + (1/3) * K
    # J = 3 * K - 2 * D

    k_values = pd.Series(index=rsv.index, dtype=float)
    d_values = pd.Series(index=rsv.index, dtype=float)

    # Initialize first K and D. If RSV has NaNs at the start, K/D will also be NaN.
    # Start calculation from the first valid RSV value.
    first_valid_rsv_idx = rsv.first_valid_index()
    if first_valid_rsv_idx is None:
        return None # No valid RSV values

    # Initialize K and D at the first valid RSV point.
    # A common initialization is 50, or the first RSV value for K.
    k_values[first_valid_rsv_idx] = rsv[first_valid_rsv_idx] # Or 50.0
    d_values[first_valid_rsv_idx] = k_values[first_valid_rsv_idx] # Or 50.0

    # Iterative smoothing for K
    # This is equivalent to an EMA with alpha = 1/m1_period if using the (1-alpha)*prev + alpha*curr formula
    # Or span = 2*m1_period - 1 if using pandas ewm span.
    # For the typical KDJ (2/3, 1/3) rule, it's a specific type of EMA.
    # Let's use the direct formula for clarity with m1_period.
    # K_today = ( (m1_period - 1) * K_yesterday + RSV_today ) / m1_period
    # D_today = ( (m2_period - 1) * D_yesterday + K_today   ) / m2_period

    # Using pandas ewm for a more standard EMA approach for K from RSV, and D from K
    # alpha_k = 1.0 / m1_period  # Simple EMA alpha for K from RSV
    # alpha_d = 1.0 / m2_period  # Simple EMA alpha for D from K

    # K is EMA of RSV. D is EMA of K.
    # The smoothing factor in KDJ is often expressed as (N-1)/N for previous value and 1/N for current.
    # e.g., K_t = (2/3)*K_{t-1} + (1/3)*RSV_t. This is an EMA with alpha = 1/3.
    # So, if m1_period = 3, alpha = 1/3. Span for pandas ewm would be (2/alpha) - 1 = 2*3 - 1 = 5.

    k_values = rsv.ewm(span=m1_period*2-1 if m1_period > 1 else 1, adjust=False, min_periods=1).mean()
    d_values = k_values.ewm(span=m2_period*2-1 if m2_period > 1 else 1, adjust=False, min_periods=1).mean()

    j_values = 3 * k_values - 2 * d_values

    # Ensure K, D, J are clipped between 0 and 100 (or allow J to go beyond for divergence)
    # Standard KDJ J can go outside 0-100. K and D are typically within 0-100.
    k_values = k_values.clip(0, 100)
    d_values = d_values.clip(0, 100)
    # J is often not clipped, or clipped to a wider range like -20 to 120. For now, no clipping on J.

    if k_values.empty or k_values.isna().all() or \
       d_values.empty or d_values.isna().all() or \
       j_values.empty or j_values.isna().all():
        return None

    return {
        'K': k_values.iloc[-1],
        'D': d_values.iloc[-1],
        'J': j_values.iloc[-1]
    }

# 5. Parabolic SAR (Stop and Reverse)
def calculate_sar(high_prices_series, low_prices_series, initial_af=0.02, max_af=0.2, af_increment=0.02):
    """
    Calculates Parabolic SAR (Stop and Reverse).
    Expects pandas Series for high and low prices.
    Returns a dictionary {'sar': Series, 'last_sar': value, 'last_direction': value} or None.
    Direction: 1 for long (SAR below price), -1 for short (SAR above price).
    """
    if not (isinstance(high_prices_series, pd.Series) and
            isinstance(low_prices_series, pd.Series)):
        try:
            high_prices_series = pd.Series(high_prices_series, dtype=float)
            low_prices_series = pd.Series(low_prices_series, dtype=float)
        except ValueError:
            raise ValueError("Inputs (high, low) must be pandas Series or convertible to them.")

    if not (len(high_prices_series) == len(low_prices_series)):
        raise ValueError("Input high and low price series must have the same length.")

    if len(high_prices_series) < 2: # Need at least 2 points to determine initial trend
        return None

    sar_values = pd.Series(index=high_prices_series.index, dtype=float)
    direction_values = pd.Series(index=high_prices_series.index, dtype=int) # 1 for long, -1 for short

    # Initial SAR:
    # First SAR is typically the previous Low if trend is up, or previous High if trend is down.
    # Let's determine initial trend by comparing the first two close prices (if available)
    # or simply start with an assumed trend. For simplicity, we'll use High/Low of first period.
    # A common initialization: if close[1] > close[0], trend is up, SAR is low[0]. Else, SAR is high[0].
    # As we don't have close prices directly here, we'll base initial SAR on low/high of the first period
    # and assume an initial uptrend if the second period's low is higher, else downtrend.

    # Simplified initialization:
    # Start with SAR at the first low, assuming an uptrend.
    # If the next period reverses, it will flip. This is a common approach.

    sar_values.iloc[0] = low_prices_series.iloc[0]
    is_long_trend = True # Initial assumption
    direction_values.iloc[0] = 1
    af = initial_af
    ep = high_prices_series.iloc[0] # Extreme Point

    for i in range(1, len(high_prices_series)):
        prev_sar = sar_values.iloc[i-1]

        if is_long_trend:
            current_sar = prev_sar + af * (ep - prev_sar)
            # Ensure SAR does not move into the prior period's low or current period's low
            current_sar = min(current_sar, low_prices_series.iloc[i-1], low_prices_series.iloc[i])

            if low_prices_series.iloc[i] < current_sar: # Trend reversal to short
                is_long_trend = False
                direction_values.iloc[i] = -1
                current_sar = ep # SAR becomes the prior EP (which was a high)
                ep = low_prices_series.iloc[i] # New EP is current low
                af = initial_af
            else: # Continue long trend
                direction_values.iloc[i] = 1
                if high_prices_series.iloc[i] > ep: # New extreme high
                    ep = high_prices_series.iloc[i]
                    af = min(af + af_increment, max_af)
        else: # Short trend
            current_sar = prev_sar - af * (prev_sar - ep)
            # Ensure SAR does not move into the prior period's high or current period's high
            current_sar = max(current_sar, high_prices_series.iloc[i-1], high_prices_series.iloc[i])

            if high_prices_series.iloc[i] > current_sar: # Trend reversal to long
                is_long_trend = True
                direction_values.iloc[i] = 1
                current_sar = ep # SAR becomes the prior EP (which was a low)
                ep = high_prices_series.iloc[i] # New EP is current high
                af = initial_af
            else: # Continue short trend
                direction_values.iloc[i] = -1
                if low_prices_series.iloc[i] < ep: # New extreme low
                    ep = low_prices_series.iloc[i]
                    af = min(af + af_increment, max_af)

        sar_values.iloc[i] = current_sar

    if sar_values.empty or sar_values.isna().all():
        return None

    return {
        'sar': sar_values,
        'last_sar': sar_values.iloc[-1],
        'last_direction': direction_values.iloc[-1] # 1 for long, -1 for short
    }

# 6. Williams Fractal
def calculate_williams_fractal(high_prices_series, low_prices_series, window=5):
    """
    Calculates Williams Fractals.
    A bearish fractal: High[i] > High[i-1] and High[i] > High[i-2] and High[i] > High[i+1] and High[i] > High[i+2]
    A bullish fractal: Low[i] < Low[i-1] and Low[i] < Low[i-2] and Low[i] < Low[i+1] and Low[i] < Low[i+2]
    The standard window is 5 bars (middle bar is the fractal, with 2 bars on each side).

    Expects pandas Series for high and low prices.
    Returns a dictionary {'bullish': Series (boolean), 'bearish': Series (boolean),
                         'last_bullish_price': float/None, 'last_bearish_price': float/None} or None.
    The boolean series are True where a fractal is confirmed.
    Note: Fractals are lagging; a fractal at index `i` is confirmed at index `i + (window//2)`.
    This implementation identifies the fractal point at index `i` based on surrounding data.
    For real-time, one would typically look for fractals that formed `window//2` bars ago.
    """
    if not (isinstance(high_prices_series, pd.Series) and
            isinstance(low_prices_series, pd.Series)):
        try:
            high_prices_series = pd.Series(high_prices_series, dtype=float)
            low_prices_series = pd.Series(low_prices_series, dtype=float)
        except ValueError:
            raise ValueError("Inputs (high, low) must be pandas Series or convertible to them.")

    if not (len(high_prices_series) == len(low_prices_series)):
        raise ValueError("Input high and low price series must have the same length.")

    if len(high_prices_series) < window:
        return None # Not enough data for a full window comparison

    n = window // 2 # Number of bars on each side of the potential fractal

    bearish_fractals = pd.Series(index=high_prices_series.index, dtype=bool)
    bullish_fractals = pd.Series(index=low_prices_series.index, dtype=bool)

    for i in range(n, len(high_prices_series) - n):
        # Bearish Fractal Check
        is_bearish = True
        for j in range(1, n + 1):
            if not (high_prices_series.iloc[i] > high_prices_series.iloc[i-j] and \
                    high_prices_series.iloc[i] > high_prices_series.iloc[i+j]):
                is_bearish = False
                break
        bearish_fractals.iloc[i] = is_bearish

        # Bullish Fractal Check
        is_bullish = True
        for j in range(1, n + 1):
            if not (low_prices_series.iloc[i] < low_prices_series.iloc[i-j] and \
                    low_prices_series.iloc[i] < low_prices_series.iloc[i+j]):
                is_bullish = False
                break
        bullish_fractals.iloc[i] = is_bullish

    # Get the price of the last identified fractals
    last_bearish_fractal_price = None
    if bearish_fractals.any():
        # Get the high price at the location of the last True bearish fractal
        # Ensure index exists before accessing
        true_bearish_indices = bearish_fractals[bearish_fractals].index
        if not true_bearish_indices.empty:
            last_bearish_index = true_bearish_indices[-1]
            last_bearish_fractal_price = high_prices_series.get(last_bearish_index) # use .get for safety

    last_bullish_fractal_price = None
    if bullish_fractals.any():
        # Get the low price at the location of the last True bullish fractal
        true_bullish_indices = bullish_fractals[bullish_fractals].index
        if not true_bullish_indices.empty:
            last_bullish_index = true_bullish_indices[-1]
            last_bullish_fractal_price = low_prices_series.get(last_bullish_index) # use .get for safety

    return {
        'bearish': bearish_fractals, # Full series
        'bullish': bullish_fractals, # Full series
        'last_bearish_price': last_bearish_fractal_price,
        'last_bullish_price': last_bullish_fractal_price
    }

# 7. Momentum
def calculate_momentum(prices_series, period=10):
    """
    Calculates Momentum.
    Momentum = Current Price - Price N periods ago.
    Expects a pandas Series of prices.
    Returns the latest momentum value or None if not enough data.
    """
    if not isinstance(prices_series, pd.Series):
        try:
            prices_series = pd.Series(prices_series, dtype=float)
        except ValueError:
            raise ValueError("Input prices_series must be a pandas Series or convertible to one.")

    if len(prices_series) <= period: # Needs more than `period` data points for the first calculation
        return None

    momentum = prices_series.diff(period)

    if momentum.empty or pd.isna(momentum.iloc[-1]):
        return None

    return momentum.iloc[-1]

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    print("--- Testing Indicator Calculations ---")

    # Test data (simulate a series of closing prices)
    # For MACD, we need at least long_period + signal_period data points for full calculation.
    # Example: long_period=26, signal_period=9. So ~35 points for all values.
    test_prices_short = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25] # 16 points
    test_prices_long = list(range(10, 50)) # 40 points, enough for MACD

    print("\n--- MACD Test ---")
    macd_result_short = calculate_macd(test_prices_short)
    print(f"MACD with short data (16 points): {macd_result_short}") # Expect some Nones or partials

    macd_result_long = calculate_macd(test_prices_long)
    if macd_result_long:
        print(f"MACD with long data (40 points):")
        print(f"  MACD Line: {macd_result_long['macd']:.4f}")
        print(f"  Signal Line: {macd_result_long['signal']:.4f}")
        print(f"  Histogram: {macd_result_long['histogram']:.4f}")
    else:
        print("MACD with long data: Not enough data (this shouldn't happen with 40 points).")

    # Example: test with a more realistic price series
    realistic_prices = [
        22.27, 22.19, 22.08, 22.17, 22.18, 22.13, 22.23, 22.43, 22.24, 22.29, 22.15, 22.39,
        22.38, 22.61, 23.36, 24.05, 23.75, 23.83, 23.95, 23.63, 23.82, 23.87, 23.65, 23.19,
        23.10, 23.33, 22.94, 23.00, 22.70, 22.62, 22.40, 22.17, 22.03, 21.75, 21.54, 21.25
    ] # 36 points

    macd_realistic = calculate_macd(realistic_prices)
    if macd_realistic and macd_realistic['signal'] is not None:
        print(f"MACD with realistic data (36 points):")
        print(f"  MACD Line: {macd_realistic['macd']:.4f}")
        print(f"  Signal Line: {macd_realistic['signal']:.4f}")
        print(f"  Histogram: {macd_realistic['histogram']:.4f}")
    else:
        print(f"MACD with realistic data: {macd_realistic}")

    print("\n--- RSI Test ---")
    # For RSI, period=14 is common. Need at least period + 1 data points.
    # Using the same 'realistic_prices' which has 36 points.
    rsi_result_short = calculate_rsi(test_prices_short, period=14) # 16 points
    if rsi_result_short is not None:
        print(f"RSI with short data (16 points, period 14): {rsi_result_short:.2f}")
    else:
        print("RSI with short data: Not enough data or initial values prevent calculation")

    rsi_result_realistic = calculate_rsi(realistic_prices, period=14)
    if rsi_result_realistic is not None:
        print(f"RSI with realistic data (36 points, period 14): {rsi_result_realistic:.2f}")
    else:
        print("RSI with realistic data: Not enough data or initial values prevent calculation")

    # Test edge case for RSI (all gains, RSI should be 100)
    all_gains_prices = list(range(10, 30)) # 20 points, all increasing
    rsi_all_gains = calculate_rsi(all_gains_prices, period=14)
    if rsi_all_gains is not None:
        print(f"RSI with all gains (20 points, period 14): {rsi_all_gains:.2f}")
    else:
        print("RSI with all gains: Not enough data or initial values prevent calculation")

    # Test edge case for RSI (all losses, RSI should be close to 0)
    all_losses_prices = list(range(30, 10, -1)) # 20 points, all decreasing
    rsi_all_losses = calculate_rsi(all_losses_prices, period=14)
    if rsi_all_losses is not None:
        print(f"RSI with all losses (20 points, period 14): {rsi_all_losses:.2f}")
    else:
        print("RSI with all losses: Not enough data or initial values prevent calculation")

    print("\n--- Supertrend Test ---")
    # Supertrend needs High, Low, Close data.
    # Using 'realistic_prices' for close, and generating dummy high/low.
    # Ensure realistic_prices_series is defined from MACD tests or define it here.
    # realistic_prices was defined above.

    if 'realistic_prices' in locals() or 'realistic_prices' in globals():
        realistic_prices_series = pd.Series(realistic_prices, dtype=float)
        # Create dummy High and Low prices around the Close prices
        high_data = realistic_prices_series * 1.02 # Approx 2% above close
        low_data = realistic_prices_series * 0.98  # Approx 2% below close

        if len(realistic_prices_series) > 15: # Check if enough data for ATR period 10
            supertrend_result = calculate_supertrend(high_data, low_data, realistic_prices_series, atr_period=10, atr_multiplier=3.0)
            if supertrend_result and not pd.isna(supertrend_result['last_trend']):
                print(f"Supertrend with realistic data (36 points, ATR 10, Multiplier 3):")
                print(f"  Last Trend Value: {supertrend_result['last_trend']:.4f}")
                print(f"  Last Direction: {'Uptrend' if supertrend_result['last_direction'] == 1 else 'Downtrend'}")
                # print(f"  Full Trend Series (last 5):\n{supertrend_result['trend'].tail()}")
                # print(f"  Full Direction Series (last 5):\n{supertrend_result['direction'].tail()}")
            else:
                print("Supertrend with realistic data: Not enough data or NaN result.")
        else:
            print("Supertrend test: Not enough realistic price data points for the test parameters.")

    else:
        print("Supertrend test: 'realistic_prices' data not found for testing.")

    print("\n--- KDJ Test ---")
    # KDJ also needs High, Low, Close data.
    if 'realistic_prices' in locals() or 'realistic_prices' in globals():
        realistic_prices_series_kdj = pd.Series(realistic_prices, dtype=float)
        high_data_kdj = realistic_prices_series_kdj * 1.02
        low_data_kdj = realistic_prices_series_kdj * 0.98

        # n_period=9, m1_period=3, m2_period=3. Need len >= 9.
        if len(realistic_prices_series_kdj) >= 9:
            kdj_result = calculate_kdj(high_data_kdj, low_data_kdj, realistic_prices_series_kdj, n_period=9, m1_period=3, m2_period=3)
            if kdj_result and not pd.isna(kdj_result['K']):
                print(f"KDJ with realistic data (36 points, n=9, m1=3, m2=3):")
                print(f"  K: {kdj_result['K']:.2f}")
                print(f"  D: {kdj_result['D']:.2f}")
                print(f"  J: {kdj_result['J']:.2f}")
            else:
                print(f"KDJ with realistic data: Not enough data or NaN result. Result: {kdj_result}")
        else:
            print("KDJ test: Not enough realistic price data points for the test parameters.")

        # Test with shorter data to check None returns
        short_prices_kdj = realistic_prices_series_kdj.head(8) # Less than n_period=9
        short_high_kdj = high_data_kdj.head(8)
        short_low_kdj = low_data_kdj.head(8)
        kdj_short_result = calculate_kdj(short_high_kdj, short_low_kdj, short_prices_kdj, n_period=9)
        print(f"KDJ with very short data (8 points): {kdj_short_result}")


    else:
        print("KDJ test: 'realistic_prices' data not found for testing.")

    print("\n--- Parabolic SAR Test ---")
    if 'realistic_prices' in locals() or 'realistic_prices' in globals():
        realistic_prices_series_sar = pd.Series(realistic_prices, dtype=float)
        # SAR needs high and low prices. We'll use the same dummy data as before.
        high_data_sar = realistic_prices_series_sar * 1.02
        low_data_sar = realistic_prices_series_sar * 0.98

        if len(realistic_prices_series_sar) >= 2: # SAR needs at least 2 points
            sar_result = calculate_sar(high_data_sar, low_data_sar)
            if sar_result and not pd.isna(sar_result['last_sar']):
                print(f"SAR with realistic data (36 points):")
                print(f"  Last SAR Value: {sar_result['last_sar']:.4f}")
                print(f"  Last Direction: {'Long' if sar_result['last_direction'] == 1 else 'Short'}")
                # print(f"  SAR Series (last 5):\n{sar_result['sar'].tail()}")
            else:
                print(f"SAR with realistic data: Not enough data or NaN result. Result: {sar_result}")
        else:
            print("SAR test: Not enough realistic price data points for test.")

        # Test with very short data
        short_high_sar = high_data_sar.head(1)
        short_low_sar = low_data_sar.head(1)
        sar_short_result = calculate_sar(short_high_sar, short_low_sar)
        print(f"SAR with very short data (1 point): {sar_short_result}") # Expect None

        medium_high_sar = high_data_sar.head(5)
        medium_low_sar = low_data_sar.head(5)
        sar_medium_result = calculate_sar(medium_high_sar, medium_low_sar)
        if sar_medium_result and not pd.isna(sar_medium_result['last_sar']):
            print(f"SAR with medium data (5 points): Last SAR: {sar_medium_result['last_sar']:.4f}, Dir: {'Long' if sar_medium_result['last_direction'] == 1 else 'Short'}")
        else:
            print(f"SAR with medium data (5 points): {sar_medium_result}")

    else:
        print("SAR test: 'realistic_prices' data not found for testing.")

    print("\n--- Williams Fractal Test ---")
    if 'realistic_prices' in locals() or 'realistic_prices' in globals():
        realistic_prices_series_frac = pd.Series(realistic_prices, dtype=float)
        high_data_frac = realistic_prices_series_frac * 1.02
        low_data_frac = realistic_prices_series_frac * 0.98

        # Standard window is 5 (2 bars on each side)
        if len(realistic_prices_series_frac) >= 5:
            fractal_result = calculate_williams_fractal(high_data_frac, low_data_frac, window=5)
            if fractal_result:
                print(f"Williams Fractal with realistic data (36 points, window 5):")
                num_bearish = fractal_result['bearish'].sum()
                num_bullish = fractal_result['bullish'].sum()
                print(f"  Number of Bearish Fractals: {num_bearish}")
                print(f"  Last Bearish Fractal Price: {fractal_result['last_bearish_price']}")
                # print(f"  Bearish Fractal Series (where True):\n{high_data_frac[fractal_result['bearish']]}")
                print(f"  Number of Bullish Fractals: {num_bullish}")
                print(f"  Last Bullish Fractal Price: {fractal_result['last_bullish_price']}")
                # print(f"  Bullish Fractal Series (where True):\n{low_data_frac[fractal_result['bullish']]}")
            else:
                print("Williams Fractal with realistic data: Not enough data or error.")
        else:
            print("Williams Fractal test: Not enough realistic price data for window 5.")

        # Test with data that should form a clear fractal
        # Bearish: 10, 11, 15, 12, 11 (fractal at 15)
        # Bullish: 15, 12, 10, 11, 14 (fractal at 10)
        test_high_specific = pd.Series([10, 11, 15, 12, 11, 13, 14, 16, 13, 12]) # Bearish at index 2 (15) and 7 (16)
        test_low_specific = pd.Series([15, 12, 10, 11, 14, 9, 12, 10, 13, 15])  # Bullish at index 2 (10) and 5 (9) and 7 (10)

        fractal_specific_result = calculate_williams_fractal(test_high_specific, test_low_specific, window=5)
        if fractal_specific_result:
            print(f"Williams Fractal with specific data (10 points, window 5):")
            bearish_points = test_high_specific[fractal_specific_result['bearish']]
            bullish_points = test_low_specific[fractal_specific_result['bullish']]
            print(f"  Bearish Fractals expected at index 2 (price 15) and 7 (price 16):")
            print(f"  Found Bearish: {bearish_points.to_dict() if not bearish_points.empty else 'None'}")
            print(f"  Last Bearish Price: {fractal_specific_result['last_bearish_price']}")
            print(f"  Bullish Fractals expected at index 2 (price 10), 5 (price 9), 7 (price 10):")
            print(f"  Found Bullish: {bullish_points.to_dict() if not bullish_points.empty else 'None'}")
            print(f"  Last Bullish Price: {fractal_specific_result['last_bullish_price']}")

    else:
        print("Williams Fractal test: 'realistic_prices' data not found for testing.")

    print("\n--- Momentum Test ---")
    if 'realistic_prices' in locals() or 'realistic_prices' in globals():
        realistic_prices_series_mom = pd.Series(realistic_prices, dtype=float)
        momentum_period = 10

        if len(realistic_prices_series_mom) > momentum_period:
            momentum_result = calculate_momentum(realistic_prices_series_mom, period=momentum_period)
            if momentum_result is not None:
                expected_momentum = realistic_prices_series_mom.iloc[-1] - realistic_prices_series_mom.iloc[-1 - momentum_period]
                print(f"Momentum with realistic data (36 points, period {momentum_period}): {momentum_result:.4f}")
                print(f"  Expected by manual diff: {expected_momentum:.4f}")
                assert abs(momentum_result - expected_momentum) < 0.0001, "Momentum calculation mismatch"
            else:
                print(f"Momentum with realistic data: Not enough data or NaN result. Period: {momentum_period}")
        else:
            print(f"Momentum test: Not enough realistic price data for period {momentum_period}.")

        # Test with short data
        short_prices_mom = realistic_prices_series_mom.head(momentum_period) # Exactly `period` items
        momentum_short_result = calculate_momentum(short_prices_mom, period=momentum_period)
        print(f"Momentum with short data ({momentum_period} points, period {momentum_period}): {momentum_short_result}") # Expect None

        shorter_prices_mom = realistic_prices_series_mom.head(momentum_period -1) # Less than `period` items
        momentum_shorter_result = calculate_momentum(shorter_prices_mom, period=momentum_period)
        print(f"Momentum with shorter data ({momentum_period-1} points, period {momentum_period}): {momentum_shorter_result}") # Expect None

        enough_prices_mom = realistic_prices_series_mom.head(momentum_period + 1) # `period` + 1 items
        momentum_enough_result = calculate_momentum(enough_prices_mom, period=momentum_period)
        if momentum_enough_result is not None:
             expected_enough_momentum = enough_prices_mom.iloc[-1] - enough_prices_mom.iloc[-1 - momentum_period]
             print(f"Momentum with just enough data ({momentum_period+1} points, period {momentum_period}): {momentum_enough_result:.4f}")
             assert abs(momentum_enough_result - expected_enough_momentum) < 0.0001, "Momentum (enough) calculation mismatch"
        else:
            print(f"Momentum with just enough data ({momentum_period+1} points, period {momentum_period}): None (unexpected)")

    else:
        print("Momentum test: 'realistic_prices' data not found for testing.")

    print("\nNote: EMA and MACD calculations need a sufficient history of prices.")
    print("The first few values might differ from charting platforms until the EMAs stabilize.")
