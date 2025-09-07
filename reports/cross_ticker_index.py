"""
Cross-ticker index system - enables "what did I analyze today" queries.
Atomic JSON updates with timezone support.
"""

import json
import os
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Import path utilities
from reports.path_policy import parse_timestamp_from_filename, get_local_timezone


class CrossTickerIndexError(Exception):
    """Raised when cross-ticker index operations fail."""
    pass


INDEX_SCHEMA_VERSION = "1.0.0"


def update_cross_ticker_index(
    index_path: Path,
    ticker: str,
    report_path: str,
    latest_path: str,
    run_id: Optional[int],
    timestamp_local: datetime,
    pointer_strategy: str = 'symlink'
) -> Dict[str, Any]:
    """
    Update cross-ticker index with new report entry.
    
    Args:
        index_path: Path to latest_reports.json
        ticker: Stock ticker
        report_path: Path to timestamped report
        latest_path: Path to latest pointer
        run_id: Analysis run ID
        timestamp_local: Local generation timestamp
        pointer_strategy: 'symlink' or 'copy'
        
    Returns:
        Dictionary with update results
    """
    try:
        # Load existing index or create new
        if index_path.exists():
            with open(index_path, 'r') as f:
                index_data = json.load(f)
        else:
            index_data = {
                'schema_version': INDEX_SCHEMA_VERSION,
                'generated_at_utc': None,
                'timezone': None,
                'latest': []
            }
        
        # Update metadata
        index_data['generated_at_utc'] = datetime.now(timezone.utc).isoformat()
        index_data['timezone'] = str(get_local_timezone())
        
        # Create new entry
        new_entry = {
            'ticker': ticker,
            'report_path': report_path,
            'latest_path': latest_path,
            'run_id': run_id,
            'generated_at_local': timestamp_local.isoformat(),
            'pointer_strategy': pointer_strategy
        }
        
        # Update or add entry
        existing_entries = index_data['latest']
        updated = False
        
        for i, entry in enumerate(existing_entries):
            if entry['ticker'] == ticker:
                existing_entries[i] = new_entry
                updated = True
                break
        
        if not updated:
            existing_entries.append(new_entry)
        
        # Sort by ticker for consistent ordering
        index_data['latest'].sort(key=lambda x: x['ticker'])
        
        # Write atomically
        _write_index_atomic(index_data, index_path)
        
        return {
            'status': 'completed',
            'entries_count': len(index_data['latest']),
            'updated_existing': updated
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'entries_count': 0
        }


def query_today_reports(
    index_path: Path,
    target_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Query reports generated today (or target date).
    
    Args:
        index_path: Path to latest_reports.json
        target_date: Date to query (defaults to today)
        
    Returns:
        List of report entries for the target date
    """
    if not index_path.exists():
        return []
    
    if target_date is None:
        target_date = date.today()
    
    try:
        with open(index_path, 'r') as f:
            index_data = json.load(f)
        
        today_reports = []
        
        for entry in index_data.get('latest', []):
            # Parse timestamp from entry
            timestamp_str = entry.get('generated_at_local', '')
            if timestamp_str:
                try:
                    # Parse ISO format timestamp
                    if 'T' in timestamp_str:
                        entry_datetime = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        entry_datetime = datetime.fromisoformat(timestamp_str)
                    
                    entry_date = entry_datetime.date()
                    
                    if entry_date == target_date:
                        today_reports.append(entry)
                        
                except ValueError:
                    # Skip entries with invalid timestamps
                    continue
        
        # Sort by generation time (newest first)
        today_reports.sort(
            key=lambda x: x.get('generated_at_local', ''),
            reverse=True
        )
        
        return today_reports
        
    except Exception:
        return []


def rebuild_index_from_filesystem(
    reports_dir: Path,
    index_path: Path
) -> Dict[str, Any]:
    """
    Rebuild cross-ticker index by scanning filesystem.
    
    Args:
        reports_dir: Base reports directory
        index_path: Path to index file to rebuild
        
    Returns:
        Dictionary with rebuild results
    """
    try:
        if not reports_dir.exists():
            return {
                'status': 'failed',
                'error': f'Reports directory does not exist: {reports_dir}',
                'tickers_found': 0
            }
        
        # Scan for ticker directories
        tickers_found = []
        entries_created = 0
        
        for item in reports_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                ticker = item.name
                
                # Find latest report in ticker directory
                latest_path = item / 'latest.md'
                if latest_path.exists():
                    # Determine target report
                    if latest_path.is_symlink():
                        try:
                            target_report = latest_path.resolve()
                            strategy = 'symlink'
                        except:
                            continue  # Skip broken symlinks
                    else:
                        target_report = latest_path
                        strategy = 'copy'
                    
                    if target_report.exists():
                        # Parse timestamp from filename
                        try:
                            if strategy == 'symlink':
                                timestamp = parse_timestamp_from_filename(target_report.name)
                            else:
                                # For copy strategy, use file modification time
                                timestamp = datetime.fromtimestamp(target_report.stat().st_mtime)
                            
                            # Add to index
                            update_cross_ticker_index(
                                index_path, ticker,
                                str(target_report.relative_to(reports_dir.parent)),
                                str(latest_path.relative_to(reports_dir.parent)),
                                run_id=None,  # Unknown from filesystem scan
                                timestamp_local=timestamp,
                                pointer_strategy=strategy
                            )
                            
                            tickers_found.append(ticker)
                            entries_created += 1
                            
                        except Exception:
                            # Skip entries we can't parse
                            continue
        
        return {
            'status': 'completed',
            'tickers_found': len(tickers_found),
            'entries_created': entries_created,
            'tickers': tickers_found
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'tickers_found': 0
        }


def _write_index_atomic(index_data: Dict[str, Any], index_path: Path) -> None:
    """
    Write index data atomically.
    
    Args:
        index_data: Complete index dictionary
        index_path: Path to index file
        
    Raises:
        CrossTickerIndexError: If write fails
    """
    try:
        # Ensure parent directory exists
        index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first
        temp_path = index_path.with_suffix('.tmp')
        
        with open(temp_path, 'w') as f:
            json.dump(index_data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        
        # Atomic rename
        if os.name == 'nt' and index_path.exists():
            # Windows requires removing target
            index_path.unlink()
        
        temp_path.rename(index_path)
        
    except Exception as e:
        # Cleanup temp file
        temp_path = index_path.with_suffix('.tmp')
        if temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass
        
        raise CrossTickerIndexError(f"Failed to write index: {e}")


def get_index_stats(index_path: Path) -> Dict[str, Any]:
    """
    Get statistics about the cross-ticker index.
    
    Args:
        index_path: Path to index file
        
    Returns:
        Dictionary with index statistics
    """
    if not index_path.exists():
        return {
            'exists': False,
            'total_tickers': 0,
            'total_reports': 0,
            'last_updated': None
        }
    
    try:
        with open(index_path, 'r') as f:
            index_data = json.load(f)
        
        entries = index_data.get('latest', [])
        
        return {
            'exists': True,
            'schema_version': index_data.get('schema_version'),
            'total_tickers': len(entries),
            'total_reports': len(entries),  # One latest per ticker
            'last_updated': index_data.get('generated_at_utc'),
            'timezone': index_data.get('timezone'),
            'tickers': [entry['ticker'] for entry in entries]
        }
        
    except Exception as e:
        return {
            'exists': True,
            'error': str(e),
            'total_tickers': 0
        }
