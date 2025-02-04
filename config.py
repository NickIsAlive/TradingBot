import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Alpaca API Configuration
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Trading Parameters
MAX_POSITIONS = int(os.getenv('MAX_POSITIONS') or 5)
POSITION_SIZE = float(os.getenv('POSITION_SIZE') or 0.1)
MAX_POSITION_PCT = float(os.getenv('MAX_POSITION_PCT') or 0.20)

# Risk Management
INITIAL_STOP_LOSS_PCT = float(os.getenv('INITIAL_STOP_LOSS_PCT') or 0.03)
TRAILING_STOP_PCT = float(os.getenv('TRAILING_STOP_PCT') or 0.02)
TRAILING_GAIN_PCT = float(os.getenv('TRAILING_GAIN_PCT') or 0.01)

# Bollinger Bands Configuration
MIN_PERIOD = int(os.getenv('MIN_PERIOD') or 10)
MAX_PERIOD = int(os.getenv('MAX_PERIOD') or 50)
MIN_STD = float(os.getenv('MIN_STD') or 1.5)
MAX_STD = float(os.getenv('MAX_STD') or 3.0)

# Stock Screening Parameters
MIN_PRICE = float(os.getenv('MIN_PRICE') or 10)
MAX_PRICE = float(os.getenv('MAX_PRICE') or 200)
MIN_VOLUME = int(os.getenv('MIN_VOLUME') or 500000)
MIN_VOLATILITY = float(os.getenv('MIN_VOLATILITY') or 0.2)
SCREEN_INTERVAL = int(os.getenv('SCREEN_INTERVAL') or 3600)

# Liquidity Parameters
MIN_DOLLAR_VOLUME = float(os.getenv('MIN_DOLLAR_VOLUME') or 5000000)
MAX_SPREAD_PCT = float(os.getenv('MAX_SPREAD_PCT') or 0.002)
MIN_AVG_VOLUME = int(os.getenv('MIN_AVG_VOLUME') or 100000)
VOLUME_RATIO_THRESHOLD = float(os.getenv('VOLUME_RATIO_THRESHOLD') or 1.5)

# Time intervals
CHECK_INTERVAL = 300  # 5 minutes in seconds
MARKET_DATA_LOOKBACK = '1D'

# Logging Configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'
LOG_FILE = 'trading_bot.log' 