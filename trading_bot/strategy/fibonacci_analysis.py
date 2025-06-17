import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Standard Fibonacci levels
RETRACEMENT_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
EXTENSION_LEVELS_PRIMARY = [0, 0.382, 0.618, 1.0, 1.382, 1.618] # Based on AB swing
EXTENSION_LEVELS_SECONDARY = [-0.618, -0.382, 0, 0.382, 0.618, 1.0, 1.382, 1.618, 2.0, 2.618] # Based on ABC, C is a retracement point

def find_significant_swings(prices_series, order=5):
    """
    Finds significant swing high and low points.
    A simple approach: a swing high is higher than `order` bars on either side.
    A swing low is lower than `order` bars on either side.
    This is similar to Williams Fractal but more generalized for swings.

    prices_series: pandas Series of prices (e.g., close, high, or low).
    order: number of bars on each side to check for significance.
    Returns: list of tuples (index, price, type: 'high' or 'low')
    """
    if not isinstance(prices_series, pd.Series):
        prices_series = pd.Series(prices_series)

    if len(prices_series) < 2 * order + 1:
        return []

    swings = []
    # Check for swing highs using high prices
    for i in range(order, len(prices_series) - order):
        is_swing_high = True
        for j in range(1, order + 1):
            if not (prices_series.iloc[i] >= prices_series.iloc[i-j] and \
                    prices_series.iloc[i] >= prices_series.iloc[i+j]):
                is_swing_high = False
                break
        if is_swing_high:
            # Ensure it's higher than immediate neighbors to avoid flat tops being multiple swings
            if not (prices_series.iloc[i] > prices_series.iloc[i-1] or prices_series.iloc[i] > prices_series.iloc[i+1]):
                 # If part of a flat top, only take the first instance or a defined point
                 # This simple check might still allow multiple points on perfectly flat tops.
                 # A more robust way is to check if previous point was also a swing of same value.
                 if i > order and prices_series.iloc[i] == prices_series.iloc[i-1] and any(s['index'] == prices_series.index[i-1] and s['type']=='high' for s in swings):
                     continue # Skip if previous bar was same high swing
            swings.append({'index': prices_series.index[i], 'price': prices_series.iloc[i], 'type': 'high'})

    # Check for swing lows using low prices (can use same series or a dedicated low_prices_series)
    for i in range(order, len(prices_series) - order):
        is_swing_low = True
        for j in range(1, order + 1):
            if not (prices_series.iloc[i] <= prices_series.iloc[i-j] and \
                    prices_series.iloc[i] <= prices_series.iloc[i+j]):
                is_swing_low = False
                break
        if is_swing_low:
            if not (prices_series.iloc[i] < prices_series.iloc[i-1] or prices_series.iloc[i] < prices_series.iloc[i+1]):
                if i > order and prices_series.iloc[i] == prices_series.iloc[i-1] and any(s['index'] == prices_series.index[i-1] and s['type']=='low' for s in swings):
                    continue
            swings.append({'index': prices_series.index[i], 'price': prices_series.iloc[i], 'type': 'low'})

    # Sort by index
    swings.sort(key=lambda x: x['index'])

    # Filter consecutive swings of the same type
    if not swings: return []
    filtered_swings = [swings[0]]
    for i in range(1, len(swings)):
        if swings[i]['type'] == filtered_swings[-1]['type']:
            # Keep the more extreme one if same type consecutively
            if swings[i]['type'] == 'high' and swings[i]['price'] > filtered_swings[-1]['price']:
                filtered_swings[-1] = swings[i]
            elif swings[i]['type'] == 'low' and swings[i]['price'] < filtered_swings[-1]['price']:
                filtered_swings[-1] = swings[i]
        else:
            filtered_swings.append(swings[i])

    return filtered_swings

def calculate_fib_levels(start_price, end_price, levels):
    """Calculates Fibonacci levels for a given swing."""
    diff = end_price - start_price
    return {level: start_price + diff * level for level in levels}


def analyze(all_kline_data_deque, on_status_update=None):
    """
    Analyzes Fibonacci retracement and extension levels based on recent major swings.
    all_kline_data_deque: A deque of kline dictionaries.
    on_status_update: Callback for status messages.

    This is a basic implementation focusing on Retracements from the last major swing.
    "Circular/Cascade/Concentric" Fibonacci are not standard and require specific definitions.
    """
    if on_status_update:
        on_status_update("[FibonacciAnalysis] Analyzing standard retracements/extensions (placeholder for circular/cascade)...")

    if len(all_kline_data_deque) < 15: # Need some data to find swings (e.g., 2*order+1 for order=5, or 2*3+1=7 for order=3)
        return {"status": "Not enough kline data for Fibonacci analysis."}

    # Use high prices for swing highs, low prices for swing lows
    high_prices = pd.Series([float(k['h']) for k in all_kline_data_deque], index=[k['t'] for k in all_kline_data_deque])
    low_prices = pd.Series([float(k['l']) for k in all_kline_data_deque], index=[k['t'] for k in all_kline_data_deque])
    close_prices = pd.Series([float(k['c']) for k in all_kline_data_deque], index=[k['t'] for k in all_kline_data_deque])


    swing_highs = find_significant_swings(high_prices, order=3)
    swing_lows = find_significant_swings(low_prices, order=3)

    all_swings = sorted(swing_highs + swing_lows, key=lambda x: x['index'])

    if not all_swings:
        return {"status": "No significant swings found for Fibonacci analysis."}

    filtered_swings = [all_swings[0]]
    for i in range(1, len(all_swings)):
        if all_swings[i]['type'] != filtered_swings[-1]['type']:
            filtered_swings.append(all_swings[i])
        else:
            if all_swings[i]['type'] == 'high' and all_swings[i]['price'] > filtered_swings[-1]['price']:
                filtered_swings[-1] = all_swings[i]
            elif all_swings[i]['type'] == 'low' and all_swings[i]['price'] < filtered_swings[-1]['price']:
                filtered_swings[-1] = all_swings[i]


    if len(filtered_swings) < 2:
        return {"status": "Not enough alternating swings to define a Fibonacci range."}

    last_swing = filtered_swings[-1]
    prev_swing = filtered_swings[-2]

    pointA = prev_swing
    pointB = last_swing

    current_price = close_prices.iloc[-1]
    retracements = {}

    trend_type = "unknown"
    # For retracements of the move from pointA to pointB:
    # If pointA is low and pointB is high (uptrend), levels are B - (B-A)*level_val or A + (B-A)*level_val
    # If pointA is high and pointB is low (downtrend), levels are B + (A-B)*level_val or A - (A-B)*level_val

    # The function calculate_fib_levels(start, end, levels) calculates: start + (end-start)*level
    # For an uptrend A(low) to B(high): start=A, end=B. Levels are A + (B-A)*level.
    # For a downtrend A(high) to B(low): start=A, end=B. Levels are A + (B-A)*level (B-A is negative).

    if pointB['type'] == 'high' and pointA['type'] == 'low': # Uptrend A->B
        trend_type = "uptrend"
        retracements = calculate_fib_levels(pointA['price'], pointB['price'], RETRACEMENT_LEVELS)
    elif pointB['type'] == 'low' and pointA['type'] == 'high': # Downtrend A->B
        trend_type = "downtrend"
        retracements = calculate_fib_levels(pointA['price'], pointB['price'], RETRACEMENT_LEVELS)
    else: # Should not happen if swings are alternating
        return {"status": "Last two swings are of the same type, cannot define range."}


    if on_status_update and retracements:
        on_status_update(f"[FibonacciAnalysis] Trend: {trend_type}. Swing A({pointA['type']}): {pointA['price']:.2f} at {pointA['index']}, B({pointB['type']}): {pointB['price']:.2f} at {pointB['index']}.")

    return {
        "status": "Fibonacci analysis complete.",
        "last_swing_pointA": pointA,
        "last_swing_pointB": pointB,
        "trend_type": trend_type,
        "retracement_levels_A_to_B": retracements,
        "current_price_for_context": current_price
    }

if __name__ == '__main__':
    print("Testing fibonacci_analysis.py...")

    def test_status_update_fib(message):
        print(f"FIB_TEST_STATUS: {message}")

    from collections import deque

    data_points = [
        {'t': 1, 'h': '105', 'l': '100', 'c': '101', 'o': '101', 'v': '100'},
        {'t': 2, 'h': '106', 'l': '101', 'c': '102', 'o': '102', 'v': '100'},
        {'t': 3, 'h': '107', 'l': '100', 'c': '103', 'o': '103', 'v': '100'}, # Actual swing low L=100 at t=3 (original was t=1)
        {'t': 4, 'h': '125', 'l': '120', 'c': '123', 'o': '123', 'v': '100'},
        {'t': 5, 'h': '126', 'l': '119', 'c': '122', 'o': '122', 'v': '100'}, # Actual swing high H=126 at t=5 (original was t=4 H=125)
        {'t': 6, 'h': '123', 'l': '118', 'c': '121', 'o': '121', 'v': '100'},
        {'t': 7, 'h': '115', 'l': '110', 'c': '112', 'o': '112', 'v': '100'},
        {'t': 8, 'h': '116', 'l': '111', 'c': '113', 'o': '113', 'v': '100'},
        {'t': 9, 'h': '117', 'l': '112', 'c': '114', 'o': '114', 'v': '100'},
        {'t': 10,'h': '118', 'l': '113', 'c': '115', 'o': '115', 'v': '100'},
        {'t': 11,'h': '119', 'l': '114', 'c': '116', 'o': '116', 'v': '100'},
        {'t': 12,'h': '120', 'l': '115', 'c': '117', 'o': '117', 'v': '100'},
        {'t': 13,'h': '121', 'l': '116', 'c': '118', 'o': '118', 'v': '100'},
        {'t': 14,'h': '122', 'l': '117', 'c': '119', 'o': '119', 'v': '100'},
        {'t': 15,'h': '122', 'l': '117', 'c': '120', 'o': '120', 'v': '100'}, # Current price 120
    ]

    test_deque = deque(data_points)

    print("\n--- Test with generated data ---")
    fib_results = analyze(test_deque, on_status_update=test_status_update_fib)
    if fib_results and "retracement_levels_A_to_B" in fib_results and fib_results["retracement_levels_A_to_B"]:
        print(f"Status: {fib_results['status']}")
        print(f"Trend Type: {fib_results['trend_type']}")
        print(f"Point A: Type {fib_results['last_swing_pointA']['type']}, Price {fib_results['last_swing_pointA']['price']} at index {fib_results['last_swing_pointA']['index']}")
        print(f"Point B: Type {fib_results['last_swing_pointB']['type']}, Price {fib_results['last_swing_pointB']['price']} at index {fib_results['last_swing_pointB']['index']}")
        print(f"Current Price for Context: {fib_results['current_price_for_context']}")
        print("Retracement Levels (A to B):")
        for level, price in fib_results["retracement_levels_A_to_B"].items():
            print(f"  {level*100:.1f}% : {price:.2f}")

        # Expected: Swing Low A (100 at t=3), Swing High B (126 at t=5)
        # Uptrend A->B. diff = 126 - 100 = 26.
        # Levels are A + diff * level_value
        # 0.0% => 100 + 26*0.0 = 100.0 (Point A)
        # 23.6% => 100 + 26*0.236 = 100 + 6.136 = 106.14
        # 38.2% => 100 + 26*0.382 = 100 + 9.932 = 109.93
        # 50.0% => 100 + 26*0.5 = 100 + 13.0 = 113.0
        # 61.8% => 100 + 26*0.618 = 100 + 16.068 = 116.07
        # 78.6% => 100 + 26*0.786 = 100 + 20.436 = 120.44
        # 100.0% => 100 + 26*1.0 = 126.0 (Point B)

        assert fib_results['last_swing_pointA']['price'] == 100
        assert fib_results['last_swing_pointB']['price'] == 126
        assert abs(fib_results["retracement_levels_A_to_B"][0.0] - 100.0) < 0.01
        assert abs(fib_results["retracement_levels_A_to_B"][0.5] - 113.0) < 0.01
        assert abs(fib_results["retracement_levels_A_to_B"][1.0] - 126.0) < 0.01

    else:
        print(f"Fibonacci analysis failed or no levels: {fib_results}")

    print("\n--- Test with insufficient data ---")
    short_deque = deque(list(test_deque)[:5]) # Only 5 data points
    fib_results_short = analyze(short_deque, on_status_update=test_status_update_fib)
    print(f"Fibonacci results (short data): {fib_results_short}")
    assert "Not enough kline data" in fib_results_short.get("status","")

    print("\nFibonacci analysis tests finished.")
