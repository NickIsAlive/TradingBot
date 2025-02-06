import pandas as pd
import numpy as np
import talib
import logging
from typing import Tuple
import math

logger = logging.getLogger(__name__)

class TechnicalAnalysis:
    def __init__(self, period: int = 20, num_std: float = 2.0):
        """
        Initialize the technical analysis module with enhanced parameters.
        
        Args:
            period (int): The period for calculating Bollinger Bands
            num_std (float): Number of standard deviations for Bollinger Bands
        """
        self.period = period
        self.num_std = num_std

    def update_parameters(self, period: int = None, num_std: float = None):
        """
        Update Bollinger Bands parameters.
        
        Args:
            period (int): New period for calculations
            num_std (float): New number of standard deviations
        """
        if period is not None:
            self.period = period
        if num_std is not None:
            self.num_std = num_std

    def calculate_bollinger_bands(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands for a given price series.
        
        Args:
            prices (pd.Series): Series of closing prices
            
        Returns:
            Tuple[pd.Series, pd.Series, pd.Series]: Upper band, middle band, lower band
        """
        try:
            middle_band = talib.SMA(prices, timeperiod=self.period)
            std_dev = talib.STDDEV(prices, timeperiod=self.period)
            
            upper_band = middle_band + (std_dev * self.num_std)
            lower_band = middle_band - (std_dev * self.num_std)
            
            return upper_band, middle_band, lower_band
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {str(e)}")
            raise

    def generate_signal(self, price: float, upper_band: float, lower_band: float, 
                       rsi: float = None, volume_ratio: float = None) -> str:
        """
        Generate enhanced trading signals using multiple indicators.
        
        Args:
            price (float): Current price
            upper_band (float): Upper Bollinger Band
            lower_band (float): Lower Bollinger Band
            rsi (float): Current RSI value if available
            volume_ratio (float): Current volume to avg volume ratio if available
            
        Returns:
            str: Trading signal ('STRONG_BUY', 'BUY', 'SELL', 'STRONG_SELL', or 'HOLD')
        """
        try:
            # Calculate percentage distances from bands
            upper_distance = (upper_band - price) / price
            lower_distance = (price - lower_band) / price
            
            # Base signal from Bollinger Bands
            if price < lower_band:
                signal = 'BUY'
                if lower_distance > 0.02:  # Price significantly below lower band
                    signal = 'STRONG_BUY'
            elif price > upper_band:
                signal = 'SELL'
                if upper_distance > 0.02:  # Price significantly above upper band
                    signal = 'STRONG_SELL'
            else:
                signal = 'HOLD'
            
            # Enhance signal with RSI if available
            if rsi is not None:
                if signal in ['BUY', 'STRONG_BUY'] and rsi < 30:
                    signal = 'STRONG_BUY'  # Confirm oversold condition
                elif signal in ['SELL', 'STRONG_SELL'] and rsi > 70:
                    signal = 'STRONG_SELL'  # Confirm overbought condition
                elif 45 <= rsi <= 55:
                    signal = 'HOLD'  # Neutral RSI suggests waiting
            
            # Consider volume confirmation if available
            if volume_ratio is not None and volume_ratio > 1.5:
                if signal in ['BUY', 'STRONG_BUY']:
                    signal = 'STRONG_BUY'  # High volume confirms buy signal
                elif signal in ['SELL', 'STRONG_SELL']:
                    signal = 'STRONG_SELL'  # High volume confirms sell signal
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating trading signal: {str(e)}")
            raise

    def calculate_volatility(self, prices: pd.Series) -> float:
        """
        Calculate historical volatility.
        
        Args:
            prices (pd.Series): Series of closing prices
            
        Returns:
            float: Annualized volatility
        """
        try:
            returns = np.log(prices / prices.shift(1))
            return returns.std() * np.sqrt(252)
        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            raise

    def calculate_momentum(self, prices: pd.Series) -> float:
        """
        Calculate price momentum.
        
        Args:
            prices (pd.Series): Series of closing prices
            
        Returns:
            float: Momentum indicator value
        """
        try:
            return talib.ROC(prices, timeperiod=self.period)[-1]
        except Exception as e:
            logger.error(f"Error calculating momentum: {str(e)}")
            raise

    def calculate_rsi(self, prices: pd.Series, timeperiod: int = 14) -> float:
        """
        Calculate the Relative Strength Index (RSI).
        
        Args:
            prices (pd.Series): Series of closing prices
            timeperiod (int): Time period for RSI calculation
            
        Returns:
            float: RSI value
        """
        try:
            rsi = talib.RSI(prices, timeperiod=timeperiod)
            return rsi[-1] if not np.isnan(rsi[-1]) else 50.0  # Default to neutral if NaN
        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
            return 50.0  # Default to neutral

    def calculate_macd(self, prices: pd.Series) -> Tuple[float, float, float]:
        """
        Calculate the MACD (Moving Average Convergence Divergence).
        
        Args:
            prices (pd.Series): Series of closing prices
            
        Returns:
            Tuple[float, float, float]: MACD, MACD signal, MACD histogram
        """
        try:
            macd, macd_signal, macd_hist = talib.MACD(prices)
            return macd[-1], macd_signal[-1], macd_hist[-1]
        except Exception as e:
            logger.error(f"Error calculating MACD: {str(e)}")
            return 0.0, 0.0, 0.0  # Default to neutral

    def calculate_position_size(self, equity: float, price: float, atr: float, risk_pct: float = 0.01) -> float:
        """
        Calculate optimal position size based on ATR for risk management.
        
        Args:
            equity (float): Account equity
            price (float): Current stock price
            atr (float): Average True Range
            risk_pct (float): Percentage of equity to risk per trade
            
        Returns:
            float: Recommended position size in shares
        """
        try:
            # Risk a specified percentage of equity per trade
            risk_amount = equity * risk_pct
            
            # Use 2 * ATR as stop loss distance
            stop_distance = 2 * atr
            
            # Calculate position size that risks appropriate amount
            shares = risk_amount / stop_distance
            
            # Ensure minimum position size
            min_shares = math.ceil(1000 / price)  # At least $1000 position
            shares = max(shares, min_shares)
            
            return shares
            
        except Exception as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return 0 