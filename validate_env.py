import os
from typing import List, Dict
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

required_vars = {
    'ALPACA_API_KEY': str,
    'ALPACA_SECRET_KEY': str,
    'ALPACA_BASE_URL': str,
    'TELEGRAM_BOT_TOKEN': str,
    'TELEGRAM_CHAT_ID': str,
    'MAX_POSITIONS': int,
    'POSITION_SIZE': float,
    'MAX_POSITION_PCT': float,
    'INITIAL_STOP_LOSS_PCT': float,
    'TRAILING_STOP_PCT': float,
    'TRAILING_GAIN_PCT': float,
    'MIN_PERIOD': int,
    'MAX_PERIOD': int,
    'MIN_STD': float,
    'MAX_STD': float,
    'MIN_PRICE': float,
    'MAX_PRICE': float,
    'MIN_VOLUME': int,
    'MIN_VOLATILITY': float,
    'SCREEN_INTERVAL': int,
    'MIN_DOLLAR_VOLUME': float,
    'MAX_SPREAD_PCT': float,
    'MIN_AVG_VOLUME': int,
    'VOLUME_RATIO_THRESHOLD': float,
    'CHECK_INTERVAL': int,
    'LOG_LEVEL': str,
    'LOG_FILE': str,
    'DB_HOST': str,
    'DB_USER': str,
    'DB_PASSWORD': str,
    'DB_NAME': str,
    'DB_PORT': int
}

def validate_env_vars() -> Dict[str, List[str]]:
    """
    Validate all required environment variables.
    
    Returns:
        Dict with 'missing' and 'invalid' lists of variable names
    """
    load_dotenv()
    
    missing_vars = []
    invalid_vars = []
    
    for var_name, var_type in required_vars.items():
        # Check if variable exists
        value = os.getenv(var_name)
        if value is None:
            missing_vars.append(var_name)
            continue
            
        # Validate variable type
        try:
            if var_type == bool:
                value = value.lower() in ('true', '1', 'yes')
            else:
                var_type(value)
        except ValueError:
            invalid_vars.append(var_name)
    
    return {
        'missing': missing_vars,
        'invalid': invalid_vars
    }

def validate_alpaca_credentials() -> bool:
    """
    Validate Alpaca API credentials by attempting to connect.
    
    Returns:
        bool: True if credentials are valid
    """
    try:
        from alpaca.trading.client import TradingClient
        
        client = TradingClient(
            api_key=os.getenv('ALPACA_API_KEY'),
            secret_key=os.getenv('ALPACA_SECRET_KEY'),
            paper=True
        )
        
        # Try to get account information
        account = client.get_account()
        logger.info(f"Successfully connected to Alpaca. Account status: {account.status}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to validate Alpaca credentials: {str(e)}")
        return False

def validate_telegram_config() -> bool:
    """
    Validate Telegram configuration by attempting to send a test message.
    
    Returns:
        bool: True if configuration is valid
    """
    try:
        import telegram
        import asyncio
        
        async def send_test_message():
            bot = telegram.Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
            chat_id = os.getenv('TELEGRAM_CHAT_ID')
            message = "🤖 Trading Bot: Environment validation test message"
            
            logger.info(f"Attempting to send test message to chat ID: {chat_id}")
            await bot.send_message(chat_id=chat_id, text=message)
            logger.info("Successfully sent Telegram test message")
            return True

        async def run_validation():
            try:
                return await send_test_message()
            except telegram.error.InvalidToken:
                logger.error("Invalid Telegram bot token. Please check your TELEGRAM_BOT_TOKEN.")
            except telegram.error.NetworkError:
                logger.error("Network error while trying to connect to Telegram. Please check your internet connection.")
            except telegram.error.TelegramError as e:
                logger.error(f"Telegram API error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error during Telegram message sending: {str(e)}")
            return False

        async def async_wrapper():
            try:
                return await asyncio.wait_for(run_validation(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error("Telegram validation timed out after 10 seconds")
                return False

        # Try to get the current event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Check if we're inside a running event loop
        if loop.is_running():
            # We're in an async context, create and run a task
            task = asyncio.create_task(async_wrapper())
            # Use asyncio.shield to prevent cancellation during cleanup
            return asyncio.shield(task)
        else:
            # No running loop, we can use run_until_complete
            try:
                return loop.run_until_complete(async_wrapper())
            finally:
                loop.close()

    except Exception as e:
        logger.error(f"Critical error in Telegram validation: {str(e)}")
        return False

def main():
    """Validate all configurations before bot startup."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Validate environment variables
    validation_results = validate_env_vars()
    
    if validation_results['missing'] or validation_results['invalid']:
        if validation_results['missing']:
            logger.error(f"Missing environment variables: {', '.join(validation_results['missing'])}")
        if validation_results['invalid']:
            logger.error(f"Invalid environment variables: {', '.join(validation_results['invalid'])}")
        return False
    
    # Validate Alpaca credentials
    if not validate_alpaca_credentials():
        logger.error("Failed to validate Alpaca credentials")
        return False
    
    # Validate Telegram configuration
    if not validate_telegram_config():
        logger.error("Failed to validate Telegram configuration")
        return False
    
    logger.info("All configurations validated successfully!")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)