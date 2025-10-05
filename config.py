from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()  # loads .env if present

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = int(os.getenv('CHAT_ID', '-1003157309802'))
THREAD_ID = int(os.getenv('THREAD_ID', '7')) or None
TIMEFRAME = os.getenv('TIMEFRAME', '4h')
CHECK_INTERVAL_MINUTES = int(os.getenv('CHECK_INTERVAL_MINUTES', '10'))
MIN_AGREE = int(os.getenv('MIN_AGREE', '3'))
OHLCV_LIMIT = int(os.getenv('OHLCV_LIMIT', '500'))
STORAGE_PATH = Path(os.getenv('STORAGE_PATH', 'storage.json'))
DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT"]
