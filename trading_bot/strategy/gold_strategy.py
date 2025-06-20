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
    def __init__(self, on_status_update=None, on_indicators_update=None, on_signal_update=None, on_chart_update=None, on_liquidity_update_callback=None):
        self.on_status_update = on_status_update
        self.on_indicators_update = on_indicators_update
        self.on_signal_update = on_signal_update
        self.on_chart_update = on_chart_update
        self.on_liquidity_update_callback = on_liquidity_update_callback
        self.latest_order_book_snapshot = None
        self.latest_liquidity_analysis = None

        self.raw_kline_max_len = 200
        self.raw_all_kline_data_deque = deque(maxlen=self.raw_kline_max_len)

        self.strategy_timeframe_str = settings.STRATEGY_TIMEFRAME
        td_str = self.strategy_timeframe_str.lower()
        if 't' in td_str and not 'min' in td_str:
            td_str = td_str.replace('t', 'min')
        self.timeframe_delta = pd.Timedelta(td_str)

        buffer_for_indicators = 20
        min_bars_needed = max(
            (settings.MACD_LONG_PERIOD + settings.MACD_SIGNAL_PERIOD),
            settings.RSI_PERIOD,
            settings.SUPERTREND_ATR_PERIOD,
            settings.KDJ_N_PERIOD,
            settings.ATR_PERIOD
        )
        self.agg_kline_max_len = min_bars_needed + buffer_for_indicators

        self.agg_open_prices = deque(maxlen=self.agg_kline_max_len)
        self.agg_high_prices = deque(maxlen=self.agg_kline_max_len)
        self.agg_low_prices = deque(maxlen=self.agg_kline_max_len)
        self.agg_close_prices = deque(maxlen=self.agg_kline_max_len)
        self.agg_volumes = deque(maxlen=self.agg_kline_max_len)
        self.agg_timestamps = deque(maxlen=self.agg_kline_max_len)
        self.agg_kline_data_deque = deque(maxlen=self.agg_kline_max_len)

        self.current_agg_kline_buffer = []
        self.last_agg_bar_start_time = None
        self.is_historical_fill_active = False

        if self.on_status_update:
            self.on_status_update(f"[GoldenStrategy] Initialized for timeframe: {self.strategy_timeframe_str}. Agg history len: {self.agg_kline_max_len} (needs {min_bars_needed} for indicators).")

    def _process_incoming_kline(self, kline_data):
        try:
            k_time_ms = int(kline_data['t'])
            k_time_dt = pd.to_datetime(k_time_ms, unit='ms', utc=True)
            k_open = float(kline_data['o'])
            k_high = float(kline_data['h'])
            k_low = float(kline_data['l'])
            k_close = float(kline_data['c'])
            k_volume = float(kline_data['v'])

            processed_kline = {
                't_ms': k_time_ms,
                't_dt': k_time_dt,
                'o': k_open, 'h': k_high,
                'l': k_low, 'c': k_close, 'v': k_volume
            }
            self.raw_all_kline_data_deque.append(processed_kline)
        except (KeyError, ValueError) as e:
            logger.error(f"[GoldenStrategy] Invalid kline data for raw storage: {e}. Data: {kline_data}")
            return

        self.current_agg_kline_buffer.append(processed_kline)

        if not self.is_historical_fill_active:
            self._trigger_provisional_chart_update()

        if not self.current_agg_kline_buffer:
            return

        current_kline_agg_period_start_time = processed_kline['t_dt'].floor(self.timeframe_delta)

        if self.last_agg_bar_start_time is None:
            self.last_agg_bar_start_time = current_kline_agg_period_start_time
            if self.on_status_update:
                 self.on_status_update(f"[GoldenStrategy] First kline received. Aggregation period started at {self.last_agg_bar_start_time.strftime('%Y-%m-%d %H:%M:%S')} for timeframe {self.strategy_timeframe_str}.")
            if not self.is_historical_fill_active:
                self._trigger_provisional_chart_update()

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
                if self.on_status_update:
                    self.on_status_update(f"[GoldenStrategy] Potential data gap or timing issue: No klines found for completed bar period {self.last_agg_bar_start_time.strftime('%Y-%m-%d %H:%M:%S')}.")

            self.last_agg_bar_start_time = current_kline_agg_period_start_time
            if not self.is_historical_fill_active:
                 self._trigger_provisional_chart_update()

    def _finalize_and_process_aggregated_bar(self, bar_klines, bar_start_time_dt):
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
            't': int(bar_start_time_dt.timestamp() * 1000),
            'ts_datetime': bar_start_time_dt,
            'o': agg_open, 'h': agg_high, 'l': agg_low, 'c': agg_close, 'v': agg_volume
        }
        self.agg_kline_data_deque.append(aggregated_kline_data)

        if self.on_status_update:
            self.on_status_update(f"[GoldenStrategy] New {self.strategy_timeframe_str} bar: O:{agg_open:.2f} H:{agg_high:.2f} L:{agg_low:.2f} C:{agg_close:.2f} V:{agg_volume:.2f} @ {bar_start_time_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        self._run_strategy_on_aggregated_data()

    def _run_strategy_on_aggregated_data(self):
        min_agg_bars_for_strategy = max(
            (settings.MACD_LONG_PERIOD + settings.MACD_SIGNAL_PERIOD),
            settings.RSI_PERIOD,
            settings.SUPERTREND_ATR_PERIOD,
            settings.KDJ_N_PERIOD,
            settings.ATR_PERIOD
        ) + 5

        if len(self.agg_close_prices) < min_agg_bars_for_strategy:
            status_msg_waiting = f"[GoldenStrategy] Collecting more AGGREGATED bars... ({len(self.agg_close_prices)}/{min_agg_bars_for_strategy}) for {self.strategy_timeframe_str} timeframe"
            if self.on_status_update:
                self.on_status_update(status_msg_waiting)
            if not self.is_historical_fill_active:
                if self.on_indicators_update:
                    self.on_indicators_update({
                        'timeframe': self.strategy_timeframe_str,
                        'status': f"Waiting for {min_agg_bars_for_strategy - len(self.agg_close_prices)} more '{self.strategy_timeframe_str}' bars..."
                    })
                if self.on_signal_update:
                    self.on_signal_update(f"Waiting for data on {self.strategy_timeframe_str}...")
                if self.on_chart_update: self._trigger_provisional_chart_update()
            return

        # --- Chart update for completed bars (now handled by provisional or final update from main) ---
        # The old block for chart update based *only* on agg_kline_data_deque is removed.
        # Provisional updates handle live, and main.py's call after historical fill handles the one-off update.
        # If a chart update is desired *after* indicators for a completed bar are calculated (live),
        # _trigger_provisional_chart_update can be called here again.
        # For now, the most frequent update is from _process_incoming_kline.

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

        # Use the latest analysis from order book data, if available
        liquidity_info_for_signal = self.latest_liquidity_analysis

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
                'liquidity': liquidity_info_for_signal # Use order book derived liquidity
            }
        )

        # --- Process Signal Output ---
        if not self.is_historical_fill_active: # Only send updates for live data or final historical update
            if signal and self.on_signal_update:
                signal_type = signal.get('type')
                if signal_type in ["LONG", "SHORT"]:
                    tp_val = signal.get('tp')
                    sl_val = signal.get('sl')
                    price_val = signal.get('price')
                    tp_info = f", TP: {tp_val:.2f}" if tp_val is not None else ""
                    sl_info = f", SL: {sl_val:.2f}" if sl_val is not None else ""
                    price_info = f" @ {price_val:.2f}" if price_val is not None else ""
                    self.on_signal_update(f"({self.strategy_timeframe_str}) {signal_type}{price_info}{tp_info}{sl_info}")
                    logger.info(f"({self.strategy_timeframe_str}) Generated Trade Signal: {signal}")
                elif signal_type == 'CONSOLIDATION_INFO':
                    long_p = signal.get('long_perc', 0.0)
                    short_p = signal.get('short_perc', 0.0)
                    debug_states_for_log = signal.get('debug_states', {})
                    self.on_signal_update(f"({self.strategy_timeframe_str}) Consolidation: LONG {long_p:.0f}% | SHORT {short_p:.0f}%")
                    logger.debug(f"[GoldenStrategy] ({self.strategy_timeframe_str}) Consolidation Info: Long {long_p:.0f}%, Short {short_p:.0f}%. States: {debug_states_for_log}")
                else: # Signal is None or unrecognized type
                    self.on_signal_update(f"({self.strategy_timeframe_str}) No specific signal / Awaiting conditions")
            elif self.on_signal_update and not self.is_historical_fill_active: # signal is None
                self.on_signal_update(f"({self.strategy_timeframe_str}) No signal data returned by strategy")

        # Status update if no actual trade signal was generated
        if not (signal and signal.get('type') in ["LONG", "SHORT"]):
            if self.on_status_update and not self.is_historical_fill_active:
                self.on_status_update(f"[GoldenStrategy] ({self.strategy_timeframe_str}) No *trade* signal generated on this bar.")

    def process_order_book_update(self, order_book_snapshot):
        """ Processes new order book data and triggers liquidity analysis. """
        self.latest_order_book_snapshot = order_book_snapshot
        # logger.debug(f"[GoldenStrategy] Order book snapshot received. Top bid: {order_book_snapshot['bids'][0] if order_book_snapshot.get('bids') else 'N/A'}")

        # Call liquidity analysis using the imported module
        # The 'settings' module is globally available in this file.
        self.latest_liquidity_analysis = liquidity_analysis.analyze(
            order_book_snapshot,
            settings,
            self.on_status_update
        )

        if self.on_liquidity_update_callback and not self.is_historical_fill_active: # Assuming OB updates are live only
            self.on_liquidity_update_callback(self.latest_liquidity_analysis)

    def process_new_kline(self, kline_data):
        self._process_incoming_kline(kline_data)

    # --- Method for Live Chart Update ---
    def _trigger_provisional_chart_update(self):
        """
        Prepares and sends data for chart update, including the current forming (provisional) bar.
        This is called frequently (e.g., with each new base kline).
        """
        if not self.on_chart_update: # Only proceed if callback is set
            return

        chart_klines_dicts = list(self.agg_kline_data_deque)

        if self.current_agg_kline_buffer and self.last_agg_bar_start_time is not None:
            try:
                prov_bar = {
                    'ts_datetime': self.last_agg_bar_start_time,
                    'o': self.current_agg_kline_buffer[0]['o'],
                    'h': max(k['h'] for k in self.current_agg_kline_buffer),
                    'l': min(k['l'] for k in self.current_agg_kline_buffer),
                    'c': self.current_agg_kline_buffer[-1]['c'],
                    'v': sum(k['v'] for k in self.current_agg_kline_buffer)
                }
                chart_klines_dicts.append(prov_bar)
            except (IndexError, KeyError, TypeError) as e:
                logger.warning(f"[GoldenStrategy] Could not form provisional bar for chart: {e}. Buffer size: {len(self.current_agg_kline_buffer)}")

        if not chart_klines_dicts:
            self.on_chart_update(pd.DataFrame())
            return

        chart_df_data = []
        for kline_dict in chart_klines_dicts:
            chart_df_data.append({
                'Timestamp': kline_dict.get('ts_datetime'),
                'Open': kline_dict.get('o'),
                'High': kline_dict.get('h'),
                'Low': kline_dict.get('l'),
                'Close': kline_dict.get('c'),
                'Volume': kline_dict.get('v')
            })

        try:
            chart_df = pd.DataFrame(chart_df_data)
            if chart_df.empty or 'Timestamp' not in chart_df.columns or chart_df['Timestamp'].isnull().all():
                self.on_chart_update(pd.DataFrame())
                return
            chart_df.set_index('Timestamp', inplace=True)
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                chart_df[col] = pd.to_numeric(chart_df[col], errors='coerce')
            chart_df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)

            if not chart_df.empty:
                max_chart_bars = getattr(settings, 'CHART_MAX_AGG_BARS_DISPLAY', 100)
                chart_df_to_send = chart_df.iloc[-max_chart_bars:] if len(chart_df) > max_chart_bars else chart_df
                self.on_chart_update(chart_df_to_send)
            else:
                self.on_chart_update(pd.DataFrame())

        except Exception as e_chart_df_prov:
            logger.error(f'[GoldenStrategy] Error preparing DataFrame for provisional chart: {e_chart_df_prov}', exc_info=False)
            if self.on_status_update: self.on_status_update(f'[GoldenStrategy] Error preparing chart data (live): {e_chart_df_prov}')
    # --- End Method for Live Chart Update ---

    # --- Signal Generation Helper Methods ---

    def _get_indicator_state(self, value, neutral_low, neutral_high, strong_threshold=None, weak_threshold=None):
        if value is None: return 'NEUTRAL'
        if strong_threshold:
            if value >= strong_threshold: return 'VERY_STRONG_BULLISH'
            if value <= -strong_threshold: return 'VERY_STRONG_BEARISH'
        if weak_threshold:
            if value > neutral_high and value < weak_threshold : return 'WEAK_BULLISH'
            if value < neutral_low and value > -weak_threshold: return 'WEAK_BEARISH'
        if value > neutral_high: return 'BULLISH'
        if value < neutral_low: return 'BEARISH'
        return 'NEUTRAL'

    def _assess_trend_filters(self, supertrend, sar, current_price):
        st_trend = 'NEUTRAL'
        sar_trend = 'NEUTRAL'

        if supertrend and supertrend.get('last_direction') is not None:
            if supertrend['last_direction'] == 1: st_trend = 'BULLISH'
            elif supertrend['last_direction'] == -1: st_trend = 'BEARISH'

        if sar and sar.get('last_sar') is not None and current_price is not None:
            if current_price > sar['last_sar']: sar_trend = 'BULLISH'
            elif current_price < sar['last_sar']: sar_trend = 'BEARISH'

        if st_trend == 'BULLISH' and sar_trend == 'BULLISH': return 'STRONG_BULLISH_TREND'
        if st_trend == 'BEARISH' and sar_trend == 'BEARISH': return 'STRONG_BEARISH_TREND'
        if st_trend == 'BULLISH': return 'BULLISH_TREND_ST'
        if st_trend == 'BEARISH': return 'BEARISH_TREND_ST'
        if sar_trend == 'BULLISH': return 'BULLISH_TREND_SAR'
        if sar_trend == 'BEARISH': return 'BEARISH_TREND_SAR'
        return 'NEUTRAL_TREND'

    def _assess_macd(self, macd_data):
        if not macd_data or macd_data.get('macd') is None or macd_data.get('signal') is None or macd_data.get('histogram') is None:
            return 'NEUTRAL'
        macd_line, signal_line, histogram = macd_data['macd'], macd_data['signal'], macd_data['histogram']
        hist_strength_threshold = getattr(settings, 'MACD_HIST_STRENGTH_THRESHOLD', 0.0001)

        if macd_line > signal_line and histogram > 0:
            return 'STRONG_BULLISH' if histogram > hist_strength_threshold else 'BULLISH'
        if macd_line < signal_line and histogram < 0:
            return 'STRONG_BEARISH' if histogram < -hist_strength_threshold else 'BEARISH'
        if histogram > 0: return 'WEAK_BULLISH'
        if histogram < 0: return 'WEAK_BEARISH'
        return 'NEUTRAL'

    def _assess_rsi(self, rsi_data):
        if rsi_data is None: return 'NEUTRAL'
        ob = settings.STRATEGY_RSI_OVERBOUGHT
        os = settings.STRATEGY_RSI_OVERSOLD
        bc = getattr(settings, 'RSI_BULLISH_CONFIRM', 55)
        sc = getattr(settings, 'RSI_BEARISH_CONFIRM', 45)
        if rsi_data >= ob: return 'OVERBOUGHT'
        if rsi_data <= os: return 'OVERSOLD'
        if rsi_data >= bc: return 'BULLISH'
        if rsi_data <= sc: return 'BEARISH'
        return 'NEUTRAL'

    def _assess_kdj(self, kdj_data):
        if not kdj_data or kdj_data.get('K') is None or kdj_data.get('D') is None or kdj_data.get('J') is None:
            return 'NEUTRAL'
        k, d, j = kdj_data['K'], kdj_data['D'], kdj_data['J']
        j_overbought = getattr(settings, 'KDJ_J_OVERBOUGHT', 90)
        j_oversold = getattr(settings, 'KDJ_J_OVERSOLD', 10)
        k_confirm_ob = getattr(settings, 'KDJ_K_CONFIRM_OVERBOUGHT', 80)
        k_confirm_os = getattr(settings, 'KDJ_K_CONFIRM_OVERSOLD', 20)

        if j > j_overbought or (j > k_confirm_ob and k > k_confirm_ob): return 'OVERBOUGHT'
        if j < j_oversold or (j < k_confirm_os and k < k_confirm_os): return 'OVERSOLD'
        if k > d and j < j_overbought : return 'BULLISH'
        if k < d and j > j_oversold : return 'BEARISH'
        return 'NEUTRAL'

    def _assess_fractals(self, fractal_data, current_high, current_low):
        if not fractal_data or current_high is None or current_low is None: return 'NEUTRAL'
        last_bearish_f = fractal_data.get('last_bearish_price')
        last_bullish_f = fractal_data.get('last_bullish_price')
        if last_bearish_f and current_high > last_bearish_f: return 'BROKE_BEARISH_FRACTAL_UP'
        if last_bullish_f and current_low < last_bullish_f: return 'BROKE_BULLISH_FRACTAL_DOWN'
        return 'NEUTRAL'

    def _assess_sr_levels(self, current_price, current_low, current_high, pivots, fib_analysis, liquidity_zones):
        method_body_indent = "        " # Assuming 8 spaces for method body based on typical class structure
        if current_price is None: return 'NEUTRAL_SR'
        prox_factor = getattr(settings, 'SR_PROXIMITY_FACTOR', 0.003)

        # 1. Check Pivots
        if pivots and pivots.get('daily_pivots'):
            s1 = pivots['daily_pivots'].get('S1')
            r1 = pivots['daily_pivots'].get('R1')
            if s1 and current_low <= s1 * (1 + prox_factor) and current_price > s1:
                logger.debug(f"[SR_Assess] Bounce detected off Pivot S1: {s1:.2f}")
                return 'BOUNCE_SUPPORT_PIVOT'
            if r1 and current_high >= r1 * (1 - prox_factor) and current_price < r1:
                logger.debug(f"[SR_Assess] Rejection detected at Pivot R1: {r1:.2f}")
                return 'REJECT_RESISTANCE_PIVOT'
            # Stronger conditions for breakout/breakdown (e.g. close beyond pivot)
            if r1 and current_price > r1 * (1 + prox_factor / 2): # Closed clearly above R1
                logger.debug(f"[SR_Assess] Breakout above Pivot R1: {r1:.2f}")
                return 'BREAKOUT_ABOVE_R1_PIVOT'
            if s1 and current_price < s1 * (1 - prox_factor / 2): # Closed clearly below S1
                logger.debug(f"[SR_Assess] Breakdown below Pivot S1: {s1:.2f}")
                return 'BREAKDOWN_BELOW_S1_PIVOT'

        # 2. Check Fibonacci Levels
        # Assuming 'retracement_levels_from_B' is the correct key based on fibonacci_analysis.py
        if fib_analysis and fib_analysis.get('retracement_levels_from_B'):
            levels = fib_analysis['retracement_levels_from_B']
            for fib_val_key in [0.5, 0.618]: # Check common levels
                fib_level_price = levels.get(fib_val_key)
                if fib_level_price:
                    if fib_analysis.get('trend_type') == 'uptrend' and current_low <= fib_level_price * (1 + prox_factor) and current_price > fib_level_price:
                        logger.debug(f"[SR_Assess] Bounce detected off Fib {fib_val_key*100:.1f}% support: {fib_level_price:.2f}")
                        return 'BOUNCE_SUPPORT_FIB'
                    if fib_analysis.get('trend_type') == 'downtrend' and current_high >= fib_level_price * (1 - prox_factor) and current_price < fib_level_price:
                        logger.debug(f"[SR_Assess] Rejection detected at Fib {fib_val_key*100:.1f}% resistance: {fib_level_price:.2f}")
                        return 'REJECT_RESISTANCE_FIB'

        # 3. Check Order Book Liquidity Levels (New Logic)
        # 'liquidity_zones' argument now contains the result from order-book based liquidity_analysis.analyze()
        if liquidity_zones and isinstance(liquidity_zones, dict):
            significant_bids = liquidity_zones.get('significant_bids', [])
            significant_asks = liquidity_zones.get('significant_asks', [])

            # Check top N significant bids (e.g., top 1-2 from liquidity_analysis which sorts by qty)
            for bid_info in significant_bids[:getattr(settings, 'LIQUIDITY_LEVELS_TO_CHECK', 2)] :
                bid_price = bid_info['price']
                if current_low <= bid_price * (1 + prox_factor) and current_price > bid_price:
                    logger.debug(f"[SR_Assess] Bounce detected off OB liquidity (bid): {bid_price:.2f} (Qty: {bid_info['qty']})")
                    return 'BOUNCE_SUPPORT_LIQ'

            # Check top N significant asks
            for ask_info in significant_asks[:getattr(settings, 'LIQUIDITY_LEVELS_TO_CHECK', 2)]:
                ask_price = ask_info['price']
                if current_high >= ask_price * (1 - prox_factor) and current_price < ask_price:
                    logger.debug(f"[SR_Assess] Rejection detected at OB liquidity (ask): {ask_price:.2f} (Qty: {ask_info['qty']})")
                    return 'REJECT_RESISTANCE_LIQ'

        return 'NEUTRAL_SR' # Default if no specific S/R interaction found

    def _assess_volume(self, current_agg_kline, agg_volume_series):
        if current_agg_kline is None or not hasattr(agg_volume_series, 'mean') or agg_volume_series.empty: return 'NEUTRAL_VOLUME'
        current_vol = current_agg_kline.get('v')
        if current_vol is None or len(agg_volume_series) < 5: return 'NEUTRAL_VOLUME'

        avg_vol_window = min(getattr(settings, 'VOLUME_AVG_PERIOD', 20), max(1, len(agg_volume_series)-1) )
        avg_vol = agg_volume_series.rolling(window=avg_vol_window, min_periods=1).mean().iloc[-1]

        vol_high_multiplier = getattr(settings, 'VOLUME_HIGH_MULTIPLIER', 1.5)
        vol_low_multiplier = getattr(settings, 'VOLUME_LOW_MULTIPLIER', 0.7)

        if avg_vol == 0 :
            return 'HIGH_VOLUME' if current_vol > 0 else 'NEUTRAL_VOLUME'

        if current_vol > avg_vol * vol_high_multiplier: return 'HIGH_VOLUME'
        if current_vol < avg_vol * vol_low_multiplier: return 'LOW_VOLUME'
        return 'AVERAGE_VOLUME'

    def _calculate_signal_consolidation(self, assessed_states_dict, target_signal_type):
        """Calculates a consolidation percentage towards a target signal type."""
        current_score = 0
        max_score = 0

        trend_state = assessed_states_dict.get('trend', 'NEUTRAL_TREND')
        macd_state = assessed_states_dict.get('macd', 'NEUTRAL')
        rsi_state = assessed_states_dict.get('rsi', 'NEUTRAL')
        kdj_state = assessed_states_dict.get('kdj', 'NEUTRAL')
        fractal_assessment = assessed_states_dict.get('fractal', 'NEUTRAL')
        sr_level_assessment = assessed_states_dict.get('sr', 'NEUTRAL_SR')
        volume_assessment = assessed_states_dict.get('volume', 'NEUTRAL_VOLUME')

        if target_signal_type == "LONG":
            max_score += 2 # Trend
            if trend_state == 'STRONG_BULLISH_TREND': current_score += 2
            elif trend_state == 'BULLISH_TREND_ST' or trend_state == 'BULLISH_TREND_SAR': current_score += 1
            max_score += 2 # MACD
            if macd_state == 'STRONG_BULLISH': current_score += 2
            elif macd_state == 'BULLISH': current_score += 1
            max_score += 1 # RSI
            if rsi_state == 'BULLISH': current_score += 1
            max_score += 1 # KDJ
            if kdj_state == 'BULLISH' or kdj_state == 'OVERSOLD': current_score += 1
            max_score += 2 # S/R
            if sr_level_assessment in ['BOUNCE_SUPPORT_PIVOT', 'BOUNCE_SUPPORT_FIB', 'BOUNCE_SUPPORT_LIQ', 'BREAKOUT_ABOVE_R1_PIVOT']: current_score += 2
            max_score += 1 # Fractal
            if fractal_assessment == 'BROKE_BEARISH_FRACTAL_UP': current_score += 1
            max_score += 2 # Volume
            if volume_assessment == 'HIGH_VOLUME': current_score += 2
            elif volume_assessment == 'AVERAGE_VOLUME': current_score += 1
        elif target_signal_type == "SHORT":
            max_score += 2 # Trend
            if trend_state == 'STRONG_BEARISH_TREND': current_score += 2
            elif trend_state == 'BEARISH_TREND_ST' or trend_state == 'BEARISH_TREND_SAR': current_score += 1
            max_score += 2 # MACD
            if macd_state == 'STRONG_BEARISH': current_score += 2
            elif macd_state == 'BEARISH': current_score += 1
            max_score += 1 # RSI
            if rsi_state == 'BEARISH': current_score += 1
            max_score += 1 # KDJ
            if kdj_state == 'BEARISH' or kdj_state == 'OVERBOUGHT': current_score += 1
            max_score += 2 # S/R
            if sr_level_assessment in ['REJECT_RESISTANCE_PIVOT', 'REJECT_RESISTANCE_FIB', 'REJECT_RESISTANCE_LIQ', 'BREAKDOWN_BELOW_S1_PIVOT']: current_score += 2
            max_score += 1 # Fractal
            if fractal_assessment == 'BROKE_BULLISH_FRACTAL_DOWN': current_score += 1
            max_score += 2 # Volume
            if volume_assessment == 'HIGH_VOLUME': current_score += 2
            elif volume_assessment == 'AVERAGE_VOLUME': current_score += 1

        if max_score == 0: return 0.0
        return (current_score / max_score) * 100

    # --- End Signal Generation Helper Methods ---

    def _calculate_tp_sl(self, signal_type, entry_price, current_kline_low, current_kline_high, indicators, analysis):
        """ Helper to calculate TP and SL based on current logic. """
        atr_value = indicators.get('atr')
        pivots_data = analysis.get('pivots', {}).get('daily_pivots')

        take_profit = None
        stop_loss = None

        price_buffer_factor = getattr(settings, 'SL_PRICE_BUFFER_ATR_FACTOR', 0.1)

        # --- Stop Loss Calculation ---
        sl_atr_defined = False
        if atr_value is not None and atr_value > 0:
            sl_distance = settings.ATR_SL_MULTIPLIER * atr_value
            price_buffer = atr_value * price_buffer_factor

            if signal_type == "LONG":
                sl_atr = entry_price - sl_distance
                stop_loss = min(sl_atr, current_kline_low - price_buffer)
            elif signal_type == "SHORT":
                sl_atr = entry_price + sl_distance
                stop_loss = max(sl_atr, current_kline_high + price_buffer)
            sl_atr_defined = True

        if not sl_atr_defined:
            if signal_type == "LONG":
                stop_loss = entry_price * (1 - settings.MIN_SL_FALLBACK_PERCENTAGE)
            else: # SHORT
                stop_loss = entry_price * (1 + settings.MIN_SL_FALLBACK_PERCENTAGE)

        # --- Take Profit Calculation ---
        tp_atr_defined = False
        if atr_value is not None and atr_value > 0:
            tp_distance = settings.ATR_TP_MULTIPLIER * atr_value
            if signal_type == "LONG":
                take_profit = entry_price + tp_distance
            elif signal_type == "SHORT":
                take_profit = entry_price - tp_distance
            tp_atr_defined = True

        if pivots_data:
            if signal_type == "LONG" and pivots_data.get('R1'):
                tp_pivot = pivots_data['R1']
                if not tp_atr_defined or (tp_pivot > entry_price and tp_pivot < (take_profit if tp_atr_defined else float('inf'))):
                    if take_profit is None or (tp_pivot < take_profit):
                         pass
            elif signal_type == "SHORT" and pivots_data.get('S1'):
                tp_pivot = pivots_data['S1']
                if not tp_atr_defined or (tp_pivot < entry_price and tp_pivot > (take_profit if tp_atr_defined else float('-inf'))):
                         pass

        if not tp_atr_defined and take_profit is None:
            if signal_type == "LONG":
                take_profit = entry_price * (1 + settings.MIN_TP_FALLBACK_PERCENTAGE)
            else: # SHORT
                take_profit = entry_price * (1 - settings.MIN_TP_FALLBACK_PERCENTAGE)

        if signal_type == "LONG":
            if take_profit <= entry_price: take_profit = entry_price * (1 + settings.MIN_TP_DISTANCE_PERCENTAGE)
            if stop_loss >= entry_price: stop_loss = entry_price * (1 - settings.MIN_SL_DISTANCE_PERCENTAGE)
        elif signal_type == "SHORT":
            if take_profit >= entry_price: take_profit = entry_price * (1 - settings.MIN_TP_DISTANCE_PERCENTAGE)
            if stop_loss <= entry_price: stop_loss = entry_price * (1 + settings.MIN_SL_DISTANCE_PERCENTAGE)

        if stop_loss is not None and take_profit is not None and stop_loss != entry_price:
            reward_abs = abs(take_profit - entry_price)
            risk_abs = abs(entry_price - stop_loss)
            if risk_abs > 0:
                current_rr = reward_abs / risk_abs
                if current_rr < settings.MIN_RR_RATIO:
                    if self.on_status_update and not self.is_historical_fill_active:
                        self.on_status_update(f"[StrategySignal] ({self.strategy_timeframe_str}) {signal_type} signal R/R ratio {current_rr:.2f} < min {settings.MIN_RR_RATIO}. TP={take_profit:.2f}, SL={stop_loss:.2f}. Signal invalidated.")
                    return None, None
            else:
                if self.on_status_update and not self.is_historical_fill_active:
                     self.on_status_update(f"[StrategySignal] ({self.strategy_timeframe_str}) {signal_type} SL is at entry or invalid. R/R undefined or invalid. TP={take_profit:.2f}, SL={stop_loss:.2f}. Signal invalidated.")
                return None, None


        return take_profit, stop_loss

    def _generate_signal(self, current_kline, indicators, analysis): # current_kline is an aggregated kline dict
        """
        Refactored signal generation logic.
        Combines states from helper assessment methods to find confluence.
        """
        current_price = float(current_kline['c'])
        current_high = float(current_kline['h'])
        current_low = float(current_kline['l'])

        trend_state = self._assess_trend_filters(indicators.get('supertrend'), indicators.get('sar'), current_price)
        macd_state = self._assess_macd(indicators.get('macd'))
        rsi_state = self._assess_rsi(indicators.get('rsi'))
        kdj_state = self._assess_kdj(indicators.get('kdj'))
        fractal_assessment = self._assess_fractals(indicators.get('fractal'), current_high, current_low)
        sr_level_assessment = self._assess_sr_levels(current_price, current_low, current_high,
                                                     analysis.get('pivots'),
                                                     analysis.get('fibonacci'),
                                                     analysis.get('liquidity'))

        agg_volume_series = pd.Series(list(self.agg_volumes)) if self.agg_volumes else pd.Series([], dtype=float)
        volume_assessment = self._assess_volume(current_kline, agg_volume_series)

        if self.on_status_update and not self.is_historical_fill_active:
            log_msg_parts = [
                f"Trend={trend_state}", f"MACD={macd_state}", f"RSI={rsi_state}",
                f"KDJ={kdj_state}", f"Fractal={fractal_assessment}",
                f"S/R={sr_level_assessment}", f"Vol={volume_assessment}"
            ]
            self.on_status_update(f"[StrategyDebug] ({self.strategy_timeframe_str}) States: {', '.join(log_msg_parts)}")

        is_long_signal = False
        if (trend_state == 'STRONG_BULLISH_TREND' or trend_state == 'BULLISH_TREND_ST'):
            if (macd_state == 'STRONG_BULLISH' or macd_state == 'BULLISH') and \
               (rsi_state == 'BULLISH' and rsi_state != 'OVERBOUGHT') and \
               (kdj_state == 'BULLISH' or kdj_state == 'OVERSOLD'):
                sr_confirms_long = sr_level_assessment in ['BOUNCE_SUPPORT_PIVOT', 'BOUNCE_SUPPORT_FIB', 'BOUNCE_SUPPORT_LIQ', 'BREAKOUT_ABOVE_R1_PIVOT']
                fractal_confirms_long = fractal_assessment == 'BROKE_BEARISH_FRACTAL_UP'
                volume_supports_move = volume_assessment in ['AVERAGE_VOLUME', 'HIGH_VOLUME']
                if sr_confirms_long and volume_supports_move:
                    is_long_signal = True
                    if self.on_status_update and not self.is_historical_fill_active: self.on_status_update(f"[StrategySignal] LONG Condition Met (Trend + Momentum + S/R_Bounce/Break + Volume). Fractal: {fractal_assessment}")
                elif fractal_confirms_long and volume_supports_move and sr_level_assessment == 'NEUTRAL_SR':
                    is_long_signal = True
                    if self.on_status_update and not self.is_historical_fill_active: self.on_status_update(f"[StrategySignal] LONG Condition Met (Trend + Momentum + Fractal_Break + Volume). S/R: {sr_level_assessment}")

        if is_long_signal:
            signal_type = "LONG"
            entry_price = current_price
            take_profit, stop_loss = self._calculate_tp_sl(signal_type, entry_price, current_low, current_high, indicators, analysis)
            if take_profit is not None and stop_loss is not None:
                debug_states = { "trend": trend_state, "macd": macd_state, "rsi": rsi_state, "kdj": kdj_state, "fractal": fractal_assessment, "sr": sr_level_assessment, "volume": volume_assessment }
                return {'type': signal_type, 'price': entry_price, 'tp': take_profit, 'sl': stop_loss, 'debug_states': debug_states}

        is_short_signal = False
        if (trend_state == 'STRONG_BEARISH_TREND' or trend_state == 'BEARISH_TREND_ST'):
            if (macd_state == 'STRONG_BEARISH' or macd_state == 'BEARISH') and \
               (rsi_state == 'BEARISH' and rsi_state != 'OVERSOLD') and \
               (kdj_state == 'BEARISH' or kdj_state == 'OVERBOUGHT'):
                sr_confirms_short = sr_level_assessment in ['REJECT_RESISTANCE_PIVOT', 'REJECT_RESISTANCE_FIB', 'REJECT_RESISTANCE_LIQ', 'BREAKDOWN_BELOW_S1_PIVOT']
                fractal_confirms_short = fractal_assessment == 'BROKE_BULLISH_FRACTAL_DOWN'
                volume_supports_move = volume_assessment in ['AVERAGE_VOLUME', 'HIGH_VOLUME']
                if sr_confirms_short and volume_supports_move:
                    is_short_signal = True
                    if self.on_status_update and not self.is_historical_fill_active: self.on_status_update(f"[StrategySignal] SHORT Condition Met (Trend + Momentum + S/R_Rejection/Breakdown + Volume). Fractal: {fractal_assessment}")
                elif fractal_confirms_short and volume_supports_move and sr_level_assessment == 'NEUTRAL_SR':
                    is_short_signal = True
                    if self.on_status_update and not self.is_historical_fill_active: self.on_status_update(f"[StrategySignal] SHORT Condition Met (Trend + Momentum + Fractal_Breakdown + Volume). S/R: {sr_level_assessment}")

        if is_short_signal:
            signal_type = "SHORT"
            entry_price = current_price
            take_profit, stop_loss = self._calculate_tp_sl(signal_type, entry_price, current_low, current_high, indicators, analysis)
            if take_profit is not None and stop_loss is not None:
                debug_states = { "trend": trend_state, "macd": macd_state, "rsi": rsi_state, "kdj": kdj_state, "fractal": fractal_assessment, "sr": sr_level_assessment, "volume": volume_assessment }
                return {'type': signal_type, 'price': entry_price, 'tp': take_profit, 'sl': stop_loss, 'debug_states': debug_states}

        # Calculate consolidation percentages if no trade signal
        assessed_states_dict = {
            'trend': trend_state, 'macd': macd_state, 'rsi': rsi_state, 'kdj': kdj_state,
            'fractal': fractal_assessment, 'sr': sr_level_assessment, 'volume': volume_assessment
        }
        long_consol_perc = self._calculate_signal_consolidation(assessed_states_dict, "LONG")
        short_consol_perc = self._calculate_signal_consolidation(assessed_states_dict, "SHORT")
        return {'type': 'CONSOLIDATION_INFO', 'long_perc': long_consol_perc, 'short_perc': short_consol_perc, 'debug_states': assessed_states_dict}


if __name__ == '__main__':
    print("--- Testing GoldenStrategy Integration ---")

    def mock_status_update(message):
        print(f"STATUS_UPDATE: {message}")


    strategy = GoldenStrategy(on_status_update=mock_status_update,
                              on_indicators_update=lambda ind_data: print(f"INDICATORS_UPDATE: {ind_data}"),
                              on_signal_update=lambda sig_data: print(f"SIGNAL_UPDATE: {sig_data}"),
                              on_chart_update=lambda chart_df: print(f"CHART_UPDATE: DataFrame with {len(chart_df)} rows"))

    original_timeframe = settings.STRATEGY_TIMEFRAME
    settings.STRATEGY_TIMEFRAME = "1T"
    print(f"TEST: Overriding STRATEGY_TIMEFRAME to {settings.STRATEGY_TIMEFRAME} for this test run.")
    # Re-initialize strategy with the new timeframe for the test
    strategy = GoldenStrategy(on_status_update=mock_status_update,
                              on_indicators_update=lambda ind_data: print(f"INDICATORS_UPDATE: {ind_data}"),
                              on_signal_update=lambda sig_data: print(f"SIGNAL_UPDATE: {sig_data}"),
                              on_chart_update=lambda chart_df: print(f"CHART_UPDATE: DataFrame with {len(chart_df)} rows"))

    num_seconds_to_simulate = (settings.ATR_PERIOD + 25) * 60

    base_price = 20000
    klines_to_test = []
    start_time_ms = int(pd.Timestamp('2023-01-01 00:00:00', tz='UTC').value / 10**6)

    for i in range(num_seconds_to_simulate):
        price_change = (i % 10 - 4.5) * 0.1
        current_time_ms = start_time_ms + i * 1000
        day_cycle = (i // (60*60*4)) % 2
        if day_cycle == 0:
            base_price_offset = (i % (60*10) - 300) * 0.1
        else:
            base_price_offset = -(i % (60*10) - 300) * 0.1

        k_open = base_price + base_price_offset + price_change
        k_high = k_open + abs(price_change) + 5
        k_low = k_open - abs(price_change) - 5
        k_close = k_open + price_change / 2
        k_volume = 1 + (i % 10)

        k = {
            't': str(current_time_ms),
            'o': f"{k_open:.2f}", 'h': f"{k_high:.2f}",
            'l': f"{k_low:.2f}", 'c': f"{k_close:.2f}",
            'v': f"{k_volume:.2f}"
        }
        klines_to_test.append(k)

    print(f"Generated {len(klines_to_test)} 1-second klines for testing ({num_seconds_to_simulate/60:.1f} minutes).")

    for idx, kline_data_point in enumerate(klines_to_test):
        strategy.process_new_kline(kline_data_point)

    print("\nGoldenStrategy aggregation test finished.")
    settings.STRATEGY_TIMEFRAME = original_timeframe
    print(f"TEST: Restored STRATEGY_TIMEFRAME to {settings.STRATEGY_TIMEFRAME}.")

[end of trading_bot/strategy/gold_strategy.py]
