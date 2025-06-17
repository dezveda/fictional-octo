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
        """
        Initializes the Golden Strategy module.
        on_status_update: Callback function to send status messages to GUI or logger.
        """
        self.on_status_update = on_status_update
        self.on_indicators_update = on_indicators_update # For GUI indicator updates
        self.on_signal_update = on_signal_update     # For GUI signal updates

        self.price_history_max_len = 100
        self.close_prices = deque(maxlen=self.price_history_max_len)
        self.high_prices = deque(maxlen=self.price_history_max_len)
        self.low_prices = deque(maxlen=self.price_history_max_len)
        self.all_kline_data_deque = deque(maxlen=self.price_history_max_len) # Stores full kline dicts

        if self.on_status_update:
            self.on_status_update("[GoldenStrategy] Initialized.")

    def _update_history(self, kline_data):
        """
        Updates historical data queues with the latest kline data.
        """
        try:
            # Ensure kline_data keys exist and values are convertible
            # Binance kline data comes as strings, convert to float/int as appropriate
            k_time = int(kline_data['t']) # Timestamp
            k_open = float(kline_data['o'])
            k_high = float(kline_data['h'])
            k_low = float(kline_data['l'])
            k_close = float(kline_data['c'])
            k_volume = float(kline_data['v'])

            processed_kline = {
                't': k_time, 'o': k_open, 'h': k_high,
                'l': k_low, 'c': k_close, 'v': k_volume
            }

            self.close_prices.append(k_close)
            self.high_prices.append(k_high)
            self.low_prices.append(k_low)
            self.all_kline_data_deque.append(processed_kline) # Store processed kline dict

        except KeyError as e:
            logger.error(f"[GoldenStrategy] Kline data missing key: {e}. Data: {kline_data}")
        except ValueError as e:
            logger.error(f"[GoldenStrategy] Error converting kline data to numeric: {e}. Data: {kline_data}")


    def process_new_kline(self, kline_data):
        """
        Main processing function for each new kline.
        """
        self._update_history(kline_data)

        min_data_points_for_strategy = 40 # Increased for more reliable initial indicator values
        if len(self.close_prices) < min_data_points_for_strategy:
            if self.on_status_update:
                self.on_status_update(f"[GoldenStrategy] Collecting more data... ({len(self.close_prices)}/{min_data_points_for_strategy})")
            return None

        # Convert deques to pandas Series for indicator calculations
        close_series = pd.Series(list(self.close_prices))
        high_series = pd.Series(list(self.high_prices))
        low_series = pd.Series(list(self.low_prices))

        # Prepare DataFrame for analyses that prefer it (like daily pivots)
        # Ensure 't', 'h', 'l', 'c' are correct for these analysis functions
        historical_df_for_analysis = pd.DataFrame(list(self.all_kline_data_deque))


        # 1. Calculate all required indicators
        macd_data = calculator.calculate_macd(close_series, short_period=settings.MACD_SHORT_PERIOD, long_period=settings.MACD_LONG_PERIOD, signal_period=settings.MACD_SIGNAL_PERIOD)
        rsi_data = calculator.calculate_rsi(close_series, period=settings.RSI_PERIOD)
        supertrend_data = calculator.calculate_supertrend(high_series, low_series, close_series, atr_period=settings.SUPERTREND_ATR_PERIOD, atr_multiplier=settings.SUPERTREND_MULTIPLIER)
        kdj_data = calculator.calculate_kdj(high_series, low_series, close_series, n_period=settings.KDJ_N_PERIOD, m1_period=settings.KDJ_M1_PERIOD, m2_period=settings.KDJ_M2_PERIOD)
        sar_data = calculator.calculate_sar(high_series, low_series, initial_af=settings.SAR_INITIAL_AF, max_af=settings.SAR_MAX_AF, af_increment=settings.SAR_AF_INCREMENT)
        fractal_data = calculator.calculate_williams_fractal(high_series, low_series, window=settings.FRACTAL_WINDOW)
        momentum_data = calculator.calculate_momentum(close_series, period=settings.MOMENTUM_PERIOD)
        atr_series = calculator.calculate_atr(high_series, low_series, close_series, period=settings.ATR_PERIOD)
        latest_atr = atr_series.iloc[-1] if atr_series is not None and not atr_series.empty and not pd.isna(atr_series.iloc[-1]) else None

        # Log basic indicator values if needed (be careful with verbosity)
        # if self.on_status_update:
        #     self.on_status_update(f"[GoldenStrategy] Indicators: RSI={rsi_data}, ST_Dir={'Up' if supertrend_data and supertrend_data['last_direction']==1 else ('Down' if supertrend_data else 'N/A')}")
        # Update GUI with key indicators
        if self.on_indicators_update:
            indicator_gui_data = {
                'RSI': rsi_data if rsi_data is not None else 'N/A',
                'ST_DIR': 'N/A',
                'ST_VAL': 'N/A',
                'MACD_H': (macd_data['histogram'] if macd_data and macd_data.get('histogram') is not None else 'N/A'),
                'KDJ_J': (kdj_data['J'] if kdj_data and kdj_data.get('J') is not None else 'N/A'),
                'SAR_VAL': (sar_data['last_sar'] if sar_data and sar_data.get('last_sar') is not None else 'N/A'),
                'SAR_DIR': ('Long' if sar_data and sar_data.get('last_direction') == 1 else ('Short' if sar_data and sar_data.get('last_direction') == -1 else 'N/A'))
                # 'Momentum': momentum_data if momentum_data is not None else 'N/A',
                # 'Fractal_Bear': fractals.get('last_bearish_price') if fractals else 'N/A',
                # 'Fractal_Bull': fractals.get('last_bullish_price') if fractals else 'N/A',
            }
            if supertrend_data and supertrend_data.get('last_direction') is not None:
                indicator_gui_data['ST_DIR'] = 'Up' if supertrend_data['last_direction'] == 1 else 'Down'
                indicator_gui_data['ST_VAL'] = supertrend_data.get('last_trend', 'N/A')
            self.on_indicators_update(indicator_gui_data)

        # 2. Perform specialized analysis
        # Pass the deque of kline dicts or the DataFrame as needed by analysis functions
        fib_analysis_result = fibonacci_analysis.analyze(self.all_kline_data_deque, self.on_status_update)
        pivot_points_result = pivot_points.analyze_pivot_points(historical_df_for_analysis, self.on_status_update)
        liquidity_info = liquidity_analysis.analyze(self.all_kline_data_deque, self.on_status_update)

        # 3. Combine indicators and analysis for signal generation
        signal = self._generate_signal(
            current_kline=self.all_kline_data_deque[-1], # Pass the latest kline for entry price context
            indicators={
                'macd': macd_data, 'rsi': rsi_data, 'supertrend': supertrend_data,
                'kdj': kdj_data, 'sar': sar_data, 'fractal': fractal_data, 'momentum': momentum_data,
                'atr': latest_atr
            },
            analysis={
                'fibonacci': fib_analysis_result,
                'pivots': pivot_points_result,
                'liquidity': liquidity_info
            }
        )

        if signal:
            if self.on_signal_update:
                tp_info = f", TP: {signal.get('tp'):.2f}" if signal.get('tp') is not None else ""
                sl_info = f", SL: {signal.get('sl'):.2f}" if signal.get('sl') is not None else ""
                self.on_signal_update(f"{signal['type']} @ {signal['price']:.2f}{tp_info}{sl_info}")
            # The existing on_status_update for signal can remain or be removed if redundant
            if self.on_status_update: # Optional: keep general status log for signal
                tp_info = f", TP: {signal.get('tp'):.2f}" if signal.get('tp') is not None else ""
                sl_info = f", SL: {signal.get('sl'):.2f}" if signal.get('sl') is not None else ""
                self.on_status_update(f"[GoldenStrategy] Signal: {signal['type']} at {signal['price']:.2f}{tp_info}{sl_info}")
            logger.info(f"Generated Signal: {signal}")
            return signal

        return None

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

    def mock_status_update(message):
        # Limit printing for cleaner test output during normal runs
        if "Collecting more data" not in message or "Generating signal" not in message:
             print(f"STATUS_UPDATE: {message}")

    strategy = GoldenStrategy(on_status_update=mock_status_update)

    # Simulate receiving kline data points
    base_price = 20000
    klines_to_test = []
    # Generate enough data for indicators (e.g., 50 points)
    # Start with a downtrend then an uptrend to see if signals might change
    for i in range(50):
        price_change = 0
        if i < 25: # Downtrend phase
            price_change = - (i % 5 + 1) * 5
        else: # Uptrend phase
            price_change = (i % 5 + 1) * 7

        # Ensure base_price doesn't go too low
        if base_price + price_change < 5000 : base_price = 5000

        k_time = pd.Timestamp('2023-01-01 00:00:00', tz='UTC').value // 10**6 + i * 1000 * 60 # 1 minute klines
        if i > 30 and i < 35: # Simulate a day change for pivot points
             k_time = pd.Timestamp('2023-01-02 00:00:00', tz='UTC').value // 10**6 + (i-30) * 1000 * 60


        k = {
            't': str(k_time), # Timestamps for pivot points
            'o': str(base_price + price_change - 5),
            'h': str(base_price + price_change + 50),
            'l': str(base_price + price_change - 50),
            'c': str(base_price + price_change),
            'v': str(100 + i*2)
        }
        klines_to_test.append(k)
        base_price += price_change
        if base_price < 1000: base_price = 1000 # Floor price

    print(f"Generated {len(klines_to_test)} klines for testing.")

    final_signal = None
    for idx, kline_data_point in enumerate(klines_to_test):
        # print(f"Processing kline {idx+1}/{len(klines_to_test)}: C={kline_data_point['c']}")
        signal = strategy.process_new_kline(kline_data_point)
        if signal:
            final_signal = signal # Store the last signal generated
            print(f"** Signal at kline {idx+1}: {signal} ** (Price: {kline_data_point['c']})")
            # break # Optional: stop on first signal for cleaner test output

    if final_signal:
        print(f"\nLast Generated Test Signal: {final_signal}")
    else:
        print("\nNo signal generated with the first pass heuristic logic and test data.")
        # This might be expected if scores don't meet threshold or data isn't conducive.
        # Check last few indicator values if possible from logs if on_status_update was more verbose.
        if len(strategy.all_kline_data_deque) >= strategy.price_history_max_len: # Check if maxlen was reached, not min_data_points
             print("Debug info: Strategy history deque is full.")
             # Could print last indicator values here if captured.

    print("\nGoldenStrategy integration test finished.")
