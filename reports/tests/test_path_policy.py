"""
Tests for filename and path policy.
Contract tests: given {ticker, timestamp_local}, compute exact file paths.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os

# Import path utilities (will be created next)
from reports.path_policy import (
    create_report_paths,
    parse_timestamp_from_filename,
    get_local_timezone,
    PathPolicyError
)


class TestReportPaths:
    """Tests for report path generation."""
    
    def test_create_report_paths_basic(self):
        """Test basic report path creation."""
        ticker = 'AAPL'
        timestamp_local = datetime(2025, 9, 6, 14, 30, 0)
        base_dir = Path('./reports')
        
        paths = create_report_paths(ticker, timestamp_local, base_dir)
        
        # Verify path structure
        expected_report = base_dir / 'AAPL' / '2025-09-06_143000_report.md'
        expected_latest = base_dir / 'AAPL' / 'latest.md'
        expected_metrics = base_dir / 'AAPL' / '2025-09-06_143000_metrics.json'
        
        assert paths['report_path'] == expected_report
        assert paths['latest_path'] == expected_latest
        assert paths['metrics_path'] == expected_metrics
        assert paths['ticker_dir'] == base_dir / 'AAPL'
    
    def test_create_report_paths_different_times(self):
        """Test path creation with different timestamps."""
        ticker = 'MSFT'
        base_dir = Path('./reports')
        
        # Morning timestamp
        morning = datetime(2025, 9, 6, 9, 15, 30)
        morning_paths = create_report_paths(ticker, morning, base_dir)
        
        # Evening timestamp
        evening = datetime(2025, 9, 6, 17, 45, 15)
        evening_paths = create_report_paths(ticker, evening, base_dir)
        
        # Should have different filenames but same latest path
        assert morning_paths['report_path'] != evening_paths['report_path']
        assert morning_paths['latest_path'] == evening_paths['latest_path']
        
        # Filenames should be sortable chronologically
        morning_name = morning_paths['report_path'].name
        evening_name = evening_paths['report_path'].name
        assert morning_name < evening_name  # Lexicographic = chronological
    
    def test_create_report_paths_ticker_normalization(self):
        """Test ticker symbol normalization for filesystem safety."""
        # Test various ticker formats
        test_cases = [
            ('AAPL', 'AAPL'),
            ('BRK.B', 'BRK_B'),  # Dots to underscores
            ('BF-B', 'BF_B'),    # Dashes to underscores  
            ('aapl', 'AAPL'),    # Uppercase
        ]
        
        timestamp = datetime(2025, 9, 6, 14, 30, 0)
        base_dir = Path('./reports')
        
        for input_ticker, expected_normalized in test_cases:
            paths = create_report_paths(input_ticker, timestamp, base_dir)
            
            # Directory should use normalized ticker
            assert expected_normalized in str(paths['ticker_dir'])
            assert expected_normalized in str(paths['report_path'])
    
    def test_create_report_paths_timezone_handling(self):
        """Test timezone handling in filenames."""
        ticker = 'AAPL'
        base_dir = Path('./reports')
        
        # Create timestamp with timezone info
        tz_local = timezone(timedelta(hours=-7))  # MST
        timestamp_with_tz = datetime(2025, 9, 6, 14, 30, 0, tzinfo=tz_local)
        
        paths = create_report_paths(ticker, timestamp_with_tz, base_dir)
        
        # Filename should use local time (14:30), not UTC
        assert '143000' in paths['report_path'].name
        
        # Should handle naive datetime (assume local)
        naive_timestamp = datetime(2025, 9, 6, 14, 30, 0)
        naive_paths = create_report_paths(ticker, naive_timestamp, base_dir)
        
        # Should produce same filename for same local time
        assert naive_paths['report_path'].name == paths['report_path'].name
    
    def test_create_report_paths_edge_cases(self):
        """Test edge cases in path creation."""
        base_dir = Path('./reports')
        timestamp = datetime(2025, 12, 31, 23, 59, 59)
        
        # Empty ticker
        with pytest.raises(PathPolicyError, match="Ticker cannot be empty"):
            create_report_paths('', timestamp, base_dir)
        
        # Very long ticker
        long_ticker = 'A' * 50
        with pytest.raises(PathPolicyError, match="Ticker too long"):
            create_report_paths(long_ticker, timestamp, base_dir)
        
        # Invalid characters in ticker
        invalid_ticker = 'AAPL/INVALID'
        with pytest.raises(PathPolicyError, match="Invalid characters"):
            create_report_paths(invalid_ticker, timestamp, base_dir)


class TestTimestampParsing:
    """Tests for timestamp parsing from filenames."""
    
    def test_parse_timestamp_from_filename(self):
        """Test parsing timestamp from report filename."""
        filename = '2025-09-06_143000_report.md'
        
        timestamp = parse_timestamp_from_filename(filename)
        
        assert timestamp.year == 2025
        assert timestamp.month == 9
        assert timestamp.day == 6
        assert timestamp.hour == 14
        assert timestamp.minute == 30
        assert timestamp.second == 0
    
    def test_parse_timestamp_different_formats(self):
        """Test parsing various filename formats."""
        test_cases = [
            ('2025-01-01_090000_report.md', datetime(2025, 1, 1, 9, 0, 0)),
            ('2025-12-31_235959_report.md', datetime(2025, 12, 31, 23, 59, 59)),
            ('2024-02-29_120000_report.md', datetime(2024, 2, 29, 12, 0, 0)),  # Leap year
        ]
        
        for filename, expected in test_cases:
            result = parse_timestamp_from_filename(filename)
            assert result == expected
    
    def test_parse_timestamp_invalid_format(self):
        """Test parsing invalid filename formats."""
        invalid_filenames = [
            'AAPL_report.md',  # No timestamp
            '2025-09-06_report.md',  # No time
            '2025-13-01_120000_report.md',  # Invalid month
            '2025-09-32_120000_report.md',  # Invalid day
            '2025-09-06_250000_report.md',  # Invalid hour
        ]
        
        for filename in invalid_filenames:
            with pytest.raises(PathPolicyError, match="Invalid filename format"):
                parse_timestamp_from_filename(filename)


class TestTimezoneHandling:
    """Tests for timezone handling."""
    
    def test_get_local_timezone_default(self):
        """Test getting local timezone."""
        # Should return a timezone object
        tz = get_local_timezone()
        assert tz is not None
        
        # Should be able to create localized datetime
        now = datetime.now(tz)
        assert now.tzinfo is not None
    
    def test_get_local_timezone_from_env(self):
        """Test timezone from environment variable."""
        # Mock environment variable
        with pytest.MonkeyPatch().context() as m:
            m.setenv('REPORTS_TZ', 'America/New_York')
            
            tz = get_local_timezone()
            
            # Should use environment timezone
            # Note: This test may need adjustment based on system timezone support
            assert tz is not None
    
    def test_filename_timestamp_deterministic(self):
        """Test that filename timestamps are deterministic."""
        ticker = 'TEST'
        timestamp = datetime(2025, 9, 6, 14, 30, 0)
        base_dir = Path('./reports')
        
        # Generate paths twice
        paths1 = create_report_paths(ticker, timestamp, base_dir)
        paths2 = create_report_paths(ticker, timestamp, base_dir)
        
        # Should be identical (deterministic)
        assert paths1 == paths2
    
    def test_filename_sorting_chronological(self):
        """Test that filenames sort chronologically."""
        ticker = 'TEST'
        base_dir = Path('./reports')
        
        # Create timestamps in order
        timestamps = [
            datetime(2025, 9, 6, 9, 0, 0),   # Morning
            datetime(2025, 9, 6, 14, 30, 0), # Afternoon
            datetime(2025, 9, 6, 18, 45, 0), # Evening
            datetime(2025, 9, 7, 9, 0, 0),   # Next day
        ]
        
        # Generate filenames
        filenames = []
        for ts in timestamps:
            paths = create_report_paths(ticker, ts, base_dir)
            filenames.append(paths['report_path'].name)
        
        # Should be in chronological order
        sorted_filenames = sorted(filenames)
        assert filenames == sorted_filenames
