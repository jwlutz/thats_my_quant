"""
Database loaders - idempotent upsert functions for SQLite.
Thin IO layer with focus on data integrity and idempotence.
"""

import sqlite3
from datetime import date, datetime
from typing import Dict, Any, List, Tuple, Optional


def init_database(conn: sqlite3.Connection) -> None:
    """
    Initialize database with required tables.
    Idempotent - safe to call multiple times.
    
    Args:
        conn: SQLite connection
    """
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Create prices table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            ticker TEXT NOT NULL,
            date DATE NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            adj_close REAL,
            volume INTEGER NOT NULL,
            source TEXT NOT NULL,
            as_of DATE NOT NULL,
            ingested_at DATETIME NOT NULL,
            PRIMARY KEY (ticker, date)
        )
    """)
    
    # Create holdings_13f table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS holdings_13f (
            cik TEXT NOT NULL,
            filer TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            cusip TEXT NOT NULL,
            value_usd REAL NOT NULL,
            shares REAL NOT NULL,
            as_of DATE NOT NULL,
            source TEXT NOT NULL,
            ingested_at DATETIME NOT NULL,
            PRIMARY KEY (cik, cusip, as_of)
        )
    """)
    
    # Create runs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dag_name TEXT NOT NULL,
            started_at DATETIME NOT NULL,
            finished_at DATETIME,
            status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
            rows_in INTEGER,
            rows_out INTEGER,
            log_path TEXT
        )
    """)
    
    # Create indices for performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_13f_cik ON holdings_13f(cik)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_13f_ticker ON holdings_13f(ticker)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_13f_as_of ON holdings_13f(as_of)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
    
    conn.commit()


def get_connection(db_path: str = './data/research.db') -> sqlite3.Connection:
    """
    Get SQLite connection with proper configuration.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        Configured SQLite connection
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
    return conn


def upsert_prices(conn: sqlite3.Connection, rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Upsert price rows into database.
    Idempotent - can be called multiple times with same data.
    
    Args:
        conn: SQLite connection
        rows: List of canonical price dictionaries
        
    Returns:
        Tuple of (inserted_count, updated_count)
    """
    if not rows:
        return (0, 0)
    
    inserted = 0
    updated = 0
    
    for row in rows:
        # Check if row exists (by primary key)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker = ? AND date = ?",
            (row['ticker'], row['date'])
        )
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            # Update existing row
            conn.execute("""
                UPDATE prices SET
                    open = ?, high = ?, low = ?, close = ?, adj_close = ?,
                    volume = ?, source = ?, as_of = ?, ingested_at = ?
                WHERE ticker = ? AND date = ?
            """, (
                row['open'], row['high'], row['low'], row['close'], row['adj_close'],
                row['volume'], row['source'], row['as_of'], row['ingested_at'],
                row['ticker'], row['date']
            ))
            updated += 1
        else:
            # Insert new row
            conn.execute("""
                INSERT INTO prices (
                    ticker, date, open, high, low, close, adj_close,
                    volume, source, as_of, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['ticker'], row['date'], row['open'], row['high'], row['low'],
                row['close'], row['adj_close'], row['volume'], row['source'],
                row['as_of'], row['ingested_at']
            ))
            inserted += 1
    
    conn.commit()
    return (inserted, updated)


def upsert_13f(conn: sqlite3.Connection, rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Upsert 13F holdings rows into database.
    Idempotent - can be called multiple times with same data.
    
    Args:
        conn: SQLite connection
        rows: List of canonical 13F dictionaries
        
    Returns:
        Tuple of (inserted_count, updated_count)
    """
    if not rows:
        return (0, 0)
    
    inserted = 0
    updated = 0
    
    for row in rows:
        # Check if row exists (by primary key)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM holdings_13f WHERE cik = ? AND cusip = ? AND as_of = ?",
            (row['cik'], row['cusip'], row['as_of'])
        )
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            # Update existing row
            conn.execute("""
                UPDATE holdings_13f SET
                    filer = ?, ticker = ?, name = ?, value_usd = ?, shares = ?,
                    source = ?, ingested_at = ?
                WHERE cik = ? AND cusip = ? AND as_of = ?
            """, (
                row['filer'], row['ticker'], row['name'], row['value_usd'], row['shares'],
                row['source'], row['ingested_at'],
                row['cik'], row['cusip'], row['as_of']
            ))
            updated += 1
        else:
            # Insert new row
            conn.execute("""
                INSERT INTO holdings_13f (
                    cik, filer, ticker, name, cusip, value_usd, shares,
                    as_of, source, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['cik'], row['filer'], row['ticker'], row['name'], row['cusip'],
                row['value_usd'], row['shares'], row['as_of'], row['source'],
                row['ingested_at']
            ))
            inserted += 1
    
    conn.commit()
    return (inserted, updated)


def upsert_run(
    conn: sqlite3.Connection,
    dag_name: str,
    started_at: datetime,
    finished_at: Optional[datetime] = None,
    status: str = 'running',
    rows_in: Optional[int] = None,
    rows_out: Optional[int] = None,
    log_path: Optional[str] = None,
    run_id: Optional[int] = None
) -> int:
    """
    Upsert run record.
    
    Args:
        conn: SQLite connection
        dag_name: Pipeline identifier
        started_at: Run start time
        finished_at: Run end time (None if still running)
        status: One of 'running', 'completed', 'failed'
        rows_in: Input row count
        rows_out: Output row count
        log_path: Path to detailed log
        run_id: If provided, update existing run; otherwise insert new
        
    Returns:
        Run ID
    """
    if run_id is not None:
        # Update existing run
        conn.execute("""
            UPDATE runs SET
                finished_at = ?, status = ?, rows_in = ?, rows_out = ?, log_path = ?
            WHERE run_id = ?
        """, (finished_at, status, rows_in, rows_out, log_path, run_id))
        conn.commit()
        return run_id
    else:
        # Insert new run
        cursor = conn.execute("""
            INSERT INTO runs (dag_name, started_at, finished_at, status, rows_in, rows_out, log_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (dag_name, started_at, finished_at, status, rows_in, rows_out, log_path))
        conn.commit()
        return cursor.lastrowid
