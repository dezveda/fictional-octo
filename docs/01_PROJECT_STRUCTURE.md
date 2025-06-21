# 01 Project Structure

This document outlines the directory structure and the purpose of key files and folders within the Minimalist Trading Bot project.

## 1. Root Directory

The project root directory contains the main application folder, documentation, and configuration files:

```
/
|-- trading_bot/         # Main application source code
|-- docs/                # Detailed documentation files (this folder)
|-- .gitignore           # Specifies intentionally untracked files that Git should ignore
|-- DEPLOYMENT.md        # Instructions for setup, running, and packaging the bot
|-- README.md            # Main project readme, introduction, and links
|-- Errorlog.md          # (If present) User-provided error logs for debugging
```

## 2. `trading_bot/` - Main Application Directory

This directory houses all the core Python source code for the bot, organized into modules.

```
trading_bot/
|-- __init__.py                   # Makes 'trading_bot' a Python package
|-- main.py                       # Main entry point of the application (BotApplication class)
|-- requirements.txt              # Lists Python package dependencies
|
|-- data_fetcher/
|   |-- __init__.py               # Makes 'data_fetcher' a sub-package
|   |-- fetcher.py                # Contains DataFetcher class for Binance kline and order book data
|
|-- gui/
|   |-- __init__.py               # Makes 'gui' a sub-package
|   |-- main_window.py            # Contains App class (CustomTkinter GUI) for the user interface
|
|-- indicators/
|   |-- __init__.py               # Makes 'indicators' a sub-package
|   |-- calculator.py             # Contains functions for all technical indicator calculations
|
|-- strategy/
|   |-- __init__.py               # Makes 'strategy' a sub-package
|   |-- gold_strategy.py          # Contains GoldenStrategy class, core strategy logic, signal generation
|   |-- fibonacci_analysis.py     # Module for Fibonacci retracement analysis
|   |-- liquidity_analysis.py     # Module for order book depth based liquidity analysis
|   |-- pivot_points.py           # Module for daily Pivot Point calculations
|
|-- utils/
    |-- __init__.py               # Makes 'utils' a sub-package
    |-- settings.py               # Contains global settings and configurable parameters for the bot
```

### Key Files and Their Roles:

*   **`trading_bot/__init__.py`**: Initializes the `trading_bot` directory as a Python package, allowing modules within it to be imported using `trading_bot.module_name`.

*   **`trading_bot/main.py`**:
    *   The main executable script to run the application.
    *   Contains the `BotApplication` class which orchestrates the GUI, `DataFetcher`, and `GoldenStrategy`.
    *   Handles application startup, initialization of components, threading for asynchronous operations (like data fetching), and graceful shutdown.

*   **`trading_bot/requirements.txt`**:
    *   Lists all external Python libraries required by the project (e.g., `python-binance`, `pandas`, `numpy`, `customtkinter`, `matplotlib`, `mplfinance`).
    *   Used for setting up the environment via `pip install -r trading_bot/requirements.txt`.

*   **`trading_bot/data_fetcher/__init__.py`**: Makes `data_fetcher` a package.
*   **`trading_bot/data_fetcher/fetcher.py`**:
    *   Defines the `DataFetcher` class.
    *   Responsible for connecting to Binance API via WebSockets.
    *   Fetches live kline data (e.g., 1-minute) for the specified symbol.
    *   Fetches live order book depth data (partial book snapshots).
    *   Fetches historical kline data on startup for strategy pre-fill.
    *   Provides data to other modules via callbacks.
    *   Manages local order book cache.

*   **`trading_bot/gui/__init__.py`**: Makes `gui` a package.
*   **`trading_bot/gui/main_window.py`**:
    *   Defines the `App` class, which is the main GUI window built using CustomTkinter.
    *   Responsible for all UI elements: price display, candlestick chart (using Matplotlib/mplfinance), indicator display, signal display, liquidity information panel, and status bar.
    *   Contains methods to update these UI elements based on data received from callbacks.

*   **`trading_bot/indicators/__init__.py`**: Makes `indicators` a package.
*   **`trading_bot/indicators/calculator.py`**:
    *   A collection of functions for calculating various technical indicators from scratch (MACD, RSI, Supertrend, KDJ, Parabolic SAR, Williams Fractal, Momentum, ATR).
    *   Uses `pandas` and `numpy` for numerical operations.

*   **`trading_bot/strategy/__init__.py`**: Makes `strategy` a package.
*   **`trading_bot/strategy/gold_strategy.py`**:
    *   Defines the `GoldenStrategy` class, which contains the core trading logic ("Estrategia de Oro").
    *   Aggregates base kline data (e.g., 1-minute) into a higher strategy timeframe (e.g., 1-hour).
    *   Calculates indicators based on these aggregated bars using `indicators.calculator`.
    *   Calls specialized analysis modules (`fibonacci_analysis.py`, `liquidity_analysis.py`, `pivot_points.py`).
    *   Contains helper methods (`_assess_*`) to evaluate market conditions based on indicators and analyses.
    *   The `_generate_signal` method uses a confluence of these assessments to produce LONG/SHORT trading signals or "consolidation percentage" information.
    *   Calculates Take Profit (TP) and Stop Loss (SL) levels for signals, including Risk/Reward ratio checks.
    *   Manages provisional updates for GUI display (live chart candle, live indicators/consolidation).
*   **`trading_bot/strategy/fibonacci_analysis.py`**:
    *   Contains logic for calculating Fibonacci retracement levels based on detected swing high/low points.
*   **`trading_bot/strategy/liquidity_analysis.py`**:
    *   Analyzes real-time order book depth snapshots (from `DataFetcher`) to identify significant liquidity levels (support/resistance based on large order quantities).
*   **`trading_bot/strategy/pivot_points.py`**:
    *   Calculates standard daily Pivot Points (P, S1-S3, R1-R3) based on the previous day's OHLC data.

*   **`trading_bot/utils/__init__.py`**: Makes `utils` a package.
*   **`trading_bot/utils/settings.py`**:
    *   Centralized configuration file for the application.
    *   Contains tunable parameters such as trading symbol, API settings (like request timeout), kline intervals, strategy timeframe, indicator periods, strategy logic thresholds (e.g., RSI levels, R/R ratio), and GUI display settings.

## 3. `docs/` - Detailed Documentation

This directory contains detailed markdown documentation for different aspects of the project, aimed at developers or advanced users (including other LLMs) for understanding the codebase.

*   **`00_OVERVIEW.md`**: This file (the one you are reading parts of).
*   **`01_PROJECT_STRUCTURE.md`**: This document.
*   **`02_DATA_FLOW.md`**: Explains how data moves between different modules.
*   *(Other files will detail specific modules like DataFetcher, Indicators, Strategy, GUI, etc.)*

This structure aims to keep the project organized and make it easier to navigate and understand the different components and their roles.
