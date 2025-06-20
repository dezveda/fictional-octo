import customtkinter as ctk
import tkinter as tk
from collections import deque
import logging
from trading_bot.utils import settings # For displaying ATR_PERIOD
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd # For DataFrame type hinting and data prep
import mplfinance as mpf # Import mplfinance


logger_gui = logging.getLogger(__name__ + '_gui')

# --- Appearance Settings ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Golden Strategy BTC/USDT Bot")
        self.geometry("900x700")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.main_content_frame = ctk.CTkFrame(self, corner_radius=5)
        self.main_content_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10,5))
        self.main_content_frame.grid_columnconfigure(0, weight=1)

        self.price_signal_frame = ctk.CTkFrame(self.main_content_frame, corner_radius=5)
        self.price_signal_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.price_signal_frame.grid_columnconfigure(0, weight=1)
        self.price_signal_frame.grid_columnconfigure(1, weight=1)
        self.price_signal_frame.grid_columnconfigure(2, weight=2)

        ctk.CTkLabel(self.price_signal_frame, text="BTC/USDT:", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=(10,0), pady=10, sticky="w")
        self.price_label = ctk.CTkLabel(self.price_signal_frame, text="N/A", font=ctk.CTkFont(size=20, weight="bold"), text_color=("green", "lightgreen"))
        self.price_label.grid(row=0, column=1, padx=(0,10), pady=10, sticky="w")

        self.signal_label = ctk.CTkLabel(self.price_signal_frame, text="Signal: Awaiting strategy data...", font=ctk.CTkFont(size=18, weight="bold"), text_color="yellow")
        self.signal_label.grid(row=0, column=2, padx=10, pady=10, sticky="e")

        self.main_content_frame.grid_rowconfigure(0, weight=0)

        self.indicators_outer_frame = ctk.CTkFrame(self.main_content_frame, corner_radius=5)
        self.indicators_outer_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.indicators_outer_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.indicators_outer_frame, text="Key Indicators", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(5,5))

        self.indicators_frame = ctk.CTkScrollableFrame(self.indicators_outer_frame, corner_radius=3, height=150)
        self.indicators_frame.pack(fill="x", expand=True, padx=5, pady=5)
        self.indicators_details_label = ctk.CTkLabel(self.indicators_frame, text="Waiting for strategy data...",
                                                     font=ctk.CTkFont(size=14), justify="left", anchor="nw")
        self.indicators_details_label.pack(padx=5, pady=5, anchor="nw", fill="x")

        self.main_content_frame.grid_rowconfigure(1, weight=1) # Indicators frame weight

        # --- Section for Liquidity Info ---
        self.liquidity_info_frame = ctk.CTkFrame(self.main_content_frame, corner_radius=5)
        self.liquidity_info_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5) # Liquidity on new row 2
        self.liquidity_info_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.liquidity_info_frame, text="Order Book Liquidity (Top Levels)", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(5,2))
        self.liquidity_display_label = ctk.CTkLabel(self.liquidity_info_frame, text="Liquidity: Awaiting data...", font=ctk.CTkFont(size=12), justify="left", anchor="w")
        self.liquidity_display_label.pack(padx=10, pady=(0,5), anchor="w", fill="x")

        self.main_content_frame.grid_rowconfigure(2, weight=0) # Liquidity frame row (fixed size)

        self.chart_frame = ctk.CTkFrame(self.main_content_frame, corner_radius=5)
        self.chart_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=10) # Chart frame moved to row 3

        self.figure = Figure(figsize=(5, 4), dpi=100, facecolor='#2B2B2B')
        spec = self.figure.add_gridspec(nrows=2, ncols=1, height_ratios=[3, 1], hspace=0.05)
        self.ax = self.figure.add_subplot(spec[0,0])
        self.volume_ax = self.figure.add_subplot(spec[1,0], sharex=self.ax)

        self.ax.set_facecolor('#1c1c1c')
        self.ax.tick_params(axis='x', colors='lightgray', labelbottom=False)
        self.ax.tick_params(axis='y', colors='lightgray', labelsize=8)
        for spine_pos in ['bottom', 'top', 'left', 'right']:
            self.ax.spines[spine_pos].set_color('gray')
        self.ax.yaxis.label.set_color('lightgray')
        self.ax.set_title("Candlestick Chart (Initializing...)", color='white', fontsize=10)
        self.ax.grid(True, linestyle=':', linewidth=0.5, color='gray', alpha=0.3)

        self.volume_ax.set_facecolor('#1c1c1c')
        self.volume_ax.tick_params(axis='x', colors='lightgray', labelsize=8)
        self.volume_ax.tick_params(axis='y', colors='lightgray', labelsize=7)
        self.volume_ax.spines['top'].set_visible(False)
        self.volume_ax.spines['right'].set_color('gray')
        self.volume_ax.spines['left'].set_color('gray')
        self.volume_ax.spines['bottom'].set_color('gray')
        self.volume_ax.grid(True, linestyle=':', linewidth=0.5, color='gray', alpha=0.3)

        self.figure.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(side=ctk.TOP, fill=ctk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.draw()

        self.main_content_frame.grid_rowconfigure(3, weight=2) # Chart frame weight on row 3

        self.status_bar_frame = ctk.CTkFrame(self, corner_radius=0)
        self.status_bar_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=0)

        self.status_textbox = ctk.CTkTextbox(
            self.status_bar_frame,
            height=100,
            activate_scrollbars=True,
            wrap="word",
            font=ctk.CTkFont(size=11)
        )
        self.status_textbox.pack(fill="x", expand=True, padx=5, pady=(0,5))
        self.status_textbox.configure(state="disabled")

        self.max_status_messages = 100
        self.status_messages = deque(maxlen=self.max_status_messages)
        self.price_annotation = None # For chart's live price label

    def update_status_bar(self, message):
        try:
            if not hasattr(self, 'status_textbox'): return
            from datetime import datetime
            time_str = datetime.now().strftime("%H:%M:%S")

            self.status_messages.append(f"[{time_str}] {message}")

            self.status_textbox.configure(state="normal")
            self.status_textbox.delete("1.0", "end")
            self.status_textbox.insert("1.0", "\n".join(self.status_messages))
            self.status_textbox.see("end")
            self.status_textbox.configure(state="disabled")
        except Exception as e:
            logger_gui.error(f"Error in update_status_bar: {e}", exc_info=False)

    def update_price_display(self, price_str):
        try:
            logger_gui.info(f"[GUI] update_price_display received: '{price_str}'")
            self.price_label.configure(text=f"{price_str}")
        except Exception as e:
            logger_gui.error(f"Error updating price display: {e}", exc_info=False)

    def update_signal_display(self, signal_info_str):
        try:
            text_to_display = f"Signal: {signal_info_str}"
            text_color = "#DCE4EE"

            if isinstance(signal_info_str, str):
                upper_signal_str = signal_info_str.upper()
                if "CONSOLIDATION:" in upper_signal_str:
                    text_color = "#FFD700"
                elif "LONG" in upper_signal_str and "@" in upper_signal_str:
                    text_color = "#2ECC71"
                elif "SHORT" in upper_signal_str and "@" in upper_signal_str:
                    text_color = "#E74C3C"
                elif "WAITING" in upper_signal_str or "AWAITING" in upper_signal_str or "INITIALIZING" in upper_signal_str or "CALCULATING" in upper_signal_str:
                    text_color = "#7F8C8D"
            else:
                text_to_display = f"Signal: Invalid data type ({type(signal_info_str)})"
                text_color = "#E74C3C"

            self.signal_label.configure(text=text_to_display, text_color=text_color)
        except Exception as e:
            logger_gui.error(f"Error in update_signal_display: {e}", exc_info=False)
            try:
                self.signal_label.configure(text=f"Signal Display Error: {e}", text_color="red")
            except Exception: pass

    def update_indicators_display(self, indicators_data):
        try:
            if isinstance(indicators_data, dict):
                if 'status' in indicators_data:
                    timeframe = indicators_data.get('timeframe', settings.STRATEGY_TIMEFRAME if 'settings' in globals() else '')
                    status_text = f"({timeframe}) {indicators_data['status']}" if timeframe else indicators_data['status']
                    self.indicators_details_label.configure(text=status_text)
                    return

                display_text = []
                timeframe = indicators_data.get('timeframe', '')
                if timeframe:
                    display_text.append(f"--- Indicators ({timeframe}) ---")

                if 'RSI' in indicators_data: display_text.append(f"RSI ({settings.RSI_PERIOD if 'settings' in globals() else 'N/A'}): {indicators_data['RSI']:.2f}" if isinstance(indicators_data['RSI'], float) else f"RSI ({settings.RSI_PERIOD if 'settings' in globals() else 'N/A'}): {indicators_data['RSI']}")
                if 'ST_DIR' in indicators_data: display_text.append(f"Supertrend ({settings.ATR_PERIOD if 'settings' in globals() else 'N/A'},{settings.SUPERTREND_MULTIPLIER if 'settings' in globals() else 'N/A'}): {indicators_data['ST_DIR']}")
                if 'ST_VAL' in indicators_data: display_text.append(f"  └ Value: {indicators_data['ST_VAL']:.2f}" if isinstance(indicators_data['ST_VAL'], float) else f"  └ Value: {indicators_data['ST_VAL']}")
                if 'MACD_H' in indicators_data: display_text.append(f"MACD Hist ({settings.MACD_SHORT_PERIOD if 'settings' in globals() else 'N/A'},{settings.MACD_LONG_PERIOD if 'settings' in globals() else 'N/A'},{settings.MACD_SIGNAL_PERIOD if 'settings' in globals() else 'N/A'}): {indicators_data['MACD_H']:.4f}" if isinstance(indicators_data['MACD_H'], float) else f"MACD Hist: {indicators_data['MACD_H']}")
                if 'KDJ_J' in indicators_data: display_text.append(f"KDJ ({settings.KDJ_N_PERIOD if 'settings' in globals() else 'N/A'},{settings.KDJ_M1_PERIOD if 'settings' in globals() else 'N/A'},{settings.KDJ_M2_PERIOD if 'settings' in globals() else 'N/A'}) (J): {indicators_data['KDJ_J']:.2f}" if isinstance(indicators_data['KDJ_J'], float) else f"KDJ (J): {indicators_data['KDJ_J']}")
                if 'SAR_VAL' in indicators_data: display_text.append(f"SAR ({settings.SAR_INITIAL_AF if 'settings' in globals() else 'N/A'},{settings.SAR_AF_INCREMENT if 'settings' in globals() else 'N/A'},{settings.SAR_MAX_AF if 'settings' in globals() else 'N/A'}): {indicators_data['SAR_VAL']:.2f}" if isinstance(indicators_data['SAR_VAL'], float) else f"SAR: {indicators_data['SAR_VAL']}")
                if 'SAR_DIR' in indicators_data: display_text.append(f"  └ Dir: {indicators_data['SAR_DIR']}")
                if 'ATR' in indicators_data: display_text.append(f"ATR ({settings.ATR_PERIOD if 'settings' in globals() else 'N/A'}): {indicators_data['ATR']:.4f}" if isinstance(indicators_data['ATR'], float) else f"ATR: {indicators_data['ATR']}")

                self.indicators_details_label.configure(text="\n".join(display_text))
            else:
                self.indicators_details_label.configure(text=str(indicators_data))
        except Exception as e:
            if 'logger_gui' in globals() or 'logger_gui' in locals():
                 logger_gui.error(f"Error in update_indicators_display: {e}", exc_info=False)
            else:
                 print(f"GUI Error in update_indicators_display: {e}")

    def update_chart(self, chart_data_df: pd.DataFrame = None):
        current_logger = logging.getLogger(__name__ + '_gui') # Ensure logger is accessible

        # Always remove old price annotation first if it exists
        if self.price_annotation:
            try: self.price_annotation.remove(); self.price_annotation = None; except Exception: pass

        if chart_data_df is None or chart_data_df.empty or not all(col in chart_data_df.columns for col in ['Open', 'High', 'Low', 'Close']) or not isinstance(chart_data_df.index, pd.DatetimeIndex):
            self.ax.clear()
            if hasattr(self, 'volume_ax'): self.volume_ax.clear()
            self.ax.text(0.5, 0.5, "Waiting for chart data...",
                         horizontalalignment='center', verticalalignment='center',
                         transform=self.ax.transAxes, color="gray", fontsize=12)
            chart_title_tf = settings.STRATEGY_TIMEFRAME if 'settings' in globals() else 'N/A'
            self.ax.set_title(f"{chart_title_tf} Candlestick Chart (No Data)", color='white', fontsize=10)
            # Reapply styles
            for axis_obj in [self.ax, getattr(self, 'volume_ax', None)]:
                if axis_obj:
                    axis_obj.set_facecolor('#1c1c1c')
                    axis_obj.tick_params(axis='x', colors='lightgray', labelsize=8)
                    axis_obj.tick_params(axis='y', colors='lightgray', labelsize=8)
                    for spine_pos in ['bottom', 'top', 'left', 'right']:
                        if hasattr(axis_obj.spines[spine_pos], 'set_color'):
                             axis_obj.spines[spine_pos].set_color('gray')
            if hasattr(self, 'volume_ax') and self.volume_ax:
                self.volume_ax.tick_params(axis='x', labelbottom=False)
                if hasattr(self.volume_ax.spines['top'], 'set_visible'): self.volume_ax.spines['top'].set_visible(False)
            self.canvas.draw()
            return

        self.ax.clear()
        if hasattr(self, 'volume_ax'): self.volume_ax.clear()

        for axis_obj in [self.ax, getattr(self, 'volume_ax', None)]:
            if axis_obj:
                axis_obj.set_facecolor('#1c1c1c')
                axis_obj.tick_params(axis='x', colors='lightgray', labelsize=8)
                axis_obj.tick_params(axis='y', colors='lightgray', labelsize=8)
                for spine_pos in ['bottom', 'top', 'left', 'right']:
                    if hasattr(axis_obj.spines[spine_pos], 'set_color'):
                        axis_obj.spines[spine_pos].set_color('gray')
        if hasattr(self, 'volume_ax') and self.volume_ax:
            self.ax.tick_params(axis='x', labelbottom=False) # Corrected from self.volume_ax
            if hasattr(self.volume_ax.spines['top'], 'set_visible'): self.volume_ax.spines['top'].set_visible(False)

        mc = mpf.make_marketcolors(up='#00b060', down='#fe3032',
                                   edge={'up':'#00b060', 'down':'#fe3032'},
                                   wick={'up':'#00b060', 'down':'#fe3032'},
                                   volume={'up':'#00b060', 'down':'#fe3032'}, ohlc='inherit')
        s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc, gridstyle=':',
                               facecolor='#1c1c1c', figcolor='#2B2B2B')

        try:
            mpf.plot(chart_data_df,
                     type='candle',
                     ax=self.ax,
                     volume=self.volume_ax if hasattr(self, 'volume_ax') else False, # Pass volume_ax if it exists
                     style=s,
                     datetime_format='%H:%M', xrotation=15,
                     show_nontrading=False, tight_layout=True, # Use mplfinance's tight_layout
                     update_width_config=dict(candle_linewidth=0.8, candle_width=0.5, volume_width=0.5)
                    )
            chart_title_tf = settings.STRATEGY_TIMEFRAME if 'settings' in globals() else 'N/A'
            self.ax.set_title(f"{chart_title_tf} Candlestick Chart ({len(chart_data_df)} bars)", color='white', fontsize=10)

            # --- Add Live Price Annotation ---
            if not chart_data_df.empty and 'Close' in chart_data_df.columns:
                last_kline_index_num = len(chart_data_df) - 1
                last_close = chart_data_df['Close'].iloc[-1]
                if pd.notna(last_close):
                    # self.price_annotation is already cleared at the start of the method
                    x_pos = last_kline_index_num + getattr(settings, 'CHART_PRICE_LABEL_XOFFSET', 0.15) # Setting for x-offset
                    price_fmt_str = f" {last_close:.{getattr(settings, 'PRICE_PRECISION', 2)}f}" # Added space for padding
                    self.price_annotation = self.ax.text(
                        x_pos, last_close, price_fmt_str,
                        color=getattr(settings, 'CHART_PRICE_LABEL_COLOR', 'white'), fontsize=8, va='center', ha='left',
                        bbox=dict(boxstyle=getattr(settings, 'CHART_PRICE_LABEL_BOXSTYLE', 'round,pad=0.15'),
                                  fc=getattr(settings, 'CHART_PRICE_LABEL_BGCOLOR', '#202020'),
                                  ec=getattr(settings, 'CHART_PRICE_LABEL_EDGECOLOR', 'gray'), alpha=0.85)
                    )
                    # Basic Y-axis auto-adjustment (optional, can be refined)
                    current_ylim = list(self.ax.get_ylim())
                    y_margin_factor = 0.10 # 10% margin for label visibility
                    needs_y_rescale = False
                    if last_close > current_ylim[1] - (current_ylim[1] - current_ylim[0]) * y_margin_factor : # Near top edge
                        current_ylim[1] = last_close + (current_ylim[1] - current_ylim[0]) * y_margin_factor * 1.5
                        needs_y_rescale = True
                    if last_close < current_ylim[0] + (current_ylim[1] - current_ylim[0]) * y_margin_factor : # Near bottom edge
                        current_ylim[0] = last_close - (current_ylim[1] - current_ylim[0]) * y_margin_factor * 1.5
                        needs_y_rescale = True
                    if needs_y_rescale:
                        min_low_on_chart = chart_data_df['Low'].min()
                        max_high_on_chart = chart_data_df['High'].max()
                        if current_ylim[0] < 0 and min_low_on_chart > 0: current_ylim[0] = min_low_on_chart * (1-y_margin_factor*2) if min_low_on_chart * (1-y_margin_factor*2) > 0 else 0
                        current_ylim[1] = max(current_ylim[1], max_high_on_chart * (1+y_margin_factor*0.5)) # Ensure high is visible
                        current_ylim[0] = min(current_ylim[0], min_low_on_chart * (1-y_margin_factor*0.5)) # Ensure low is visible

                        if current_ylim[1] > current_ylim[0]: self.ax.set_ylim(current_ylim)
            # --- End Live Price Annotation ---

        except Exception as e:
            current_logger.error(f"[GUI] Error plotting chart with mplfinance: {e}", exc_info=True)
            try: self.ax.text(0.5, 0.5, "Error plotting chart.", color="red", ha='center', va='center', transform=self.ax.transAxes)
            except Exception: pass # Avoid error in error handling

        # self.figure.tight_layout() # Removed as mplfinance handles it with tight_layout=True
        self.canvas.draw()
        current_logger.info(f"[GUI] update_chart completed. Plotted {len(chart_data_df) if chart_data_df is not None else 'no'} candles.")

    def update_liquidity_display(self, liquidity_result_dict):
        """Updates the GUI with liquidity information from order book analysis."""
        try:
            if not liquidity_result_dict or not isinstance(liquidity_result_dict, dict):
                self.liquidity_display_label.configure(text="Liquidity: Invalid data received.")
                return

            status = liquidity_result_dict.get('status', 'Processing...')
            significant_bids = liquidity_result_dict.get('significant_bids', [])
            significant_asks = liquidity_result_dict.get('significant_asks', [])
            # summary = liquidity_result_dict.get('summary', '') # Get summary if available

            display_parts = []
            # Ensure settings is imported or accessible, or use a default.
            # Assuming 'settings' is imported in this file (it is).
            price_precision = getattr(settings, 'PRICE_PRECISION', 2)
            num_levels_to_show = getattr(settings, 'LIQUIDITY_GUI_LEVELS_TO_SHOW', 3)

            if significant_bids:
                bids_str = ", ".join([f"{b['price']:.{price_precision}f}@{b['qty']:.2f}" for b in significant_bids[:num_levels_to_show]])
                display_parts.append(f"Bids: {bids_str}")
            else:
                display_parts.append("Bids: None sig.")

            if significant_asks:
                asks_str = ", ".join([f"{a['price']:.{price_precision}f}@{a['qty']:.2f}" for a in significant_asks[:num_levels_to_show]])
                display_parts.append(f"Asks: {asks_str}")
            else:
                display_parts.append("Asks: None sig.")

            final_text = "Liq: " + " | ".join(display_parts)
            # if summary : final_text += f" ({summary})" # Optional summary

            self.liquidity_display_label.configure(text=final_text)

        except Exception as e:
            if 'logger_gui' in globals(): # Check if logger_gui is defined
                logger_gui.error(f"[GUI] Error updating liquidity display: {e}", exc_info=False)
            else: # Fallback print
                print(f"[GUI Error] In update_liquidity_display: {e}")
            try:
                # Check if self.liquidity_display_label exists before configuring
                if hasattr(self, 'liquidity_display_label'):
                    self.liquidity_display_label.configure(text=f"Liquidity Display Error: {e}")
            except Exception: pass # Avoid recursive error


if __name__ == '__main__':
    app = App()
    app.update_status_bar("GUI Initialized. Welcome to Golden Strategy Bot!")

    app.update_price_display("25000.50")
    app.update_signal_display("LONG @ 25000.00, TP: 25250.00")

    indicator_example_dict = {
        'timeframe': '1H',
        'RSI': 62.73,
        'ST_DIR': 'Up',
        'ST_VAL': 24800.12,
        'MACD_H': 0.0152,
        'KDJ_J': 78.19,
        'SAR_VAL': 24750.00,
        'SAR_DIR': 'Long',
        'ATR': 123.4567
    }
    app.update_indicators_display(indicator_example_dict)

    try:
        num_bars = 50
        index = pd.date_range(start='2023-01-01 00:00', periods=num_bars, freq='1H', tz='UTC')
        data = {
            'Open': np.random.uniform(20000, 21000, num_bars),
            'High': np.random.uniform(21000, 22000, num_bars),
            'Low': np.random.uniform(19000, 20000, num_bars),
            'Close': np.random.uniform(20000, 21000, num_bars),
            'Volume': np.random.uniform(10, 100, num_bars)
        }
        for i in range(num_bars):
            data['High'][i] = max(data['High'][i], data['Open'][i], data['Close'][i])
            data['Low'][i] = min(data['Low'][i], data['Open'][i], data['Close'][i])

        sample_chart_df = pd.DataFrame(data, index=index)
        app.update_chart(sample_chart_df)
        app.update_status_bar("Sample chart data displayed.")
    except Exception as e_test:
        app.update_status_bar(f"Error creating/displaying sample chart: {e_test}")

    app.update_status_bar("Test data displayed.")
    app.mainloop()
