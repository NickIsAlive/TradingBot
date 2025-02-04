import asyncio
import logging
import sys
from datetime import datetime
import pytz
import config
from trading import TradingBot
from health_check import start_health_check
from validate_env import main as validate_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def is_market_hours() -> bool:
    """Check if the US market is currently open."""
    ny_tz = pytz.timezone('America/New_York')
    now = datetime.now(ny_tz)
    
    # Check if it's a weekday
    if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return False
    
    # Check if it's between 9:30 AM and 4:00 PM EST
    market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_start <= now <= market_end

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
    last_screen_time = 0
    
    while True:
        try:
            current_time = datetime.now().timestamp()
            
            if is_market_hours():
                # Update trading symbols periodically
                if current_time - last_screen_time >= config.SCREEN_INTERVAL:
                    logger.info("Screening for new trading candidates...")
                    await bot.update_trading_symbols()
                    last_screen_time = current_time
                
                if bot.trading_symbols:
                    logger.info("Processing trading symbols...")
                    for symbol in bot.trading_symbols:
                        try:
                            await bot.process_symbol(symbol)
                        except Exception as e:
                            logger.error(f"Error processing {symbol}: {str(e)}")
                            continue
                    logger.info("Finished processing symbols")
                else:
                    logger.warning("No trading symbols available")
            else:
                logger.info("Market is closed. Waiting...")
            
            # Wait for the next check interval
            await asyncio.sleep(config.CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            await asyncio.sleep(config.CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1) 