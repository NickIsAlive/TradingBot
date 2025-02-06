from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed, Adjustment
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import config
from indicators import TechnicalAnalysis
from notifications import TelegramNotifier
from screener import StockScreener
from database import TradingDatabase
import talib
import pytz
import asyncio

logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        """Initialize the trading bot with API clients and configuration."""
        self.trading_client = TradingClient(
            api_key=config.ALPACA_API_KEY,
            secret_key=config.ALPACA_SECRET_KEY,
            paper=True
        )
        
        self.data_client = StockHistoricalDataClient(
            api_key=config.ALPACA_API_KEY,
            secret_key=config.ALPACA_SECRET_KEY
        )
        
        self.technical_analysis = TechnicalAnalysis()
        self._notifier = None  # Initialize as None
        self.screener = StockScreener(self.data_client)
        self.db = TradingDatabase()
        self.trading_symbols = []
        self.position_trackers = {}  # Track position metrics for trailing stops
        self.active_trades = {}  # Track active trade IDs for database updates
        
        # Initialize account info
        try:
            account = self.trading_client.get_account()
            self.initial_equity = float(account.equity)
            logger.info(f"Initial account equity: ${self.initial_equity:,.2f}")
        except Exception as e:
            logger.error(f"Error initializing account: {str(e)}")
            self.initial_equity = 100000.0  # Default to 100k if can't get actual equity
        
    @property
    def notifier(self):
        """Lazy initialization of the Telegram notifier."""
        if self._notifier is None:
            self._notifier = TelegramNotifier()
            self._notifier.set_trading_client(self.trading_client)
        return self._notifier
        
    async def start(self):
        """Start the Telegram bot."""
        await self.notifier.start()
        logger.info("Telegram bot started")
        return self
        
    async def stop(self):
        """Stop the Telegram bot and clean up resources."""
        await self.notifier.stop()
        self.db.close()
        logger.info("Telegram bot stopped and database connection closed")
        return self

    def send_notification(self, message: str) -> None:
        """Send a notification through the Telegram bot."""
        try:
            # Create task to run coroutine
            asyncio.create_task(self.notifier.send_message(message))
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")

    def send_error(self, error_message: str) -> None:
        """Send an error notification through the Telegram bot."""
        try:
            self.notifier.send_error_notification(error_message)
        except Exception as e:
            logger.error(f"Error sending error notification: {str(e)}")

    def send_trade_notification(self, symbol: str, action: str, price: float, quantity: float, execution_time: datetime, market_conditions: str, sentiment_score: float) -> None:
        """Send a trade notification through the Telegram bot."""
        try:
            self.notifier.send_trade_notification(
                symbol=symbol,
                action=action,
                price=price,
                quantity=quantity,
                execution_time=execution_time,
                market_conditions=market_conditions,
                sentiment_score=sentiment_score
            )
        except Exception as e:
            logger.error(f"Error sending trade notification: {str(e)}")

    def send_market_update(self, market_summary: str) -> None:
        """Send a market update through the Telegram bot."""
        try:
            self.notifier.send_market_update(market_summary)
        except Exception as e:
            logger.error(f"Error sending market update: {str(e)}")

    def send_account_summary(self) -> None:
        """Send an account summary through the Telegram bot."""
        try:
            self.notifier.send_account_summary()
        except Exception as e:
            logger.error(f"Error sending account summary: {str(e)}")

    async def update_trading_symbols(self, markets: list = None, max_stocks: int = 5) -> None:
        """Update trading symbols with multi-market support."""
        try:
            # If no markets specified, use all configured markets
            if markets is None:
                markets = [market['name'] for market in config.MARKETS_TO_TRADE]
            
            # Get trading candidates across specified markets
            new_symbols = self.screener.get_trading_candidates(
                max_stocks=max_stocks,
                markets=markets
            )
            
            if new_symbols:
                old_symbols = set(self.trading_symbols)
                new_symbols_set = set(new_symbols)
                
                # Log symbols that were added and removed
                added = new_symbols_set - old_symbols
                removed = old_symbols - new_symbols_set
                
                if added:
                    logger.info(f"Added new trading symbols: {added}")
                    # Log market distribution of new symbols
                    market_distribution = {}
                    for symbol in added:
                        market = self.get_symbol_market(symbol)
                        market_distribution[market] = market_distribution.get(market, 0) + 1
                    logger.info(f"Market distribution of new symbols: {market_distribution}")
                
                if removed:
                    logger.info(f"Removed trading symbols: {removed}")
                
                self.trading_symbols = new_symbols
                
                # Notify about symbol changes
                if added or removed:
                    message = "🔄 Trading Symbols Updated\n\n"
                    if added:
                        message += f"Added: {', '.join(added)}\n"
                    if removed:
                        message += f"Removed: {', '.join(removed)}"
                    await self.notifier.send_message(message)
        
        except Exception as e:
            logger.error(f"Error updating trading symbols: {str(e)}")

    def get_symbol_market(self, symbol: str) -> str:
        """
        Determine the market for a given stock symbol.
        
        Args:
            symbol (str): Stock symbol
        
        Returns:
            str: Market name (e.g., 'NYSE', 'NASDAQ')
        """
        # Market-specific symbol mappings
        market_mappings = {
            'NYSE': lambda s: not s.endswith('.L') and not s.endswith('.AX'),
            'NASDAQ': lambda s: not s.endswith('.L') and not s.endswith('.AX'),
            'LSE': lambda s: s.endswith('.L'),
            'ASX': lambda s: s.endswith('.AX')
        }
        
        # Default to NYSE if no specific mapping matches
        for market, check_func in market_mappings.items():
            if check_func(symbol):
                return market
        
        return 'NYSE'  # Default fallback

    def get_historical_data(self, symbol: str) -> pd.DataFrame:
        """
        Get historical price data for a symbol.
        
        Args:
            symbol (str): The trading symbol
            
        Returns:
            pd.DataFrame: DataFrame with historical price data
        """
        try:
            # Get current time in UTC
            end_dt = datetime.now(pytz.UTC)
            start_dt = end_dt - timedelta(days=30)  # Get 30 days of data
            
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_dt,
                end=end_dt,
                adjustment=Adjustment.SPLIT,
                feed=DataFeed.IEX
            )
            
            bars = self.data_client.get_stock_bars(request)
            
            if bars and bars.data:
                df = pd.DataFrame([{
                    'timestamp': bar.timestamp,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': float(bar.volume)
                } for bar in bars.data[symbol]])
                
                if not df.empty:
                    df.set_index('timestamp', inplace=True)
                    return df
                    
            logger.error(f"No data available for {symbol}")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return pd.DataFrame()

    def check_position(self, symbol: str) -> dict:
        """
        Check if we have an open position for the symbol.
        
        Args:
            symbol (str): The trading symbol
            
        Returns:
            dict: Position information or None
        """
        try:
            positions = self.trading_client.get_all_positions()
            for position in positions:
                if position.symbol == symbol:
                    return {
                        'qty': float(position.qty),
                        'avg_entry_price': float(position.avg_entry_price)
                    }
            return None
        except Exception as e:
            logger.error(f"Error checking position for {symbol}: {str(e)}")
            raise

    def calculate_position_size(self, symbol: str, current_price: float) -> float:
        """
        Calculate dynamic position size based on account equity and volatility.
        
        Args:
            symbol: Stock symbol
            current_price: Current stock price
            
        Returns:
            float: Quantity to trade
        """
        try:
            # Get current account equity
            account = self.trading_client.get_account()
            current_equity = float(account.equity)
            
            if current_equity <= 0:
                logger.error("Invalid account equity")
                return 0
            
            # Get historical volatility
            df = self.get_historical_data(symbol)
            if df.empty:
                logger.error("No historical data available for volatility calculation")
                return 0
                
            returns = np.log(df['close'] / df['close'].shift(1))
            volatility = returns.std() * np.sqrt(252)
            
            # Adjust position size based on volatility
            # Lower volatility = larger position size
            volatility_factor = 1 / (1 + volatility) if volatility > 0 else 0.5
            
            # Calculate base position value using current equity
            base_position_value = current_equity * config.POSITION_SIZE
            
            # Adjust for volatility
            adjusted_position_value = base_position_value * volatility_factor
            
            # Ensure we don't exceed maximum position size
            max_position_value = current_equity * config.MAX_POSITION_PCT
            position_value = min(adjusted_position_value, max_position_value)
            
            # Calculate quantity
            quantity = position_value / current_price if current_price > 0 else 0
            
            logger.info(f"Calculated position size for {symbol}: {quantity:.2f} shares at ${current_price:.2f}")
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size for {symbol}: {str(e)}")
            return 0

    def initialize_position_tracker(self, symbol: str, entry_price: float, 
                                  quantity: float, atr: float):
        """Initialize enhanced position tracking."""
        self.position_trackers[symbol] = {
            'entry_price': entry_price,
            'quantity': quantity,
            'highest_price': entry_price,
            'lowest_price': entry_price,
            'atr': atr,
            'initial_stop': entry_price - (2 * atr),  # 2 ATR initial stop
            'trailing_stop': entry_price - (2 * atr)
        }

    def update_trailing_stops(self, symbol: str, current_price: float, 
                            atr: float = None, rsi: float = None) -> tuple:
        """
        Update trailing stops with enhanced exit conditions.
        
        Returns:
            Tuple of (should_exit, exit_reason)
        """
        if symbol not in self.position_trackers:
            return False, None
            
        tracker = self.position_trackers[symbol]
        entry_price = tracker['entry_price']
        
        # Update price extremes
        tracker['highest_price'] = max(tracker['highest_price'], current_price)
        tracker['lowest_price'] = min(tracker['lowest_price'], current_price)
        
        # Calculate profit/loss
        pnl_pct = (current_price - entry_price) / entry_price
        
        # Update ATR if provided
        if atr is not None:
            tracker['atr'] = atr
        
        # Enhanced exit conditions
        
        # 1. Stop loss hit
        if current_price <= tracker['trailing_stop']:
            return True, 'Trailing Stop'
            
        # 2. Take profit at 3x ATR
        if pnl_pct > 0 and current_price >= entry_price + (3 * tracker['atr']):
            return True, 'Take Profit Target'
            
        # 3. RSI-based exit
        if rsi is not None and rsi > 80 and pnl_pct > 0:
            return True, 'RSI Overbought Exit'
            
        # 4. Time-based exit if profit target not hit
        days_held = (datetime.now() - tracker.get('entry_time', datetime.now())).days
        if days_held > 5 and pnl_pct < 0.02:  # Exit if no significant profit after 5 days
            return True, 'Time Stop'
        
        # Update trailing stop if in profit
        if pnl_pct > 0:
            # Use tighter trailing stop as profit increases
            stop_distance = max(1.5 * tracker['atr'], 
                              (tracker['highest_price'] - entry_price) * 0.5)
            new_stop = current_price - stop_distance
            tracker['trailing_stop'] = max(tracker['trailing_stop'], new_stop)
        
        return False, None

    def detect_market_regime(self, df: pd.DataFrame) -> str:
        """
        Detect the current market regime (trending/ranging) based on price action.
        
        Args:
            df: DataFrame with historical price data
            
        Returns:
            str: Market regime ('TRENDING_UP', 'TRENDING_DOWN', 'RANGING')
        """
        try:
            # Calculate moving averages
            sma20 = talib.SMA(df['close'].values, timeperiod=20)
            sma50 = talib.SMA(df['close'].values, timeperiod=50)
            
            # Calculate ADX for trend strength
            adx = talib.ADX(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
            
            # Get current values
            current_adx = adx[-1]
            current_price = df['close'].iloc[-1]
            current_sma20 = sma20[-1]
            current_sma50 = sma50[-1]
            
            # Strong trend if ADX > 25
            if current_adx > 25:
                if current_price > current_sma20 and current_sma20 > current_sma50:
                    return 'TRENDING_UP'
                elif current_price < current_sma20 and current_sma20 < current_sma50:
                    return 'TRENDING_DOWN'
            
            return 'RANGING'
            
        except Exception as e:
            logger.error(f"Error detecting market regime: {str(e)}")
            return 'RANGING'  # Default to ranging if error occurs

    def adjust_position_size_for_regime(self, base_quantity: float, regime: str) -> float:
        """
        Adjust position size based on market regime.
        
        Args:
            base_quantity: Initial position size
            regime: Market regime
            
        Returns:
            float: Adjusted position size
        """
        try:
            # Reduce position size in ranging markets
            if regime == 'RANGING':
                return base_quantity * 0.7  # 30% reduction
            # Increase position size in trending markets
            elif regime in ['TRENDING_UP', 'TRENDING_DOWN']:
                return base_quantity * 1.2  # 20% increase
            return base_quantity
            
        except Exception as e:
            logger.error(f"Error adjusting position size for regime: {str(e)}")
            return base_quantity

    async def process_symbol(self, symbol: str) -> None:
        """Process a single symbol for trading opportunities."""
        try:
            # Get current account info for position sizing
            account = self.trading_client.get_account()
            current_equity = float(account.equity)
            
            # Get historical data and calculate indicators
            df = self.get_historical_data(symbol)
            if df.empty:
                logger.warning(f"No historical data available for {symbol}")
                return
            
            # Calculate technical indicators
            signal, current_price, rsi, atr = self.analyze_symbol(df)
            
            if not signal:
                return
            
            # Check current position
            position = self.check_position(symbol)
            
            if position:
                # Exit logic
                should_exit, exit_reason = self.update_trailing_stops(
                    symbol, 
                    current_price,
                    atr=atr,
                    rsi=rsi.iloc[-1] if isinstance(rsi, pd.Series) else rsi[-1] if isinstance(rsi, np.ndarray) else rsi
                )
                
                if should_exit:
                    logger.info(f"{exit_reason} triggered for {symbol}")
                    self.execute_trade(symbol, 'SELL', position['qty'])
                    
                    # Record trade exit in database
                    if symbol in self.active_trades:
                        await self.db.record_trade_exit(
                            self.active_trades[symbol],
                            current_price,
                            exit_reason
                        )
                        del self.active_trades[symbol]
                        del self.position_trackers[symbol]
            
            elif signal == 'BUY':
                # Calculate position size using current equity
                position_size = self.calculate_position_size(symbol, current_price)
                
                if position_size > 0:
                    # Execute buy order
                    logger.info(f"Executing {signal} for {symbol} - Price: ${current_price:.2f}, Size: {position_size:.2f} shares")
                    self.execute_trade(symbol, 'BUY', position_size)
                    
                    # Record trade entry in database
                    trade_id = await self.db.record_trade_entry(
                        symbol=symbol,
                        side='BUY',
                        quantity=position_size,
                        price=current_price,
                        strategy='ENHANCED_BOLLINGER',
                        market_regime=self.detect_market_regime(df),
                        rsi=rsi[-1] if isinstance(rsi, (pd.Series, np.ndarray)) else rsi,
                        atr=atr
                    )
                    
                    # Track active trade
                    self.active_trades[symbol] = trade_id
                    
                    # Initialize position tracking
                    self.initialize_position_tracker(
                        symbol,
                        entry_price=current_price,
                        quantity=position_size,
                        atr=atr
                    )
            
            # Update daily performance metrics
            await self.db.update_daily_performance()
                
        except Exception as e:
            logger.error(f"Error processing {symbol}: {str(e)}")
            if self._notifier:
                self._notifier.send_error_notification(f"Error processing {symbol}: {str(e)}")

    def execute_trade(self, symbol: str, side: str, quantity: float) -> None:
        """
        Execute a trade order.
        
        Args:
            symbol (str): The trading symbol
            side (str): Order side (buy/sell)
            quantity (float): Order quantity
        """
        try:
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=OrderSide.BUY if side == 'BUY' else OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            
            order = self.trading_client.submit_order(order_data)
            
            # Wait for order to fill
            filled_order = self.trading_client.get_order(order.id)
            
            # Get market conditions and sentiment
            df = self.get_historical_data(symbol)
            market_conditions = self.detect_market_regime(df)
            sentiment_score = 0.5  # Default neutral sentiment
            
            self.notifier.send_trade_notification(
                symbol=symbol,
                action=side,
                price=float(filled_order.filled_avg_price),
                quantity=float(filled_order.filled_qty),
                execution_time=datetime.now(pytz.UTC),
                market_conditions=market_conditions,
                sentiment_score=sentiment_score
            )
            
        except Exception as e:
            error_msg = f"Error executing {side} order for {symbol}: {str(e)}"
            logger.error(error_msg)
            self.notifier.send_error_notification(error_msg)
            raise

    def is_market_favorable(self) -> bool:
        """
        Check if overall market conditions are favorable for trading.
        """
        try:
            # Get SPY data as market proxy
            spy_data = self.get_historical_data('SPY')
            if spy_data.empty:
                return False
                
            # Calculate market trend
            spy_sma20 = talib.SMA(spy_data.close.values, timeperiod=20)[-1]
            spy_sma50 = talib.SMA(spy_data.close.values, timeperiod=50)[-1]
            
            # Calculate market volatility
            spy_atr = talib.ATR(spy_data.high.values, spy_data.low.values, spy_data.close.values, timeperiod=14)[-1]
            spy_price = spy_data.close.iloc[-1]
            market_volatility = spy_atr / spy_price
            
            # Market conditions are favorable if:
            # 1. SPY is above both moving averages (uptrend)
            # 2. Market volatility is not too high
            return (spy_price > spy_sma20 and spy_price > spy_sma50 and 
                   market_volatility < 0.02)  # 2% volatility threshold
                   
        except Exception as e:
            logger.error(f"Error checking market conditions: {str(e)}")
            return False  # Conservative approach - assume unfavorable if can't check 

    def analyze_symbol(self, df: pd.DataFrame) -> tuple:
        """
        Analyze a symbol and generate trading signals.
        
        Args:
            df (pd.DataFrame): DataFrame with historical price data
            
        Returns:
            tuple: (signal, current_price, rsi, atr)
        """
        try:
            # Ensure we're working with pandas Series
            close_series = pd.Series(df.close)
            high_series = pd.Series(df.high)
            low_series = pd.Series(df.low)
            current_price = close_series.iloc[-1]
            
            # Calculate indicators
            upper_band, middle_band, lower_band = self.technical_analysis.calculate_bollinger_bands(close_series)
            rsi = self.technical_analysis.calculate_rsi(close_series)
            macd, macd_signal, macd_hist = self.technical_analysis.calculate_macd(close_series)
            atr = talib.ATR(high_series.values, low_series.values, close_series.values, timeperiod=14)[-1]
            
            # Generate trading signal
            signal = self.technical_analysis.generate_signal(
                price=current_price,
                upper_band=upper_band.iloc[-1] if isinstance(upper_band, pd.Series) else upper_band[-1],
                lower_band=lower_band.iloc[-1] if isinstance(lower_band, pd.Series) else lower_band[-1],
                rsi=rsi.iloc[-1] if isinstance(rsi, pd.Series) else rsi[-1] if isinstance(rsi, np.ndarray) else rsi
            )
            
            return signal, current_price, rsi, atr
            
        except Exception as e:
            logger.error(f"Error analyzing symbol: {str(e)}")
            return None, None, None, None 