"""
Tests for loader functions - idempotent SQLite upserts.
Uses in-memory SQLite for fast, isolated tests.
"""

import pytest
import sqlite3
from datetime import date, datetime
from typing import Dict, Any

# Import loaders (will be created next)
from storage.loaders import (
    upsert_prices,
    upsert_13f,
    init_database,
    get_connection
)


@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite database for testing."""
    conn = sqlite3.connect(':memory:')
    init_database(conn)
    return conn


class TestPriceLoader:
    """Tests for upsert_prices function."""
    
    def test_upsert_prices_insert_new(self, in_memory_db):
        """Test inserting new price rows."""
        rows = [
            {
                'ticker': 'AAPL',
                'date': date(2024, 1, 15),
                'open': 185.25,
                'high': 186.80,
                'low': 184.50,
                'close': 185.92,
                'adj_close': 185.75,
                'volume': 65284300,
                'source': 'yfinance',
                'as_of': date(2024, 1, 15),
                'ingested_at': datetime(2024, 1, 16, 9, 0, 0),
            },
            {
                'ticker': 'AAPL',
                'date': date(2024, 1, 16),
                'open': 186.10,
                'high': 187.45,
                'low': 185.80,
                'close': 187.11,
                'adj_close': 186.94,
                'volume': 58414500,
                'source': 'yfinance',
                'as_of': date(2024, 1, 16),
                'ingested_at': datetime(2024, 1, 16, 9, 0, 0),
            }
        ]
        
        # First insert
        inserted, updated = upsert_prices(in_memory_db, rows)
        
        assert inserted == 2
        assert updated == 0
        
        # Verify data in database
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker = 'AAPL'"
        )
        count = cursor.fetchone()[0]
        assert count == 2
    
    def test_upsert_prices_update_existing(self, in_memory_db):
        """Test updating existing price rows (idempotent)."""
        # Initial data
        rows = [
            {
                'ticker': 'AAPL',
                'date': date(2024, 1, 15),
                'open': 185.25,
                'high': 186.80,
                'low': 184.50,
                'close': 185.92,
                'adj_close': 185.75,
                'volume': 65284300,
                'source': 'yfinance',
                'as_of': date(2024, 1, 15),
                'ingested_at': datetime(2024, 1, 16, 9, 0, 0),
            }
        ]
        
        # First insert
        inserted1, updated1 = upsert_prices(in_memory_db, rows)
        assert inserted1 == 1
        assert updated1 == 0
        
        # Update with revised data (same PK)
        rows[0]['close'] = 186.00  # Changed close price
        rows[0]['ingested_at'] = datetime(2024, 1, 16, 10, 0, 0)  # New timestamp
        
        # Second upsert (should update)
        inserted2, updated2 = upsert_prices(in_memory_db, rows)
        assert inserted2 == 0
        assert updated2 == 1
        
        # Verify updated data
        cursor = in_memory_db.execute(
            "SELECT close FROM prices WHERE ticker = 'AAPL' AND date = '2024-01-15'"
        )
        close_price = cursor.fetchone()[0]
        assert close_price == 186.00
        
        # Should still have only one row
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker = 'AAPL'"
        )
        count = cursor.fetchone()[0]
        assert count == 1
    
    def test_upsert_prices_idempotent(self, in_memory_db):
        """Test that repeated upserts with same data are idempotent."""
        rows = [
            {
                'ticker': 'AAPL',
                'date': date(2024, 1, 15),
                'open': 185.25,
                'high': 186.80,
                'low': 184.50,
                'close': 185.92,
                'adj_close': 185.75,
                'volume': 65284300,
                'source': 'yfinance',
                'as_of': date(2024, 1, 15),
                'ingested_at': datetime(2024, 1, 16, 9, 0, 0),
            }
        ]
        
        # First upsert
        inserted1, updated1 = upsert_prices(in_memory_db, rows)
        
        # Get initial state
        cursor = in_memory_db.execute(
            "SELECT * FROM prices WHERE ticker = 'AAPL' AND date = '2024-01-15'"
        )
        initial_row = cursor.fetchone()
        
        # Second upsert with identical data
        inserted2, updated2 = upsert_prices(in_memory_db, rows)
        
        # Get final state
        cursor = in_memory_db.execute(
            "SELECT * FROM prices WHERE ticker = 'AAPL' AND date = '2024-01-15'"
        )
        final_row = cursor.fetchone()
        
        # Should be identical (idempotent)
        assert initial_row == final_row
        assert inserted2 == 0
        assert updated2 == 1  # Still counts as update even if no change
    
    def test_upsert_prices_empty_list(self, in_memory_db):
        """Test upserting empty list."""
        inserted, updated = upsert_prices(in_memory_db, [])
        assert inserted == 0
        assert updated == 0
    
    def test_upsert_prices_mixed_insert_update(self, in_memory_db):
        """Test mix of new inserts and updates in same batch."""
        # Insert initial data
        initial_rows = [
            {
                'ticker': 'AAPL',
                'date': date(2024, 1, 15),
                'open': 185.25,
                'high': 186.80,
                'low': 184.50,
                'close': 185.92,
                'adj_close': 185.75,
                'volume': 65284300,
                'source': 'yfinance',
                'as_of': date(2024, 1, 15),
                'ingested_at': datetime(2024, 1, 16, 9, 0, 0),
            }
        ]
        upsert_prices(in_memory_db, initial_rows)
        
        # Mix of update (existing) and insert (new)
        mixed_rows = [
            {
                'ticker': 'AAPL',
                'date': date(2024, 1, 15),  # Existing - will update
                'open': 185.25,
                'high': 186.80,
                'low': 184.50,
                'close': 186.00,  # Changed
                'adj_close': 185.85,  # Changed
                'volume': 65284300,
                'source': 'yfinance',
                'as_of': date(2024, 1, 15),
                'ingested_at': datetime(2024, 1, 16, 10, 0, 0),
            },
            {
                'ticker': 'AAPL',
                'date': date(2024, 1, 16),  # New - will insert
                'open': 186.10,
                'high': 187.45,
                'low': 185.80,
                'close': 187.11,
                'adj_close': 186.94,
                'volume': 58414500,
                'source': 'yfinance',
                'as_of': date(2024, 1, 16),
                'ingested_at': datetime(2024, 1, 16, 10, 0, 0),
            }
        ]
        
        inserted, updated = upsert_prices(in_memory_db, mixed_rows)
        assert inserted == 1  # One new row
        assert updated == 1   # One updated row
        
        # Verify total count
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker = 'AAPL'"
        )
        count = cursor.fetchone()[0]
        assert count == 2


class TestHoldings13FLoader:
    """Tests for upsert_13f function."""
    
    def test_upsert_13f_insert_new(self, in_memory_db):
        """Test inserting new 13F rows."""
        rows = [
            {
                'cik': '0001067983',
                'filer': 'BERKSHIRE HATHAWAY INC',
                'ticker': 'AAPL',
                'name': 'APPLE INC',
                'cusip': '037833100',
                'value_usd': 174800000000.0,
                'shares': 915560382.0,
                'as_of': date(2023, 9, 30),
                'source': 'sec_edgar',
                'ingested_at': datetime(2024, 1, 16, 10, 0, 0),
            }
        ]
        
        inserted, updated = upsert_13f(in_memory_db, rows)
        
        assert inserted == 1
        assert updated == 0
        
        # Verify data
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM holdings_13f WHERE cik = '0001067983'"
        )
        count = cursor.fetchone()[0]
        assert count == 1
    
    def test_upsert_13f_update_existing(self, in_memory_db):
        """Test updating existing 13F rows."""
        rows = [
            {
                'cik': '0001067983',
                'filer': 'BERKSHIRE HATHAWAY INC',
                'ticker': 'AAPL',
                'name': 'APPLE INC',
                'cusip': '037833100',
                'value_usd': 174800000000.0,
                'shares': 915560382.0,
                'as_of': date(2023, 9, 30),
                'source': 'sec_edgar',
                'ingested_at': datetime(2024, 1, 16, 10, 0, 0),
            }
        ]
        
        # First insert
        upsert_13f(in_memory_db, rows)
        
        # Update with revised data (same PK: cik, cusip, as_of)
        rows[0]['shares'] = 920000000.0  # Changed shares
        rows[0]['value_usd'] = 175000000000.0  # Changed value
        
        inserted, updated = upsert_13f(in_memory_db, rows)
        assert inserted == 0
        assert updated == 1
        
        # Verify updated data
        cursor = in_memory_db.execute(
            "SELECT shares FROM holdings_13f WHERE cik = '0001067983' AND cusip = '037833100'"
        )
        shares = cursor.fetchone()[0]
        assert shares == 920000000.0
    
    def test_upsert_13f_idempotent(self, in_memory_db):
        """Test that repeated 13F upserts are idempotent."""
        rows = [
            {
                'cik': '0001067983',
                'filer': 'BERKSHIRE HATHAWAY INC',
                'ticker': 'AAPL',
                'name': 'APPLE INC',
                'cusip': '037833100',
                'value_usd': 174800000000.0,
                'shares': 915560382.0,
                'as_of': date(2023, 9, 30),
                'source': 'sec_edgar',
                'ingested_at': datetime(2024, 1, 16, 10, 0, 0),
            }
        ]
        
        # First upsert
        upsert_13f(in_memory_db, rows)
        
        # Get initial state
        cursor = in_memory_db.execute(
            "SELECT * FROM holdings_13f WHERE cik = '0001067983' AND cusip = '037833100'"
        )
        initial_row = cursor.fetchone()
        
        # Second upsert with identical data
        inserted, updated = upsert_13f(in_memory_db, rows)
        
        # Get final state
        cursor = in_memory_db.execute(
            "SELECT * FROM holdings_13f WHERE cik = '0001067983' AND cusip = '037833100'"
        )
        final_row = cursor.fetchone()
        
        # Should be identical
        assert initial_row == final_row
        assert inserted == 0
        assert updated == 1  # Still counts as update
    
    def test_upsert_13f_pk_uniqueness(self, in_memory_db):
        """Test primary key uniqueness (cik, cusip, as_of)."""
        # Same CIK and CUSIP, different as_of dates
        rows = [
            {
                'cik': '0001067983',
                'filer': 'BERKSHIRE HATHAWAY INC',
                'ticker': 'AAPL',
                'name': 'APPLE INC',
                'cusip': '037833100',
                'value_usd': 174800000000.0,
                'shares': 915560382.0,
                'as_of': date(2023, 6, 30),  # Q2
                'source': 'sec_edgar',
                'ingested_at': datetime(2024, 1, 16, 10, 0, 0),
            },
            {
                'cik': '0001067983',
                'filer': 'BERKSHIRE HATHAWAY INC',
                'ticker': 'AAPL',
                'name': 'APPLE INC',
                'cusip': '037833100',  # Same CUSIP
                'value_usd': 180000000000.0,
                'shares': 920000000.0,
                'as_of': date(2023, 9, 30),  # Q3 - different quarter
                'source': 'sec_edgar',
                'ingested_at': datetime(2024, 1, 16, 10, 0, 0),
            }
        ]
        
        inserted, updated = upsert_13f(in_memory_db, rows)
        assert inserted == 2  # Both should be inserted (different PKs)
        assert updated == 0
        
        # Verify both rows exist
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM holdings_13f WHERE cik = '0001067983' AND cusip = '037833100'"
        )
        count = cursor.fetchone()[0]
        assert count == 2


class TestDatabaseInit:
    """Tests for database initialization."""
    
    def test_init_database_creates_tables(self):
        """Test that init_database creates all required tables."""
        conn = sqlite3.connect(':memory:')
        init_database(conn)
        
        # Check tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'prices' in tables
        assert 'holdings_13f' in tables
        assert 'runs' in tables
    
    def test_init_database_idempotent(self):
        """Test that init_database can be called multiple times safely."""
        conn = sqlite3.connect(':memory:')
        
        # Call twice
        init_database(conn)
        init_database(conn)  # Should not error
        
        # Tables should still exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'prices' in tables
        assert 'holdings_13f' in tables
        assert 'runs' in tables
