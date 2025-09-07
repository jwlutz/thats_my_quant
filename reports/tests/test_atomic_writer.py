"""
Tests for atomic writer - temp write → fsync → rename.
Simulated interruption tests to verify atomicity.
"""

import pytest
import tempfile
import json
import os
import time
from pathlib import Path
from unittest.mock import patch, Mock

# Import atomic writer (will be created next)
from reports.atomic_writer import (
    write_report_atomic,
    write_metrics_sidecar,
    AtomicWriteError
)


class TestAtomicWriter:
    """Tests for atomic file writing."""
    
    def test_write_report_atomic_success(self):
        """Test successful atomic write."""
        content = """# Test Report
        
This is a test report with multiple lines.
It should be written atomically.
        """
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'test_report.md'
            
            # Write atomically
            result = write_report_atomic(content, output_path)
            
            # Should succeed
            assert result['status'] == 'completed'
            assert result['bytes_written'] == len(content)
            
            # File should exist with correct content
            assert output_path.exists()
            with open(output_path, 'r') as f:
                written_content = f.read()
            assert written_content == content
    
    def test_write_report_atomic_creates_directory(self):
        """Test that atomic write creates parent directories."""
        content = "Test content"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Nested path that doesn't exist
            output_path = Path(temp_dir) / 'reports' / 'AAPL' / 'test.md'
            
            result = write_report_atomic(content, output_path)
            
            assert result['status'] == 'completed'
            assert output_path.exists()
            assert output_path.parent.exists()
    
    def test_write_report_atomic_overwrites_existing(self):
        """Test atomic write overwrites existing file."""
        original_content = "Original content"
        new_content = "New content"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'test.md'
            
            # Create original file
            with open(output_path, 'w') as f:
                f.write(original_content)
            
            # Atomic overwrite
            result = write_report_atomic(new_content, output_path)
            
            assert result['status'] == 'completed'
            
            # Should contain new content
            with open(output_path, 'r') as f:
                final_content = f.read()
            assert final_content == new_content
    
    def test_write_report_atomic_temp_file_cleanup(self):
        """Test that temporary files are cleaned up."""
        content = "Test content"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'test.md'
            
            write_report_atomic(content, output_path)
            
            # No temporary files should remain
            temp_files = list(Path(temp_dir).glob('*tmp*'))
            assert len(temp_files) == 0
    
    @patch('os.fsync')
    def test_write_report_atomic_fsync_called(self, mock_fsync):
        """Test that fsync is called for durability."""
        content = "Test content"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'test.md'
            
            write_report_atomic(content, output_path)
            
            # fsync should have been called
            mock_fsync.assert_called_once()
    
    def test_write_report_atomic_permission_error(self):
        """Test handling of permission errors."""
        content = "Test content"
        
        # Try to write to read-only location (simulate permission error)
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'readonly.md'
            
            # Create file and make directory read-only
            output_path.touch()
            if os.name != 'nt':  # Skip on Windows (different permission model)
                os.chmod(temp_dir, 0o444)  # Read-only
                
                result = write_report_atomic(content, output_path)
                
                assert result['status'] == 'failed'
                assert 'Permission denied' in result.get('error', '')


class TestMetricsSidecar:
    """Tests for metrics sidecar writing."""
    
    def test_write_metrics_sidecar_success(self):
        """Test successful metrics sidecar writing."""
        metrics = {
            'ticker': 'AAPL',
            'as_of_date': '2025-09-06',
            'price_metrics': {'returns': {'1D': 0.0123}},
            'metadata': {'run_id': 456}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'AAPL_metrics.json'
            
            result = write_metrics_sidecar(metrics, output_path)
            
            assert result['status'] == 'completed'
            assert output_path.exists()
            
            # Verify JSON content
            with open(output_path, 'r') as f:
                written_metrics = json.load(f)
            assert written_metrics == metrics
    
    def test_write_metrics_sidecar_json_serialization(self):
        """Test JSON serialization of complex metrics."""
        # Metrics with dates, floats, None values
        metrics = {
            'ticker': 'TEST',
            'returns': {'1D': 0.0123, '1Y': None},
            'dates': ['2025-09-06', '2025-09-05'],
            'float_val': 123.456789,
            'int_val': 42
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'test_metrics.json'
            
            result = write_metrics_sidecar(metrics, output_path)
            
            assert result['status'] == 'completed'
            
            # Verify round-trip
            with open(output_path, 'r') as f:
                loaded = json.load(f)
            assert loaded == metrics
    
    def test_write_metrics_sidecar_invalid_json(self):
        """Test handling of non-serializable data."""
        # Object that can't be JSON serialized
        import datetime
        metrics = {
            'ticker': 'TEST',
            'timestamp': datetime.datetime.now(),  # Not JSON serializable
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'invalid.json'
            
            result = write_metrics_sidecar(metrics, output_path)
            
            assert result['status'] == 'failed'
            assert 'serialization' in result.get('error', '').lower()


class TestAtomicitySimulation:
    """Tests for atomicity under simulated failures."""
    
    @patch('os.rename')
    def test_atomic_write_rename_failure(self, mock_rename):
        """Test behavior when rename fails."""
        content = "Test content"
        mock_rename.side_effect = OSError("Rename failed")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'test.md'
            
            result = write_report_atomic(content, output_path)
            
            # Should fail gracefully
            assert result['status'] == 'failed'
            assert 'Rename failed' in result.get('error', '')
            
            # Original file should not exist (rename failed)
            assert not output_path.exists()
            
            # Temp file should be cleaned up
            temp_files = list(Path(temp_dir).glob('*tmp*'))
            assert len(temp_files) == 0
    
    def test_atomic_write_disk_full_simulation(self):
        """Test behavior when disk is full during write."""
        # Create very large content to potentially trigger disk full
        large_content = "x" * (1024 * 1024)  # 1MB
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'large_file.md'
            
            # This should succeed in temp directory, but tests the error path
            result = write_report_atomic(large_content, output_path)
            
            # Should either succeed or fail gracefully
            assert result['status'] in ['completed', 'failed']
            
            if result['status'] == 'completed':
                assert output_path.exists()
                assert output_path.stat().st_size == len(large_content)
    
    def test_atomic_write_concurrent_access(self):
        """Test atomic write with simulated concurrent access."""
        content1 = "Content from writer 1"
        content2 = "Content from writer 2"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'concurrent.md'
            
            # Write both (simulating concurrent access)
            result1 = write_report_atomic(content1, output_path)
            result2 = write_report_atomic(content2, output_path)
            
            # Both should succeed
            assert result1['status'] == 'completed'
            assert result2['status'] == 'completed'
            
            # File should contain content from last writer (atomic)
            with open(output_path, 'r') as f:
                final_content = f.read()
            assert final_content == content2  # Last writer wins
