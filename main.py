from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import sys
from datetime import datetime
import pytz
import config
from trading import TradingBot
from health_check import start_health_check
from validate_env import main as validate_config
import os

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
            'open_time': (9, 30),   # 9:30 AM
            'close_time': (16, 0),  # 4:00 PM
            'days': range(0, 5)     # Monday to Friday
        },
        'NASDAQ': {
            'timezone': 'America/New_York',
            'open_time': (9, 30),
            'close_time': (16, 0),
            'days': range(0, 5)
        },
        'LSE': {  # London Stock Exchange
            'timezone': 'Europe/London',
            'open_time': (8, 0),    # 8:00 AM
            'close_time': (16, 30), # 4:30 PM
            'days': range(0, 5)
        },
        'TSX': {  # Toronto Stock Exchange
            'timezone': 'America/Toronto',
            'open_time': (9, 30),
            'close_time': (16, 0),
            'days': range(0, 5)
        },
        'ASX': {  # Australian Securities Exchange
            'timezone': 'Australia/Sydney',
            'open_time': (10, 0),   # 10:00 AM
            'close_time': (16, 0),  # 4:00 PM
            'days': range(0, 5)
        },
        'HKEX': {  # Hong Kong Stock Exchange
            'timezone': 'Asia/Hong_Kong',
            'open_time': (9, 30),   # 9:30 AM
            'close_time': (16, 0),  # 4:00 PM
            'days': range(0, 5)
        },
        'SSE': {  # Shanghai Stock Exchange
            'timezone': 'Asia/Shanghai',
            'open_time': (9, 30),   # 9:30 AM
            'close_time': (15, 0),  # 3:00 PM
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
    market_info = get_market_hours(market)
    
    # Get the market's timezone
    market_tz = pytz.timezone(market_info['timezone'])
    now = datetime.now(market_tz)
    
    # Check if it's a trading day
    if now.weekday() not in market_info['days']:
        return False
    
    # Create datetime objects for market open and close times
    market_open = now.replace(
        hour=market_info['open_time'][0], 
        minute=market_info['open_time'][1], 
        second=0, 
        microsecond=0
    )
    market_close = now.replace(
        hour=market_info['close_time'][0], 
        minute=market_info['close_time'][1], 
        second=0, 
        microsecond=0
    )
    
    return market_open <= now <= market_close

async def main():
    """Main function to run the trading bot."""
    logger.info("Starting trading bot...")
    
    # Validate configuration
    if not validate_config():
        logger.error("Configuration validation failed. Exiting...")
        sys.exit(1)
    
    # Start health check server
    await start_health_check()
    
    bot = TradingBot()
    
    # Start Telegram bot
    await bot.start()
    logger.info("Telegram bot started successfully")
    
    last_screen_time = 0
    
    try:
        while True:
            try:
                current_time = datetime.now().timestamp()
                
                # Check multiple markets dynamically from configuration
                markets_to_check = [market['name'] for market in config.MARKETS_TO_TRADE]
                market_open = any(is_market_hours(market) for market in markets_to_check)
                
                if market_open:
                    # Update trading symbols periodically
                    if current_time - last_screen_time >= config.SCREEN_INTERVAL:
                        logger.info("Screening for new trading candidates...")
                        
                        # Get trading candidates across multiple markets
                        await bot.update_trading_symbols(
                            markets=markets_to_check,
                            max_stocks=config.MULTI_MARKET_STRATEGY['max_total_positions']
                        )
                        
                        last_screen_time = current_time
                    
                    if bot.trading_symbols:
                        logger.info("Processing trading symbols...")
                        
                        # Track market allocation
                        market_allocation = {}
                        
                        for symbol in bot.trading_symbols:
                            try:
                                # Determine market for symbol
                                symbol_market = bot.get_symbol_market(symbol)
                                
                                # Check market allocation limits
                                if symbol_market not in market_allocation:
                                    market_allocation[symbol_market] = 0
                                
                                market_config = next(
                                    (m for m in config.MARKETS_TO_TRADE if m['name'] == symbol_market), 
                                    None
                                )
                                
                                if market_config and market_allocation[symbol_market] < market_config['max_positions']:
                                    await bot.process_symbol(symbol)
                                    market_allocation[symbol_market] += 1
                                else:
                                    logger.info(f"Skipping {symbol} due to market allocation limits")
                                
                                # Global position limit
                                if sum(market_allocation.values()) >= config.MULTI_MARKET_STRATEGY['max_total_positions']:
                                    break
                            
                            except Exception as e:
                                logger.error(f"Error processing {symbol}: {str(e)}")
                                continue
                        
                        logger.info("Finished processing symbols")
                        logger.info(f"Market Allocation: {market_allocation}")
                    else:
                        logger.warning("No trading symbols available")
                else:
                    logger.info("All checked markets are closed. Waiting...")
                
                # Wait for the next check interval
                await asyncio.sleep(config.CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                await asyncio.sleep(config.CHECK_INTERVAL)
    finally:
        # Ensure Telegram bot is stopped properly
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