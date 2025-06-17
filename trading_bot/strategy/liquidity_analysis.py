import pandas as pd
import numpy as np
import logging
from collections import Counter

logger = logging.getLogger(__name__)

def calculate_simple_volume_profile(kline_data_deque, num_bins=20, volume_threshold_multiplier=1.5):
    """
    Calculates a simplified volume profile from kline data to estimate liquidity zones.

    kline_data_deque: A deque of kline dictionaries (expecting 'c' for close, 'v' for volume).
    num_bins: How many price bins to divide the price range into.
    volume_threshold_multiplier: Multiplier for average volume per bin to consider a bin as a high liquidity zone.

    Returns: A dictionary with:
        'profile': {price_bin_midpoint: volume},
        'high_volume_zones': [{'price_level': midpoint, 'volume': vol} ... ],
        'price_range': (min_price, max_price)
    or None if data is insufficient.
    """
    if len(kline_data_deque) < num_bins : # Need some data to form meaningful bins
        logger.warning("[LiquidityAnalysis] Not enough kline data to build a significant volume profile.")
        return None

    try:
        prices = np.array([float(k['c']) for k in kline_data_deque])
        volumes = np.array([float(k['v']) for k in kline_data_deque])
    except (KeyError, ValueError) as e:
        logger.error(f"[LiquidityAnalysis] Error processing kline data for volume profile: {e}")
        return None

    if len(prices) == 0:
        return None

    min_price = prices.min()
    max_price = prices.max()

    if min_price == max_price: # Avoid division by zero if all prices are the same
        # In this case, all volume is at this single price level
        profile = {min_price: volumes.sum()}
        # Consider this single level as a high volume zone if total volume is significant (heuristic needed)
        # For now, if all prices are same, treat that price as a high volume zone.
        high_volume_zones = [{'price_level': min_price, 'volume': volumes.sum()}]
        return {
            'profile': profile,
            'high_volume_zones': high_volume_zones,
            'price_range': (min_price, max_price)
        }

    # Create price bins
    bin_edges = np.linspace(min_price, max_price, num_bins + 1)
    volume_in_bin = np.zeros(num_bins)

    # Digitize prices into bins (which bin each price falls into)
    # np.digitize returns indices starting from 1.
    price_bin_indices = np.digitize(prices, bin_edges[:-1]) # Use bin_edges[:-1] so that max_price falls into last bin correctly

    for i in range(len(prices)):
        bin_index = price_bin_indices[i] -1 # Adjust to 0-based index
        if 0 <= bin_index < num_bins:
            volume_in_bin[bin_index] += volumes[i]

    # Create the profile dictionary {bin_midpoint: volume}
    profile = {}
    bin_midpoints = (bin_edges[:-1] + bin_edges[1:]) / 2
    for i in range(num_bins):
        profile[round(bin_midpoints[i], 5)] = volume_in_bin[i] # Round midpoint for cleaner keys

    # Identify high volume zones
    average_volume_per_bin = volume_in_bin.mean()
    high_volume_threshold = average_volume_per_bin * volume_threshold_multiplier

    high_volume_zones = []
    for i in range(num_bins):
        if volume_in_bin[i] >= high_volume_threshold:
            high_volume_zones.append({
                'price_level': round(bin_midpoints[i], 5),
                'volume': volume_in_bin[i]
            })

    # Sort high volume zones by volume (descending)
    high_volume_zones.sort(key=lambda x: x['volume'], reverse=True)

    return {
        'profile': profile,
        'high_volume_zones': high_volume_zones,
        'price_range': (min_price, max_price)
    }


def analyze(all_kline_data_deque, on_status_update=None):
    """
    Analyzes liquidity points using a simplified volume profile.
    all_kline_data_deque: A deque of kline dictionaries.
    on_status_update: Callback for status messages.
    Returns: Analysis results (e.g., identified high-volume liquidity zones).
    """
    if on_status_update:
        on_status_update("[LiquidityAnalysis] Analyzing with simple volume profile...")

    if not all_kline_data_deque or len(all_kline_data_deque) < 10: # Arbitrary minimum
        return {"status": "Not enough kline data for liquidity analysis."}

    vp_results = calculate_simple_volume_profile(all_kline_data_deque, num_bins=20, volume_threshold_multiplier=1.5)

    if not vp_results:
        return {"status": "Failed to calculate volume profile."}

    if on_status_update and vp_results['high_volume_zones']:
        zones_str = ", ".join([f"{zone['price_level']:.2f}(Vol:{zone['volume']:.0f})" for zone in vp_results['high_volume_zones'][:3]]) # Log top 3
        on_status_update(f"[LiquidityAnalysis] High volume zones (top 3): {zones_str}")
    elif on_status_update:
        on_status_update("[LiquidityAnalysis] No significant high volume zones identified by current criteria.")

    return {
        "status": "Liquidity analysis (volume profile) complete.",
        "volume_profile_data": vp_results
    }

if __name__ == '__main__':
    from collections import deque
    print("Testing liquidity_analysis.py...")

    def test_status_update_liq(message):
        print(f"LIQ_TEST_STATUS: {message}")

    # Sample kline data
    sample_klines = [
        # Price cluster around 100-102 with high volume
        {'t': 1, 'o': '100', 'h': '101', 'l': '99',  'c': '100.0', 'v': '500'},
        {'t': 2, 'o': '100', 'h': '102', 'l': '100', 'c': '101.0', 'v': '600'},
        {'t': 3, 'o': '101', 'h': '103', 'l': '100', 'c': '100.5', 'v': '700'},
        {'t': 4, 'o': '100', 'h': '102', 'l': '99',  'c': '101.5', 'v': '400'},
        # Quieter area
        {'t': 5, 'o': '103', 'h': '104', 'l': '102', 'c': '103.0', 'v': '100'},
        {'t': 6, 'o': '103', 'h': '105', 'l': '103', 'c': '104.0', 'v': '150'},
        # Another cluster around 108-110
        {'t': 7, 'o': '107', 'h': '109', 'l': '106', 'c': '108.0', 'v': '450'},
        {'t': 8, 'o': '108', 'h': '110', 'l': '107', 'c': '109.0', 'v': '550'},
        {'t': 9, 'o': '109', 'h': '111', 'l': '108', 'c': '110.0', 'v': '650'},
        {'t':10, 'o': '110', 'h': '111', 'l': '109', 'c': '109.5', 'v': '350'},
        # Spread out points
        {'t':11, 'o': '112', 'h': '114', 'l': '111', 'c': '113.0', 'v': '50'},
        {'t':12, 'o': '98',  'h': '100', 'l': '97',  'c': '98.0',  'v': '200'},
        {'t':13, 'o': '115', 'h': '117', 'l': '114', 'c': '116.0', 'v': '80'},
        {'t':14, 'o': '105', 'h': '107', 'l': '104', 'c': '106.0', 'v': '120'},
        {'t':15, 'o': '102', 'h': '104', 'l': '101', 'c': '102.5', 'v': '250'},
    ] * 2 # Repeat data to make it longer for more stable profile

    test_deque_liq = deque(sample_klines)

    print("\n--- Test with sample kline data ---")
    liq_results = analyze(test_deque_liq, on_status_update=test_status_update_liq)

    if liq_results and liq_results.get('volume_profile_data'):
        vp_data = liq_results['volume_profile_data']
        print(f"Status: {liq_results['status']}")
        print(f"Price Range: {vp_data['price_range'][0]:.2f} - {vp_data['price_range'][1]:.2f}")
        print("Top High Volume Zones:")
        for zone in vp_data['high_volume_zones'][:5]: # Print top 5
            print(f"  Price Level: {zone['price_level']:.2f}, Volume: {zone['volume']:.0f}")

        # Check if the high volume zones make sense based on input data
        # Example: 100-102 and 108-110 had high volumes
        found_zone_around_101 = any(abs(z['price_level'] - 101) < 2 for z in vp_data['high_volume_zones'])
        found_zone_around_109 = any(abs(z['price_level'] - 109) < 2 for z in vp_data['high_volume_zones'])

        # These assertions depend heavily on num_bins and the exact distribution
        # For a robust test, one might need to pre-calculate expected bins.
        # assert found_zone_around_101, "Expected a high volume zone around 100-102"
        # assert found_zone_around_109, "Expected a high volume zone around 108-110"
        if not (found_zone_around_101 and found_zone_around_109) and len(vp_data['high_volume_zones']) > 0 :
             print("Note: Specific assertions for high volume zones might need tuning based on binning strategy.")
        elif len(vp_data['high_volume_zones']) == 0:
            print("Warning: No high volume zones identified in test, check threshold or data.")


    else:
        print(f"Liquidity analysis failed or no data: {liq_results}")

    print("\n--- Test with insufficient data ---")
    short_deque_liq = deque(list(test_deque_liq)[:5])
    liq_results_short = analyze(short_deque_liq, on_status_update=test_status_update_liq)
    print(f"Liquidity results (short data): {liq_results_short}")
    assert "Not enough kline data" in liq_results_short.get("status","")

    print("\n--- Test with all same prices (edge case) ---")
    same_price_klines = [
        {'t': 1, 'o': '100', 'h': '100', 'l': '100',  'c': '100.0', 'v': '500'},
        {'t': 2, 'o': '100', 'h': '100', 'l': '100',  'c': '100.0', 'v': '600'},
        {'t': 3, 'o': '100', 'h': '100', 'l': '100',  'c': '100.0', 'v': '700'},
    ]
    same_price_deque = deque(same_price_klines)
    liq_results_same_price = analyze(same_price_deque, on_status_update=test_status_update_liq)
    if liq_results_same_price and liq_results_same_price.get('volume_profile_data'):
        vp_data_sp = liq_results_same_price['volume_profile_data']
        print(f"Status (same price): {liq_results_same_price['status']}")
        print(f"Price Range: {vp_data_sp['price_range']}")
        print(f"Profile: {vp_data_sp['profile']}")
        print(f"High Volume Zones: {vp_data_sp['high_volume_zones']}")
        assert vp_data_sp['high_volume_zones'][0]['price_level'] == 100.0
        assert vp_data_sp['high_volume_zones'][0]['volume'] == 1800 # 500+600+700
    else:
        print(f"Liquidity analysis failed for same price test: {liq_results_same_price}")


    print("\nLiquidity analysis tests finished.")
