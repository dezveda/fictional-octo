# Kline Data Storage

This directory stores Kline (candlestick) data for different trading symbols and intervals.

## Data Format

The Kline data is stored in JSON format. Each file contains a list of Kline data points. Each Kline data point is represented as a list:

```json
[
  [
    1499040000000,      // Kline open time
    "0.01634790",       // Open price
    "0.80000000",       // High price
    "0.01575800",       // Low price
    "0.01577100",       // Close price
    "148976.11427815",  // Volume
    1499644799999,      // Kline close time
    "2434.19055334",    // Quote asset volume
    308,                // Number of trades
    "1756.87402397",    // Taker buy base asset volume
    "28.46694368",      // Taker buy quote asset volume
    "0"                 // Unused field, ignore.
  ]
]
```

## Naming Convention

Files are named using the following convention:

`<SYMBOL>_<INTERVAL>.json`

Where:
- `<SYMBOL>`: The trading symbol (e.g., BTCUSDT, ETHBTC).
- `<INTERVAL>`: The Kline interval (e.g., 1m, 5m, 1h, 1d).

For example, the Kline data for Bitcoin/Tether US on a 1-hour interval would be stored in a file named `BTCUSDT_1h.json`.
