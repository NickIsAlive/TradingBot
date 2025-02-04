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
import talib

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
        self.notifier = TelegramNotifier()
        self.screener = StockScreener(self.data_client)
        self.trading_symbols = []
        self.position_trackers = {}  # Track position metrics for trailing stops
        
    async def update_trading_symbols(self):
        """Update the list of trading symbols based on screening criteria."""
        try:
            new_symbols = await self.screener.get_trading_candidates(max_stocks=config.MAX_POSITIONS)
            
            if new_symbols:
                old_symbols = set(self.trading_symbols)
                new_symbols_set = set(new_symbols)
                
                # Log symbols that were added and removed
                added = new_symbols_set - old_symbols
                removed = old_symbols - new_symbols_set
                
                if added:
                    logger.info(f"Added new trading symbols: {added}")
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
            
    async def get_historical_data(self, symbol: str) -> pd.DataFrame:
        """
        Get historical price data for a symbol.
        
        Args:
            symbol (str): The trading symbol
            
        Returns:
            pd.DataFrame: DataFrame with historical price data
        """
        try:
            end_dt = datetime.now()
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
            Quantity to trade
        """
        try:
            account = self.trading_client.get_account()
            equity = float(account.equity)
            
            # Get historical volatility
            df = self.get_historical_data(symbol)
            returns = np.log(df['close'] / df['close'].shift(1))
            volatility = returns.std() * np.sqrt(252)
            
            # Adjust position size based on volatility
            # Lower volatility = larger position size
            volatility_factor = 1 / (1 + volatility)
            
            # Calculate base position value
            base_position_value = equity * config.POSITION_SIZE
            
            # Adjust for volatility
            adjusted_position_value = base_position_value * volatility_factor
            
            # Ensure we don't exceed maximum position size
            max_position_value = equity * config.MAX_POSITION_PCT
            position_value = min(adjusted_position_value, max_position_value)
            
            # Calculate quantity
            quantity = position_value / current_price
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
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
        """
        Process a single symbol for trading opportunities with enhanced risk management.
        
        Args:
            symbol (str): The trading symbol
        """
        try:
            # Get historical data
            df = await self.get_historical_data(symbol)
            if df.empty:
                return
                
            current_price = df.close.iloc[-1]
            
            # Detect market regime
            regime = self.detect_market_regime(df)
            logger.info(f"Market regime for {symbol}: {regime}")
            
            # Calculate volume ratio for signal confirmation
            avg_volume = df.volume.mean()
            current_volume = df.volume.iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            # Calculate RSI for signal confirmation
            rsi = talib.RSI(df.close.values, timeperiod=14)[-1]
            
            # Calculate ATR for position sizing
            atr = talib.ATR(df.high.values, df.low.values, df.close.values, timeperiod=14)[-1]
            
            # Get optimal Bollinger Bands parameters
            try:
                params = self.screener.get_optimal_parameters(symbol)
            except Exception as e:
                logger.warning(f"Could not get optimal parameters for {symbol}, using defaults: {str(e)}")
                params = {'period': 20, 'std': 2.0}
            
            # Calculate indicators
            self.technical_analysis.update_parameters(
                period=params['period'],
                num_std=params['std']
            )
            
            upper_band, middle_band, lower_band = self.technical_analysis.calculate_bollinger_bands(df.close)
            
            # Generate enhanced trading signal
            signal = self.technical_analysis.generate_signal(
                current_price,
                upper_band.iloc[-1],
                lower_band.iloc[-1],
                rsi=rsi,
                volume_ratio=volume_ratio
            )
            
            # Check current position
            position = self.check_position(symbol)
            
            if position:
                # Enhanced exit logic
                should_exit, exit_reason = self.update_trailing_stops(
                    symbol, 
                    current_price,
                    atr=atr,
                    rsi=rsi
                )
                
                if should_exit:
                    logger.info(f"{exit_reason} triggered for {symbol}")
                    await self.execute_trade(symbol, 'SELL', position['qty'])
                    del self.position_trackers[symbol]
                    
            elif signal in ['BUY', 'STRONG_BUY']:
                # Check overall market conditions
                if not self.is_market_favorable():
                    logger.info(f"Skipping {signal} signal for {symbol} due to unfavorable market conditions")
                    return
                    
                # Calculate base position size
                base_quantity = self.calculate_position_size(symbol, current_price)
                
                # Adjust position size based on market regime
                adjusted_quantity = self.adjust_position_size_for_regime(base_quantity, regime)
                
                if adjusted_quantity > 0:
                    # Execute buy order with enhanced logging
                    logger.info(f"Executing {signal} for {symbol} - Price: ${current_price:.2f}, "
                              f"RSI: {rsi:.1f}, Volume Ratio: {volume_ratio:.1f}, Regime: {regime}")
                    
                    await self.execute_trade(symbol, 'BUY', adjusted_quantity)
                    
                    # Initialize position tracking with enhanced metrics
                    self.initialize_position_tracker(
                        symbol,
                        entry_price=current_price,
                        quantity=adjusted_quantity,
                        atr=atr
                    )
                
        except Exception as e:
            error_msg = f"Error processing {symbol}: {str(e)}"
            logger.error(error_msg)
            await self.notifier.send_error_notification(error_msg)

    async def execute_trade(self, symbol: str, side: str, quantity: float) -> None:
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
            
            await self.notifier.send_trade_notification(
                symbol=symbol,
                action=side,
                price=float(filled_order.filled_avg_price),
                quantity=float(filled_order.filled_qty)
            )
            
        except Exception as e:
            error_msg = f"Error executing {side} order for {symbol}: {str(e)}"
            logger.error(error_msg)
            await self.notifier.send_error_notification(error_msg)
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