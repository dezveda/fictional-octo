import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import os
import json
import tempfile
import shutil # For cleaning up temp directories if needed and TemporaryDirectory doesn't suffice

# Module to be tested
from trading_bot.data_fetcher import fetcher

# Functions and class from the module
# These will be accessible via fetcher.FunctionName or fetcher.ClassName
# _get_kline_filepath, save_klines, load_klines, DataFetcher, KLINE_DATA_DIR (original)


# Sample data for tests
SAMPLE_KLINES_DATA = [
    {'t': 1678886400000, 'o': 100.0, 'h': 110.0, 'l': 90.0, 'c': 105.0, 'v': 1000.0},
    {'t': 1678886460000, 'o': 105.0, 'h': 115.0, 'l': 100.0, 'c': 110.0, 'v': 1200.0},
    {'t': 1678886520000, 'o': 110.0, 'h': 120.0, 'l': 105.0, 'c': 115.0, 'v': 1100.0},
]

# Raw kline data from Binance API (list of lists)
SAMPLE_RAW_API_KLINE = [
    1678886580000,  # Kline open time
    "115.0",        # Open price
    "125.0",        # High price
    "110.0",        # Low price
    "120.0",        # Close price
    "1300.0",       # Volume
    1678886639999,  # Kline close time
    "150000.0",     # Quote asset volume
    100,            # Number of trades
    "700.0",        # Taker buy base asset volume
    "80000.0",      # Taker buy quote asset volume
    "0"             # Unused field
]
# Corresponding processed kline
PROCESSED_FROM_SAMPLE_RAW = {'t': 1678886580000, 'o': 115.0, 'h': 125.0, 'l': 110.0, 'c': 120.0, 'v': 1300.0}


class TestKlineStorageFunctions(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for file operations
        self.test_dir = tempfile.TemporaryDirectory()
        # Override KLINE_DATA_DIR within the fetcher module for these tests
        self.patcher_kline_data_dir = patch.object(fetcher, 'KLINE_DATA_DIR', self.test_dir.name)
        self.mock_kline_data_dir = self.patcher_kline_data_dir.start()

        # Also, ensure logger isn't too verbose or problematic during tests
        # You might want to patch 'fetcher.logger' if it causes issues
        self.patcher_logger = patch.object(fetcher, 'logger', MagicMock())
        self.mock_logger = self.patcher_logger.start()


    def tearDown(self):
        # Stop the patchers
        self.patcher_kline_data_dir.stop()
        self.patcher_logger.stop()
        # Clean up the temporary directory
        self.test_dir.cleanup()

    def test_get_kline_filepath(self):
        symbol = "BTCUSDT"
        interval = "1h"
        expected_filename = f"{symbol.upper()}_{interval}.json"
        expected_path = os.path.join(self.mock_kline_data_dir, expected_filename)

        # Call the function from the fetcher module
        actual_path = fetcher._get_kline_filepath(symbol, interval)
        self.assertEqual(actual_path, expected_path)

    def test_save_and_load_klines_successful(self):
        filepath = os.path.join(self.mock_kline_data_dir, "test_klines.json")

        # Test saving
        save_success = fetcher.save_klines(filepath, SAMPLE_KLINES_DATA)
        self.assertTrue(save_success)
        self.assertTrue(os.path.exists(filepath))

        # Test loading
        loaded_data = fetcher.load_klines(filepath)
        self.assertEqual(loaded_data, SAMPLE_KLINES_DATA)

    def test_save_klines_empty_data(self):
        filepath = os.path.join(self.mock_kline_data_dir, "empty_klines.json")
        save_success = fetcher.save_klines(filepath, [])
        self.assertTrue(save_success)
        self.assertTrue(os.path.exists(filepath))

        loaded_data = fetcher.load_klines(filepath)
        self.assertEqual(loaded_data, [])

    def test_save_klines_io_error(self):
        # Make filepath invalid by trying to save to a path that is a directory
        with patch('builtins.open', mock_open()) as mocked_file:
            mocked_file.side_effect = IOError("Test IOError")
            save_success = fetcher.save_klines("/some/invalid/path.json", SAMPLE_KLINES_DATA)
            self.assertFalse(save_success)
            fetcher.logger.error.assert_called() # Check if logger.error was called

    def test_load_klines_non_existent_file(self):
        filepath = os.path.join(self.mock_kline_data_dir, "non_existent.json")
        loaded_data = fetcher.load_klines(filepath)
        self.assertEqual(loaded_data, [])
        # Check log message (optional, can make tests brittle)
        # fetcher.logger.info.assert_any_call(f"[KlinesStorage] File not found: {filepath}. Returning empty list.")


    def test_load_klines_invalid_json(self):
        filepath = os.path.join(self.mock_kline_data_dir, "invalid_json.json")
        with open(filepath, 'w') as f:
            f.write("this is not json")

        loaded_data = fetcher.load_klines(filepath)
        self.assertEqual(loaded_data, [])
        fetcher.logger.error.assert_called() # Check if logger.error was called for JSONDecodeError

    def test_load_klines_io_error(self):
        filepath = os.path.join(self.mock_kline_data_dir, "io_error_test.json")
        # Create the file first, so os.path.exists is true
        with open(filepath, 'w') as f:
            json.dump(SAMPLE_KLINES_DATA, f)

        with patch('builtins.open', mock_open()) as mocked_file:
            mocked_file.side_effect = IOError("Test IOError on load")
            loaded_data = fetcher.load_klines(filepath)
            self.assertEqual(loaded_data, [])
            fetcher.logger.error.assert_called()


@patch.object(fetcher, 'AsyncClient', MagicMock()) # Mock AsyncClient for all tests in this class
class TestDataFetcherPersistence(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        # Patch KLINE_DATA_DIR in the 'fetcher' module where it's used by the functions
        self.patcher_kline_data_dir = patch.object(fetcher, 'KLINE_DATA_DIR', self.test_dir.name)
        self.mock_kline_data_dir = self.patcher_kline_data_dir.start()

        self.patcher_logger = patch.object(fetcher, 'logger', MagicMock())
        self.mock_logger = self.patcher_logger.start()

        # Mock the Binance AsyncClient methods that would be called
        # We can refine these mocks per test method if needed
        self.mock_binance_client = MagicMock()
        fetcher.AsyncClient.create = MagicMock(return_value=self.mock_binance_client)

        # Initialize DataFetcher instance
        # It will try to create an AsyncClient, which is now mocked
        self.fetcher_instance = fetcher.DataFetcher(
            symbol="BTCUSDT",
            fetch_interval_str="1m" # used by _process_kline_message for filename
        )
        # Explicitly set client and bsm if _initialize_client is not called or needs to be bypassed
        self.fetcher_instance.client = self.mock_binance_client
        self.fetcher_instance.bsm = MagicMock()


    def tearDown(self):
        self.patcher_kline_data_dir.stop()
        self.patcher_logger.stop()
        self.test_dir.cleanup()

    # Helper to run async functions
    def _run_async(self, coro):
        return unittest.IsolatedAsyncioTestCase().run_until_complete(coro)

    # --- Tests for fetch_historical_klines ---

    @patch.object(fetcher, 'save_klines', wraps=fetcher.save_klines) # Wrap to spy and still execute
    @patch.object(fetcher, 'load_klines', wraps=fetcher.load_klines)
    async def test_fetch_historical_no_cache_api_returns_data(self, mock_load_klines, mock_save_klines):
        symbol_to_fetch = "ETHUSDT"
        interval_api_const = fetcher.AsyncClient.KLINE_INTERVAL_1HOUR # "1h"

        # API mock to return some data
        self.fetcher_instance.client.get_historical_klines = MagicMock(
            return_value=[SAMPLE_RAW_API_KLINE] # one raw kline
        )

        expected_processed_kline = PROCESSED_FROM_SAMPLE_RAW

        result = await self.fetcher_instance.fetch_historical_klines(
            symbol_to_fetch, interval_api_const, lookback_start_str="1 day ago"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], expected_processed_kline)

        # Check that load_klines was called (should find no file initially)
        expected_filepath = fetcher._get_kline_filepath(symbol_to_fetch, "1h") # Map const to str
        mock_load_klines.assert_called_once_with(expected_filepath)

        # Check that save_klines was called with the correct data
        mock_save_klines.assert_called_once_with(expected_filepath, [expected_processed_kline])

        # Verify API call parameters (optional, but good for confidence)
        self.fetcher_instance.client.get_historical_klines.assert_called_once_with(
            symbol=symbol_to_fetch,
            interval=interval_api_const,
            start_str="1 day ago",
            limit=None
        )

    @patch.object(fetcher, 'save_klines', wraps=fetcher.save_klines)
    @patch.object(fetcher, 'load_klines') # Fully mock load_klines to control cache state
    async def test_fetch_historical_cache_exists_api_returns_newer_data(self, mock_load_klines, mock_save_klines):
        symbol_to_fetch = "BTCUSDT"
        interval_str = "5m"
        interval_api_const = fetcher.AsyncClient.KLINE_INTERVAL_5MINUTE

        # Simulate cache having one kline
        cached_kline = SAMPLE_KLINES_DATA[0] # {'t': 1678886400000, ...}
        mock_load_klines.return_value = [cached_kline]

        # API mock to return a newer kline
        # SAMPLE_RAW_API_KLINE has t=1678886580000
        self.fetcher_instance.client.get_historical_klines = MagicMock(
            return_value=[SAMPLE_RAW_API_KLINE]
        )

        expected_merged_data = [cached_kline, PROCESSED_FROM_SAMPLE_RAW]

        result = await self.fetcher_instance.fetch_historical_klines(
            symbol_to_fetch, interval_api_const # No start_str/limit, should use cache
        )

        self.assertEqual(result, expected_merged_data)

        expected_filepath = fetcher._get_kline_filepath(symbol_to_fetch, interval_str)
        mock_load_klines.assert_called_once_with(expected_filepath)
        mock_save_klines.assert_called_once_with(expected_filepath, expected_merged_data)

        # API should be called with start_str derived from cached_kline['t']
        self.fetcher_instance.client.get_historical_klines.assert_called_once_with(
            symbol=symbol_to_fetch,
            interval=interval_api_const,
            start_str=str(cached_kline['t']), # Fetch from last kline's time (inclusive)
            limit=None
        )

    @patch.object(fetcher, 'save_klines') # Mock save, not crucial to check its internals here
    @patch.object(fetcher, 'load_klines')
    async def test_fetch_historical_cache_exists_api_no_new_data(self, mock_load_klines, mock_save_klines):
        symbol_to_fetch = "LTCUSDT"
        interval_str = "15m"
        interval_api_const = fetcher.AsyncClient.KLINE_INTERVAL_15MINUTE

        cached_data = SAMPLE_KLINES_DATA[:2]
        mock_load_klines.return_value = cached_data

        # API mock returns no new klines (empty list)
        self.fetcher_instance.client.get_historical_klines = MagicMock(return_value=[])

        result = await self.fetcher_instance.fetch_historical_klines(
            symbol_to_fetch, interval_api_const
        )

        self.assertEqual(result, cached_data) # Should return data from cache

        expected_filepath = fetcher._get_kline_filepath(symbol_to_fetch, interval_str)
        mock_load_klines.assert_called_once_with(expected_filepath)
        # save_klines should still be called to re-save the (unchanged) data
        mock_save_klines.assert_called_once_with(expected_filepath, cached_data)

        self.fetcher_instance.client.get_historical_klines.assert_called_once_with(
            symbol=symbol_to_fetch,
            interval=interval_api_const,
            start_str=str(cached_data[-1]['t']),
            limit=None
        )

    @patch.object(fetcher, 'save_klines', wraps=fetcher.save_klines)
    @patch.object(fetcher, 'load_klines')
    async def test_fetch_historical_cache_exists_api_returns_overlapping_data(self, mock_load_klines, mock_save_klines):
        symbol_to_fetch = "XRPUSDT"
        interval_str = "30m"
        interval_api_const = fetcher.AsyncClient.KLINE_INTERVAL_30MINUTE

        # Cache has first kline
        cached_kline = SAMPLE_KLINES_DATA[0].copy() # t: 1678886400000
        mock_load_klines.return_value = [cached_kline]

        # API returns a kline that is the *same* as the cached one (by timestamp) but maybe different data,
        # and one new kline.
        # SAMPLE_KLINES_DATA[0] is {'t': 1678886400000, 'o': 100.0, 'h': 110.0, 'l': 90.0, 'c': 105.0, 'v': 1000.0}
        # Let's make a raw version of this with a modified close price
        overlapping_raw_kline = [
            1678886400000, "100.0", "110.0", "90.0", "106.0", "1001.0", 1678886459999, "Q", 1, "T", "T", "I"
        ]
        new_raw_kline = SAMPLE_RAW_API_KLINE # t: 1678886580000

        self.fetcher_instance.client.get_historical_klines = MagicMock(
            return_value=[overlapping_raw_kline, new_raw_kline]
        )

        # Expected: the overlapping kline from API should replace the one from cache
        expected_kline1_updated = {'t': 1678886400000, 'o': 100.0, 'h': 110.0, 'l': 90.0, 'c': 106.0, 'v': 1001.0}
        expected_kline2_new = PROCESSED_FROM_SAMPLE_RAW
        expected_merged_data = [expected_kline1_updated, expected_kline2_new]

        result = await self.fetcher_instance.fetch_historical_klines(
            symbol_to_fetch, interval_api_const
        )

        self.assertEqual(result, expected_merged_data)

        expected_filepath = fetcher._get_kline_filepath(symbol_to_fetch, interval_str)
        mock_load_klines.assert_called_once_with(expected_filepath)
        mock_save_klines.assert_called_once_with(expected_filepath, expected_merged_data)

        self.fetcher_instance.client.get_historical_klines.assert_called_once_with(
            symbol=symbol_to_fetch,
            interval=interval_api_const,
            start_str=str(cached_kline['t']),
            limit=None
        )

    @patch.object(fetcher, 'save_klines') # Mock save, not expecting it to be called if API fails badly
    @patch.object(fetcher, 'load_klines')
    async def test_fetch_historical_api_error(self, mock_load_klines, mock_save_klines):
        symbol_to_fetch = "ADABNB"
        interval_str = "2h"
        interval_api_const = fetcher.AsyncClient.KLINE_INTERVAL_2HOUR

        # Simulate some cached data
        cached_data = [SAMPLE_KLINES_DATA[0]]
        mock_load_klines.return_value = cached_data

        # API mock to raise an exception
        self.fetcher_instance.client.get_historical_klines = MagicMock(side_effect=Exception("Binance API Error"))

        result = await self.fetcher_instance.fetch_historical_klines(
            symbol_to_fetch, interval_api_const
        )

        # Should return the cached data if API fails
        self.assertEqual(result, cached_data)

        expected_filepath = fetcher._get_kline_filepath(symbol_to_fetch, interval_str)
        mock_load_klines.assert_called_once_with(expected_filepath)
        mock_save_klines.assert_not_called() # Save should not happen if API fetch fails
        self.mock_logger.error.assert_called() # Check for error logging


    # --- Tests for _process_kline_message ---

    @patch.object(fetcher, 'load_klines')
    @patch.object(fetcher, 'save_klines')
    def test_process_kline_closed_no_cache(self, mock_save_klines, mock_load_klines):
        mock_load_klines.return_value = [] # No cache

        # self.fetcher_instance.symbol is "BTCUSDT"
        # self.fetcher_instance.fetch_interval_str is "1m"

        kline_msg_data = {
            't': 1678886700000, 'o': "200", 'h': "201", 'l': "199", 'c': "200.5", 'v': "50",
            'x': True, # Kline is closed
            's': self.fetcher_instance.symbol, 'i': self.fetcher_instance.fetch_interval_str
        }
        msg = {'e': 'kline', 'k': kline_msg_data}

        self.fetcher_instance._process_kline_message(msg) # This is a synchronous method

        expected_filepath = fetcher._get_kline_filepath(
            self.fetcher_instance.symbol, self.fetcher_instance.fetch_interval_str
        )
        mock_load_klines.assert_called_once_with(expected_filepath)

        expected_saved_kline = {
            't': 1678886700000, 'o': 200.0, 'h': 201.0, 'l': 199.0, 'c': 200.5, 'v': 50.0
        }
        mock_save_klines.assert_called_once_with(expected_filepath, [expected_saved_kline])

    @patch.object(fetcher, 'load_klines')
    @patch.object(fetcher, 'save_klines')
    def test_process_kline_closed_cache_exists_append(self, mock_save_klines, mock_load_klines):
        cached_klines = [SAMPLE_KLINES_DATA[0].copy()] # t: 1678886400000
        mock_load_klines.return_value = cached_klines

        kline_msg_data = {
            't': 1678886700000, 'o': "200", 'h': "201", 'l': "199", 'c': "200.5", 'v': "50", 'x': True,
            's': self.fetcher_instance.symbol, 'i': self.fetcher_instance.fetch_interval_str
        }
        msg = {'e': 'kline', 'k': kline_msg_data}

        self.fetcher_instance._process_kline_message(msg)

        expected_filepath = fetcher._get_kline_filepath(
            self.fetcher_instance.symbol, self.fetcher_instance.fetch_interval_str
        )

        new_kline_processed = {
            't': 1678886700000, 'o': 200.0, 'h': 201.0, 'l': 199.0, 'c': 200.5, 'v': 50.0
        }
        expected_data_to_save = cached_klines + [new_kline_processed]
        mock_save_klines.assert_called_once_with(expected_filepath, expected_data_to_save)

    @patch.object(fetcher, 'load_klines')
    @patch.object(fetcher, 'save_klines')
    def test_process_kline_closed_cache_exists_update_last(self, mock_save_klines, mock_load_klines):
        # Last kline in cache has same timestamp as incoming
        last_cached_kline_ts = 1678886700000
        cached_klines = [
            SAMPLE_KLINES_DATA[0].copy(), # An older kline
            {'t': last_cached_kline_ts, 'o': 190.0, 'h': 195.0, 'l': 185.0, 'c': 188.0, 'v': 40.0} # This one will be updated
        ]
        mock_load_klines.return_value = cached_klines

        kline_msg_data = { # Incoming kline with same timestamp as last cached one
            't': last_cached_kline_ts, 'o': "190", 'h': "196", 'l': "185", 'c': "195.5", 'v': "45", 'x': True,
            's': self.fetcher_instance.symbol, 'i': self.fetcher_instance.fetch_interval_str
        }
        msg = {'e': 'kline', 'k': kline_msg_data}

        self.fetcher_instance._process_kline_message(msg)

        expected_filepath = fetcher._get_kline_filepath(
            self.fetcher_instance.symbol, self.fetcher_instance.fetch_interval_str
        )

        updated_kline_processed = {
            't': last_cached_kline_ts, 'o': 190.0, 'h': 196.0, 'l': 185.0, 'c': 195.5, 'v': 45.0
        }
        expected_data_to_save = [cached_klines[0], updated_kline_processed] # First kline unchanged, second updated
        mock_save_klines.assert_called_once_with(expected_filepath, expected_data_to_save)

    @patch.object(fetcher, 'load_klines')
    @patch.object(fetcher, 'save_klines')
    def test_process_kline_not_closed(self, mock_save_klines, mock_load_klines):
        kline_msg_data = {
            't': 1678886700000, 'o': "200", 'h': "201", 'l': "199", 'c': "200.5", 'v': "50",
            'x': False, # Kline is NOT closed
            's': self.fetcher_instance.symbol, 'i': self.fetcher_instance.fetch_interval_str
        }
        msg = {'e': 'kline', 'k': kline_msg_data}

        self.fetcher_instance._process_kline_message(msg)

        mock_load_klines.assert_not_called()
        mock_save_klines.assert_not_called()


if __name__ == '__main__':
    unittest.main()
