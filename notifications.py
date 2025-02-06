import logging
from telegram import Bot, Update
from telegram.error import TelegramError, Conflict, NetworkError
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, JobQueue
import config
from datetime import datetime, timedelta
import pandas as pd
from queue import Queue, Empty
import pytz
import time
import os
import fcntl
import atexit
import threading
import asyncio

logger = logging.getLogger(__name__)

class SingleInstanceException(Exception):
    pass

class TelegramNotifier:
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    _lock_file = '/tmp/telegram_bot.lock'
    _lock_fd = None
    _event_loop = None

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        with self._lock:
            if not self._initialized:
                self._initialized = True
                self._start_time = time.time()
                self.application = None
                self.trading_client = None
                self.message_queue = Queue()
                self._running = True
                self._event_loop = asyncio.new_event_loop()
                self._start_message_worker()

    async def initialize(self):
        """Async initialization of the bot."""
        await self._initialize_bot()

    async def _initialize_bot(self):
        """Async initialization of the bot."""
        try:
            logger.info("Starting async bot initialization...")
            
            # Verify token exists
            if not config.TELEGRAM_BOT_TOKEN:
                raise ValueError("Telegram bot token is not configured")
            
            logger.info("Bot token verified, proceeding with bot initialization...")
            
            # Initialize bot and application
            self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            self.chat_id = config.TELEGRAM_CHAT_ID
            
            # Verify chat ID
            logger.info(f"Using chat ID: {self.chat_id}")
            try:
                await self.bot.get_chat(self.chat_id)
                logger.info("Successfully verified chat ID")
            except Exception as e:
                logger.error(f"Failed to verify chat ID: {str(e)}")
                raise
            
            self._ensure_single_instance()
            
            logger.info("Creating Application instance...")
            try:
                self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
                # Initialize application only once here
                await self.application.initialize()
                logger.info("Application instance created and initialized successfully")
            except Exception as e:
                logger.error(f"Error creating Application instance: {str(e)}")
                raise
            
            logger.info("Setting up commands...")
            await self.setup_commands()
            
            # Test bot functionality
            try:
                logger.info("Sending test message...")
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text="🤖 Trading Bot initialized successfully!\n\nAvailable commands:\n/trades - View recent trades\n/symbols - View current positions\n/profits - View profit/loss\n/balance - View account balance\n/help - Show this help message",
                    parse_mode='HTML'
                )
                logger.info("Test message sent successfully")
            except Exception as e:
                logger.error(f"Failed to send test message: {str(e)}")
                raise
            
            atexit.register(self._cleanup)
            logger.info("Telegram bot initialized successfully")
            logger.info("Async bot initialization completed")
            
        except Exception as e:
            logger.error(f"Error initializing TelegramNotifier: {str(e)}")
            self.application = None  # Ensure application is None on error
            raise

    def _ensure_single_instance(self):
        try:
            self._lock_fd = open(self._lock_file, 'w')
            try:
                fcntl.lockf(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                logger.error("Another instance is already running")
                raise SingleInstanceException("Another bot instance is already running")
            
            # Write PID and start time
            self._lock_fd.write(f"{os.getpid()},{self._start_time}")
            self._lock_fd.flush()
            
            logger.info("Lock acquired, bot instance is running")
            
        except Exception as e:
            logger.error(f"Error in single instance check: {str(e)}")
            raise

    def _cleanup(self):
        try:
            # Signal worker thread to stop
            self._running = False
            
            if self._lock_fd:
                if not hasattr(self, '_start_time'):
                    self._start_time = 0
                
                try:
                    with open(self._lock_file, 'r') as f:
                        pid, start_time = f.read().split(',')
                        if float(start_time) != self._start_time:
                            logger.warning("Cleaning up stale lock from previous instance")
                except Exception as e:
                    logger.error(f"Error reading lock file: {str(e)}")
                
                try:
                    fcntl.lockf(self._lock_fd, fcntl.LOCK_UN)
                    self._lock_fd.close()
                    os.unlink(self._lock_file)
                except Exception as e:
                    logger.error(f"Error releasing lock: {str(e)}")
            
            # Wait for worker thread with timeout
            if hasattr(self, 'worker_thread'):
                try:
                    self.worker_thread.join(timeout=2)
                except Exception as e:
                    logger.error(f"Error joining worker thread: {str(e)}")
            
            logger.info("Full cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

    async def start(self):
        """Start the Telegram bot with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Remove initialization here since it's already done
                await self.application.start()
                await self.application.updater.start_polling()
                logger.info("Telegram bot started successfully")
                return
            except NetworkError as e:
                logger.warning(f"Connection attempt {attempt+1}/{max_retries} failed: {str(e)}")
                await asyncio.sleep(2 ** attempt)
        raise ConnectionError("Failed to start Telegram bot after multiple attempts")

    async def stop(self):
        """Stop the Telegram bot and clean up resources."""
        try:
            # Signal the message worker to stop
            self._running = False
            
            if self.application:
                # Stop the application first
                await self.application.stop()
                await self.application.shutdown()
                # Wait for any pending updates to complete
                await asyncio.sleep(1)
                self.application = None
            
            # Wait for message queue to empty with timeout
            try:
                self.message_queue.join()
            except Exception as e:
                logger.error(f"Error waiting for message queue: {str(e)}")
            
            logger.info("Telegram bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {str(e)}")
            raise

    def send_message(self, message: str) -> None:
        """Add message to queue instead of sending directly."""
        try:
            logger.info(f"Queueing message: {message[:100]}...")  # Log first 100 chars
            self.message_queue.put(message)
        except Exception as e:
            logger.error(f"Error queueing message: {str(e)}")

    def set_trading_client(self, trading_client):
        """Set the trading client for accessing account and trade information."""
        self.trading_client = trading_client

    async def error_handler(self, update: Update, context: CallbackContext) -> None:
        """Handle errors in the dispatcher."""
        try:
            if isinstance(context.error, Conflict):
                logger.warning("Update conflict detected, attempting to recover...")
                if self.application:
                    await self.stop()
                    await asyncio.sleep(2)
                    await self.start()
            elif isinstance(context.error, NetworkError):
                logger.warning("Network error detected, waiting before retry...")
                await asyncio.sleep(5)
            else:
                logger.error(f"Update {update} caused error: {context.error}")
        except Exception as e:
            logger.error(f"Error in error handler: {str(e)}")

    async def setup_commands(self):
        """Set up command handlers for the bot."""
        try:
            if not self.application:
                logger.error("Application not initialized")
                raise RuntimeError("Application not initialized")
            
            # Remove the initialization here since it's already done
            # Add command handlers directly to application
            self.application.add_handler(CommandHandler("symbols", self.cmd_symbols))
            self.application.add_handler(CommandHandler("trades", self.cmd_trades))
            self.application.add_handler(CommandHandler("profits", self.cmd_profits))
            self.application.add_handler(CommandHandler("balance", self.cmd_balance))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            
            # Add error handler
            self.application.add_error_handler(self.error_handler)
            
            # Add fallback handler for unrecognized commands
            self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))
            
            logger.info("Command handlers set up successfully")
            
        except Exception as e:
            logger.error(f"Error setting up commands: {str(e)}")
            raise

    def unknown_command(self, update: Update, context: CallbackContext) -> None:
        """Handle unknown commands."""
        self.send_message("❌ Unknown command. Use /help to see available commands.")

    def send_trade_notification(self, symbol: str, action: str, price: float, quantity: float, execution_time: datetime, market_conditions: str, sentiment_score: float) -> None:
        """Send a detailed trade notification."""
        try:
            # Add HTML escaping for special characters
            symbol = symbol.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            message = (
                f"🤖 <b>Trade Executed</b>\n\n"
                f"▪️ Symbol: <code>{symbol}</code>\n"
                f"▪️ Action: {action.upper()}\n"
                f"▪️ Price: ${price:.2f}\n"
                f"▪️ Quantity: {quantity:.2f}\n"
                f"▪️ Time: {execution_time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                f"▪️ Conditions: {market_conditions}\n"
                f"▪️ Sentiment: {sentiment_score:.2f}/1.0"
            )
            self.send_message(message)
        except Exception as e:
            logger.error(f"Error formatting trade notification: {str(e)}")

    def send_error_notification(self, error_message: str) -> None:
        """Send an error notification."""
        message = f"⚠️ <b>Error Alert</b>\n\n{error_message}"
        self.send_message(message)

    def cmd_symbols(self, update: Update, context: CallbackContext) -> None:
        """Handle /symbols command - Show current trading symbols."""
        try:
            if not self.trading_client:
                self.send_message("❌ Trading client not initialized")
                return

            account = self.trading_client.get_account()
            if not account:
                self.send_message("🔴 Unable to connect to trading account")
                return
            
            positions = self.trading_client.get_all_positions()
            if not positions:
                self.send_message("📊 No active positions")
                return

            message = "📊 <b>Current Positions</b>\n\n"
            for pos in positions:
                current_price = float(pos.current_price)
                entry_price = float(pos.avg_entry_price)
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                
                message += (
                    f"Symbol: {pos.symbol}\n"
                    f"Quantity: {pos.qty}\n"
                    f"Entry: ${entry_price:.2f}\n"
                    f"Current: ${current_price:.2f}\n"
                    f"P/L: {pnl_pct:+.2f}%\n\n"
                )

            self.send_message(message)

        except Exception as e:
            logger.error(f"Error in /symbols command: {str(e)}")
            self.send_error_notification(f"Command error: {str(e)}")

    def cmd_trades(self, update: Update, context: CallbackContext) -> None:
        """Handle /trades command - Show trades from the last month."""
        logger.info(f"Received /trades command from user {update.effective_user.id if update and update.effective_user else 'unknown'}")
        
        if not self.trading_client:
            logger.error("Trading client not initialized")
            self.send_message("❌ Trading client not initialized")
            return

        try:
            end = datetime.now(pytz.UTC)
            start = end - timedelta(days=30)
            
            logger.info("Fetching orders from Alpaca API...")
            # Get filled orders from the last 30 days using list_orders
            orders = self.trading_client.list_orders(
                status='closed',
                after=start.isoformat(),
                until=end.isoformat(),
                limit=50
            )

            if not orders:
                logger.info("No trades found in the last 30 days")
                self.send_message("📈 No trades in the last 30 days")
                return

            logger.info(f"Found {len(orders)} trades")
            message = "📈 <b>Recent Trades (Last 30 Days)</b>\n\n"
            for order in orders:
                side = order.side
                symbol = order.symbol
                price = float(order.filled_avg_price) if order.filled_avg_price else 0.0
                qty = float(order.filled_qty) if order.filled_qty else 0.0
                timestamp = order.filled_at.strftime('%Y-%m-%d %H:%M %Z') if order.filled_at else 'N/A'
                
                message += (
                    f"Date: {timestamp}\n"
                    f"Symbol: {symbol}\n"
                    f"Action: {side}\n"
                    f"Price: ${price:.2f}\n"
                    f"Quantity: {qty}\n"
                    f"Total: ${price * qty:.2f}\n\n"
                )

            logger.info("Sending trade history message")
            self.send_message(message)

        except Exception as e:
            error_msg = f"Error fetching trades: {str(e)}"
            logger.error(error_msg)
            self.send_error_notification(error_msg)

    def cmd_profits(self, update: Update, context: CallbackContext) -> None:
        """Handle /profits command - Show total profits/losses in the last month."""
        if not self.trading_client:
            self.send_message("❌ Trading client not initialized")
            return

        try:
            end = datetime.now(pytz.UTC)
            start = end - timedelta(days=30)
            
            history = self.trading_client.get_portfolio_history(
                timeframe='1D',
                start=start,
                end=end
            )

            if not history:
                self.send_message("📊 No portfolio history available")
                return

            total_pl = float(history.profit_loss[-1])
            total_pl_pct = float(history.profit_loss_pct[-1])

            daily_pl = pd.Series(history.profit_loss)
            best_day = daily_pl.max()
            worst_day = daily_pl.min()

            message = (
                f"💰 <b>Profit/Loss Summary (Last 30 Days)</b>\n\n"
                f"Total P/L: ${total_pl:+,.2f} ({total_pl_pct:+.2f}%)\n"
                f"Best Day: ${best_day:+,.2f}\n"
                f"Worst Day: ${worst_day:+,.2f}\n"
            )

            self.send_message(message)

        except Exception as e:
            self.send_error_notification(f"Error fetching profits: {str(e)}")

    def cmd_balance(self, update: Update, context: CallbackContext) -> None:
        """Handle /balance command - Show account balance and performance."""
        if not self.trading_client:
            self.send_message("❌ Trading client not initialized")
            return

        try:
            account = self.trading_client.get_account()
            
            equity = float(account.equity)
            cash = float(account.cash)
            starting_capital = float(account.initial_margin)
            pct_gain = ((equity - starting_capital) / starting_capital) * 100 if starting_capital > 0 else 0
            buying_power = float(account.buying_power)

            message = (
                f"💼 <b>Account Summary</b>\n\n"
                f"Equity: ${equity:,.2f}\n"
                f"Cash: ${cash:,.2f}\n"
                f"Starting Capital: ${starting_capital:,.2f}\n"
                f"Total Return: {pct_gain:+.2f}%\n"
                f"Buying Power: ${buying_power:,.2f}\n"
                f"Account Status: {account.status}"
            )

            self.send_message(message)

        except Exception as e:
            self.send_error_notification(f"Error fetching account balance: {str(e)}")

    def cmd_help(self, update: Update, context: CallbackContext) -> None:
        """Handle /help command - List available commands."""
        message = (
            "ℹ️ <b>Available Commands</b>\n\n"
            "/symbols - Show current trading symbols\n"
            "/trades - Show trades from the last month\n"
            "/profits - Show total profits/losses in the last month\n"
            "/balance - Show account balance and performance\n"
            "/help - Show this help message"
        )
        self.send_message(message)

    def send_account_summary(self) -> None:
        """Send a comprehensive account summary."""
        if not self.trading_client:
            self.send_message("❌ Trading client not initialized")
            return

        try:
            account = self.trading_client.get_account()
            equity = float(account.equity)
            cash = float(account.cash)
            starting_capital = float(account.initial_margin)
            pct_gain = ((equity - starting_capital) / starting_capital) * 100 if starting_capital > 0 else 0
            buying_power = float(account.buying_power)

            message = (
                f"💼 <b>Daily Account Summary</b>\n\n"
                f"Equity: ${equity:,.2f}\n"
                f"Cash: ${cash:,.2f}\n"
                f"Starting Capital: ${starting_capital:,.2f}\n"
                f"Total Return: {pct_gain:+.2f}%\n"
                f"Buying Power: ${buying_power:,.2f}\n"
                f"Account Status: {account.status}"
            )

            self.send_message(message)

        except Exception as e:
            self.send_error_notification(f"Error sending account summary: {str(e)}")

    def send_market_update(self, market_summary: str) -> None:
        """Send a market update message."""
        message = f"📊 <b>Market Update</b>\n\n{market_summary}"
        self.send_message(message)

    def _start_message_worker(self):
        """Start background thread to process messages."""
        from threading import Thread
        self.worker_thread = Thread(target=self._process_messages)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    async def _process_message(self, message: str) -> None:
        """Process a single message asynchronously."""
        try:
            logger.info(f"Sending message to Telegram: {message[:100]}...")  # Log first 100 chars
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info("Message sent successfully")
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")

    def _process_messages(self):
        """Process messages from the queue."""
        logger.info("Starting message processing worker thread")
        asyncio.set_event_loop(self._event_loop)
        
        while self._running:
            try:
                logger.debug("Checking message queue...")
                message = self.message_queue.get(timeout=1.0)  # 1 second timeout
                logger.info(f"Processing message from queue: {message[:100]}...")  # Log first 100 chars
                
                try:
                    self._event_loop.run_until_complete(self._process_message(message))
                    logger.info("Successfully processed message")
                except Exception as e:
                    logger.error(f"Failed to process message: {str(e)}")
                
                self.message_queue.task_done()
                time.sleep(0.5)  # Rate limiting
            except Empty:
                continue  # No messages, continue checking _running flag
            except Exception as e:
                logger.error(f"Error in message queue processing: {str(e)}")
                self.message_queue.task_done()
        
        self._event_loop.close()
        logger.info("Message worker thread stopped") 