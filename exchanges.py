import ccxt

BINANCE = ccxt.binance({'enableRateLimit': True})
BYBIT = ccxt.bybit({'enableRateLimit': True})

EXCHANGE_MAP = {
    'binance': BINANCE,
    'bybit': BYBIT,
}

def fetch_ohlcv(exchange_name, symbol, timeframe, limit=500):
    exchange = EXCHANGE_MAP.get(exchange_name.lower())
    if exchange is None:
        raise ValueError(f"Unknown exchange: {exchange_name}")
    return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

def fetch_from_best(exchange_names, symbol, timeframe, limit):
    results = []
    for ex in exchange_names:
        try:
            bars = fetch_ohlcv(ex, symbol, timeframe, limit)
            results.append((ex, bars))
        except Exception:
            continue
    return results
