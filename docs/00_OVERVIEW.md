# 00 Overview of the Minimalist Trading Bot

## 1. Project Purpose and Goal

This project is a Python-based trading bot designed for analyzing the BTC/USDT market and generating potential trading signals. The primary goal is to create a functional bot that adheres to principles of minimalism, modularity, and efficiency, avoiding overly complex dependencies or "black box" AI solutions.

The bot focuses on:
-   Real-time data ingestion for BTC/USDT.
-   Calculation of a suite of standard technical indicators from scratch.
-   Implementation of a user-defined "Golden Strategy" that combines these indicators and other market analyses (Pivots, Fibonacci, Order Book Liquidity) to identify trading opportunities.
-   Operation on a configurable higher timeframe (e.g., 1-hour bars) for strategic decision-making, while processing more granular data (e.g., 1-minute klines) to build these higher-timeframe bars and provide dynamic chart updates.
-   A minimalist but informative and visually appealing Graphical User Interface (GUI) for monitoring market data, indicators, strategy state, and generated signals.

## 2. Core Functionalities

The bot encompasses the following core functionalities:

*   **Real-time Data Fetching**: Connects to Binance API (via `python-binance`) to stream live kline data (e.g., 1-minute intervals for BTC/USDT) and live order book depth information. It also fetches historical kline data on startup to pre-fill the strategy's required history.
*   **Indicator Calculation**: Implements a comprehensive set of technical indicators (MACD, RSI, Supertrend, KDJ, Parabolic SAR, Williams Fractal, Momentum, ATR) using custom calculations (primarily with Pandas and NumPy), avoiding external libraries like TA-Lib.
*   **Strategy Engine ("Golden Strategy")**:
    *   Aggregates base kline data (e.g., 1-minute) into a higher, configurable strategy timeframe (e.g., 1-hour).
    *   Calculates indicators based on these aggregated bars.
    *   Performs specialized analyses:
        *   Daily Pivot Points.
        *   Standard Fibonacci Retracements based on detected swing points.
        *   Liquidity Analysis based on real-time order book depth (significant bid/ask levels).
    *   A sophisticated signal generation logic (`_generate_signal`) uses helper methods to assess qualitative states from all indicators and analyses. It then looks for a confluence of these states to generate LONG or SHORT trading signals with fixed entry, Take Profit (TP), and Stop Loss (SL) levels. TP/SL levels are primarily ATR-based with risk/reward considerations.
*   **Graphical User Interface (GUI)**:
    *   Built with CustomTkinter for a modern and minimalist look.
    *   Displays:
        *   Live BTC/USDT price (updates with each base kline).
        *   A candlestick chart (using `mplfinance`) for the strategy timeframe (e.g., 1-hour candles), featuring a live-updating last candle and a price action label.
        *   Key strategy indicators, updated provisionally with each base kline for the forming aggregated bar, and finalized when an aggregated bar closes.
        *   Signal Consolidation Percentage: Shows how close current conditions (on the forming aggregated bar) are to meeting criteria for a LONG or SHORT signal.
        *   Actual trading signals when generated.
        *   Real-time order book liquidity information (top significant bids/asks).
        *   A detailed status bar for logs and messages from all modules.
*   **Configuration**: Key parameters for data fetching, strategy timeframes, indicator periods, strategy logic thresholds, and GUI are managed via a central `utils/settings.py` file.

## 3. Key Design Principles

*   **Minimalism**: Avoiding unnecessary complexity in code, dependencies, and UI. Focus on core functionality and efficiency. Explicitly avoids TensorFlow, Docker Desktop.
*   **Modularity**: Code is organized into distinct modules for data fetching, indicator calculation, strategy logic, GUI, and utilities, promoting separation of concerns and maintainability.
*   **Granularity & Responsiveness**: While strategy decisions are on a higher timeframe, the system processes more granular data (e.g., 1-minute klines, live order book updates) to provide responsive chart updates, live price display, and provisional indicator states.
*   **Custom Implementation**: Core analytical components (indicators, specific analyses) are implemented from scratch where feasible to reduce reliance on large external libraries and allow for tailored logic.
*   **User Feedback Driven**: The bot's features, such as the higher-timeframe strategy core with more granular live updates and detailed GUI feedback, have evolved based on specific user requirements and iterations.

## 4. High-Level Architecture

The system generally flows as follows:

1.  **`DataFetcher`**: Connects to Binance for kline and order book data streams. Provides raw data via callbacks.
2.  **`BotApplication` (`main.py`)**: Orchestrates all modules. Initializes components, manages the historical data pre-fill, and routes live data from `DataFetcher` to `GoldenStrategy`. It also manages the GUI lifecycle and thread safety for UI updates.
3.  **`GoldenStrategy`**:
    *   Receives base kline data, aggregates it to the `STRATEGY_TIMEFRAME`.
    *   Receives order book data.
    *   Calculates indicators (via `Indicators/calculator.py`) on aggregated data.
    *   Performs specialized analyses (Pivots, Fibonacci, Liquidity via `strategy/*.py` submodules).
    *   Generates trading signals or consolidation percentages based on its "Golden Strategy" logic.
    *   Sends data (indicators, signals, chart data, liquidity info) to the GUI via callbacks.
4.  **`GUI` (`gui/main_window.py`)**: Displays all information received from `GoldenStrategy` and `DataFetcher` in real-time or near real-time.
5.  **`Utils/Settings`**: Provides global configuration.
6.  **`Indicators/Calculator`**: Standalone module for all indicator math.

This overview provides a starting point for understanding the project. Subsequent documents in this `docs/` folder will delve into each component in more detail.
