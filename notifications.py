import logging
import telegram
from telegram.error import TelegramError
import config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot = telegram.Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.chat_id = config.TELEGRAM_CHAT_ID

    async def send_message(self, message: str) -> None:
        """
        Send a message to the configured Telegram chat.
        
        Args:
            message (str): The message to send
        """
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {str(e)}")

    async def send_trade_notification(self, symbol: str, action: str, price: float, quantity: float) -> None:
        """
        Send a formatted trade notification.
        
        Args:
            symbol (str): The trading symbol
            action (str): The trade action (BUY/SELL)
            price (float): The execution price
            quantity (float): The quantity traded
        """
        message = (
            f"🤖 <b>Trade Executed</b>\n\n"
            f"Symbol: {symbol}\n"
            f"Action: {action}\n"
            f"Price: ${price:.2f}\n"
            f"Quantity: {quantity}\n"
            f"Total Value: ${price * quantity:.2f}"
        )
        await self.send_message(message)

    async def send_error_notification(self, error_message: str) -> None:
        """
        Send an error notification.
        
        Args:
            error_message (str): The error message to send
        """
        message = f"⚠️ <b>Error Alert</b>\n\n{error_message}"
        await self.send_message(message) 