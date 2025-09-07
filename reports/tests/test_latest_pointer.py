"""
Tests for latest pointer system - symlink preferred, copy fallback.
Windows compatibility and pointer integrity testing.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

# Import pointer system (will be created next)
from reports.latest_pointer import (
    update_latest_pointer,
    check_pointer_integrity,
    PointerStrategy,
    LatestPointerError
)


class TestLatestPointer:
    """Tests for latest pointer management."""
    
    def test_update_latest_pointer_symlink(self):
        """Test updating latest pointer with symlink strategy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            # Create a report file
            report_path = ticker_dir / '2025-09-06_143000_report.md'
            report_path.write_text("Test report content")
            
            # Update latest pointer
            result = update_latest_pointer(
                ticker_dir=ticker_dir,
                report_path=report_path,
                prefer_symlinks=True
            )
            
            # Should succeed
            assert result['status'] == 'completed'
            assert result['strategy'] in ['symlink', 'copy']
            
            # Latest pointer should exist
            latest_path = ticker_dir / 'latest.md'
            assert latest_path.exists()
            
            # Should point to correct file
            if latest_path.is_symlink():
                resolved = latest_path.resolve()
                assert resolved == report_path
            else:
                # Copy fallback
                with open(latest_path, 'r') as f:
                    content = f.read()
                assert content == "Test report content"
    
    def test_update_latest_pointer_copy_fallback(self):
        """Test copy fallback when symlinks not available."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            report_path = ticker_dir / '2025-09-06_143000_report.md'
            report_content = "Test report for copy fallback"
            report_path.write_text(report_content)
            
            # Force copy strategy
            result = update_latest_pointer(
                ticker_dir=ticker_dir,
                report_path=report_path,
                prefer_symlinks=False
            )
            
            assert result['status'] == 'completed'
            assert result['strategy'] == 'copy'
            
            # Latest should be a copy, not symlink
            latest_path = ticker_dir / 'latest.md'
            assert latest_path.exists()
            assert not latest_path.is_symlink()
            
            # Content should match
            with open(latest_path, 'r') as f:
                latest_content = f.read()
            assert latest_content == report_content
    
    def test_update_latest_pointer_overwrites_existing(self):
        """Test that latest pointer is updated when new report is newer."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            # Create old report and latest pointer
            old_report = ticker_dir / '2025-09-06_143000_report.md'
            old_report.write_text("Old report")
            
            old_result = update_latest_pointer(ticker_dir, old_report)
            assert old_result['status'] == 'completed'
            
            # Create new report
            new_report = ticker_dir / '2025-09-06_150000_report.md'
            new_report.write_text("New report")
            
            # Update latest pointer
            new_result = update_latest_pointer(ticker_dir, new_report)
            assert new_result['status'] == 'completed'
            
            # Latest should now point to new report
            latest_path = ticker_dir / 'latest.md'
            if latest_path.is_symlink():
                resolved = latest_path.resolve()
                assert resolved == new_report
            else:
                with open(latest_path, 'r') as f:
                    content = f.read()
                assert content == "New report"
    
    @patch('os.symlink')
    def test_update_latest_pointer_symlink_failure(self, mock_symlink):
        """Test symlink failure triggers copy fallback."""
        mock_symlink.side_effect = OSError("Symlinks not supported")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            report_path = ticker_dir / '2025-09-06_143000_report.md'
            report_path.write_text("Test content")
            
            # Should fall back to copy
            result = update_latest_pointer(
                ticker_dir=ticker_dir,
                report_path=report_path,
                prefer_symlinks=True
            )
            
            assert result['status'] == 'completed'
            assert result['strategy'] == 'copy'
            
            # Should have copied, not symlinked
            latest_path = ticker_dir / 'latest.md'
            assert latest_path.exists()
            assert not latest_path.is_symlink()
    
    def test_update_latest_pointer_nonexistent_report(self):
        """Test updating pointer to nonexistent report."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            nonexistent_report = ticker_dir / 'nonexistent.md'
            
            result = update_latest_pointer(ticker_dir, nonexistent_report)
            
            assert result['status'] == 'failed'
            assert 'does not exist' in result['error']


class TestPointerIntegrity:
    """Tests for pointer integrity checking."""
    
    def test_check_pointer_integrity_valid_symlink(self):
        """Test integrity check with valid symlink."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            # Create report and symlink
            report_path = ticker_dir / '2025-09-06_143000_report.md'
            report_path.write_text("Valid report")
            
            latest_path = ticker_dir / 'latest.md'
            if os.name != 'nt':  # Skip symlink test on Windows
                latest_path.symlink_to(report_path.name)
                
                integrity = check_pointer_integrity(ticker_dir)
                
                assert integrity['valid'] is True
                assert integrity['strategy'] == 'symlink'
                assert integrity['target_exists'] is True
    
    def test_check_pointer_integrity_broken_symlink(self):
        """Test integrity check with broken symlink."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            latest_path = ticker_dir / 'latest.md'
            
            if os.name != 'nt':  # Skip symlink test on Windows
                # Create symlink to nonexistent file
                latest_path.symlink_to('nonexistent.md')
                
                integrity = check_pointer_integrity(ticker_dir)
                
                assert integrity['valid'] is False
                assert integrity['strategy'] == 'symlink'
                assert integrity['target_exists'] is False
    
    def test_check_pointer_integrity_copy_strategy(self):
        """Test integrity check with copy strategy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            # Create latest.md as regular file (copy strategy)
            latest_path = ticker_dir / 'latest.md'
            latest_path.write_text("Copied report content")
            
            integrity = check_pointer_integrity(ticker_dir)
            
            assert integrity['valid'] is True
            assert integrity['strategy'] == 'copy'
            assert integrity['target_exists'] is True
    
    def test_check_pointer_integrity_no_latest(self):
        """Test integrity check when no latest pointer exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            integrity = check_pointer_integrity(ticker_dir)
            
            assert integrity['valid'] is False
            assert integrity['strategy'] is None
            assert 'latest.md not found' in integrity['error']


class TestPointerStrategy:
    """Tests for pointer strategy detection."""
    
    def test_pointer_strategy_enum(self):
        """Test PointerStrategy enum values."""
        assert PointerStrategy.SYMLINK == 'symlink'
        assert PointerStrategy.COPY == 'copy'
    
    def test_detect_pointer_strategy(self):
        """Test automatic detection of pointer strategy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ticker_dir = Path(temp_dir) / 'AAPL'
            ticker_dir.mkdir()
            
            latest_path = ticker_dir / 'latest.md'
            
            # Test copy strategy
            latest_path.write_text("Copy content")
            integrity = check_pointer_integrity(ticker_dir)
            assert integrity['strategy'] == 'copy'
            
            # Clean up for symlink test
            latest_path.unlink()
            
            if os.name != 'nt':  # Test symlink on non-Windows
                # Test symlink strategy
                latest_path.symlink_to('target.md')
                integrity = check_pointer_integrity(ticker_dir)
                assert integrity['strategy'] == 'symlink'
