import logging
import telegram
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler
import config
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot = telegram.Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.trading_client = None  # Will be set by TradingBot

    def set_trading_client(self, trading_client):
        """Set the trading client for accessing account and trade information."""
        self.trading_client = trading_client

    async def setup_commands(self, application: Application):
        """Set up command handlers for the bot."""
        application.add_handler(CommandHandler("symbols", self.cmd_symbols))
        application.add_handler(CommandHandler("trades", self.cmd_trades))
        application.add_handler(CommandHandler("profits", self.cmd_profits))
        application.add_handler(CommandHandler("balance", self.cmd_balance))

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

    async def cmd_symbols(self, update: telegram.Update, context) -> None:
        """Handle /symbols command - Show current trading symbols."""
        if not self.trading_client:
            await self.send_message("❌ Trading client not initialized")
            return

        try:
            positions = self.trading_client.get_all_positions()
            if not positions:
                await self.send_message("📊 No active positions")
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

            await self.send_message(message)

        except Exception as e:
            await self.send_error_notification(f"Error fetching symbols: {str(e)}")

    async def cmd_trades(self, update: telegram.Update, context) -> None:
        """Handle /trades command - Show trades from the last month."""
        if not self.trading_client:
            await self.send_message("❌ Trading client not initialized")
            return

        try:
            # Get trades from the last 30 days
            end = datetime.now()
            start = end - timedelta(days=30)
            
            activities = self.trading_client.get_activities(
                activity_types=['FILL'],
                start=start,
                end=end
            )

            if not activities:
                await self.send_message("📈 No trades in the last 30 days")
                return

            message = "📈 <b>Recent Trades (Last 30 Days)</b>\n\n"
            for activity in activities:
                side = activity.side
                symbol = activity.symbol
                price = float(activity.price)
                qty = float(activity.qty)
                timestamp = activity.timestamp.strftime('%Y-%m-%d %H:%M')
                
                message += (
                    f"Date: {timestamp}\n"
                    f"Symbol: {symbol}\n"
                    f"Action: {side}\n"
                    f"Price: ${price:.2f}\n"
                    f"Quantity: {qty}\n"
                    f"Total: ${price * qty:.2f}\n\n"
                )

            await self.send_message(message)

        except Exception as e:
            await self.send_error_notification(f"Error fetching trades: {str(e)}")

    async def cmd_profits(self, update: telegram.Update, context) -> None:
        """Handle /profits command - Show total profits/losses in the last month."""
        if not self.trading_client:
            await self.send_message("❌ Trading client not initialized")
            return

        try:
            # Get portfolio history for the last month
            end = datetime.now()
            start = end - timedelta(days=30)
            
            history = self.trading_client.get_portfolio_history(
                timeframe='1D',
                start=start,
                end=end
            )

            if not history:
                await self.send_message("📊 No portfolio history available")
                return

            # Calculate total P/L
            total_pl = float(history.profit_loss[-1])
            total_pl_pct = float(history.profit_loss_pct[-1])

            # Get daily P/L
            daily_pl = pd.Series(history.profit_loss)
            best_day = daily_pl.max()
            worst_day = daily_pl.min()

            message = (
                f"💰 <b>Profit/Loss Summary (Last 30 Days)</b>\n\n"
                f"Total P/L: ${total_pl:+,.2f} ({total_pl_pct:+.2f}%)\n"
                f"Best Day: ${best_day:+,.2f}\n"
                f"Worst Day: ${worst_day:+,.2f}\n"
            )

            await self.send_message(message)

        except Exception as e:
            await self.send_error_notification(f"Error fetching profits: {str(e)}")

    async def cmd_balance(self, update: telegram.Update, context) -> None:
        """Handle /balance command - Show account balance and performance."""
        if not self.trading_client:
            await self.send_message("❌ Trading client not initialized")
            return

        try:
            account = self.trading_client.get_account()
            
            # Calculate performance metrics
            equity = float(account.equity)
            cash = float(account.cash)
            starting_capital = float(account.initial_margin)  # Using initial margin as starting capital
            
            # Calculate percentage gain from starting capital
            pct_gain = ((equity - starting_capital) / starting_capital) * 100 if starting_capital > 0 else 0
            
            # Calculate buying power and day trading buying power
            buying_power = float(account.buying_power)
            day_trade_buying_power = float(account.daytrading_buying_power) if account.daytrading_buying_power else 0

            message = (
                f"💼 <b>Account Summary</b>\n\n"
                f"Equity: ${equity:,.2f}\n"
                f"Cash: ${cash:,.2f}\n"
                f"Starting Capital: ${starting_capital:,.2f}\n"
                f"Total Return: {pct_gain:+.2f}%\n\n"
                f"Buying Power: ${buying_power:,.2f}\n"
                f"Day Trading Buying Power: ${day_trade_buying_power:,.2f}\n"
                f"Account Status: {account.status}"
            )

            await self.send_message(message)

        except Exception as e:
            await self.send_error_notification(f"Error fetching account balance: {str(e)}") 