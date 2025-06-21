# Minimalist Trading Bot for BTC/USDT

## 1. Introduction

This project is a Python-based trading bot designed for analyzing the BTC/USDT market from Binance and generating potential trading signals. The development emphasizes:
-   **Minimalism**: Avoiding unnecessary complexity and dependencies.
-   **Modularity**: Clear separation of concerns into distinct modules.
-   **Custom Implementation**: Core logic like indicator calculations are built from scratch.
-   **User-Driven Refinement**: Features and logic have evolved based on iterative feedback.

The bot operates by fetching live and historical market data (klines and order book depth), processing this data through a custom strategy engine, and presenting information through a real-time graphical user interface.

**Note**: This bot is an experimental project. Trading financial markets involves significant risk. Use with caution and at your own risk.

## 2. Key Features

*   **Real-time Data**:
    *   Connects to Binance for live 1-minute (configurable) BTC/USDT kline data via WebSockets.
    *   Connects to Binance for live order book depth snapshots (e.g., top 20 levels @ 100ms).
    *   Fetches historical kline data on startup to pre-fill strategy history.
*   **Custom Indicator Calculations**:
    *   All technical indicators implemented from scratch using Pandas/NumPy (no TA-Lib):
        *   MACD, RSI, Supertrend, KDJ, Parabolic SAR, Williams Fractal, Momentum, ATR, SMA, EMA.
*   **Advanced Strategy Engine ("Golden Strategy")**:
    *   Aggregates base kline data (e.g., 1-minute) to a higher strategy timeframe (e.g., 1-hour, configurable).
    *   Calculates indicators and makes decisions based on these aggregated bars.
    *   Incorporates specialized analyses:
        *   Daily Pivot Points.
        *   Standard Fibonacci Retracements.
        *   Order Book Liquidity Analysis (significant bid/ask levels).
    *   Generates LONG/SHORT signals based on a confluence of states from various indicators and analyses.
    *   Calculates Take Profit (TP) and Stop Loss (SL) using ATR and a Risk/Reward ratio check.
*   **Graphical User Interface (GUI)**:
    *   Built with `customtkinter` for a modern, dark-themed UI.
    *   Live BTC/USDT price display.
    *   Candlestick chart (`mplfinance`) for the strategy timeframe, with a live-updating last candle and price action label.
    *   Display of provisional "live" strategy indicators and signal consolidation percentages, updating with each base kline.
    *   Display of finalized indicators and trading signals at the close of each strategy timeframe bar.
    *   Real-time display of significant order book liquidity levels.
    *   Scrollable status bar for detailed operational messages and logs.
*   **Configurability**:
    *   Most parameters (trading symbol, kline intervals, strategy timeframe, indicator periods, strategy logic thresholds, TP/SL parameters, GUI elements) are configurable via `trading_bot/utils/settings.py`.
*   **Comprehensive Logging**:
    *   Detailed logging throughout the application for monitoring and debugging, with configurable log levels.

## 3. Technology Stack

*   **Python 3**: Core programming language.
*   **`python-binance`**: For interacting with the Binance API (fetching klines, order book data via WebSockets and REST).
*   **`pandas`**: For data manipulation and time series analysis (especially for indicators).
*   **`numpy`**: For numerical operations.
*   **`customtkinter`**: For building the modern graphical user interface.
*   **`matplotlib`**: For embedding charts in the GUI.
*   **`mplfinance`**: For creating candlestick and volume charts.
*   Standard Python libraries: `asyncio`, `threading`, `logging`, `collections`, `json`, `re`, `os`.

## 4. Getting Started

### Prerequisites
*   Python 3.8+
*   Internet connection

### Setup and Running
Detailed instructions for setting up a virtual environment, installing dependencies, and running the bot can be found in:
**[DEPLOYMENT.MD](DEPLOYMENT.md)**

### Configuration
Before running, you might want to review and adjust parameters in `trading_bot/utils/settings.py`.

## 5. Detailed Documentation

For an in-depth understanding of the project's architecture, modules, data flow, and specific logic, please refer to the documentation in the `docs/` folder:

*   **[docs/00_OVERVIEW.md](docs/00_OVERVIEW.md)**: Project goals, core functions, design, architecture.
*   **[docs/01_PROJECT_STRUCTURE.md](docs/01_PROJECT_STRUCTURE.md)**: Directory and file layout.
*   **[docs/02_DATA_FLOW.md](docs/02_DATA_FLOW.md)**: How kline and order book data moves through the system.
*   **[docs/03_MODULE_DATA_FETCHER.md](docs/03_MODULE_DATA_FETCHER.md)**: Details of `data_fetcher.py`.
*   **[docs/04_MODULE_INDICATORS.md](docs/04_MODULE_INDICATORS.md)**: Details of `indicators/calculator.py`.
*   **[docs/05_MODULE_STRATEGY.md](docs/05_MODULE_STRATEGY.md)**: Details of `strategy/gold_strategy.py` and its sub-modules.
*   **[docs/06_MODULE_GUI.md](docs/06_MODULE_GUI.md)**: Details of `gui/main_window.py`.
*   **[docs/07_MODULE_MAIN.md](docs/07_MODULE_MAIN.md)**: Details of `main.py` (`BotApplication`).
*   **[docs/08_SETTINGS_CONFIGURATION.md](docs/08_SETTINGS_CONFIGURATION.md)**: Guide to all parameters in `utils/settings.py`.
*   **[docs/09_LOGGING_DEBUGGING.md](docs/09_LOGGING_DEBUGGING.md)**: Information on logging and troubleshooting.

## 6. Current Status & Future Work

*   **Current Status**: The bot is functional with the features listed above. Core logic for data fetching, aggregation, indicator calculation, strategy assessment (confluence-based), signal generation (with R/R managed TP/SL), and GUI display (including live chart, provisional indicators, and order book liquidity) is implemented.
*   **Areas for Future Refinement**:
    *   **Strategy Optimization**: The "Golden Strategy" confluence rules and parameters in `_generate_signal` offer a starting point. Extensive backtesting and forward testing are needed to tune these for optimal performance, adjust weights, and potentially add more sophisticated conditions or adaptive logic.
    *   **Advanced Fibonacci/Liquidity Analysis**: The "circular/cascade Fibonacci" is not yet implemented. Liquidity analysis could be further enhanced (e.g., looking at order book imbalance, decay, spoofing).
    *   **Risk Management**: More advanced risk management rules (e.g., position sizing, daily loss limits, max concurrent trades if it were to manage trades).
    *   **Order Execution**: Currently, the bot only generates signals. Actual order placement logic for Binance would be a major addition.
    *   **Error Resilience**: Further hardening against all types of API errors, network issues, and unexpected data.
    *   **Chart Interactivity**: Adding zoom/pan, drawing tools, or more overlay indicators to the chart.
    *   **Unit & Integration Testing**: Expanding the test suite for better code coverage and reliability.

---
*This project was developed with the assistance of an AI model.*
