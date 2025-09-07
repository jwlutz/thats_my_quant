"""
Atomic file writer - ensures no partial writes or corrupted files.
Implements temp-write → fsync → rename pattern for durability.
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any


class AtomicWriteError(Exception):
    """Raised when atomic write operations fail."""
    pass


def write_report_atomic(content: str, output_path: Path) -> Dict[str, Any]:
    """
    Write report content atomically to prevent partial files.
    
    Uses temp-write → fsync → rename pattern for atomicity.
    
    Args:
        content: Report content to write
        output_path: Final path for the report
        
    Returns:
        Dictionary with write results
    """
    start_time = time.time() if 'time' in globals() else 0
    
    try:
        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create temporary file in same directory for atomic rename
        temp_fd = None
        temp_path = None
        
        try:
            # Create temp file in same directory
            temp_fd, temp_path_str = tempfile.mkstemp(
                suffix='.tmp',
                prefix=f'{output_path.stem}_',
                dir=output_path.parent
            )
            temp_path = Path(temp_path_str)
            
            # Write content to temp file
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            temp_fd = None  # Closed by context manager
            
            # Atomic rename
            if os.name == 'nt':  # Windows
                # Windows requires removing target if it exists
                if output_path.exists():
                    output_path.unlink()
            
            temp_path.rename(output_path)
            
            return {
                'status': 'completed',
                'output_path': str(output_path),
                'bytes_written': len(content),
                'duration_seconds': time.time() - start_time if 'time' in globals() else 0
            }
            
        except Exception as e:
            # Cleanup temp file on error
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except:
                    pass
            
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass
            
            raise e
            
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'output_path': str(output_path),
            'bytes_written': 0,
            'duration_seconds': time.time() - start_time if 'time' in globals() else 0
        }


def write_metrics_sidecar(metrics: Dict[str, Any], output_path: Path) -> Dict[str, Any]:
    """
    Write metrics JSON sidecar atomically.
    
    Args:
        metrics: Complete MetricsJSON dictionary
        output_path: Path for metrics JSON file
        
    Returns:
        Dictionary with write results
    """
    try:
        # Serialize to JSON string first (catch serialization errors early)
        json_content = json.dumps(metrics, indent=2, default=str)
        
        # Use atomic write for JSON content
        return write_report_atomic(json_content, output_path)
        
    except (TypeError, ValueError) as e:
        return {
            'status': 'failed',
            'error': f'JSON serialization failed: {e}',
            'output_path': str(output_path),
            'bytes_written': 0
        }


def write_both_atomic(
    report_content: str,
    metrics: Dict[str, Any],
    report_path: Path,
    metrics_path: Path
) -> Dict[str, Any]:
    """
    Write both report and metrics atomically.
    
    If either write fails, neither file is created (all-or-nothing).
    
    Args:
        report_content: Markdown report content
        metrics: MetricsJSON dictionary
        report_path: Path for report file
        metrics_path: Path for metrics file
        
    Returns:
        Dictionary with combined write results
    """
    try:
        # Write report first
        report_result = write_report_atomic(report_content, report_path)
        
        if report_result['status'] != 'completed':
            return {
                'status': 'failed',
                'error': f"Report write failed: {report_result.get('error', 'Unknown')}",
                'report_written': False,
                'metrics_written': False
            }
        
        # Write metrics sidecar
        metrics_result = write_metrics_sidecar(metrics, metrics_path)
        
        if metrics_result['status'] != 'completed':
            # Report succeeded but metrics failed - clean up report
            try:
                report_path.unlink()
            except:
                pass  # Best effort cleanup
            
            return {
                'status': 'failed',
                'error': f"Metrics write failed: {metrics_result.get('error', 'Unknown')}",
                'report_written': False,
                'metrics_written': False
            }
        
        # Both succeeded
        return {
            'status': 'completed',
            'report_path': str(report_path),
            'metrics_path': str(metrics_path),
            'report_bytes': report_result['bytes_written'],
            'metrics_bytes': metrics_result['bytes_written'],
            'report_written': True,
            'metrics_written': True
        }
        
    except Exception as e:
        # Clean up any partial writes
        for path in [report_path, metrics_path]:
            if path.exists():
                try:
                    path.unlink()
                except:
                    pass
        
        return {
            'status': 'failed',
            'error': str(e),
            'report_written': False,
            'metrics_written': False
        }


def verify_file_integrity(file_path: Path, expected_size: int = None) -> bool:
    """
    Verify file integrity after atomic write.
    
    Args:
        file_path: Path to file to verify
        expected_size: Expected file size in bytes (optional)
        
    Returns:
        True if file appears intact, False otherwise
    """
    if not file_path.exists():
        return False
    
    try:
        # Check file size
        actual_size = file_path.stat().st_size
        if expected_size is not None and actual_size != expected_size:
            return False
        
        # Try to read file (basic corruption check)
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read()
        
        return True
        
    except Exception:
        return False


# Add missing import
import time
