import pytz
from datetime import datetime
import logging
import config

logger = logging.getLogger(__name__)

def is_market_hours(market: str) -> bool:
    """Check if the given market is currently open."""
    # Get current UTC time
    utc_now = datetime.now(pytz.UTC)
    
    # Get market-specific configuration
    market_config = next((m for m in config.MARKETS_TO_TRADE if m['name'] == market), None)
    if not market_config:
        logger.warning(f"No configuration found for market {market}")
        return False
    
    # Get current time in market timezone
    market_tz = pytz.timezone(market_config['timezone'])
    market_time = utc_now.astimezone(market_tz)
    current_time = market_time.time()
    
    # Convert string times to time objects
    market_open = datetime.strptime(market_config['open_time'], '%H:%M').time()
    market_close = datetime.strptime(market_config['close_time'], '%H:%M').time()
    
    # Check if it's a weekday
    if market_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
        
    # Check if current time is within market hours
    if market_open <= market_close:
        return market_open <= current_time <= market_close
    else:
        # Handle markets that cross midnight
        return current_time >= market_open or current_time <= market_close 