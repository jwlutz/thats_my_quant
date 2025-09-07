"""
Latest pointer management - symlink preferred, copy fallback.
Handles Windows compatibility and pointer integrity.
"""

import os
import shutil
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional


class PointerStrategy(str, Enum):
    """Enumeration of pointer strategies."""
    SYMLINK = 'symlink'
    COPY = 'copy'


class LatestPointerError(Exception):
    """Raised when latest pointer operations fail."""
    pass


def update_latest_pointer(
    ticker_dir: Path,
    report_path: Path,
    prefer_symlinks: bool = True
) -> Dict[str, Any]:
    """
    Update latest.md pointer to point to the specified report.
    
    Args:
        ticker_dir: Directory containing ticker reports
        report_path: Path to the report to point to
        prefer_symlinks: Whether to prefer symlinks over copying
        
    Returns:
        Dictionary with update results
    """
    if not report_path.exists():
        return {
            'status': 'failed',
            'error': f'Report file does not exist: {report_path}',
            'strategy': None
        }
    
    latest_path = ticker_dir / 'latest.md'
    
    # Ensure ticker directory exists
    ticker_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Try symlink strategy first if preferred
        if prefer_symlinks:
            try:
                # Remove existing latest pointer
                if latest_path.exists():
                    latest_path.unlink()
                
                # Create relative symlink (more portable)
                relative_target = report_path.name
                latest_path.symlink_to(relative_target)
                
                return {
                    'status': 'completed',
                    'strategy': PointerStrategy.SYMLINK,
                    'latest_path': str(latest_path),
                    'target_path': str(report_path)
                }
                
            except (OSError, NotImplementedError):
                # Symlink failed - fall back to copy
                pass
        
        # Copy strategy (fallback or preferred)
        if latest_path.exists():
            latest_path.unlink()
        
        shutil.copy2(report_path, latest_path)
        
        return {
            'status': 'completed',
            'strategy': PointerStrategy.COPY,
            'latest_path': str(latest_path),
            'target_path': str(report_path)
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'strategy': None
        }


def check_pointer_integrity(ticker_dir: Path) -> Dict[str, Any]:
    """
    Check integrity of latest.md pointer.
    
    Args:
        ticker_dir: Directory containing ticker reports
        
    Returns:
        Dictionary with integrity check results
    """
    latest_path = ticker_dir / 'latest.md'
    
    if not latest_path.exists():
        return {
            'valid': False,
            'strategy': None,
            'target_exists': False,
            'error': 'latest.md not found'
        }
    
    try:
        # Detect strategy
        if latest_path.is_symlink():
            # Symlink strategy
            try:
                target = latest_path.resolve()
                target_exists = target.exists()
                
                return {
                    'valid': target_exists,
                    'strategy': PointerStrategy.SYMLINK,
                    'target_exists': target_exists,
                    'target_path': str(target) if target_exists else None,
                    'error': None if target_exists else 'Broken symlink'
                }
                
            except Exception as e:
                return {
                    'valid': False,
                    'strategy': PointerStrategy.SYMLINK,
                    'target_exists': False,
                    'error': f'Symlink resolution failed: {e}'
                }
        
        else:
            # Copy strategy (regular file)
            # Check if file is readable
            try:
                with open(latest_path, 'r') as f:
                    f.read(1)  # Try to read first character
                
                return {
                    'valid': True,
                    'strategy': PointerStrategy.COPY,
                    'target_exists': True,
                    'target_path': str(latest_path),
                    'error': None
                }
                
            except Exception as e:
                return {
                    'valid': False,
                    'strategy': PointerStrategy.COPY,
                    'target_exists': False,
                    'error': f'File read failed: {e}'
                }
                
    except Exception as e:
        return {
            'valid': False,
            'strategy': None,
            'target_exists': False,
            'error': str(e)
        }


def repair_latest_pointer(ticker_dir: Path) -> Dict[str, Any]:
    """
    Attempt to repair broken latest.md pointer.
    
    Finds the newest timestamped report and updates latest.md to point to it.
    
    Args:
        ticker_dir: Directory containing ticker reports
        
    Returns:
        Dictionary with repair results
    """
    from reports.path_policy import list_report_files
    
    # Find newest report
    report_files = list_report_files(ticker_dir)
    
    if not report_files:
        return {
            'status': 'failed',
            'error': 'No timestamped reports found to repair pointer',
            'reports_found': 0
        }
    
    # Use newest report
    newest_report = report_files[0]  # list_report_files returns newest first
    
    # Update pointer
    result = update_latest_pointer(ticker_dir, newest_report)
    
    if result['status'] == 'completed':
        return {
            'status': 'completed',
            'repaired': True,
            'target_report': str(newest_report),
            'strategy': result['strategy'],
            'reports_found': len(report_files)
        }
    else:
        return {
            'status': 'failed',
            'error': f"Repair failed: {result.get('error', 'Unknown')}",
            'reports_found': len(report_files)
        }


def get_latest_report_content(ticker_dir: Path) -> Optional[str]:
    """
    Get content of latest report, following pointer if valid.
    
    Args:
        ticker_dir: Directory containing ticker reports
        
    Returns:
        Report content string, or None if not available
    """
    latest_path = ticker_dir / 'latest.md'
    
    if not latest_path.exists():
        return None
    
    try:
        # Check integrity first
        integrity = check_pointer_integrity(ticker_dir)
        
        if not integrity['valid']:
            # Try to repair
            repair_result = repair_latest_pointer(ticker_dir)
            if repair_result['status'] != 'completed':
                return None
        
        # Read content
        with open(latest_path, 'r') as f:
            return f.read()
            
    except Exception:
        return None


def list_all_latest_pointers(reports_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Check all latest pointers across all tickers.
    
    Args:
        reports_dir: Base reports directory
        
    Returns:
        Dictionary mapping tickers to pointer integrity results
    """
    results = {}
    
    if not reports_dir.exists():
        return results
    
    # Find all ticker directories
    for item in reports_dir.iterdir():
        if item.is_dir():
            ticker = item.name
            integrity = check_pointer_integrity(item)
            results[ticker] = integrity
    
    return results
