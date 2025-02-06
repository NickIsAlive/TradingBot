from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import sys
from datetime import datetime, time
import time as time_module
import pytz
import config
from trading import TradingBot
from health_check import start_health_check
from validate_env import main as validate_config
import os
from notifications import SingleInstanceException

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level.upper()),
    format=config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def get_market_hours(market: str = 'NYSE') -> dict:
    """
    Get trading hours for different global markets.
    
    Args:
        market (str): The market to check. Supports 'NYSE', 'NASDAQ', 'LSE', 'TSX', 'ASX', 'HKEX', 'SSE'
    
    Returns:
        dict: Market trading hours and timezone
    """
    market_hours = {
        'NYSE': {
            'timezone': 'America/New_York',
            'open_time': time(9, 30),   # 9:30 AM
            'close_time': time(16, 0),  # 4:00 PM
            'days': range(0, 5)         # Monday to Friday
        },
        'NASDAQ': {
            'timezone': 'America/New_York',
            'open_time': time(9, 30),
            'close_time': time(16, 0),
            'days': range(0, 5)
        },
        'LSE': {  # London Stock Exchange
            'timezone': 'Europe/London',
            'open_time': time(8, 0),    # 8:00 AM
            'close_time': time(16, 30), # 4:30 PM
            'days': range(0, 5)
        },
        'TSX': {  # Toronto Stock Exchange
            'timezone': 'America/New_York',
            'open_time': time(9, 30),
            'close_time': time(16, 0),
            'days': range(0, 5)
        },
        'ASX': {  # Australian Securities Exchange
            'timezone': 'Australia/Sydney',
            'open_time': time(10, 0),   # 10:00 AM
            'close_time': time(16, 0),  # 4:00 PM
            'days': range(0, 5)
        },
        'HKEX': {  # Hong Kong Stock Exchange
            'timezone': 'Asia/Hong_Kong',
            'open_time': time(9, 30),   # 9:30 AM
            'close_time': time(16, 0),  # 4:00 PM
            'days': range(0, 5)
        },
        'SSE': {  # Shanghai Stock Exchange
            'timezone': 'Asia/Shanghai',
            'open_time': time(9, 30),   # 9:30 AM
            'close_time': time(15, 0),  # 3:00 PM
            'days': range(0, 5)
        }
    }
    return market_hours.get(market.upper(), market_hours['NYSE'])

def is_market_hours(market: str = 'NYSE') -> bool:
    """
    Check if the specified market is currently open.
    
    Args:
        market (str): The market to check. Supports multiple global indices.
    
    Returns:
        bool: True if market is open, False otherwise
    """
    try:
        market_info = get_market_hours(market)
        
        # Get the market's timezone
        market_tz = pytz.timezone(market_info['timezone'])
        
        # Get current UTC time and convert to market timezone
        utc_now = datetime.now(pytz.UTC)
        market_now = utc_now.astimezone(market_tz)
        
        # Check if it's a trading day
        if market_now.weekday() not in market_info['days']:
            return False
        
        # Create timezone-aware datetime objects for market open and close times
        today = market_now.date()
        market_open_time = market_info['open_time']
        market_close_time = market_info['close_time']
        
        # Combine date and time to create timezone-aware datetime objects
        market_open = market_tz.localize(datetime.combine(today, market_open_time))
        market_close = market_tz.localize(datetime.combine(today, market_close_time))
        
        # Compare using datetime objects instead of time objects
        return market_open <= market_now <= market_close
        
    except Exception as e:
        logger.error(f"Error checking market hours for {market}: {str(e)}")
        raise

async def process_trading_symbols(bot, config):
    """Process trading symbols."""
    logger.info("Processing trading symbols...")
    
    # Track market allocation
    market_allocation = {}
    
    for symbol in bot.trading_symbols:
        # Get symbol's market
        market = bot.get_symbol_market(symbol)
        
        # Check if we've hit the limit for this market
        market_limit = next((m['max_positions'] for m in config.MARKETS_TO_TRADE if m['name'] == market), 0)
        current_allocation = market_allocation.get(market, 0)
        
        if current_allocation >= market_limit:
            logger.info(f"Skipping {symbol} due to market allocation limits")
            continue
            
        # Process symbol and update allocation
        await bot.process_symbol(symbol)
        market_allocation[market] = current_allocation + 1
    
    logger.info("Finished processing symbols")
    logger.info(f"Market Allocation: {market_allocation}")

async def main():
    """Main function to run the trading bot."""
    logger.info("Starting trading bot...")
    
    # Validate configuration
    if not await validate_config():
        logger.error("Configuration validation failed. Exiting...")
        sys.exit(1)
    
    try:
        # Start health check server
        start_health_check()
        
        bot = TradingBot()
        logger.info("Initializing Telegram notifier...")
        await bot.notifier.initialize()
        
        if not bot.notifier.application:
            raise RuntimeError("Telegram application failed to initialize")
            
        await bot.start()
        logger.info("Telegram bot started successfully")
        
        last_screen_time = 0
        
        while True:
            try:
                # Get current time with proper timezone handling
                current_time = pytz.utc.localize(datetime.now()).timestamp()
                
                # Check multiple markets dynamically from configuration
                markets_to_check = [market['name'] for market in config.MARKETS_TO_TRADE]
                
                try:
                    market_open = any(is_market_hours(market) for market in markets_to_check)
                except Exception as market_error:
                    logger.error(f"Error checking market hours: {str(market_error)}")
                    raise
                
                if market_open:
                    # Update trading symbols periodically
                    if current_time - last_screen_time >= config.SCREEN_INTERVAL:
                        logger.info("Screening for new trading candidates...")
                        
                        # Get trading candidates across multiple markets
                        bot.update_trading_symbols(
                            markets=markets_to_check,
                            max_stocks=config.MULTI_MARKET_STRATEGY['max_total_positions']
                        )
                        
                        last_screen_time = current_time
                    
                    if bot.trading_symbols:
                        logger.info("Processing trading symbols...")
                        await process_trading_symbols(bot, config)
                    else:
                        logger.warning("No trading symbols available")
                else:
                    logger.info("All checked markets are closed. Waiting...")
                
                # Wait for the next check interval
                await asyncio.sleep(config.CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                await asyncio.sleep(config.CHECK_INTERVAL)
    except SingleInstanceException as e:
        logger.error(f"Cannot start bot: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)
    finally:
        await bot.stop()
        logger.info("Telegram bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1) 