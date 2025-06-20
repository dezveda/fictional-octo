import pandas as pd
import numpy as np
import logging
# from trading_bot.utils import settings # Import settings if used directly here

logger = logging.getLogger(__name__)

def analyze(order_book_snapshot, settings, on_status_update=None): # Added settings
    """
    Analyzes order book snapshot to identify significant liquidity levels.
    order_book_snapshot: Dict with 'bids': [[price_str, qty_str], ...], 'asks': [[price_str, qty_str], ...]
                        Note: DataFetcher's get_order_book_snapshot provides sorted [price_float, qty_float]
    settings: The application settings module.
    on_status_update: Callback for status messages.
    Returns: Dict with 'significant_bids': [{'price': p, 'qty': q}, ...], 'significant_asks': [...]
    """
    logger.debug(f"[LiquidityAnalysisOB] Received snapshot. "
               f"Bids: {len(order_book_snapshot.get('bids',[])) if order_book_snapshot else 'N/A'}, "
               f"Asks: {len(order_book_snapshot.get('asks',[])) if order_book_snapshot else 'N/A'}")
    if on_status_update:
        on_status_update("[LiquidityAnalysisOB] Analyzing order book snapshot...")

    if not order_book_snapshot or not isinstance(order_book_snapshot, dict):
        if on_status_update: on_status_update("[LiquidityAnalysisOB] Invalid or empty order book snapshot.")
        return {"status": "Invalid order book data.", "significant_bids": [], "significant_asks": []}

    # DataFetcher's get_order_book_snapshot provides sorted lists of [price_float, qty_float]
    bids = order_book_snapshot.get('bids', []) # List of [price, qty]
    asks = order_book_snapshot.get('asks', []) # List of [price, qty]

    significant_bids = []
    significant_asks = []

    # Use settings for thresholds
    qty_threshold = getattr(settings, 'LIQUIDITY_SIGNIFICANT_QTY_THRESHOLD', 10) # Default 10 BTC
    logger.debug(f"[LiquidityAnalysisOB] Using LIQUIDITY_SIGNIFICANT_QTY_THRESHOLD: {qty_threshold}")

    for price, qty in bids:
        if qty >= qty_threshold:
            significant_bids.append({'price': price, 'qty': qty})

    for price, qty in asks:
        if qty >= qty_threshold:
            significant_asks.append({'price': price, 'qty': qty})

    # Sort by quantity descending to show most significant first (optional)
    significant_bids.sort(key=lambda x: x['qty'], reverse=True)
    significant_asks.sort(key=lambda x: x['qty'], reverse=True)

    status_msg = "Order book analyzed."
    if not significant_bids and not significant_asks:
        status_msg = "Order book analyzed. No liquidity levels found exceeding threshold."
    elif on_status_update: # Log if some found
         top_bid_info = f"Top Sig Bid: {significant_bids[0]['price']:.2f} Qty:{significant_bids[0]['qty']:.2f}" if significant_bids else "None"
         top_ask_info = f"Top Sig Ask: {significant_asks[0]['price']:.2f} Qty:{significant_asks[0]['qty']:.2f}" if significant_asks else "None"
         on_status_update(f"[LiquidityAnalysisOB] {top_bid_info} | {top_ask_info}")

    logger.debug(f"[LiquidityAnalysisOB] Analysis complete. "
               f"Found {len(significant_bids)} significant bids, {len(significant_asks)} significant asks.")
    # For more detail on top levels (optional, can be verbose):
    # logger.debug(f'[LiquidityAnalysisOB] Top sig bids: {significant_bids[:3]}')
    # logger.debug(f'[LiquidityAnalysisOB] Top sig asks: {significant_asks[:3]}')
    return {
        "status": status_msg,
        "significant_bids": significant_bids, # Top N can be sliced later
        "significant_asks": significant_asks,
        "raw_snapshot_summary": f"Bids: {len(bids)} levels, Asks: {len(asks)} levels" # For debug
    }

if __name__ == '__main__':
    print("Testing liquidity_analysis.py with order book data...")
    # Mock settings for testing
    class MockSettings:
        LIQUIDITY_SIGNIFICANT_QTY_THRESHOLD = 5.0
        STRATEGY_TIMEFRAME = "1H" # Needed by some status messages via GoldenStrategy context potentially
        # Add any other settings that might be indirectly accessed via on_status_update context

    mock_settings = MockSettings()

    sample_ob_snapshot = {
        'bids': [[29990.0, 10.5], [29985.0, 5.2], [29980.0, 2.1]], # Price, Qty
        'asks': [[30010.0, 8.8], [30015.0, 4.1], [30020.0, 1.5]]
    }
    def mock_status(msg): print(f"OB_STATUS: {msg}")

    analysis_result = analyze(sample_ob_snapshot, mock_settings, mock_status)
    print(f"Analysis Result:\n{analysis_result}")
    assert len(analysis_result['significant_bids']) == 2 # Both 10.5 and 5.2 are >= 5.0
    assert analysis_result['significant_bids'][0]['price'] == 29990.0 # Still check the first one
    assert analysis_result['significant_bids'][1]['price'] == 29985.0 # Check the second one
    assert len(analysis_result['significant_asks']) == 1
    assert analysis_result['significant_asks'][0]['price'] == 30010.0

    empty_snapshot = {'bids': [], 'asks': []}
    analysis_empty = analyze(empty_snapshot, mock_settings, mock_status)
    print(f"Analysis Empty Result:\n{analysis_empty}")
    assert not analysis_empty['significant_bids']
    assert not analysis_empty['significant_asks']
