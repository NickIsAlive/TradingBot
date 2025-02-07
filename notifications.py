import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import config
import httpx
from market_utils import is_market_hours

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self._running = False
        self.application = None
        self.bot = None
        self.start_time = None

    async def initialize(self) -> None:
        """Initialize the bot"""
        try:
            logger.info("Initializing Telegram bot...")
            # Create application with just the token
            self.application = (
                Application.builder()
                .token(config.TELEGRAM_BOT_TOKEN)
                .build()
            )
            self.bot = self.application.bot
            
            # Register command handlers
            self.application.add_handler(CommandHandler("start", self._cmd_start))
            self.application.add_handler(CommandHandler("status", self._cmd_status))
            self.application.add_handler(CommandHandler("help", self._cmd_help))
            self.application.add_handler(CommandHandler("positions", self._cmd_positions))
            self.application.add_handler(CommandHandler("balance", self._cmd_balance))
            
            logger.info("Telegram bot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize bot: {str(e)}")
            raise

    async def start(self) -> None:
        """Start the bot with polling"""
        if self._running:
            return
            
        try:
            self._running = True
            # Just start polling - no webhook stuff
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
            logger.info("Bot started")
        except Exception as e:
            self._running = False
            logger.error(f"Failed to start bot: {str(e)}")
            raise

    async def stop(self) -> None:
        """Stop the bot"""
        if not self._running:
            return
            
        try:
            self._running = False
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Bot stopped")
        except Exception as e:
            logger.error(f"Error stopping bot: {str(e)}")

    async def send_message(self, message: str) -> None:
        """Send a message"""
        try:
            # Create a client that skips SSL verification
            async with httpx.AsyncClient(verify=False) as client:
                await client.post(
                    f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": config.TELEGRAM_CHAT_ID,
                        "text": message
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 Trading Bot Online!\n\n"
            "Available commands:\n"
            "/status - Check bot status\n"
            "/positions - View open positions\n"
            "/balance - Check account balance\n"
            "/help - Show all commands"
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        help_text = (
            "📚 *Available Commands*\n\n"
            "/start - Start the bot\n"
            "/status - Check bot status\n"
            "/positions - View open positions\n"
            "/balance - Check account balance\n"
            "/help - Show this help message\n\n"
            "ℹ️ The bot automatically trades based on configured strategies."
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command"""
        status = "🟢 Running" if self._running else "🔴 Stopped"
        
        # Check each market's status
        market_statuses = []
        for market in config.MARKETS_TO_TRADE:
            is_open = is_market_hours(market['name'])
            symbol = "🟢" if is_open else "🔴"
            market_statuses.append(f"{symbol} {market['name']}")
        
        markets_text = "\n".join(market_statuses)
        
        await update.message.reply_text(
            f"*Bot Status:* {status}\n\n"
            f"*Markets:*\n{markets_text}\n\n"
            f"*Active Strategies:* Mean Reversion\n"
            f"*Trading Enabled:* Yes\n"
            f"*Max Positions:* {config.MAX_POSITIONS}\n"
            f"*Position Size:* {config.POSITION_SIZE*100}% of equity",
            parse_mode='Markdown'
        )

    async def _cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /positions command"""
        try:
            from alpaca.trading.client import TradingClient
            
            client = TradingClient(
                api_key=config.ALPACA_API_KEY,
                secret_key=config.ALPACA_SECRET_KEY,
                paper=True
            )
            
            positions = client.get_all_positions()
            
            if not positions:
                await update.message.reply_text("No open positions")
                return
                
            positions_text = "*Current Positions:*\n\n"
            for pos in positions:
                pl_pct = float(pos.unrealized_pl_pc) * 100
                positions_text += (
                    f"*{pos.symbol}*\n"
                    f"Qty: {pos.qty}\n"
                    f"Entry: ${float(pos.avg_entry_price):.2f}\n"
                    f"Current: ${float(pos.current_price):.2f}\n"
                    f"P/L: {pl_pct:+.2f}%\n\n"
                )
            
            await update.message.reply_text(positions_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            await update.message.reply_text("Error getting positions")

    async def _cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /balance command"""
        try:
            from alpaca.trading.client import TradingClient
            
            client = TradingClient(
                api_key=config.ALPACA_API_KEY,
                secret_key=config.ALPACA_SECRET_KEY,
                paper=True
            )
            
            account = client.get_account()
            
            balance_text = (
                f"*Account Balance*\n\n"
                f"Equity: ${float(account.equity):,.2f}\n"
                f"Cash: ${float(account.cash):,.2f}\n"
                f"Buying Power: ${float(account.buying_power):,.2f}\n"
                f"Day Trade Count: {account.daytrade_count}"
            )
            
            await update.message.reply_text(balance_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error getting balance: {str(e)}")
            await update.message.reply_text("Error getting account balance") 