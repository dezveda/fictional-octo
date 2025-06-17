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
    pyinstaller --noconfirm --onefile --windowed --icon="path/to/your/icon.ico" --add-data "trading_bot/utils:trading_bot/utils" trading_bot/main.py --name GoldenStrategyBot
    ```

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
    *   **Hidden Imports:** PyInstaller might not always detect all necessary imports, especially for libraries like CustomTkinter or dynamically loaded ones. You might need to use the `--hidden-import` option in PyInstaller.
    *   **Data Files/Assets:** As mentioned, ensure all necessary data files (like `settings.py` or any UI assets) are correctly included using `--add-data` or by copying them to the `dist` folder post-build. The paths used in your code to access these files might need to be adjusted to work correctly when running as a bundled executable (e.g., using helper functions to determine the correct path when running as a bundled executable).
    *   **Anti-virus Software:** Sometimes, executables created by PyInstaller can be flagged by anti-virus software (false positives).

Always test the packaged executable thoroughly on a clean Windows environment (ideally one that doesn't have Python installed) to ensure it runs as expected.
