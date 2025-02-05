import os
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import pandas as pd
import ssl

load_dotenv()
logger = logging.getLogger(__name__)

class TradingDatabase:
    def __init__(self):
        """Initialize database connection using environment variables."""
        try:
            # Create SSL context for secure connection
            ssl_context = ssl.create_default_context()
            ssl_context.verify_mode = ssl.CERT_REQUIRED

            # Connection parameters for Supabase
            conn_params = {
                'host': os.getenv('DB_HOST'),
                'database': os.getenv('DB_NAME'),
                'user': os.getenv('DB_USER'),
                'password': os.getenv('DB_PASSWORD').strip('"'),  # Remove any quotes
                'port': os.getenv('DB_PORT', '5432'),
                'sslmode': 'require',
                'connect_timeout': 10
            }

            logger.info(f"Connecting to Supabase database at {conn_params['host']}:{conn_params['port']}")
            self.conn = psycopg2.connect(**conn_params)
            logger.info("Successfully connected to Supabase database")
            
            self.create_tables()
        except Exception as e:
            logger.error(f"Failed to connect to Supabase database: {str(e)}")
            raise

    def create_tables(self):
        """Create necessary database tables if they don't exist."""
        with self.conn.cursor() as cur:
            # Create trades table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(10) NOT NULL,
                    side VARCHAR(4) NOT NULL,
                    quantity DECIMAL NOT NULL,
                    entry_price DECIMAL NOT NULL,
                    exit_price DECIMAL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    profit_loss DECIMAL,
                    profit_loss_pct DECIMAL,
                    strategy VARCHAR(50),
                    exit_reason VARCHAR(50),
                    market_regime VARCHAR(20),
                    rsi DECIMAL,
                    volume_ratio DECIMAL,
                    atr DECIMAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create daily_performance table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_performance (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL UNIQUE,
                    starting_equity DECIMAL NOT NULL,
                    ending_equity DECIMAL NOT NULL,
                    daily_returns DECIMAL NOT NULL,
                    daily_returns_pct DECIMAL NOT NULL,
                    num_trades INTEGER NOT NULL,
                    winning_trades INTEGER NOT NULL,
                    losing_trades INTEGER NOT NULL,
                    largest_gain DECIMAL,
                    largest_loss DECIMAL,
                    market_regime VARCHAR(20),
                    spy_performance_pct DECIMAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create market_data table for storing relevant market indicators
            cur.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(10) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    open DECIMAL NOT NULL,
                    high DECIMAL NOT NULL,
                    low DECIMAL NOT NULL,
                    close DECIMAL NOT NULL,
                    volume BIGINT NOT NULL,
                    rsi DECIMAL,
                    sma20 DECIMAL,
                    sma50 DECIMAL,
                    upper_band DECIMAL,
                    lower_band DECIMAL,
                    atr DECIMAL,
                    market_regime VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timestamp)
                )
            """)

            self.conn.commit()

    async def record_trade_entry(self, symbol: str, side: str, quantity: float, 
                               price: float, strategy: str, market_regime: str,
                               rsi: float = None, volume_ratio: float = None, 
                               atr: float = None) -> int:
        """Record a new trade entry."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trades (
                    symbol, side, quantity, entry_price, entry_time,
                    strategy, market_regime, rsi, volume_ratio, atr
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                symbol, side, quantity, price, datetime.now(),
                strategy, market_regime, rsi, volume_ratio, atr
            ))
            trade_id = cur.fetchone()[0]
            self.conn.commit()
            return trade_id

    async def record_trade_exit(self, trade_id: int, exit_price: float, 
                              exit_reason: str) -> None:
        """Record a trade exit."""
        with self.conn.cursor() as cur:
            # Get trade entry details
            cur.execute("""
                SELECT entry_price, quantity
                FROM trades
                WHERE id = %s
            """, (trade_id,))
            entry_price, quantity = cur.fetchone()

            # Calculate P/L
            profit_loss = (exit_price - entry_price) * quantity
            profit_loss_pct = ((exit_price - entry_price) / entry_price) * 100

            # Update trade record
            cur.execute("""
                UPDATE trades
                SET exit_price = %s,
                    exit_time = %s,
                    profit_loss = %s,
                    profit_loss_pct = %s,
                    exit_reason = %s
                WHERE id = %s
            """, (
                exit_price, datetime.now(),
                profit_loss, profit_loss_pct,
                exit_reason, trade_id
            ))
            self.conn.commit()

    async def update_daily_performance(self) -> None:
        """Update daily performance metrics."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            today = datetime.now().date()
            
            # Get today's trades
            cur.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(*) FILTER (WHERE profit_loss > 0) as winning_trades,
                    COUNT(*) FILTER (WHERE profit_loss < 0) as losing_trades,
                    MAX(profit_loss) as largest_gain,
                    MIN(profit_loss) as largest_loss
                FROM trades
                WHERE DATE(exit_time) = %s
            """, (today,))
            trade_stats = cur.fetchone()

            # Get market regime and SPY performance
            cur.execute("""
                SELECT market_regime, 
                       (MAX(close) - MIN(close)) / MIN(close) * 100 as spy_perf
                FROM market_data
                WHERE symbol = 'SPY' AND DATE(timestamp) = %s
                GROUP BY market_regime
            """, (today,))
            market_data = cur.fetchone()

            # Insert or update daily performance
            cur.execute("""
                INSERT INTO daily_performance (
                    date, starting_equity, ending_equity, daily_returns,
                    daily_returns_pct, num_trades, winning_trades, losing_trades,
                    largest_gain, largest_loss, market_regime, spy_performance_pct
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (date) DO UPDATE SET
                    ending_equity = EXCLUDED.ending_equity,
                    daily_returns = EXCLUDED.ending_equity - daily_performance.starting_equity,
                    daily_returns_pct = (EXCLUDED.ending_equity - daily_performance.starting_equity) / 
                                      daily_performance.starting_equity * 100,
                    num_trades = EXCLUDED.num_trades,
                    winning_trades = EXCLUDED.winning_trades,
                    losing_trades = EXCLUDED.losing_trades,
                    largest_gain = EXCLUDED.largest_gain,
                    largest_loss = EXCLUDED.largest_loss,
                    market_regime = EXCLUDED.market_regime,
                    spy_performance_pct = EXCLUDED.spy_performance_pct
            """, (
                today,
                trade_stats['starting_equity'],
                trade_stats['ending_equity'],
                trade_stats['daily_returns'],
                trade_stats['daily_returns_pct'],
                trade_stats['total_trades'],
                trade_stats['winning_trades'],
                trade_stats['losing_trades'],
                trade_stats['largest_gain'],
                trade_stats['largest_loss'],
                market_data['market_regime'] if market_data else None,
                market_data['spy_perf'] if market_data else None
            ))
            self.conn.commit()

    async def record_market_data(self, symbol: str, timestamp: datetime,
                               ohlcv: dict, indicators: dict) -> None:
        """Record market data and indicators."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO market_data (
                    symbol, timestamp, open, high, low, close, volume,
                    rsi, sma20, sma50, upper_band, lower_band, atr, market_regime
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (symbol, timestamp) DO UPDATE SET
                    rsi = EXCLUDED.rsi,
                    sma20 = EXCLUDED.sma20,
                    sma50 = EXCLUDED.sma50,
                    upper_band = EXCLUDED.upper_band,
                    lower_band = EXCLUDED.lower_band,
                    atr = EXCLUDED.atr,
                    market_regime = EXCLUDED.market_regime
            """, (
                symbol, timestamp,
                ohlcv['open'], ohlcv['high'], ohlcv['low'], 
                ohlcv['close'], ohlcv['volume'],
                indicators.get('rsi'),
                indicators.get('sma20'),
                indicators.get('sma50'),
                indicators.get('upper_band'),
                indicators.get('lower_band'),
                indicators.get('atr'),
                indicators.get('market_regime')
            ))
            self.conn.commit()

    def get_trade_history(self, start_date: datetime = None, 
                         end_date: datetime = None) -> pd.DataFrame:
        """Get trade history as a pandas DataFrame."""
        query = """
            SELECT *
            FROM trades
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND entry_time >= %s"
            params.append(start_date)
        if end_date:
            query += " AND entry_time <= %s"
            params.append(end_date)

        query += " ORDER BY entry_time DESC"

        return pd.read_sql_query(query, self.conn, params=params)

    def get_performance_metrics(self, start_date: datetime = None,
                              end_date: datetime = None) -> pd.DataFrame:
        """Get daily performance metrics as a pandas DataFrame."""
        query = """
            SELECT *
            FROM daily_performance
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND date <= %s"
            params.append(end_date)

        query += " ORDER BY date DESC"

        return pd.read_sql_query(query, self.conn, params=params)

    def close(self):
        """Close database connection."""
        self.conn.close() 