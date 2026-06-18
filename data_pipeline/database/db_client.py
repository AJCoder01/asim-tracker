"""
ASIM-Tracker: SQLite Analytical Storage Client
Manages database initialization, persistent storage of market microstructure vectors
and sentiment logs, and implements the time-decay forward-window alignment join.
"""

import math
import sqlite3
import logging
from typing import Any, Dict, List, Optional

import config

logger = logging.getLogger("asim_tracker.db_client")


def get_db_connection(db_path: str) -> sqlite3.Connection:
    """
    Creates a database connection and configures WAL mode to allow
    concurrent read-write access without blocking.
    """
    conn = sqlite3.connect(db_path)
    # Enable WAL mode for high performance concurrent writes
    conn.execute("PRAGMA journal_mode=WAL;")
    # Ensure foreign keys are enforced
    conn.execute("PRAGMA foreign_keys=ON;")
    # Return rows as dictionaries
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: str = config.SQLITE_DB_PATH) -> None:
    """
    Initializes SQLite tables 'market_vectors' and 'sentiment_logs' if they do not exist.
    """
    logger.info(f"Initializing database at: {db_path}")
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        # 1. Create market_vectors table (composite primary key on timestamp + ticker)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_vectors (
                timestamp INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                delivery_pct REAL,
                order_book_imbalance REAL,
                wavelet_close REAL,
                PRIMARY KEY (timestamp, ticker)
            );
        """)

        # Create index on ticker for fast lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_ticker ON market_vectors(ticker);")

        # 2. Create sentiment_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_logs (
                item_id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                sentiment_score REAL NOT NULL,
                matched_ticker TEXT NOT NULL,
                info_velocity REAL NOT NULL
            );
        """)

        # Create indexes for filtering by ticker and timestamp window
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_ticker_time ON sentiment_logs(matched_ticker, timestamp);")

        conn.commit()
        logger.info("Database schemas initialized successfully.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialize database: {e}")
        raise e
    finally:
        conn.close()


def insert_market_vector(data: Dict[str, Any], db_path: str = config.SQLITE_DB_PATH) -> bool:
    """
    Inserts or replaces a record in the 'market_vectors' table.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO market_vectors (
                timestamp, ticker, open, high, low, close, volume, 
                delivery_pct, order_book_imbalance, wavelet_close
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            data["timestamp"],
            data["ticker"].strip().upper(),
            float(data["open"]),
            float(data["high"]),
            float(data["low"]),
            float(data["close"]),
            float(data["volume"]),
            float(data["delivery_pct"]) if data.get("delivery_pct") is not None else None,
            float(data["order_book_imbalance"]) if data.get("order_book_imbalance") is not None else None,
            float(data["wavelet_close"]) if data.get("wavelet_close") is not None else None
        ))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting market vector: {e}")
        return False
    finally:
        conn.close()


def calculate_info_velocity(
    ticker: str,
    timestamp: int,
    conn: sqlite3.Connection
) -> float:
    """
    Calculates rolling 60-minute mention frequency acceleration for a ticker:
    acceleration = count(t - 60m, t) - count(t - 120m, t - 60m)
    """
    cursor = conn.cursor()
    ticker_upper = ticker.strip().upper()

    t_end = timestamp
    t_mid = t_end - (60 * 60 * 1000)      # t - 60 minutes in ms
    t_start = t_end - (120 * 60 * 1000)   # t - 120 minutes in ms

    try:
        # Current 60-minute window count
        cursor.execute("""
            SELECT COUNT(*) FROM sentiment_logs
            WHERE matched_ticker = ? AND timestamp >= ? AND timestamp < ?
        """, (ticker_upper, t_mid, t_end))
        count_current = cursor.fetchone()[0]

        # Previous 60-minute window count
        cursor.execute("""
            SELECT COUNT(*) FROM sentiment_logs
            WHERE matched_ticker = ? AND timestamp >= ? AND timestamp < ?
        """, (ticker_upper, t_start, t_mid))
        count_previous = cursor.fetchone()[0]

        return float(count_current - count_previous)
    except Exception as e:
        logger.error(f"Error calculating info velocity: {e}")
        return 0.0


def insert_sentiment_log(
    data: Dict[str, Any],
    db_path: str = config.SQLITE_DB_PATH
) -> bool:
    """
    Inserts or replaces a record in 'sentiment_logs' table.
    Automatically calculates rolling info_velocity before inserting.
    """
    conn = get_db_connection(db_path)
    try:
        ticker = data["matched_ticker"].strip().upper()
        ts = int(data["timestamp"])

        # Compute information velocity acceleration
        info_vel = calculate_info_velocity(ticker, ts, conn)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO sentiment_logs (
                item_id, timestamp, raw_text, sentiment_score, matched_ticker, info_velocity
            ) VALUES (?, ?, ?, ?, ?, ?);
        """, (
            data["item_id"],
            ts,
            data["raw_text"].strip(),
            float(data["sentiment_score"]),
            ticker,
            info_vel
        ))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting sentiment log: {e}")
        return False
    finally:
        conn.close()


def calculate_aggregated_sentiment(
    ticker: str,
    t_mkt: int,
    window_ms: int = 15 * 60 * 1000,
    gamma: float = config.DEFAULT_HAWKES_GAMMA,
    db_path: str = config.SQLITE_DB_PATH
) -> float:
    """
    Implements the forward-window synchronization join function:
    Psi = sum_k (sentiment_score_k * e^(-gamma * delta_t))
    where delta_t = (t_mkt - t_k) in minutes.
    Active window: [t_mkt - window_ms, t_mkt].
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    ticker_upper = ticker.strip().upper()
    t_start = t_mkt - window_ms

    try:
        # Fetch all sentiment logs in active window for this ticker
        cursor.execute("""
            SELECT sentiment_score, timestamp FROM sentiment_logs
            WHERE matched_ticker = ? AND timestamp >= ? AND timestamp <= ?
        """, (ticker_upper, t_start, t_mkt))
        
        rows = cursor.fetchall()
        
        psi = 0.0
        for row in rows:
            sentiment_score = row["sentiment_score"]
            t_k = row["timestamp"]
            
            # Compute time-decay in minutes
            dt_minutes = (t_mkt - t_k) / 60000.0
            weight = math.exp(-gamma * dt_minutes)
            
            psi += sentiment_score * weight
            
        return psi
    except Exception as e:
        logger.error(f"Error calculating aggregated sentiment: {e}")
        return 0.0
    finally:
        conn.close()


def get_joined_market_vector(
    ticker: str,
    timestamp: int,
    gamma: float = config.DEFAULT_HAWKES_GAMMA,
    db_path: str = config.SQLITE_DB_PATH
) -> Optional[Dict[str, Any]]:
    """
    Retrieves the market vector for a given ticker and timestamp,
    calculates the time-decay aggregated sentiment over [timestamp - 15m, timestamp],
    and returns the joined record payload.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    ticker_upper = ticker.strip().upper()

    try:
        cursor.execute("""
            SELECT * FROM market_vectors
            WHERE ticker = ? AND timestamp = ?
        """, (ticker_upper, timestamp))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        record = dict(row)
        
        # Calculate time-decay aggregated sentiment (15-minute window)
        psi = calculate_aggregated_sentiment(
            ticker=ticker_upper,
            t_mkt=timestamp,
            window_ms=15 * 60 * 1000,
            gamma=gamma,
            db_path=db_path
        )
        
        record["aggregated_sentiment"] = psi
        return record
    except Exception as e:
        logger.error(f"Error fetching joined market vector: {e}")
        return None
    finally:
        conn.close()
