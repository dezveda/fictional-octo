# Deploying and Running the Trading Bot

This document provides instructions on how to set up and run the Python trading bot, and how to package it as a standalone executable for Windows 10.

## Prerequisites

*   Python 3.8+ installed on your Windows 10 system.
*   Access to an internet connection for fetching market data.

## Setup and Running from Source

1.  **Clone the Repository (if applicable) or Download Source Files:**
    Ensure you have all the bot's source files in a directory on your computer. The main application directory is `trading_bot/`.

2.  **Create a Virtual Environment (Recommended):**
    Open a command prompt or PowerShell in the root directory of the project (where this `DEPLOYMENT.md` file is located).
    ```bash
    python -m venv venv
    ```

3.  **Activate the Virtual Environment:**
    ```bash
    .\venv\Scripts\activate
    ```
    Your command prompt should now indicate that you are in the `(venv)` environment.

4.  **Install Dependencies:**
    Install all required Python packages using the `requirements.txt` file located in the `trading_bot` directory.
    ```bash
    pip install -r trading_bot/requirements.txt
    ```

5.  **Run the Bot:**
    Execute the main application script:
    ```bash
    python trading_bot/main.py
    ```
    The bot's GUI should appear, and it will start fetching data and attempting to generate signals. Status messages will be displayed in the GUI's status bar and potentially in the console.

6.  **Configuration (Optional):**
    Key parameters for indicators and strategy can be adjusted in `trading_bot/utils/settings.py`.

## Packaging as a Standalone Executable (Windows 10)

To create a standalone `.exe` file that can run on Windows without requiring a Python installation (though some shared libraries might still be needed if not fully static), you can use tools like PyInstaller.

1.  **Install PyInstaller:**
    If you haven't already, install PyInstaller in your virtual environment:
    ```bash
    pip install pyinstaller
    ```

2.  **Run PyInstaller:**
    Navigate to the root directory of the project in your command prompt (where `trading_bot` folder is located).
    A common PyInstaller command for a GUI application like this would be:
    ```bash
    # On Windows (use ';' as path separator for --add-data):
    pyinstaller --noconfirm --onefile --windowed --icon="path/to/your/icon.ico" --add-data "trading_bot\\utils;trading_bot\\utils" trading_bot\\main.py --name GoldenStrategyBot
    # On Linux/macOS (use ':' as path separator for --add-data):
    # pyinstaller --noconfirm --onefile --windowed --icon="path/to/your/icon.ico" --add-data "trading_bot/utils:trading_bot/utils" trading_bot/main.py --name GoldenStrategyBot
    ```
    **Note on `--add-data` path separator**: PyInstaller uses `os.pathsep` (which is `;` on Windows, `:` on Linux/macOS) to separate multiple `--add-data` arguments if you list them one after another like `--add-data src1;dst1 --add-data src2;dst2`. However, for a single `source:destination` pair *within one* `--add-data` argument, the separator between `source` and `destination` is usually `:`, but PyInstaller is often flexible. For clarity and cross-platform PyInstaller CLI usage, the `Path(source).resolve():Path(destination_in_bundle).resolve()` syntax in spec files is more robust, but for CLI, providing the OS-specific version is safer in documentation. The example above clarifies for Windows.

    **Explanation of options:**
    *   `--noconfirm`: Overwrites previous builds without asking.
    *   `--onefile`: Creates a single executable file (can sometimes have slower startup). For multiple files (faster startup, but a folder), omit this.
    *   `--windowed`: Prevents a command console window from appearing when the GUI app runs. Use `--console` or omit for debugging.
    *   `--icon="path/to/your/icon.ico"`: (Optional) Specify a custom icon for your executable.
    *   `--add-data "source:destination"`: This is crucial for including non-code files or folders.
        *   `trading_bot/utils:trading_bot/utils` ensures the `settings.py` file (and any other files in `utils`) is included in a way that the application can find it. The path separator is system-dependent (`;` for Windows, `:` for Linux/macOS). PyInstaller often handles this well with `os.pathsep`.
        *   If CustomTkinter uses image assets internally that PyInstaller doesn't automatically find, you might need additional `--add-data` flags for those (e.g., pointing to CustomTkinter's assets folder within your `site-packages`). This can be a common packaging challenge.
    *   `trading_bot/main.py`: This is your main script.
    *   `--name GoldenStrategyBot`: (Optional) Specify the name for your executable and build folders.

3.  **Locate the Executable:**
    After PyInstaller finishes, you will find the executable in a `dist` folder created in your project's root directory (e.g., `dist/GoldenStrategyBot.exe`).

4.  **Potential Challenges with Packaging:**
    *   **Hidden Imports:** PyInstaller might not always detect all necessary imports, especially for complex libraries like `pandas`, `numpy`, `matplotlib`, `customtkinter`, or `mplfinance`. If you encounter `ModuleNotFoundError` when running the packaged executable, you might need to use the `--hidden-import` option in PyInstaller for the missing sub-modules. Common examples could be specific `pandas` or `numpy` internals, or parts of `customtkinter`.
        *Example*: `pyinstaller ... --hidden-import="pandas._libs.tslibs.timestamps"`
    *   **Data Files/Assets:**
        *   **`utils/settings.py`**: The provided `--add-data "trading_bot/utils:trading_bot/utils"` (or `trading_bot\utils;trading_bot\utils` on Windows for PyInstaller path separator) is essential for `settings.py`.
        *   **CustomTkinter Assets**: CustomTkinter themes and images are usually installed within its `site-packages` directory. If the packaged application has missing themes or visual elements, you may need to find the `customtkinter/assets` folder in your Python environment's `site-packages` and add it using `--add-data`.
            *Example path to find*: `venv\Lib\site-packages\customtkinter\assets`
            *Example `--add-data`*: `--add-data "venv/Lib/site-packages/customtkinter/assets:customtkinter/assets"`
        *   **Matplotlib/mplfinance Data**: Matplotlib usually bundles its necessary data (`matplotlibrc`, fonts, etc.). `mplfinance` uses Matplotlib's infrastructure. If specific custom styles or fonts were used directly as files (not the case in this project, as styles were defined in code), they would also need to be added.
    *   **Anti-virus Software:** Executables created by PyInstaller can sometimes be flagged by anti-virus software (false positives). This is a common issue with PyInstaller bundles.
    *   **Path Issues in Code**: Ensure that any file paths used in the code (e.g., for loading icons, though not currently used, or future features like saving reports) are relative or use functions to determine correct paths when running as a bundled executable (e.g., using `sys._MEIPASS` for temporary PyInstaller paths, or `os.path.dirname(sys.executable)` for files next to the .exe). Currently, `settings.py` is accessed via module import, which PyInstaller handles if the `utils` folder is correctly added as data.
