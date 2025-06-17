import pandas as pd
from collections import deque

# Assuming calculator.py is in trading_bot.indicators
from trading_bot.indicators import calculator

# Import analysis modules
from . import fibonacci_analysis
from . import pivot_points
from . import liquidity_analysis
from trading_bot.utils import settings

import logging

logger = logging.getLogger(__name__)

class GoldenStrategy:
    def __init__(self, on_status_update=None, on_indicators_update=None, on_signal_update=None):
        self.on_status_update = on_status_update
        self.on_indicators_update = on_indicators_update
        self.on_signal_update = on_signal_update

        # Max length for raw 1s klines (e.g., for current price display, or very short-term patterns if ever needed)
        self.raw_kline_max_len = 200 # e.g., around 3 minutes of 1s data
        self.raw_all_kline_data_deque = deque(maxlen=self.raw_kline_max_len)

        # Determine strategy timeframe properties
        self.strategy_timeframe_str = settings.STRATEGY_TIMEFRAME
        # Ensure 'min' is used for 'T' if that's what pandas Timedelta expects for minute.
        # Pandas Timedelta is quite flexible: '1T' or '1min' for minute, '1H' for hour.
        self.timeframe_delta = pd.Timedelta(self.strategy_timeframe_str.replace('T', 'min'))

        # Max length for aggregated klines (e.g., 100 bars of 1H data = 100 hours)
        # This should be based on indicator needs on aggregated data.
        # Max of MACD long period (26) + signal (9) = 35. Add buffer for other indicators like ATR (14), etc.
        # A general rule might be longest_indicator_period + some_lookback_for_stability + buffer
        # For example, if MACD (35 bars) and ATR (14 bars) are used, 35 + 14 + buffer (e.g., 10-20) = ~60-70
        # Using ATR_PERIOD (14) + 50 = 64. This should be settings based or calculated.
        # Let's make it more robust, e.g. max(MACD_LONG_PERIOD+MACD_SIGNAL_PERIOD, ATR_PERIOD) + buffer
        buffer_for_indicators = 20 # Number of extra bars
        min_bars_needed = max(
            (settings.MACD_LONG_PERIOD + settings.MACD_SIGNAL_PERIOD),
            settings.RSI_PERIOD,
            settings.SUPERTREND_ATR_PERIOD, # Supertrend needs ATR
            settings.KDJ_N_PERIOD, # KDJ main period
            settings.ATR_PERIOD # General ATR
            # SAR, Fractal, Momentum often need fewer bars than MACD or long ATRs
        )
        self.agg_kline_max_len = min_bars_needed + buffer_for_indicators


        self.agg_open_prices = deque(maxlen=self.agg_kline_max_len)
        self.agg_high_prices = deque(maxlen=self.agg_kline_max_len)
        self.agg_low_prices = deque(maxlen=self.agg_kline_max_len)
        self.agg_close_prices = deque(maxlen=self.agg_kline_max_len)
        self.agg_volumes = deque(maxlen=self.agg_kline_max_len)
        self.agg_timestamps = deque(maxlen=self.agg_kline_max_len) # Start timestamp of the aggregated bar
        self.agg_kline_data_deque = deque(maxlen=self.agg_kline_max_len) # Store full aggregated klines

        self.current_agg_kline_buffer = [] # Buffer for 1s klines for current aggregating bar
        self.last_agg_bar_start_time = None
        self.is_historical_fill_active = False # Flag to control GUI updates during fill


        if self.on_status_update:
            self.on_status_update(f"[GoldenStrategy] Initialized for timeframe: {self.strategy_timeframe_str}. Agg history len: {self.agg_kline_max_len} (needs {min_bars_needed} for indicators).")

    def _process_incoming_kline(self, kline_data):
        """
        Handles an incoming 1-second kline: stores it raw and adds to aggregation buffer.
        Triggers aggregation if a new timeframe bar is completed.
        """
        try:
            k_time_ms = int(kline_data['t'])
            k_time_dt = pd.to_datetime(k_time_ms, unit='ms', utc=True)
            k_open = float(kline_data['o'])
            k_high = float(kline_data['h'])
            k_low = float(kline_data['l'])
            k_close = float(kline_data['c'])
            k_volume = float(kline_data['v'])

            processed_kline = {
                't_ms': k_time_ms, # Keep original ms timestamp
                't_dt': k_time_dt, # Store datetime object
                'o': k_open, 'h': k_high,
                'l': k_low, 'c': k_close, 'v': k_volume
            }
            self.raw_all_kline_data_deque.append(processed_kline)
        except (KeyError, ValueError) as e:
            logger.error(f"[GoldenStrategy] Invalid kline data for raw storage: {e}. Data: {kline_data}")
            return

        self.current_agg_kline_buffer.append(processed_kline)

        if not self.current_agg_kline_buffer:
            return

        current_kline_agg_period_start_time = processed_kline['t_dt'].floor(self.timeframe_delta)

        if self.last_agg_bar_start_time is None:
            self.last_agg_bar_start_time = current_kline_agg_period_start_time
            if self.on_status_update:
                 self.on_status_update(f"[GoldenStrategy] First kline received. Aggregation period started at {self.last_agg_bar_start_time.strftime('%Y-%m-%d %H:%M:%S')} for timeframe {self.strategy_timeframe_str}.")

        if current_kline_agg_period_start_time > self.last_agg_bar_start_time:
            klines_for_completed_bar = [
                k for k in self.current_agg_kline_buffer
                if k['t_dt'] >= self.last_agg_bar_start_time and k['t_dt'] < current_kline_agg_period_start_time
            ]

            if klines_for_completed_bar:
                self._finalize_and_process_aggregated_bar(klines_for_completed_bar, self.last_agg_bar_start_time)

                self.current_agg_kline_buffer = [
                    k for k in self.current_agg_kline_buffer if k['t_dt'] >= current_kline_agg_period_start_time
                ]
            else:
                if self.on_status_update: # Log if a bar was expected but no klines were in its period
                    self.on_status_update(f"[GoldenStrategy] Potential data gap or timing issue: No klines found for completed bar period {self.last_agg_bar_start_time.strftime('%Y-%m-%d %H:%M:%S')}.")

            self.last_agg_bar_start_time = current_kline_agg_period_start_time

    def _finalize_and_process_aggregated_bar(self, bar_klines, bar_start_time_dt):
        """Aggregates klines for a completed bar and triggers strategy logic."""
        if not bar_klines:
            return

        agg_open = bar_klines[0]['o']
        agg_high = max(k['h'] for k in bar_klines)
        agg_low = min(k['l'] for k in bar_klines)
        agg_close = bar_klines[-1]['c']
        agg_volume = sum(k['v'] for k in bar_klines)

        self.agg_open_prices.append(agg_open)
        self.agg_high_prices.append(agg_high)
        self.agg_low_prices.append(agg_low)
        self.agg_close_prices.append(agg_close)
        self.agg_volumes.append(agg_volume)
        self.agg_timestamps.append(bar_start_time_dt)

        aggregated_kline_data = {
            't': int(bar_start_time_dt.timestamp() * 1000), # Millisecond timestamp for DataFrame consistency
            'ts_datetime': bar_start_time_dt,
            'o': agg_open, 'h': agg_high, 'l': agg_low, 'c': agg_close, 'v': agg_volume
        }
        self.agg_kline_data_deque.append(aggregated_kline_data)

        if self.on_status_update:
            self.on_status_update(f"[GoldenStrategy] New {self.strategy_timeframe_str} bar: O:{agg_open:.2f} H:{agg_high:.2f} L:{agg_low:.2f} C:{agg_close:.2f} V:{agg_volume:.2f} @ {bar_start_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        self._run_strategy_on_aggregated_data()


    def _run_strategy_on_aggregated_data(self):
        """
        Calculates indicators and generates signals based on the aggregated data.
        """
        min_agg_bars_for_strategy = max(
            (settings.MACD_LONG_PERIOD + settings.MACD_SIGNAL_PERIOD),
            settings.RSI_PERIOD,
            settings.SUPERTREND_ATR_PERIOD,
            settings.KDJ_N_PERIOD,
            settings.ATR_PERIOD
        ) + 5 # Use a small buffer over the absolute minimum needed by any indicator

        if len(self.agg_close_prices) < min_agg_bars_for_strategy:
            if self.on_status_update:
                self.on_status_update(f"[GoldenStrategy] Collecting more AGGREGATED bars... ({len(self.agg_close_prices)}/{min_agg_bars_for_strategy}) for {self.strategy_timeframe_str} timeframe")
            return

        close_series = pd.Series(list(self.agg_close_prices))
        high_series = pd.Series(list(self.agg_high_prices))
        low_series = pd.Series(list(self.agg_low_prices))

        historical_agg_df_for_analysis = pd.DataFrame(list(self.agg_kline_data_deque))

        macd_data = calculator.calculate_macd(close_series, short_period=settings.MACD_SHORT_PERIOD, long_period=settings.MACD_LONG_PERIOD, signal_period=settings.MACD_SIGNAL_PERIOD)
        rsi_data = calculator.calculate_rsi(close_series, period=settings.RSI_PERIOD)
        supertrend_data = calculator.calculate_supertrend(high_series, low_series, close_series, atr_period=settings.ATR_PERIOD, atr_multiplier=settings.SUPERTREND_MULTIPLIER)
        kdj_data = calculator.calculate_kdj(high_series, low_series, close_series, n_period=settings.KDJ_N_PERIOD, m1_period=settings.KDJ_M1_PERIOD, m2_period=settings.KDJ_M2_PERIOD)
        sar_data = calculator.calculate_sar(high_series, low_series, initial_af=settings.SAR_INITIAL_AF, max_af=settings.SAR_MAX_AF, af_increment=settings.SAR_AF_INCREMENT)
        fractal_data = calculator.calculate_williams_fractal(high_series, low_series, window=settings.FRACTAL_WINDOW)
        momentum_data = calculator.calculate_momentum(close_series, period=settings.MOMENTUM_PERIOD)
        atr_series = calculator.calculate_atr(high_series, low_series, close_series, period=settings.ATR_PERIOD)
        latest_atr_val = atr_series.iloc[-1] if atr_series is not None and not atr_series.empty and not pd.isna(atr_series.iloc[-1]) else None

        if self.on_indicators_update and not self.is_historical_fill_active:
            indicator_gui_data = {
                'timeframe': self.strategy_timeframe_str,
                'RSI': rsi_data if rsi_data is not None else 'N/A',
                'ST_DIR': 'N/A', 'ST_VAL': 'N/A',
                'MACD_H': (macd_data['histogram'] if macd_data and macd_data.get('histogram') is not None else 'N/A'),
                'KDJ_J': (kdj_data['J'] if kdj_data and kdj_data.get('J') is not None else 'N/A'),
                'SAR_VAL': (sar_data['last_sar'] if sar_data and sar_data.get('last_sar') is not None else 'N/A'),
                'SAR_DIR': ('Long' if sar_data and sar_data.get('last_direction') == 1 else ('Short' if sar_data and sar_data.get('last_direction') == -1 else 'N/A')),
                'ATR': latest_atr_val if latest_atr_val is not None else 'N/A'
            }
            if supertrend_data and supertrend_data.get('last_direction') is not None:
                indicator_gui_data['ST_DIR'] = 'Up' if supertrend_data['last_direction'] == 1 else 'Down'
                indicator_gui_data['ST_VAL'] = supertrend_data.get('last_trend', 'N/A')
            self.on_indicators_update(indicator_gui_data)

        fib_analysis_result = fibonacci_analysis.analyze(self.agg_kline_data_deque, self.on_status_update)
        pivot_points_result = pivot_points.analyze_pivot_points(historical_agg_df_for_analysis, self.on_status_update)
        if not pivot_points_result or not pivot_points_result.get('daily_pivots'):
            if self.on_status_update:
                status_msg = pivot_points_result.get('status', 'Pivot calculation failed or returned no data.') if pivot_points_result else 'Pivot analysis returned None.'
                self.on_status_update(f"[GoldenStrategy] ({self.strategy_timeframe_str}) Daily pivots not available for this bar. Reason: {status_msg}")
        liquidity_info = liquidity_analysis.analyze(self.agg_kline_data_deque, self.on_status_update)

        signal = self._generate_signal(
            current_kline=self.agg_kline_data_deque[-1],
            indicators={
                'macd': macd_data, 'rsi': rsi_data, 'supertrend': supertrend_data,
                'kdj': kdj_data, 'sar': sar_data, 'fractal': fractal_data,
                'momentum': momentum_data, 'atr': latest_atr_val
            },
            analysis={
                'fibonacci': fib_analysis_result,
                'pivots': pivot_points_result,
                'liquidity': liquidity_info
            }
        )

        if signal:
            if self.on_signal_update and not self.is_historical_fill_active:
                tp_info = f", TP: {signal.get('tp'):.2f}" if signal.get('tp') is not None else ""
                sl_info = f", SL: {signal.get('sl'):.2f}" if signal.get('sl') is not None else ""
                self.on_signal_update(f"({self.strategy_timeframe_str}) {signal['type']} @ {signal['price']:.2f}{tp_info}{sl_info}")
            # Log signal regardless of historical fill, but GUI update is conditional
            logger.info(f"({self.strategy_timeframe_str}) Generated Signal: {signal} (HistoricalFillActive: {self.is_historical_fill_active})")
        else:
            if self.on_status_update and not self.is_historical_fill_active: # Only log "no signal" for live bars
                 self.on_status_update(f"[GoldenStrategy] ({self.strategy_timeframe_str}) No signal generated on this bar.")

    def process_new_kline(self, kline_data):
        self._process_incoming_kline(kline_data)

    def _generate_signal(self, current_kline, indicators, analysis):
        """
        Develops the "Golden Strategy" heuristic logic.
        Combines indicator signals and specialized analysis to generate trading signals.
        Returns a dictionary like {'type': 'LONG'/'SHORT', 'price': entry_price, 'tp': take_profit_price} or None.
        """
        # Extracting latest values for convenience
        macd = indicators.get('macd')
        rsi = indicators.get('rsi') # This is a single float value
        supertrend = indicators.get('supertrend') # Dict with 'last_trend', 'last_direction'
        kdj = indicators.get('kdj') # Dict with 'K', 'D', 'J'
        sar = indicators.get('sar') # Dict with 'last_sar', 'last_direction'
        fractals = indicators.get('fractal') # Dict with 'last_bullish_price', 'last_bearish_price'
        # momentum = indicators.get('momentum') # Single float value
        atr_value = indicators.get('atr')

        pivots = analysis.get('pivots', {}).get('daily_pivots') # e.g. {'P': val, 'S1': val, ...}
        # fib_levels = analysis.get('fibonacci', {}).get('retracement_levels_from_B')
        liquidity_zones = analysis.get('liquidity', {}).get('volume_profile_data', {}).get('high_volume_zones', []) # List of {'price_level': val, 'volume': val}

        current_price = float(current_kline['c'])
        current_high = float(current_kline['h'])
        current_low = float(current_kline['l'])

        # --- Initial Heuristic Logic for "Golden Strategy" (First Pass) ---
        # This is a simplified example and needs significant expansion and tuning.
        # The goal is to combine multiple criteria.

        long_score = 0
        short_score = 0

        # 1. Supertrend Direction
        if supertrend and supertrend['last_direction'] == 1:
            long_score += 2
        elif supertrend and supertrend['last_direction'] == -1:
            short_score += 2

        # 2. RSI
        if rsi is not None:
            if rsi > 50 and rsi < settings.STRATEGY_RSI_OVERBOUGHT: # Bullish momentum, not overbought
                long_score += 1
            elif rsi < 50 and rsi > settings.STRATEGY_RSI_OVERSOLD: # Bearish momentum, not oversold
                short_score += 1
            if rsi >= settings.STRATEGY_RSI_OVERBOUGHT: # Overbought - potential reversal or strong trend
                short_score += 0.5 # Slight negative for long, potential top
            if rsi <= settings.STRATEGY_RSI_OVERSOLD: # Oversold - potential reversal or strong trend
                long_score += 0.5  # Slight negative for short, potential bottom

        # 3. MACD
        if macd and macd['macd'] is not None and macd['signal'] is not None:
            if macd['macd'] > macd['signal'] and macd['histogram'] > 0: # Bullish cross or divergence
                long_score += 1
            elif macd['macd'] < macd['signal'] and macd['histogram'] < 0: # Bearish cross or divergence
                short_score += 1

        # 4. KDJ (J value for overbought/oversold or trend strength)
        if kdj and kdj['J'] is not None:
            if kdj['J'] < 20 and kdj['K'] > kdj['D']: # Oversold, potential bullish cross forming
                long_score += 0.5
            if kdj['J'] > 80 and kdj['K'] < kdj['D']: # Overbought, potential bearish cross forming
                short_score += 0.5

        # 5. Parabolic SAR
        if sar and sar['last_sar'] is not None:
            if sar['last_direction'] == 1: # SAR is bullish (below price)
                long_score += 1
            elif sar['last_direction'] == -1: # SAR is bearish (above price)
                short_score += 1

        # 6. Pivot Point Proximity (Example: current price near a support for long, resistance for short)
        if pivots:
            if abs(current_price - pivots.get('S1', current_price)) / current_price < 0.005: # Near S1 (0.5%)
                long_score += 1
            if abs(current_price - pivots.get('R1', current_price)) / current_price < 0.005: # Near R1 (0.5%)
                short_score += 1

        # 7. Liquidity Zones (Example: price bouncing off a high volume zone)
        if liquidity_zones:
            for zone in liquidity_zones[:1]: # Check top 1 liquidity zone
                if current_low <= zone['price_level'] and current_price > zone['price_level'] and \
                   abs(current_price - zone['price_level']) / current_price < 0.01: # Bounced off support
                    long_score += 1
                if current_high >= zone['price_level'] and current_price < zone['price_level'] and \
                   abs(current_price - zone['price_level']) / current_price < 0.01: # Rejected from resistance
                    short_score += 1


        # Decision Threshold (needs tuning)
        entry_threshold = settings.STRATEGY_ENTRY_THRESHOLD
        signal_type = None
        entry_price = current_price
        take_profit = None
        stop_loss = None
        atr_tp_multiplier = settings.ATR_TP_MULTIPLIER
        atr_sl_multiplier = settings.ATR_SL_MULTIPLIER

        if long_score >= entry_threshold and long_score > short_score:
            signal_type = "LONG"
            entry_price = current_price
            if atr_value is not None and atr_value > 0:
                take_profit = entry_price + (atr_tp_multiplier * atr_value)
                stop_loss = entry_price - (atr_sl_multiplier * atr_value)
            elif pivots and pivots.get('R1'): # Fallback to Pivot R1 if ATR fails
                 take_profit = pivots.get('R1')
                 stop_loss = entry_price * (1 - settings.MIN_SL_FALLBACK_PERCENTAGE)
            else: # Further fallback
                 take_profit = entry_price * (1 + settings.MIN_TP_FALLBACK_PERCENTAGE)
                 stop_loss = entry_price * (1 - settings.MIN_SL_FALLBACK_PERCENTAGE)

        elif short_score >= entry_threshold and short_score > long_score:
            signal_type = "SHORT"
            entry_price = current_price
            if atr_value is not None and atr_value > 0:
                take_profit = entry_price - (atr_tp_multiplier * atr_value)
                stop_loss = entry_price + (atr_sl_multiplier * atr_value)
            elif pivots and pivots.get('S1'): # Fallback to Pivot S1
                 take_profit = pivots.get('S1')
                 stop_loss = entry_price * (1 + settings.MIN_SL_FALLBACK_PERCENTAGE)
            else: # Further fallback
                 take_profit = entry_price * (1 - settings.MIN_TP_FALLBACK_PERCENTAGE)
                 stop_loss = entry_price * (1 + settings.MIN_SL_FALLBACK_PERCENTAGE)

        if signal_type:
            # Ensure TP/SL are reasonably away from entry price and logical
            if signal_type == "LONG":
                if take_profit is not None and take_profit <= entry_price:
                    take_profit = entry_price * (1 + settings.MIN_TP_DISTANCE_PERCENTAGE)
                if stop_loss is not None and stop_loss >= entry_price:
                    stop_loss = entry_price * (1 - settings.MIN_SL_DISTANCE_PERCENTAGE)
            elif signal_type == "SHORT":
                if take_profit is not None and take_profit >= entry_price:
                    take_profit = entry_price * (1 - settings.MIN_TP_DISTANCE_PERCENTAGE)
                if stop_loss is not None and stop_loss <= entry_price:
                    stop_loss = entry_price * (1 + settings.MIN_SL_DISTANCE_PERCENTAGE)

            return {'type': signal_type, 'price': entry_price, 'tp': take_profit, 'sl': stop_loss, 'long_score': long_score, 'short_score': short_score}

        return None


if __name__ == '__main__':
    print("--- Testing GoldenStrategy Integration ---")

    # def mock_status_update(message):
    #     # Limit printing for cleaner test output during normal runs
    #     if "Collecting more data" not in message or "Generating signal" not in message:
    #          print(f"STATUS_UPDATE: {message}")
    # For this test, let's see more status updates for aggregation
    def mock_status_update(message):
        print(f"STATUS_UPDATE: {message}")


    strategy = GoldenStrategy(on_status_update=mock_status_update,
                              on_indicators_update=lambda ind_data: print(f"INDICATORS_UPDATE: {ind_data}"),
                              on_signal_update=lambda sig_data: print(f"SIGNAL_UPDATE: {sig_data}"))

    # Simulate receiving kline data points (1-second klines)
    # Test with STRATEGY_TIMEFRAME = "1T" (1 minute) for faster testing of aggregation
    original_timeframe = settings.STRATEGY_TIMEFRAME
    settings.STRATEGY_TIMEFRAME = "1T" # Override for this test
    print(f"TEST: Overriding STRATEGY_TIMEFRAME to {settings.STRATEGY_TIMEFRAME} for this test run.")
    strategy = GoldenStrategy(on_status_update=mock_status_update,
                              on_indicators_update=lambda ind_data: print(f"INDICATORS_UPDATE: {ind_data}"),
                              on_signal_update=lambda sig_data: print(f"SIGNAL_UPDATE: {sig_data}"))


    # Generate 3 minutes of 1-second data
    # Max length for aggregated klines (e.g., 100 bars of 1H data = 100 hours)
    # self.agg_kline_max_len = settings.ATR_PERIOD + 50
    # min_agg_bars_for_strategy = settings.ATR_PERIOD + 20
    # Need enough data for min_agg_bars_for_strategy (14+20=34 bars of 1T) -> 34 minutes
    # So we need at least 34 * 60 = 2040 seconds of data. Let's do 2100 (35 mins).

    num_seconds_to_simulate = (settings.ATR_PERIOD + 25) * 60 # (14+25)*60 = 39 * 60 = 2340 seconds

    base_price = 20000
    klines_to_test = []
    start_time_ms = int(pd.Timestamp('2023-01-01 00:00:00', tz='UTC').value / 10**6)

    for i in range(num_seconds_to_simulate):
        price_change = (i % 10 - 4.5) * 0.1 # Small price fluctuations per second

        current_time_ms = start_time_ms + i * 1000

        # Simulate a daily pattern for pivot testing (highs/lows change over a day)
        # This is very rough, pivots are calculated on previous day's data.
        # The main goal here is to test aggregation.
        day_cycle = (i // (60*60*4)) % 2 # Change general price trend every 4 hours for variety
        if day_cycle == 0:
            base_price_offset = (i % (60*10) - 300) * 0.1 # small up/down wave over 10 mins
        else:
            base_price_offset = -(i % (60*10) - 300) * 0.1


        k_open = base_price + base_price_offset + price_change
        k_high = k_open + abs(price_change) + 5
        k_low = k_open - abs(price_change) - 5
        k_close = k_open + price_change / 2
        k_volume = 1 + (i % 10) # Simple volume pattern

        k = {
            't': str(current_time_ms),
            'o': f"{k_open:.2f}",
            'h': f"{k_high:.2f}",
            'l': f"{k_low:.2f}",
            'c': f"{k_close:.2f}",
            'v': f"{k_volume:.2f}"
        }
        klines_to_test.append(k)

    print(f"Generated {len(klines_to_test)} 1-second klines for testing ({num_seconds_to_simulate/60:.1f} minutes).")

    final_signal = None
    for idx, kline_data_point in enumerate(klines_to_test):
        strategy.process_new_kline(kline_data_point)
        # Signals are now generated inside _run_strategy_on_aggregated_data
        # which is called by _finalize_and_process_aggregated_bar
        # We can't easily get the signal here directly unless we add a return to process_new_kline
        # For testing, rely on the on_signal_update callback printing.

    print("\nGoldenStrategy aggregation test finished.")
    settings.STRATEGY_TIMEFRAME = original_timeframe # Reset for other potential uses/tests
    print(f"TEST: Restored STRATEGY_TIMEFRAME to {settings.STRATEGY_TIMEFRAME}.")
