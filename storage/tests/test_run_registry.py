"""
Tests for run registry - pipeline execution tracking.
Uses in-memory SQLite for fast, isolated tests.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

# Import run registry (will be created next)
from storage.run_registry import (
    start_run,
    finish_run,
    get_run_status,
    list_recent_runs,
    RunStatus,
    RunNotFoundError
)
from storage.loaders import init_database


@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite database for testing."""
    conn = sqlite3.connect(':memory:')
    init_database(conn)
    return conn


class TestRunRegistry:
    """Tests for run registry functions."""
    
    def test_start_run_creates_record(self, in_memory_db):
        """Test that start_run creates a new run record."""
        started_at = datetime(2024, 1, 16, 9, 0, 0)
        
        run_id = start_run(
            conn=in_memory_db,
            dag_name='daily_prices',
            started_at=started_at
        )
        
        # Should return integer run ID
        assert isinstance(run_id, int)
        assert run_id > 0
        
        # Verify record in database
        cursor = in_memory_db.execute(
            "SELECT dag_name, started_at, status FROM runs WHERE run_id = ?",
            (run_id,)
        )
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] == 'daily_prices'
        assert row[1] == '2024-01-16 09:00:00'  # SQLite datetime format
        assert row[2] == 'running'
    
    def test_start_run_auto_timestamp(self, in_memory_db):
        """Test that start_run uses current time if not provided."""
        before = datetime.now()
        
        run_id = start_run(
            conn=in_memory_db,
            dag_name='test_dag'
        )
        
        after = datetime.now()
        
        # Get stored timestamp
        cursor = in_memory_db.execute(
            "SELECT started_at FROM runs WHERE run_id = ?",
            (run_id,)
        )
        stored_time_str = cursor.fetchone()[0]
        stored_time = datetime.fromisoformat(stored_time_str.replace(' ', 'T'))
        
        # Should be between before and after
        assert before <= stored_time <= after
    
    def test_finish_run_success(self, in_memory_db):
        """Test finishing a run with success status."""
        # Start run
        run_id = start_run(
            conn=in_memory_db,
            dag_name='daily_prices',
            started_at=datetime(2024, 1, 16, 9, 0, 0)
        )
        
        # Finish run
        finished_at = datetime(2024, 1, 16, 9, 5, 30)
        finish_run(
            conn=in_memory_db,
            run_id=run_id,
            status=RunStatus.COMPLETED,
            finished_at=finished_at,
            rows_in=100,
            rows_out=98,
            log_path='./data/logs/run_001.log'
        )
        
        # Verify updated record
        cursor = in_memory_db.execute(
            "SELECT status, finished_at, rows_in, rows_out, log_path FROM runs WHERE run_id = ?",
            (run_id,)
        )
        row = cursor.fetchone()
        
        assert row[0] == 'completed'
        assert row[1] == '2024-01-16 09:05:30'
        assert row[2] == 100
        assert row[3] == 98
        assert row[4] == './data/logs/run_001.log'
    
    def test_finish_run_failure(self, in_memory_db):
        """Test finishing a run with failure status."""
        run_id = start_run(
            conn=in_memory_db,
            dag_name='test_dag'
        )
        
        finish_run(
            conn=in_memory_db,
            run_id=run_id,
            status=RunStatus.FAILED,
            error_message='Network timeout'
        )
        
        # Check status updated
        cursor = in_memory_db.execute(
            "SELECT status FROM runs WHERE run_id = ?",
            (run_id,)
        )
        status = cursor.fetchone()[0]
        assert status == 'failed'
    
    def test_finish_run_nonexistent(self, in_memory_db):
        """Test finishing a run that doesn't exist."""
        with pytest.raises(RunNotFoundError, match="Run ID 999 not found"):
            finish_run(
                conn=in_memory_db,
                run_id=999,
                status=RunStatus.COMPLETED
            )
    
    def test_get_run_status(self, in_memory_db):
        """Test retrieving run status and details."""
        # Create run
        started_at = datetime(2024, 1, 16, 9, 0, 0)
        run_id = start_run(
            conn=in_memory_db,
            dag_name='daily_prices',
            started_at=started_at
        )
        
        # Get status
        run_info = get_run_status(in_memory_db, run_id)
        
        assert run_info['run_id'] == run_id
        assert run_info['dag_name'] == 'daily_prices'
        assert run_info['status'] == RunStatus.RUNNING
        assert run_info['started_at'] == started_at
        assert run_info['finished_at'] is None
        assert run_info['rows_in'] is None
        assert run_info['rows_out'] is None
    
    def test_get_run_status_completed(self, in_memory_db):
        """Test retrieving status of completed run."""
        # Create and finish run with specific times
        started_at = datetime(2024, 1, 16, 9, 0, 0)
        finished_at = datetime(2024, 1, 16, 9, 10, 0)
        
        run_id = start_run(in_memory_db, 'test_dag', started_at)
        
        finish_run(
            conn=in_memory_db,
            run_id=run_id,
            status=RunStatus.COMPLETED,
            finished_at=finished_at,
            rows_in=50,
            rows_out=45
        )
        
        # Get status
        run_info = get_run_status(in_memory_db, run_id)
        
        assert run_info['status'] == RunStatus.COMPLETED
        assert run_info['finished_at'] == finished_at
        assert run_info['rows_in'] == 50
        assert run_info['rows_out'] == 45
        assert run_info['duration_seconds'] == 600  # 10 minutes
    
    def test_get_run_status_nonexistent(self, in_memory_db):
        """Test retrieving status of nonexistent run."""
        with pytest.raises(RunNotFoundError, match="Run ID 999 not found"):
            get_run_status(in_memory_db, 999)
    
    def test_list_recent_runs_empty(self, in_memory_db):
        """Test listing runs when none exist."""
        runs = list_recent_runs(in_memory_db)
        assert runs == []
    
    def test_list_recent_runs_with_data(self, in_memory_db):
        """Test listing recent runs with data."""
        # Create multiple runs
        run1 = start_run(
            in_memory_db,
            'daily_prices',
            datetime(2024, 1, 16, 9, 0, 0)
        )
        run2 = start_run(
            in_memory_db,
            'quarterly_13f',
            datetime(2024, 1, 16, 10, 0, 0)
        )
        run3 = start_run(
            in_memory_db,
            'daily_prices',
            datetime(2024, 1, 16, 11, 0, 0)
        )
        
        # Finish some runs
        finish_run(in_memory_db, run1, RunStatus.COMPLETED)
        finish_run(in_memory_db, run2, RunStatus.FAILED)
        # run3 still running
        
        # List recent runs
        runs = list_recent_runs(in_memory_db, limit=10)
        
        assert len(runs) == 3
        
        # Should be ordered by started_at DESC (most recent first)
        assert runs[0]['run_id'] == run3
        assert runs[0]['status'] == RunStatus.RUNNING
        assert runs[1]['run_id'] == run2
        assert runs[1]['status'] == RunStatus.FAILED
        assert runs[2]['run_id'] == run1
        assert runs[2]['status'] == RunStatus.COMPLETED
    
    def test_list_recent_runs_limit(self, in_memory_db):
        """Test listing runs with limit."""
        # Create 5 runs
        for i in range(5):
            start_run(in_memory_db, f'dag_{i}')
        
        # List with limit
        runs = list_recent_runs(in_memory_db, limit=3)
        
        assert len(runs) == 3
    
    def test_list_recent_runs_by_dag(self, in_memory_db):
        """Test listing runs filtered by DAG name."""
        # Create runs for different DAGs
        start_run(in_memory_db, 'daily_prices')
        start_run(in_memory_db, 'quarterly_13f')
        start_run(in_memory_db, 'daily_prices')
        
        # Filter by DAG
        runs = list_recent_runs(in_memory_db, dag_name='daily_prices')
        
        assert len(runs) == 2
        assert all(run['dag_name'] == 'daily_prices' for run in runs)
    
    def test_run_duration_calculation(self, in_memory_db):
        """Test duration calculation for completed runs."""
        started_at = datetime(2024, 1, 16, 9, 0, 0)
        finished_at = datetime(2024, 1, 16, 9, 5, 30)
        
        run_id = start_run(in_memory_db, 'test_dag', started_at)
        finish_run(in_memory_db, run_id, RunStatus.COMPLETED, finished_at)
        
        run_info = get_run_status(in_memory_db, run_id)
        
        # 5 minutes 30 seconds = 330 seconds
        assert run_info['duration_seconds'] == 330
    
    def test_run_status_enum_values(self):
        """Test that RunStatus enum has expected values."""
        assert RunStatus.RUNNING == 'running'
        assert RunStatus.COMPLETED == 'completed'
        assert RunStatus.FAILED == 'failed'
    
    def test_concurrent_runs_same_dag(self, in_memory_db):
        """Test that multiple runs of same DAG can run concurrently."""
        run1 = start_run(in_memory_db, 'daily_prices')
        run2 = start_run(in_memory_db, 'daily_prices')
        
        # Both should be running
        assert get_run_status(in_memory_db, run1)['status'] == RunStatus.RUNNING
        assert get_run_status(in_memory_db, run2)['status'] == RunStatus.RUNNING
        
        # Should be different run IDs
        assert run1 != run2
