"""
Run registry - track pipeline execution with status, metrics, and timing.
Thin IO layer for run lifecycle management.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class RunStatus(str, Enum):
    """Enumeration of run statuses."""
    RUNNING = 'running'
    COMPLETED = 'completed' 
    FAILED = 'failed'


class RunNotFoundError(Exception):
    """Raised when run ID is not found."""
    pass


def start_run(
    conn: sqlite3.Connection,
    dag_name: str,
    started_at: Optional[datetime] = None
) -> int:
    """
    Start a new pipeline run and return run ID.
    
    Args:
        conn: SQLite connection
        dag_name: Name of the pipeline/DAG being run
        started_at: Start timestamp (defaults to now)
        
    Returns:
        Run ID for tracking this execution
    """
    if started_at is None:
        started_at = datetime.now()
    
    cursor = conn.execute("""
        INSERT INTO runs (dag_name, started_at, status)
        VALUES (?, ?, ?)
    """, (dag_name, started_at, RunStatus.RUNNING))
    
    conn.commit()
    return cursor.lastrowid


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: RunStatus,
    finished_at: Optional[datetime] = None,
    rows_in: Optional[int] = None,
    rows_out: Optional[int] = None,
    log_path: Optional[str] = None,
    error_message: Optional[str] = None
) -> None:
    """
    Mark a run as finished with final status and metrics.
    
    Args:
        conn: SQLite connection
        run_id: Run ID from start_run()
        status: Final status (COMPLETED or FAILED)
        finished_at: End timestamp (defaults to now)
        rows_in: Number of input rows processed
        rows_out: Number of output rows produced
        log_path: Path to detailed log file
        error_message: Error message if failed
        
    Raises:
        RunNotFoundError: If run_id doesn't exist
    """
    if finished_at is None:
        finished_at = datetime.now()
    
    # Check if run exists
    cursor = conn.execute("SELECT run_id FROM runs WHERE run_id = ?", (run_id,))
    if cursor.fetchone() is None:
        raise RunNotFoundError(f"Run ID {run_id} not found")
    
    # Update run record
    conn.execute("""
        UPDATE runs SET
            status = ?,
            finished_at = ?,
            rows_in = ?,
            rows_out = ?,
            log_path = ?
        WHERE run_id = ?
    """, (status, finished_at, rows_in, rows_out, log_path, run_id))
    
    conn.commit()


def get_run_status(conn: sqlite3.Connection, run_id: int) -> Dict[str, Any]:
    """
    Get detailed status and metrics for a run.
    
    Args:
        conn: SQLite connection
        run_id: Run ID to query
        
    Returns:
        Dictionary with run details and computed metrics
        
    Raises:
        RunNotFoundError: If run_id doesn't exist
    """
    cursor = conn.execute("""
        SELECT run_id, dag_name, started_at, finished_at, status, 
               rows_in, rows_out, log_path
        FROM runs 
        WHERE run_id = ?
    """, (run_id,))
    
    row = cursor.fetchone()
    if row is None:
        raise RunNotFoundError(f"Run ID {run_id} not found")
    
    # Parse row data
    run_info = {
        'run_id': row[0],
        'dag_name': row[1],
        'started_at': datetime.fromisoformat(row[2].replace(' ', 'T')) if row[2] else None,
        'finished_at': datetime.fromisoformat(row[3].replace(' ', 'T')) if row[3] else None,
        'status': RunStatus(row[4]),
        'rows_in': row[5],
        'rows_out': row[6],
        'log_path': row[7]
    }
    
    # Calculate duration if finished
    if run_info['started_at'] and run_info['finished_at']:
        duration = run_info['finished_at'] - run_info['started_at']
        run_info['duration_seconds'] = int(duration.total_seconds())
    else:
        run_info['duration_seconds'] = None
    
    # Calculate efficiency metrics
    if run_info['rows_in'] and run_info['rows_out']:
        run_info['success_rate'] = run_info['rows_out'] / run_info['rows_in']
        run_info['rows_dropped'] = run_info['rows_in'] - run_info['rows_out']
    else:
        run_info['success_rate'] = None
        run_info['rows_dropped'] = None
    
    return run_info


def list_recent_runs(
    conn: sqlite3.Connection,
    limit: int = 50,
    dag_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List recent runs with basic info, most recent first.
    
    Args:
        conn: SQLite connection
        limit: Maximum number of runs to return
        dag_name: Filter by specific DAG name (optional)
        
    Returns:
        List of run dictionaries with basic info
    """
    # Build query
    if dag_name:
        query = """
            SELECT run_id, dag_name, started_at, finished_at, status, rows_in, rows_out
            FROM runs 
            WHERE dag_name = ?
            ORDER BY started_at DESC 
            LIMIT ?
        """
        params = (dag_name, limit)
    else:
        query = """
            SELECT run_id, dag_name, started_at, finished_at, status, rows_in, rows_out
            FROM runs 
            ORDER BY started_at DESC 
            LIMIT ?
        """
        params = (limit,)
    
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    
    runs = []
    for row in rows:
        run_info = {
            'run_id': row[0],
            'dag_name': row[1],
            'started_at': datetime.fromisoformat(row[2].replace(' ', 'T')) if row[2] else None,
            'finished_at': datetime.fromisoformat(row[3].replace(' ', 'T')) if row[3] else None,
            'status': RunStatus(row[4]),
            'rows_in': row[5],
            'rows_out': row[6]
        }
        
        # Add duration if finished
        if run_info['started_at'] and run_info['finished_at']:
            duration = run_info['finished_at'] - run_info['started_at']
            run_info['duration_seconds'] = int(duration.total_seconds())
        else:
            run_info['duration_seconds'] = None
        
        runs.append(run_info)
    
    return runs


def get_dag_stats(conn: sqlite3.Connection, dag_name: str, days: int = 30) -> Dict[str, Any]:
    """
    Get aggregate statistics for a DAG over recent period.
    
    Args:
        conn: SQLite connection
        dag_name: DAG name to analyze
        days: Number of days to look back
        
    Returns:
        Dictionary with aggregate statistics
    """
    cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
    
    cursor = conn.execute("""
        SELECT 
            COUNT(*) as total_runs,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_runs,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
            SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_runs,
            AVG(CASE WHEN finished_at IS NOT NULL 
                THEN (julianday(finished_at) - julianday(started_at)) * 86400 
                ELSE NULL END) as avg_duration_seconds,
            SUM(COALESCE(rows_in, 0)) as total_rows_in,
            SUM(COALESCE(rows_out, 0)) as total_rows_out
        FROM runs 
        WHERE dag_name = ? AND started_at >= ?
    """, (dag_name, cutoff_date))
    
    row = cursor.fetchone()
    
    stats = {
        'dag_name': dag_name,
        'period_days': days,
        'total_runs': row[0] or 0,
        'completed_runs': row[1] or 0,
        'failed_runs': row[2] or 0,
        'running_runs': row[3] or 0,
        'avg_duration_seconds': row[4],
        'total_rows_in': row[5] or 0,
        'total_rows_out': row[6] or 0
    }
    
    # Calculate derived metrics
    if stats['total_runs'] > 0:
        stats['success_rate'] = stats['completed_runs'] / stats['total_runs']
        stats['failure_rate'] = stats['failed_runs'] / stats['total_runs']
    else:
        stats['success_rate'] = None
        stats['failure_rate'] = None
    
    if stats['total_rows_in'] > 0:
        stats['data_success_rate'] = stats['total_rows_out'] / stats['total_rows_in']
        stats['total_rows_dropped'] = stats['total_rows_in'] - stats['total_rows_out']
    else:
        stats['data_success_rate'] = None
        stats['total_rows_dropped'] = None
    
    return stats
