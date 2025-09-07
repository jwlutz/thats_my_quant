"""
Filename and path policy for report storage.
Deterministic path generation with timezone support.
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

try:
    import zoneinfo
except ImportError:
    # Fallback for older Python versions
    try:
        from backports import zoneinfo
    except ImportError:
        zoneinfo = None


class PathPolicyError(Exception):
    """Raised when path policy validation fails."""
    pass


def create_report_paths(
    ticker: str,
    timestamp_local: datetime,
    base_dir: Path = Path('./reports')
) -> Dict[str, Path]:
    """
    Create all report-related paths for a ticker and timestamp.
    
    Args:
        ticker: Stock ticker symbol
        timestamp_local: Local timestamp for the report
        base_dir: Base reports directory
        
    Returns:
        Dictionary with all relevant paths:
        - report_path: Main report Markdown file
        - latest_path: Latest report pointer
        - metrics_path: Metrics JSON sidecar
        - ticker_dir: Ticker directory
        
    Raises:
        PathPolicyError: If inputs are invalid
    """
    # Validate ticker
    normalized_ticker = _normalize_ticker(ticker)
    
    # Create timestamp string for filename
    # Format: YYYY-MM-DD_HHMMSS (sortable, no colons for Windows)
    if timestamp_local.tzinfo is None:
        # Naive datetime - assume local timezone
        local_tz = get_local_timezone()
        timestamp_local = timestamp_local.replace(tzinfo=local_tz)
    
    # Use local time for filename (matches user's "today" mental model)
    time_str = timestamp_local.strftime('%Y-%m-%d_%H%M%S')
    
    # Build paths
    ticker_dir = base_dir / normalized_ticker
    report_filename = f'{time_str}_report.md'
    metrics_filename = f'{time_str}_metrics.json'
    
    return {
        'report_path': ticker_dir / report_filename,
        'latest_path': ticker_dir / 'latest.md',
        'metrics_path': ticker_dir / metrics_filename,
        'ticker_dir': ticker_dir,
        'timestamp_str': time_str
    }


def _normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker symbol for filesystem safety.
    
    Args:
        ticker: Raw ticker symbol
        
    Returns:
        Normalized ticker safe for filesystem use
        
    Raises:
        PathPolicyError: If ticker is invalid
    """
    if not ticker or not isinstance(ticker, str):
        raise PathPolicyError("Ticker cannot be empty")
    
    if len(ticker) > 20:
        raise PathPolicyError(f"Ticker too long (max 20 chars): {ticker}")
    
    # Convert to uppercase
    normalized = ticker.upper()
    
    # Replace filesystem-unsafe characters with underscores
    # Allow: letters, numbers, underscores only (no hyphens for consistency)
    # Replace: dots, dashes, slashes, other special chars
    normalized = re.sub(r'[^A-Z0-9_]', '_', normalized)
    
    # Check for invalid characters that might remain
    if re.search(r'[<>:"/\\|?*]', normalized):
        raise PathPolicyError(f"Invalid characters in ticker: {ticker}")
    
    return normalized


def parse_timestamp_from_filename(filename: str) -> datetime:
    """
    Parse timestamp from report filename.
    
    Args:
        filename: Report filename (e.g., '2025-09-06_143000_report.md')
        
    Returns:
        Datetime object (naive, local timezone assumed)
        
    Raises:
        PathPolicyError: If filename format is invalid
    """
    # Expected format: YYYY-MM-DD_HHMMSS_report.md
    pattern = r'^(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})(\d{2})_report\.md$'
    match = re.match(pattern, filename)
    
    if not match:
        raise PathPolicyError(f"Invalid filename format: {filename}")
    
    year, month, day, hour, minute, second = map(int, match.groups())
    
    # Validate date/time components
    try:
        timestamp = datetime(year, month, day, hour, minute, second)
    except ValueError as e:
        raise PathPolicyError(f"Invalid date/time in filename {filename}: {e}")
    
    return timestamp


def get_local_timezone():
    """
    Get local timezone for timestamp handling.
    
    Returns:
        Timezone object for local timezone
    """
    # Try environment variable first
    tz_name = os.getenv('REPORTS_TZ')
    
    if tz_name and zoneinfo:
        try:
            return zoneinfo.ZoneInfo(tz_name)
        except Exception:
            # Fall back to system timezone if env var is invalid
            pass
    
    # Use system local timezone
    try:
        return datetime.now().astimezone().tzinfo
    except Exception:
        # Ultimate fallback: UTC
        return timezone.utc


def list_report_files(ticker_dir: Path) -> list:
    """
    List all report files in ticker directory, sorted chronologically.
    
    Args:
        ticker_dir: Path to ticker directory
        
    Returns:
        List of report file paths, newest first
    """
    if not ticker_dir.exists():
        return []
    
    # Find all report files
    report_files = list(ticker_dir.glob('*_report.md'))
    
    # Filter out latest.md (it's a pointer, not a timestamped report)
    report_files = [f for f in report_files if f.name != 'latest.md']
    
    # Sort by filename (which sorts chronologically due to our format)
    report_files.sort(reverse=True)  # Newest first
    
    return report_files


def validate_report_filename(filename: str) -> bool:
    """
    Validate that filename follows our naming convention.
    
    Args:
        filename: Filename to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        parse_timestamp_from_filename(filename)
        return True
    except PathPolicyError:
        return False


def get_latest_report_path(ticker_dir: Path) -> Optional[Path]:
    """
    Get the path to the latest report for a ticker.
    
    Args:
        ticker_dir: Path to ticker directory
        
    Returns:
        Path to latest report file, or None if no reports exist
    """
    latest_path = ticker_dir / 'latest.md'
    
    if latest_path.exists():
        # Check if it's a symlink
        if latest_path.is_symlink():
            # Resolve symlink
            try:
                resolved = latest_path.resolve()
                if resolved.exists():
                    return resolved
            except Exception:
                pass
        else:
            # Regular file (copy strategy)
            return latest_path
    
    # Fallback: find newest timestamped report
    report_files = list_report_files(ticker_dir)
    return report_files[0] if report_files else None


def create_cross_ticker_entry(
    ticker: str,
    report_path: Path,
    latest_path: Path,
    run_id: Optional[int],
    timestamp_local: datetime,
    pointer_strategy: str = 'symlink'
) -> Dict[str, str]:
    """
    Create entry for cross-ticker index.
    
    Args:
        ticker: Stock ticker
        report_path: Path to timestamped report
        latest_path: Path to latest pointer
        run_id: Analysis run ID (optional)
        timestamp_local: Local generation timestamp
        pointer_strategy: 'symlink' or 'copy'
        
    Returns:
        Dictionary entry for latest_reports.json
    """
    return {
        'ticker': ticker,
        'report_path': str(report_path),
        'latest_path': str(latest_path),
        'run_id': run_id,
        'generated_at_local': timestamp_local.isoformat(),
        'pointer_strategy': pointer_strategy
    }
