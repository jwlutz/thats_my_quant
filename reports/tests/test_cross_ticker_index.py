"""
Tests for cross-ticker index system.
Schema validation, timezone queries, atomic updates.
"""

import pytest
import json
import tempfile
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

# Import index system (will be created next)
from reports.cross_ticker_index import (
    update_cross_ticker_index,
    query_today_reports,
    rebuild_index_from_filesystem,
    CrossTickerIndexError,
    INDEX_SCHEMA_VERSION
)


class TestCrossTickerIndex:
    """Tests for cross-ticker index management."""
    
    def test_update_cross_ticker_index_new_entry(self):
        """Test adding new entry to index."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / 'latest_reports.json'
            
            # Update index with new entry
            result = update_cross_ticker_index(
                index_path=index_path,
                ticker='AAPL',
                report_path='reports/AAPL/2025-09-06_143000_report.md',
                latest_path='reports/AAPL/latest.md',
                run_id=123,
                timestamp_local=datetime(2025, 9, 6, 14, 30, 0),
                pointer_strategy='symlink'
            )
            
            assert result['status'] == 'completed'
            assert result['entries_count'] == 1
            
            # Verify index file created
            assert index_path.exists()
            
            # Verify content
            with open(index_path, 'r') as f:
                index_data = json.load(f)
            
            assert index_data['schema_version'] == INDEX_SCHEMA_VERSION
            assert len(index_data['latest']) == 1
            
            entry = index_data['latest'][0]
            assert entry['ticker'] == 'AAPL'
            assert entry['run_id'] == 123
            assert entry['pointer_strategy'] == 'symlink'
    
    def test_update_cross_ticker_index_update_existing(self):
        """Test updating existing ticker entry."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / 'latest_reports.json'
            
            # Create initial entry
            update_cross_ticker_index(
                index_path, 'AAPL', 'old_report.md', 'latest.md',
                run_id=100, timestamp_local=datetime(2025, 9, 6, 10, 0, 0),
                pointer_strategy='copy'
            )
            
            # Update with newer entry
            result = update_cross_ticker_index(
                index_path, 'AAPL', 'new_report.md', 'latest.md',
                run_id=101, timestamp_local=datetime(2025, 9, 6, 14, 30, 0),
                pointer_strategy='symlink'
            )
            
            assert result['status'] == 'completed'
            assert result['entries_count'] == 1  # Still 1 entry (updated)
            
            # Verify update
            with open(index_path, 'r') as f:
                index_data = json.load(f)
            
            entry = index_data['latest'][0]
            assert entry['run_id'] == 101  # Updated
            assert entry['pointer_strategy'] == 'symlink'  # Updated
            assert 'new_report.md' in entry['report_path']
    
    def test_update_cross_ticker_index_multiple_tickers(self):
        """Test index with multiple tickers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / 'latest_reports.json'
            
            # Add multiple tickers
            tickers = ['AAPL', 'MSFT', 'GOOGL']
            for i, ticker in enumerate(tickers):
                update_cross_ticker_index(
                    index_path, ticker, f'{ticker}_report.md', 'latest.md',
                    run_id=100 + i, 
                    timestamp_local=datetime(2025, 9, 6, 14, i * 10, 0),
                    pointer_strategy='symlink'
                )
            
            # Verify all entries
            with open(index_path, 'r') as f:
                index_data = json.load(f)
            
            assert len(index_data['latest']) == 3
            
            # Should be sorted by ticker
            entry_tickers = [entry['ticker'] for entry in index_data['latest']]
            assert entry_tickers == sorted(tickers)
    
    def test_query_today_reports_local_timezone(self):
        """Test querying today's reports with timezone handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / 'latest_reports.json'
            
            # Create entries for today and yesterday
            today = date.today()
            yesterday = today - timedelta(days=1)
            
            # Today's report
            update_cross_ticker_index(
                index_path, 'AAPL', 'today_report.md', 'latest.md',
                run_id=200, timestamp_local=datetime.combine(today, datetime.min.time()),
                pointer_strategy='symlink'
            )
            
            # Yesterday's report
            update_cross_ticker_index(
                index_path, 'MSFT', 'yesterday_report.md', 'latest.md',
                run_id=199, timestamp_local=datetime.combine(yesterday, datetime.min.time()),
                pointer_strategy='copy'
            )
            
            # Query today's reports
            today_reports = query_today_reports(index_path, target_date=today)
            
            assert len(today_reports) == 1
            assert today_reports[0]['ticker'] == 'AAPL'
            assert today_reports[0]['run_id'] == 200
    
    def test_query_today_reports_empty(self):
        """Test querying when no reports exist for today."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / 'latest_reports.json'
            
            # Create index with no entries
            initial_index = {
                'schema_version': INDEX_SCHEMA_VERSION,
                'generated_at_utc': datetime.now(timezone.utc).isoformat(),
                'timezone': 'UTC',
                'latest': []
            }
            
            with open(index_path, 'w') as f:
                json.dump(initial_index, f)
            
            today_reports = query_today_reports(index_path)
            assert today_reports == []
    
    def test_rebuild_index_from_filesystem(self):
        """Test rebuilding index by scanning filesystem."""
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir) / 'reports'
            
            # Create ticker directories with reports
            aapl_dir = reports_dir / 'AAPL'
            aapl_dir.mkdir(parents=True)
            
            # Create timestamped reports
            report1 = aapl_dir / '2025-09-06_143000_report.md'
            report2 = aapl_dir / '2025-09-06_150000_report.md'  # Newer
            
            report1.write_text("Report 1")
            report2.write_text("Report 2")
            
            # Create latest pointer
            latest = aapl_dir / 'latest.md'
            latest.write_text("Report 2")  # Copy strategy
            
            # Rebuild index
            index_path = reports_dir / 'latest_reports.json'
            result = rebuild_index_from_filesystem(reports_dir, index_path)
            
            assert result['status'] == 'completed'
            assert result['tickers_found'] == 1
            assert result['entries_created'] == 1
            
            # Verify index content
            with open(index_path, 'r') as f:
                index_data = json.load(f)
            
            assert len(index_data['latest']) == 1
            entry = index_data['latest'][0]
            assert entry['ticker'] == 'AAPL'
            assert '2025-09-06_150000_report.md' in entry['report_path']


class TestIndexSchema:
    """Tests for index schema validation."""
    
    def test_index_schema_version(self):
        """Test that schema version is defined."""
        assert INDEX_SCHEMA_VERSION is not None
        assert isinstance(INDEX_SCHEMA_VERSION, str)
        assert '.' in INDEX_SCHEMA_VERSION  # Semantic version
    
    def test_index_schema_structure(self):
        """Test index schema structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / 'test_index.json'
            
            # Create minimal index
            update_cross_ticker_index(
                index_path, 'TEST', 'test.md', 'latest.md',
                run_id=1, timestamp_local=datetime(2025, 9, 6, 14, 30, 0)
            )
            
            # Verify schema
            with open(index_path, 'r') as f:
                index_data = json.load(f)
            
            # Required top-level fields
            required_fields = ['schema_version', 'generated_at_utc', 'timezone', 'latest']
            for field in required_fields:
                assert field in index_data
            
            # Entry structure
            if index_data['latest']:
                entry = index_data['latest'][0]
                required_entry_fields = [
                    'ticker', 'report_path', 'latest_path', 'run_id',
                    'generated_at_local', 'pointer_strategy'
                ]
                for field in required_entry_fields:
                    assert field in entry
    
    def test_index_timezone_handling(self):
        """Test timezone handling in index."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / 'tz_test.json'
            
            # Create entry with timezone-aware timestamp
            tz_local = timezone(timedelta(hours=-7))  # MST
            timestamp_with_tz = datetime(2025, 9, 6, 14, 30, 0, tzinfo=tz_local)
            
            update_cross_ticker_index(
                index_path, 'TEST', 'test.md', 'latest.md',
                run_id=1, timestamp_local=timestamp_with_tz
            )
            
            # Verify timezone info preserved
            with open(index_path, 'r') as f:
                index_data = json.load(f)
            
            entry = index_data['latest'][0]
            
            # Should have timezone info in timestamp
            assert 'T' in entry['generated_at_local']
            # Should have UTC timestamp at top level
            assert 'T' in index_data['generated_at_utc']
            assert index_data['generated_at_utc'].endswith('Z')


class TestIndexQueries:
    """Tests for index query operations."""
    
    def test_query_today_reports_timezone_boundary(self):
        """Test today query across timezone boundaries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / 'tz_boundary.json'
            
            # Create reports at different times of "today"
            target_date = date(2025, 9, 6)
            
            # Early morning
            early_time = datetime.combine(target_date, datetime.min.time())
            update_cross_ticker_index(
                index_path, 'EARLY', 'early.md', 'latest.md',
                run_id=1, timestamp_local=early_time
            )
            
            # Late night
            late_time = datetime.combine(target_date, datetime.max.time().replace(microsecond=0))
            update_cross_ticker_index(
                index_path, 'LATE', 'late.md', 'latest.md', 
                run_id=2, timestamp_local=late_time
            )
            
            # Query for the target date
            today_reports = query_today_reports(index_path, target_date)
            
            assert len(today_reports) == 2
            tickers = [r['ticker'] for r in today_reports]
            assert 'EARLY' in tickers
            assert 'LATE' in tickers
    
    def test_query_today_reports_no_index_file(self):
        """Test querying when index file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_index = Path(temp_dir) / 'nonexistent.json'
            
            result = query_today_reports(nonexistent_index)
            assert result == []
