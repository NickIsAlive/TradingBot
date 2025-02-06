from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockQuotesRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import Adjustment, DataFeed
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import talib
import config
import ssl
import certifi
import requests
import time
from typing import List

logger = logging.getLogger(__name__)

class StockScreener:
    def __init__(self, data_client: StockHistoricalDataClient):
        """
        Initialize the stock screener with support for multiple markets.
        
        Args:
            data_client: Alpaca historical data client
        """
        self.data_client = data_client
        self.last_api_call = 0  # Initialize last_api_call
        self.API_CALL_DELAY = 0.1  # 100ms delay between API calls
        
        # Define market-specific screening criteria
        self.market_criteria = {
            'NYSE': {
                'min_price': 10,
                'max_price': 200,
                'min_volume': 500000,
                'min_dollar_volume': 5000000,
                'max_spread_pct': 0.002
            },
            'NASDAQ': {
                'min_price': 5,
                'max_price': 300,
                'min_volume': 300000,
                'min_dollar_volume': 3000000,
                'max_spread_pct': 0.003
            },
            'LSE': {
                'min_price': 1,  # In GBP
                'max_price': 500,
                'min_volume': 100000,
                'min_dollar_volume': 2000000,
                'max_spread_pct': 0.005
            },
            'ASX': {
                'min_price': 0.1,  # In AUD
                'max_price': 100,
                'min_volume': 50000,
                'min_dollar_volume': 1000000,
                'max_spread_pct': 0.01
            }
        }

        # Define market symbol sources
        self.market_sources = {
            'NYSE': self._get_nyse_symbols,
            'NASDAQ': self._get_nasdaq_symbols,
            'LSE': self._get_lse_symbols,
            'ASX': self._get_asx_symbols
        }

    def _get_alpaca_symbols(self, exchange):
        """Get symbols from Alpaca for a specific exchange."""
        try:
            # Test connection using IEX data feed
            request_params = StockBarsRequest(
                symbol_or_symbols=['SPY'],  # Use SPY as a test symbol
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=1),
                end=datetime.now(),
                feed=DataFeed.IEX  # Explicitly use IEX feed
            )
            
            try:
                bars = self.data_client.get_stock_bars(request_params)
                if bars:
                    logger.info("Successfully connected to Alpaca API using IEX feed")
                    # If connection works, get our reliable fallback symbols
                    symbols = self._get_fallback_symbols(exchange)
                    logger.info(f"Using reliable symbols for {exchange}")
                    return symbols
            except Exception as e:
                logger.error(f"Error testing Alpaca connection with IEX feed: {str(e)}")
                return self._get_fallback_symbols(exchange)
            
            logger.info(f"Found {len(symbols)} active symbols for {exchange}")
            return symbols
            
        except Exception as e:
            logger.error(f"Error getting {exchange} symbols from Alpaca: {str(e)}")
            return self._get_fallback_symbols(exchange)

    def _get_fallback_symbols(self, exchange):
        """Get fallback symbols when API fails."""
        fallback_symbols = {
            'NYSE': [
                'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'AXP',
                'DIS', 'KO', 'PG', 'JNJ', 'PFE', 'MRK', 'UNH',
                'WMT', 'HD', 'MCD', 'NKE', 'BA', 'CAT', 'GE'
            ],
            'NASDAQ': [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'AMD',
                'TSLA', 'NFLX', 'INTC', 'CSCO', 'ADBE', 'PYPL', 'CMCSA',
                'PEP', 'COST', 'AVGO', 'TXN', 'QCOM', 'SBUX'
            ],
            'LSE': [
                'HSBA.L', 'BP.L', 'SHELL.L', 'AZN.L', 'GSK.L', 'ULVR.L',
                'RIO.L', 'BHP.L', 'VOD.L', 'LLOY.L', 'BARC.L', 'PRU.L'
            ],
            'ASX': [
                'BHP.AX', 'CBA.AX', 'CSL.AX', 'NAB.AX', 'WBC.AX', 'ANZ.AX',
                'WES.AX', 'WOW.AX', 'MQG.AX', 'TLS.AX', 'RIO.AX'
            ]
        }
        logger.warning(f"Using fallback symbols for {exchange}")
        return fallback_symbols.get(exchange, [])

    def _get_nyse_symbols(self):
        """Get NYSE symbols with enhanced error handling."""
        try:
            symbols = self._get_alpaca_symbols('NYSE')
            if not symbols:
                # Try alternative source - NYSE API
                symbols = self._get_nyse_api_symbols()
            if not symbols:
                # Use fallback
                symbols = self._get_fallback_symbols('NYSE')
            return symbols
        except Exception as e:
            logger.error(f"Error getting NYSE symbols: {str(e)}")
            return self._get_fallback_symbols('NYSE')

    def _get_nasdaq_symbols(self):
        """Get NASDAQ symbols with enhanced error handling."""
        try:
            symbols = self._get_alpaca_symbols('NASDAQ')
            if not symbols:
                # Try alternative source - NASDAQ API
                symbols = self._get_nasdaq_api_symbols()
            if not symbols:
                # Use fallback
                symbols = self._get_fallback_symbols('NASDAQ')
            return symbols
        except Exception as e:
            logger.error(f"Error getting NASDAQ symbols: {str(e)}")
            return self._get_fallback_symbols('NASDAQ')

    def _get_lse_symbols(self):
        """Get London Stock Exchange symbols."""
        try:
            # Try to get from LSE API first
            symbols = self._get_lse_api_symbols()
            if not symbols:
                # Use fallback if API fails
                symbols = self._get_fallback_symbols('LSE')
            
            # Filter for main market stocks
            symbols = [s for s in symbols if s.endswith('.L')]
            logger.info(f"Found {len(symbols)} LSE symbols")
            return symbols
            
        except Exception as e:
            logger.error(f"Error getting LSE symbols: {str(e)}")
            return self._get_fallback_symbols('LSE')

    def _get_asx_symbols(self):
        """Get Australian Securities Exchange symbols."""
        try:
            # Try to get from ASX API first
            symbols = self._get_asx_api_symbols()
            if not symbols:
                # Use fallback if API fails
                symbols = self._get_fallback_symbols('ASX')
            
            # Filter for ASX listed stocks
            symbols = [s for s in symbols if s.endswith('.AX')]
            logger.info(f"Found {len(symbols)} ASX symbols")
            return symbols
            
        except Exception as e:
            logger.error(f"Error getting ASX symbols: {str(e)}")
            return self._get_fallback_symbols('ASX')

    def _get_nyse_api_symbols(self):
        """Get symbols directly from NYSE API."""
        try:
            url = "https://www.nyse.com/api/quotes/filter"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                symbols = [item['symbol'] for item in data if 'symbol' in item]
                return symbols
            return []
        except Exception as e:
            logger.error(f"Error getting symbols from NYSE API: {str(e)}")
            return []

    def _get_nasdaq_api_symbols(self):
        """Get symbols directly from NASDAQ API."""
        try:
            url = "https://api.nasdaq.com/api/screener/stocks"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'rows' in data['data']:
                    symbols = [row['symbol'] for row in data['data']['rows']]
                    return symbols
            return []
        except Exception as e:
            logger.error(f"Error getting symbols from NASDAQ API: {str(e)}")
            return []

    def _get_lse_api_symbols(self):
        """Get symbols from LSE."""
        try:
            url = "https://api.londonstockexchange.com/api/gw/lse/instruments"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                symbols = [item['tidm'] + '.L' for item in data if 'tidm' in item]
                return symbols
            return []
        except Exception as e:
            logger.error(f"Error getting symbols from LSE API: {str(e)}")
            return []

    def _get_asx_api_symbols(self):
        """Get symbols from ASX."""
        try:
            url = "https://asx.api.markitdigital.com/asx-research/1.0/companies/directory"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                symbols = [item['code'] + '.AX' for item in data if 'code' in item]
                return symbols
            return []
        except Exception as e:
            logger.error(f"Error getting symbols from ASX API: {str(e)}")
            return []

    def _get_sp500_symbols(self) -> list:
        """Get S&P 500 symbols using multiple fallback methods."""
        try:
            # Try Yahoo Finance top stocks list (more reliable than IEX)
            url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=true&lang=en-US&region=US&scrIds=day_gainers&count=100"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
            }
            response = requests.get(url, headers=headers, verify=True)
            
            if response.status_code == 200:
                data = response.json()
                if 'finance' in data and 'result' in data['finance']:
                    symbols = [quote['symbol'] for quote in data['finance']['result'][0]['quotes'] 
                             if quote['exchange'] in ['NYQ', 'NMS']]
                    if symbols:
                        logger.info(f"Found {len(symbols)} symbols from Yahoo Finance")
                        return symbols[:100]  # Get top 100 gainers
            
        except Exception as e:
            logger.error(f"Error fetching symbols from Yahoo: {str(e)}")

        # Fallback to static list of major tech and high-volume stocks
        fallback_symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'AMD', 'TSLA', 'NFLX', 'INTC',
            'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'V', 'MA', 'AXP', 'DIS',
            'WMT', 'TGT', 'COST', 'HD', 'LOW', 'SBUX', 'MCD', 'KO', 'PEP', 'NKE'
        ]
        logger.warning(f"Using fallback list of {len(fallback_symbols)} major stocks")
        return fallback_symbols

    def _rate_limit(self):
        """Implement rate limiting for API calls."""
        elapsed = time.time() - self.last_api_call
        if elapsed < self.API_CALL_DELAY:
            time.sleep(self.API_CALL_DELAY - elapsed)
        self.last_api_call = time.time()

    def get_historical_data(self, symbol: str, lookback_days: int = 20) -> pd.DataFrame:
        """
        Fetch historical data with error handling and rate limiting.
        """
        try:
            self._rate_limit()
            
            # Calculate start time with extended lookback for better data availability
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=lookback_days * 3)  # Triple the lookback period
            
            logger.info(f"Fetching data for {symbol} from {start_dt} to {end_dt}")
            
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_dt,
                end=end_dt,
                adjustment=Adjustment.SPLIT,
                feed=DataFeed.IEX  # Explicitly use IEX feed
            )
            
            logger.info(f"Using IEX feed for {symbol}")
            bars = self.data_client.get_stock_bars(request)
            
            if isinstance(bars, dict) and 'message' in bars:
                logger.warning(f"API Error for {symbol}: {bars['message']}")
                return pd.DataFrame()
                
            if bars and bars.data:
                symbol_data = bars.data.get(symbol, [])
                if symbol_data:
                    logger.info(f"Received {len(symbol_data)} bars for {symbol}")
                    df = pd.DataFrame([{
                        'timestamp': bar.timestamp,
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': float(bar.volume)
                    } for bar in symbol_data])
                    
                    if not df.empty:
                        df.set_index('timestamp', inplace=True)
                        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
                        df[numeric_columns] = df[numeric_columns].astype(float)
                        
                        # Take the most recent data points we need
                        if len(df) > lookback_days:
                            df = df.iloc[-lookback_days:]
                        
                        logger.info(f"Successfully processed {len(df)} rows of data for {symbol}. Last close: {df['close'].iloc[-1]:.2f}, Volume: {df['volume'].iloc[-1]:.0f}")
                        return df
                    else:
                        logger.warning(f"Empty DataFrame after processing for {symbol}")
                else:
                    logger.warning(f"No data returned for {symbol}")
            else:
                logger.warning(f"No bars data available for {symbol}")
            
            return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error in get_historical_data for {symbol}: {str(e)}")
            return pd.DataFrame()

    def calculate_metrics(self, df: pd.DataFrame) -> dict:
        """
        Calculate trading metrics for a stock.
        
        Args:
            df: DataFrame with historical price data
            
        Returns:
            Dictionary with calculated metrics
        """
        try:
            if df.empty:
                logger.warning("Empty DataFrame provided to calculate_metrics")
                return {}

            # Check if we have all required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                logger.error(f"Missing required columns. Available columns: {df.columns.tolist()}")
                return {}
                
            metrics = {}
            
            # Calculate average daily volume
            metrics['avg_volume'] = float(df['volume'].mean())
            
            # Scale volume if using minute data
            if isinstance(df.index, pd.DatetimeIndex):
                # Check if the average time difference between rows is less than 1 day
                if df.index.to_series().diff().mean().total_seconds() < 24*60*60:
                    metrics['avg_volume'] *= 390  # Scale to daily (390 minutes in trading day)
            
            # Calculate average price
            metrics['avg_price'] = float(df['close'].mean())
            
            # Calculate historical volatility
            returns = np.log(df['close'] / df['close'].shift(1)).dropna()
            if len(returns) > 0:
                # Determine if we're using daily or minute data for annualization
                if isinstance(df.index, pd.DatetimeIndex):
                    avg_time_diff = df.index.to_series().diff().mean().total_seconds()
                    if avg_time_diff < 24*60*60:  # If less than a day, assume minute data
                        annualization = 252 * 390
                    else:
                        annualization = 252
                else:
                    annualization = 252  # Default to daily if no timestamp index
                
                metrics['volatility'] = float(returns.std() * np.sqrt(annualization))
            else:
                logger.warning("Could not calculate returns for volatility")
                metrics['volatility'] = 0.0
            
            # Calculate RSI with error handling
            try:
                if len(df) >= 14:  # Need at least 14 periods for RSI
                    rsi = talib.RSI(df['close'].values, timeperiod=14)
                    if not np.isnan(rsi[-1]):
                        metrics['rsi'] = float(rsi[-1])
                    else:
                        logger.warning("RSI calculation returned NaN")
                        return {}
                else:
                    logger.warning(f"Not enough data points for RSI calculation. Need 14, got {len(df)}")
                    return {}
            except Exception as e:
                logger.error(f"Error calculating RSI: {str(e)}")
                return {}
            
            # Calculate ATR with error handling
            try:
                atr = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
                metrics['atr'] = float(atr[-1] if not np.isnan(atr[-1]) else 0.0)
            except Exception as e:
                logger.warning(f"Error calculating ATR: {str(e)}")
                metrics['atr'] = 0.0
            
            # Add some debug logging
            logger.info(f"Calculated metrics: Volume={metrics['avg_volume']:.0f}, Price=${metrics['avg_price']:.2f}, Vol={metrics['volatility']:.2%}, RSI={metrics['rsi']:.1f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            logger.error(f"DataFrame info: {df.info()}")
            return {}

    def filter_stocks(self, metrics: dict) -> bool:
        """
        Filter stocks based on enhanced trading criteria.
        """
        try:
            # Check if we have all required metrics
            required_metrics = ['avg_volume', 'avg_price', 'volatility', 'rsi', 'atr']
            if not all(metric in metrics for metric in required_metrics):
                logger.warning(f"Missing required metrics. Available: {list(metrics.keys())}")
                return False
            
            # Volume requirements - ensure good liquidity
            min_volume = 100000  # Minimum average daily volume
            
            # Price requirements - avoid penny stocks but allow for growth stocks
            min_price = 5.0
            max_price = 500.0
            
            # Volatility requirements - ensure enough movement for mean reversion
            min_volatility = 0.25  # 25% annualized volatility minimum
            max_volatility = 0.80  # 80% maximum to avoid extreme risk
            
            # ATR ratio requirements - ensure meaningful price swings
            atr_ratio = metrics['atr'] / metrics['avg_price']
            min_atr_ratio = 0.01  # ATR should be at least 1% of price
            
            logger.info(f"Checking enhanced filters for {metrics}")
            
            # Volume filter - ensure we can enter/exit easily
            if metrics['avg_volume'] < min_volume:
                logger.info(f"Rejected: Volume {metrics['avg_volume']:.0f} < {min_volume}")
                return False
            
            # Price filter - focus on established stocks
            if not (min_price <= metrics['avg_price'] <= max_price):
                logger.info(f"Rejected: Price ${metrics['avg_price']:.2f} not in range [${min_price}, ${max_price}]")
                return False
            
            # Volatility filter - ensure enough movement
            if not (min_volatility <= metrics['volatility'] <= max_volatility):
                logger.info(f"Rejected: Volatility {metrics['volatility']:.2%} not in range [{min_volatility:.2%}, {max_volatility:.2%}]")
                return False
            
            # ATR ratio filter - ensure meaningful price swings
            if atr_ratio < min_atr_ratio:
                logger.info(f"Rejected: ATR ratio {atr_ratio:.2%} < {min_atr_ratio:.2%}")
                return False
            
            # Enhanced RSI filter - look for stronger reversals
            if metrics['rsi'] >= 40 and metrics['rsi'] <= 60:
                logger.info(f"Rejected: RSI {metrics['rsi']:.1f} in neutral zone")
                return False
            elif metrics['rsi'] > 75:  # Strong overbought
                logger.info(f"✓ Stock PASSED - Strong overbought RSI: {metrics['rsi']:.1f}")
                return True
            elif metrics['rsi'] < 25:  # Strong oversold
                logger.info(f"✓ Stock PASSED - Strong oversold RSI: {metrics['rsi']:.1f}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error filtering stocks: {str(e)}")
            return False

    def get_optimal_parameters(self, symbol: str) -> dict:
        """
        Get optimal Bollinger Bands parameters for a symbol.
        For now, returns default parameters. In the future, this could be enhanced
        to calculate optimal parameters based on historical performance.
        
        Args:
            symbol (str): The trading symbol
            
        Returns:
            dict: Dictionary containing optimal parameters
        """
        # Default parameters that work well for most stocks
        default_params = {
            'period': 20,  # Standard 20-day period
            'std': 2.0    # Standard 2 standard deviations
        }
        
        # If we have optimized parameters for this symbol, use those
        if symbol in self.optimal_parameters:
            return self.optimal_parameters[symbol]
            
        # Otherwise return defaults
        return default_params

    def get_trading_candidates(self, max_stocks: int = 5, markets: list = None) -> list:
        """Get trading candidates across specified markets."""
        candidates = []
        
        for market in markets:
            if market in self.market_sources:
                source_func = self.market_sources[market]
                market_symbols = source_func()
                if market_symbols:
                    # Process symbols for this market
                    candidates.extend(self._process_market_symbols(market_symbols, market))
            else:
                logger.warning(f"Market {market} is not supported")
        
        # Sort and limit candidates
        candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)[:max_stocks]
        return [c['symbol'] for c in candidates]

    def _process_market_symbols(self, symbols: list, market: str) -> list:
        """Process symbols for a specific market."""
        processed = []
        for symbol in symbols:
            try:
                # Your existing symbol processing logic here
                # Add market-specific processing if needed
                processed.append({
                    'symbol': symbol,
                    'market': market,
                    'score': 0  # Replace with actual scoring logic
                })
            except Exception as e:
                logger.error(f"Error processing {symbol} from {market}: {str(e)}")
                continue
        return processed

    def _screen_market_stocks(self, 
                            market: str = 'NYSE', 
                            min_price: float = 10, 
                            max_price: float = 200,
                            min_volume: int = 500000,
                            min_dollar_volume: float = 5000000,
                            max_spread_pct: float = 0.002) -> List[str]:
        """
        Screen stocks for a specific market.
        
        Args:
            market: Market to screen
            min_price: Minimum stock price
            max_price: Maximum stock price
            min_volume: Minimum average daily volume
            min_dollar_volume: Minimum average daily dollar volume
            max_spread_pct: Maximum bid-ask spread percentage
            
        Returns:
            List of stock symbols that meet the criteria
        """
        try:
            # Get initial symbol list based on market
            if market in ['NYSE', 'NASDAQ']:
                symbols = self._get_sp500_symbols()
            else:
                logger.warning(f"No symbol source defined for market: {market}")
                return []
            
            candidates = []
            
            for symbol in symbols:
                try:
                    # Get historical data
                    df = self.get_historical_data(symbol)
                    if df.empty:
                        continue
                    
                    # Calculate metrics
                    metrics = self.calculate_metrics(df)
                    if not metrics:
                        continue
                    
                    # Apply filters
                    if self.filter_stocks(metrics):
                        candidates.append(symbol)
                        
                except Exception as e:
                    logger.error(f"Error screening {symbol}: {str(e)}")
                    continue
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error screening market {market}: {str(e)}")
            return [] 