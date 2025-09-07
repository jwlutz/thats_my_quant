#!/usr/bin/env python3
"""
Report renderer - reads MetricsJSON and writes formatted Markdown report.
Usage: python reports/render_report.py TICKER [options]
"""

import sys
import json
import argparse
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from reports.markdown_template import render_metrics_report


class ReportRenderError(Exception):
    """Raised when report rendering fails."""
    pass


def render_report(
    ticker: str,
    metrics_dir: Path,
    output_dir: Path,
    as_of_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Render Markdown report from MetricsJSON file.
    
    Args:
        ticker: Stock ticker symbol
        metrics_dir: Directory containing metrics JSON files
        output_dir: Directory to save Markdown reports
        as_of_date: Date for report (used in filename)
        
    Returns:
        Dictionary with render results
    """
    start_time = datetime.now()
    
    try:
        # Find metrics file
        metrics_file = _find_metrics_file(ticker, metrics_dir)
        if metrics_file is None:
            return {
                'ticker': ticker,
                'status': 'failed',
                'error_message': f'No metrics file found for {ticker} in {metrics_dir}',
                'output_path': None,
                'duration_seconds': (datetime.now() - start_time).total_seconds()
            }
        
        # Load metrics
        try:
            with open(metrics_file, 'r') as f:
                metrics = json.load(f)
        except Exception as e:
            return {
                'ticker': ticker,
                'status': 'failed',
                'error_message': f'Failed to load metrics file: {e}',
                'output_path': None,
                'duration_seconds': (datetime.now() - start_time).total_seconds()
            }
        
        # Render to Markdown
        try:
            markdown_content = render_metrics_report(metrics)
        except Exception as e:
            return {
                'ticker': ticker,
                'status': 'failed',
                'error_message': f'Template rendering failed: {e}',
                'output_path': None,
                'duration_seconds': (datetime.now() - start_time).total_seconds()
            }
        
        # Create output path
        output_path = _create_output_path(ticker, output_dir, as_of_date)
        
        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(markdown_content)
        
        return {
            'ticker': ticker,
            'status': 'completed',
            'output_path': str(output_path),
            'metrics_file': str(metrics_file),
            'report_size_bytes': len(markdown_content),
            'duration_seconds': (datetime.now() - start_time).total_seconds()
        }
        
    except Exception as e:
        return {
            'ticker': ticker,
            'status': 'failed',
            'error_message': str(e),
            'output_path': None,
            'duration_seconds': (datetime.now() - start_time).total_seconds()
        }


def _find_metrics_file(ticker: str, metrics_dir: Path) -> Optional[Path]:
    """Find metrics JSON file for ticker."""
    metrics_file = metrics_dir / f'{ticker}.json'
    return metrics_file if metrics_file.exists() else None


def _create_output_path(ticker: str, output_dir: Path, as_of_date: Optional[date] = None) -> Path:
    """Create output path for report."""
    if as_of_date is None:
        as_of_date = date.today()
    
    date_str = as_of_date.strftime('%Y_%m_%d')
    filename = f'{ticker}_{date_str}_metrics.md'
    
    return output_dir / ticker / filename


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Render Markdown report from MetricsJSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python reports/render_report.py AAPL
  python reports/render_report.py MSFT --output-dir ./custom/reports/
  python reports/render_report.py GOOGL --metrics-dir ./data/processed/metrics/
        """
    )
    
    parser.add_argument('ticker', help='Stock ticker symbol (e.g., AAPL)')
    parser.add_argument('--metrics-dir',
                       type=Path,
                       default='./data/processed/metrics',
                       help='Directory containing metrics JSON files')
    parser.add_argument('--output-dir',
                       type=Path,
                       default='./reports',
                       help='Directory to save Markdown reports')
    parser.add_argument('--as-of',
                       type=date.fromisoformat,
                       help='Report date (YYYY-MM-DD, default: today)')
    parser.add_argument('--quiet', '-q',
                       action='store_true',
                       help='Minimal output')
    
    args = parser.parse_args()
    
    if not args.quiet:
        print(f"📝 Rendering report for {args.ticker}")
        print(f"📁 Metrics source: {args.metrics_dir}")
        print(f"📄 Output directory: {args.output_dir}")
        print()
    
    # Render report
    result = render_report(
        ticker=args.ticker,
        metrics_dir=args.metrics_dir,
        output_dir=args.output_dir,
        as_of_date=args.as_of
    )
    
    if result['status'] == 'completed':
        if not args.quiet:
            print("✅ Report rendered successfully!")
            print(f"📄 Output: {result['output_path']}")
            print(f"Size: {result['report_size_bytes']:,} bytes")
            print(f"⏱️  Duration: {result['duration_seconds']:.2f}s")
            print(f"📋 Source: {result['metrics_file']}")
        else:
            print(f"✅ {args.ticker} report: {result['output_path']}")
        
        sys.exit(0)
    
    else:  # failed
        print(f"❌ Report rendering failed: {result['error_message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
