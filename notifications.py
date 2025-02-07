import logging
import os
import fcntl
import asyncio
from typing import Optional
from telegram import Bot, Update
from telegram.error import TelegramError, Conflict, NetworkError
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
import config
from datetime import datetime, timedelta
import pandas as pd
import pytz
from threading import Lock
from functools import wraps

logger = logging.getLogger(__name__)
SINGLETON_LOCK_FILE = '/tmp/trading_bot.lock'

class SingleInstanceException(Exception):
    """Exception raised when another instance of the bot is already running."""
    pass

class SingletonMeta(type):
    _instances = {}
    _lock = Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
            return cls._instances[cls]

class TelegramNotifier(metaclass=SingletonMeta):
    def __init__(self):
        self._lock_file_handle = None
        self._running = False
        self._app_initialized = False
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        self.message_queue = asyncio.Queue()
        self._ensure_single_instance()

    def _ensure_single_instance(self):
        """Ensures only one instance is running using file locking"""
        try:
            self._lock_file_handle = open(SINGLETON_LOCK_FILE, 'w')
            fcntl.lockf(self._lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_file_handle.write(f"{os.getpid()}\n")
            self._lock_file_handle.flush()
            logger.info("Acquired singleton lock")
        except IOError:
            logger.error("Another instance is already running. Exiting.")
            raise SystemExit(1)

    async def initialize(self) -> None:
        """Async initialization of the Telegram bot"""
        if self._app_initialized:
            logger.info("Bot already initialized, skipping...")
            return

        try:
            logger.info("Initializing Telegram bot...")
            
            # Delete any existing webhook first
            try:
                webhook_info = await self.bot.get_webhook_info()
                if webhook_info.url:
                    await self.bot.delete_webhook(drop_pending_updates=True)
                    await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Error checking webhook: {str(e)}")

            # Initialize application with environment variable token
            self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
            self.bot = self.application.bot
            
            # Set up command handlers
            self._setup_handlers()
            
            # Start message queue processor
            asyncio.create_task(self._message_worker())
            
            self._app_initialized = True
            logger.info("Telegram bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {str(e)}")
            self._cleanup()
            raise

    async def _configure_webhook(self) -> None:
        """Configure bot to use polling instead of webhook"""
        try:
            # First, get current webhook info
            webhook_info = await self.bot.get_webhook_info()
            if webhook_info.url:
                # If there's an existing webhook, delete it and wait
                await self.bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(1)  # Give Telegram time to process
            logger.info("Webhook configuration cleared")
        except Exception as e:
            logger.error(f"Error configuring bot: {str(e)}")
            raise

    def _setup_handlers(self) -> None:
        """Register command handlers"""
        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("help", self._cmd_help))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_error_handler(self._error_handler)
        logger.info("Command handlers registered")

    async def start(self) -> None:
        """Start the bot with polling"""
        if self._running:
            logger.warning("Bot is already running")
            return

        try:
            # Ensure clean webhook state
            if self.bot:
                await self.bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(1)
            
            # Initialize if needed
            if not self._app_initialized:
                await self.initialize()
            
            # Start polling in a background task
            self._running = True
            self.polling_task = asyncio.create_task(
                self.application.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=['message', 'callback_query'],
                    close_loop=False
                )
            )
            logger.info("Telegram bot started successfully with polling")
        except Exception as e:
            self._running = False
            logger.error(f"Failed to start bot: {str(e)}")
            raise

    async def stop(self) -> None:
        """Stop the bot gracefully"""
        if not self._running:
            logger.warning("Bot is not running")
            return

        logger.info("Stopping Telegram bot...")
        self._running = False
        
        try:
            # Stop polling first
            if hasattr(self, 'polling_task'):
                self.polling_task.cancel()
                try:
                    await self.polling_task
                except asyncio.CancelledError:
                    pass
            
            # Then stop the application
            if self.application and self.application.updater:
                if self.application.updater.running:
                    await self.application.updater.stop()
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
            
            # Clear webhook one last time
            if self.bot:
                await self.bot.delete_webhook(drop_pending_updates=True)
            
            self._cleanup()
            logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error(f"Error during bot shutdown: {str(e)}")

    def _cleanup(self) -> None:
        """Release resources and clean up"""
        if self._lock_file_handle:
            try:
                fcntl.lockf(self._lock_file_handle, fcntl.LOCK_UN)
                self._lock_file_handle.close()
                os.remove(SINGLETON_LOCK_FILE)
            except Exception as e:
                logger.warning(f"Error cleaning up lock file: {str(e)}")
            finally:
                self._lock_file_handle = None

    async def _message_worker(self) -> None:
        """Process messages from the queue"""
        logger.info("Starting message worker")
        while True:  # Changed from self._running to True
            try:
                if not self._running:
                    await asyncio.sleep(0.1)
                    continue
                
                message = await self.message_queue.get()
                await self._send_message(message)
                self.message_queue.task_done()
                await asyncio.sleep(0.1)  # Rate limiting
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await asyncio.sleep(1)  # Wait longer on error
        logger.info("Message worker stopped")

    async def _send_message(self, message: str) -> None:
        """Internal method to send messages with retries"""
        retries = 0
        max_retries = 3
        while retries < max_retries:
            try:
                # Update the URL to use the new token
                url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
                await self.bot.send_message(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode='HTML'
                )
                return
            except NetworkError as e:
                retries += 1
                wait_time = 2 ** retries
                logger.warning(f"Message send failed (attempt {retries}/{max_retries}): {str(e)}")
                await asyncio.sleep(wait_time)
            except TelegramError as e:
                logger.error(f"Telegram API error: {str(e)}")
                break

        logger.error(f"Failed to send message after {max_retries} attempts")

    # Command handlers
    async def _cmd_start(self, update: Update, context: CallbackContext) -> None:
        """Handle /start command"""
        await self.send_queued_message("🤖 Trading Bot Online\n\nAvailable commands:\n/status - Bot status\n/help - Show help")

    async def _cmd_help(self, update: Update, context: CallbackContext) -> None:
        """Handle /help command"""
        help_text = (
            "🆘 <b>Help Menu</b>\n\n"
            "/start - Start the bot\n"
            "/status - Show system status\n"
            "/help - Show this help message\n"
            "\nReport issues to @your_username"
        )
        await self.send_queued_message(help_text)

    async def _cmd_status(self, update: Update, context: CallbackContext) -> None:
        """Handle /status command"""
        status = "🟢 Operational" if self._running else "🔴 Offline"
        await self.send_queued_message(f"<b>System Status</b>\n\n{status}")

    # Error handling
    async def _error_handler(self, update: Update, context: CallbackContext) -> None:
        """Handle errors in the dispatcher"""
        error = context.error
        if isinstance(error, Conflict):
            logger.error("Conflict error detected. Possible duplicate bot instances.")
            await self.stop()
        elif isinstance(error, NetworkError):
            logger.warning("Network error occurred. Attempting to reconnect...")
            await self.start()
        else:
            logger.error(f"Unhandled error: {str(error)}")

    # Public API
    async def send_queued_message(self, message: str) -> None:
        """Add message to the processing queue"""
        await self.message_queue.put(message)

    def send_immediate_message(self, message: str) -> None:
        """Send message immediately (use with caution)"""
        asyncio.create_task(self._send_message(message))

    async def send_message(self, message: str) -> None:
        """Alias for send_queued_message for backward compatibility"""
        await self.send_queued_message(message) 