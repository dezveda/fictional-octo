import customtkinter as ctk
import tkinter as tk
from collections import deque
import logging
from trading_bot.utils import settings # For displaying ATR_PERIOD

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
        self.price_label = ctk.CTkLabel(self.price_signal_frame, text="N/A", font=ctk.CTkFont(size=20, weight="bold"), text_color=("green", "lightgreen")) # Adjusted light mode color
        self.price_label.grid(row=0, column=1, padx=(0,10), pady=10, sticky="w")

        self.signal_label = ctk.CTkLabel(self.price_signal_frame, text="Signal: Initializing...", font=ctk.CTkFont(size=18, weight="bold"), text_color="yellow")
        self.signal_label.grid(row=0, column=2, padx=10, pady=10, sticky="e")

        self.main_content_frame.grid_rowconfigure(0, weight=0)

        self.indicators_outer_frame = ctk.CTkFrame(self.main_content_frame, corner_radius=5)
        self.indicators_outer_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.indicators_outer_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.indicators_outer_frame, text="Key Indicators", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(5,5))

        self.indicators_frame = ctk.CTkScrollableFrame(self.indicators_outer_frame, corner_radius=3, height=150)
        self.indicators_frame.pack(fill="x", expand=True, padx=5, pady=5)
        self.indicators_details_label = ctk.CTkLabel(self.indicators_frame, text="Calculating initial indicators...",
                                                     font=ctk.CTkFont(size=14), justify="left", anchor="nw")
        self.indicators_details_label.pack(padx=5, pady=5, anchor="nw", fill="x")

        self.main_content_frame.grid_rowconfigure(1, weight=1)

        self.chart_frame = ctk.CTkFrame(self.main_content_frame, corner_radius=5)
        self.chart_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.chart_label = ctk.CTkLabel(self.chart_frame, text="Chart Area (Future Implementation)", font=ctk.CTkFont(size=14))
        self.chart_label.pack(pady=20, padx=20)

        self.main_content_frame.grid_rowconfigure(2, weight=2)

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
            self.price_label.configure(text=f"{price_str}")
        except Exception as e:
            logger_gui.error(f"Error updating price display: {e}", exc_info=False)

    def update_signal_display(self, signal_info_str):
        try:
            color = "white"
            if "LONG" in signal_info_str.upper():
                color = ("green", "lightgreen")
            elif "SHORT" in signal_info_str.upper():
                color = ("red", "salmon")
            self.signal_label.configure(text=f"Signal: {signal_info_str}", text_color=color)
        except Exception as e:
            logger_gui.error(f"Error updating signal display: {e}", exc_info=False)

    def update_indicators_display(self, indicators_data):
        try:
            if isinstance(indicators_data, dict):
                if 'status' in indicators_data: # Check for a status message first
                    timeframe = indicators_data.get('timeframe', settings.STRATEGY_TIMEFRAME if 'settings' in globals() else '')
                    status_text = f"({timeframe}) {indicators_data['status']}" if timeframe else indicators_data['status']
                    self.indicators_details_label.configure(text=status_text)
                    return

                display_text = []
                timeframe = indicators_data.get('timeframe', '')
                if timeframe:
                    display_text.append(f"--- Indicators ({timeframe}) ---")

                # Standard indicator formatting (from previous version)
                if 'RSI' in indicators_data: display_text.append(f"RSI ({settings.RSI_PERIOD if 'settings' in globals() else 'N/A'}): {indicators_data['RSI']:.2f}" if isinstance(indicators_data['RSI'], float) else f"RSI ({settings.RSI_PERIOD if 'settings' in globals() else 'N/A'}): {indicators_data['RSI']}")
                if 'ST_DIR' in indicators_data: display_text.append(f"Supertrend ({settings.ATR_PERIOD if 'settings' in globals() else 'N/A'},{settings.SUPERTREND_MULTIPLIER if 'settings' in globals() else 'N/A'}): {indicators_data['ST_DIR']}")
                if 'ST_VAL' in indicators_data: display_text.append(f"  └ Value: {indicators_data['ST_VAL']:.2f}" if isinstance(indicators_data['ST_VAL'], float) else f"  └ Value: {indicators_data['ST_VAL']}")
                if 'MACD_H' in indicators_data: display_text.append(f"MACD Hist ({settings.MACD_SHORT_PERIOD if 'settings' in globals() else 'N/A'},{settings.MACD_LONG_PERIOD if 'settings' in globals() else 'N/A'},{settings.MACD_SIGNAL_PERIOD if 'settings' in globals() else 'N/A'}): {indicators_data['MACD_H']:.4f}" if isinstance(indicators_data['MACD_H'], float) else f"MACD Hist: {indicators_data['MACD_H']}")
                if 'KDJ_J' in indicators_data: display_text.append(f"KDJ ({settings.KDJ_N_PERIOD if 'settings' in globals() else 'N/A'},{settings.KDJ_M1_PERIOD if 'settings' in globals() else 'N/A'},{settings.KDJ_M2_PERIOD if 'settings' in globals() else 'N/A'}) (J): {indicators_data['KDJ_J']:.2f}" if isinstance(indicators_data['KDJ_J'], float) else f"KDJ (J): {indicators_data['KDJ_J']}")
                if 'SAR_VAL' in indicators_data: display_text.append(f"SAR ({settings.SAR_INITIAL_AF if 'settings' in globals() else 'N/A'},{settings.SAR_AF_INCREMENT if 'settings' in globals() else 'N/A'},{settings.SAR_MAX_AF if 'settings' in globals() else 'N/A'}): {indicators_data['SAR_VAL']:.2f}" if isinstance(indicators_data['SAR_VAL'], float) else f"SAR: {indicators_data['SAR_VAL']}")
                if 'SAR_DIR' in indicators_data: display_text.append(f"  └ Dir: {indicators_data['SAR_DIR']}")
                if 'ATR' in indicators_data: display_text.append(f"ATR ({settings.ATR_PERIOD if 'settings' in globals() else 'N/A'}): {indicators_data['ATR']:.4f}" if isinstance(indicators_data['ATR'], float) else f"ATR: {indicators_data['ATR']}")

                self.indicators_details_label.configure(text="\n".join(display_text))
            else: # Assume it's a pre-formatted string (e.g. for signals if this method was ever misused)
                self.indicators_details_label.configure(text=str(indicators_data))
        except Exception as e:
            # Ensure logger_gui is defined or use a fallback print
            if 'logger_gui' in globals() or 'logger_gui' in locals():
                 logger_gui.error(f"Error in update_indicators_display: {e}", exc_info=False)
            else:
                 print(f"GUI Error in update_indicators_display: {e}")


if __name__ == '__main__':
    app = App()
    app.update_status_bar("GUI Initialized. Welcome to Golden Strategy Bot!")

    app.update_price_display("25000.50")
    app.update_signal_display("LONG @ 25000.00, TP: 25250.00")

    indicator_example_dict = {
        'RSI': 62.73,
        'ST_DIR': 'Up',
        'ST_VAL': 24800.12,
        'MACD_H': 0.0152,
        'KDJ_J': 78.19,
        'SAR_VAL': 24750.00,
        'SAR_DIR': 'Long'
    }
    app.update_indicators_display(indicator_example_dict)

    app.update_status_bar("Test data displayed.")
    app.mainloop()
