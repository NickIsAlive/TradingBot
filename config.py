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

# Determine if we're running in Docker or local development
if os.getenv('DOCKER_ENV'):
    # Docker environment
    LOG_DIR = '/home/trader/logs'
else:
    # Local development - use current directory
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    # Create logs directory if it doesn't exist
    os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, 'trading_bot.log')

# Multi-Market Trading Configuration
MARKETS_TO_TRADE = [
    {
        'name': 'NYSE',
        'priority': 1,
        'max_positions': 3,
        'min_price': 10,
        'max_price': 200,
        'min_volume': 500000,
        'min_dollar_volume': 5000000,
        'timezone': 'America/New_York',
        'open_time': '09:30',
        'close_time': '16:00'
    },
    {
        'name': 'NASDAQ',
        'priority': 2,
        'max_positions': 2,
        'min_price': 5,
        'max_price': 300,
        'min_volume': 300000,
        'min_dollar_volume': 3000000,
        'timezone': 'America/New_York',
        'open_time': '09:30',
        'close_time': '16:00'
    },
    {
        'name': 'LSE',
        'priority': 3,
        'max_positions': 1,
        'min_price': 1,  # In GBP
        'max_price': 500,
        'min_volume': 100000,
        'min_dollar_volume': 2000000,
        'timezone': 'Europe/London',
        'open_time': '08:00',
        'close_time': '16:30'
    },
    {
        'name': 'ASX',
        'priority': 4,
        'max_positions': 1,
        'min_price': 0.1,  # In AUD
        'max_price': 100,
        'min_volume': 50000,
        'min_dollar_volume': 1000000,
        'timezone': 'Australia/Sydney',
        'open_time': '10:00',
        'close_time': '16:00'
    }
]

# Multi-Market Trading Strategy Parameters
MULTI_MARKET_STRATEGY = {
    'max_total_positions': 5,  # Maximum total positions across all markets
    'position_allocation_method': 'proportional',  # How to allocate positions
    'market_correlation_threshold': 0.7,  # Avoid over-concentration
    'global_risk_limit_pct': 0.2,  # Maximum portfolio risk
} 