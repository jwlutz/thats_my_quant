#!/usr/bin/env python3
"""
CLI tool for analyzing individual tickers.
Usage: python analysis/analyze_ticker.py TICKER [options]
"""

import sys
import sqlite3
import argparse
import json
from datetime import date, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from analysis.analysis_job import analyze_ticker
from storage.loaders import get_connection


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze financial metrics for a ticker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analysis/analyze_ticker.py AAPL
  python analysis/analyze_ticker.py MSFT --as-of 2025-08-01
  python analysis/analyze_ticker.py GOOGL --start 2025-01-01 --end 2025-08-01
        """
    )
    
    parser.add_argument('ticker', help='Stock ticker symbol (e.g., AAPL)')
    parser.add_argument('--db-path', 
                       default='./data/research.db',
                       help='Path to SQLite database (default: ./data/research.db)')
    parser.add_argument('--output',
                       help='Output JSON file path (default: ./data/processed/metrics/{TICKER}.json)')
    parser.add_argument('--as-of',
                       type=date.fromisoformat,
                       default=date.today(),
                       help='Analysis date (YYYY-MM-DD, default: today)')
    parser.add_argument('--start',
                       type=date.fromisoformat,
                       help='Start date for price data filter (YYYY-MM-DD)')
    parser.add_argument('--end',
                       type=date.fromisoformat,
                       help='End date for price data filter (YYYY-MM-DD)')
    parser.add_argument('--quiet', '-q',
                       action='store_true',
                       help='Minimal output (just success/failure)')
    
    args = parser.parse_args()
    
    # Set default output path
    if args.output is None:
        output_dir = Path('./data/processed/metrics')
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output = output_dir / f'{args.ticker}.json'
    else:
        args.output = Path(args.output)
    
    # Validate database exists
    if not Path(args.db_path).exists():
        print(f"❌ Database not found: {args.db_path}", file=sys.stderr)
        print("💡 Run the data pipeline first: python pipeline/run.py daily_prices AAPL", file=sys.stderr)
        sys.exit(1)
    
    if not args.quiet:
        print(f"🔍 Analyzing {args.ticker}")
        print(f"📊 Database: {args.db_path}")
        print(f"📅 Analysis date: {args.as_of}")
        if args.start or args.end:
            print(f"📈 Price window: {args.start or 'earliest'} to {args.end or 'latest'}")
        print()
    
    # Connect to database
    try:
        conn = sqlite3.connect(args.db_path)
    except Exception as e:
        print(f"❌ Database connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Run analysis
    try:
        result = analyze_ticker(
            conn=conn,
            ticker=args.ticker,
            output_path=args.output,
            as_of_date=args.as_of,
            start_date=args.start,
            end_date=args.end
        )
        
        if result['status'] == 'completed':
            if not args.quiet:
                print("✅ Analysis completed successfully!")
                print(f"📊 Metrics calculated: {result['metrics_calculated']}")
                print(f"📈 Price data points: {result['price_data_points']}")
                print(f"🏢 Holdings data points: {result['holdings_data_points']}")
                print(f"⏱️  Duration: {result['duration_seconds']:.1f}s")
                print(f"💾 Results saved to: {result['output_path']}")
                print()
                
                # Show quick summary
                _show_quick_summary(result['output_path'])
            else:
                print(f"✅ {args.ticker} analysis complete: {result['output_path']}")
            
            sys.exit(0)
        
        else:  # failed
            print(f"❌ Analysis failed for {args.ticker}: {result['error_message']}", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    
    finally:
        conn.close()


def _show_quick_summary(output_path: str):
    """Show quick summary of calculated metrics."""
    try:
        with open(output_path, 'r') as f:
            metrics = json.load(f)
        
        ticker = metrics['ticker']
        
        print(f"📋 Quick Summary for {ticker}:")
        
        # Price metrics
        pm = metrics.get('price_metrics', {})
        if pm.get('current_price'):
            current = pm['current_price']
            print(f"   Current Price: ${current['close']:.2f} ({current['date']})")
        
        returns = pm.get('returns', {})
        if returns.get('1D') is not None:
            ret_1d = returns['1D'] * 100
            direction = "📈" if ret_1d > 0 else "📉" if ret_1d < 0 else "➡️"
            print(f"   1D Return: {direction} {ret_1d:+.2f}%")
        
        if returns.get('1M') is not None:
            ret_1m = returns['1M'] * 100
            direction = "📈" if ret_1m > 0 else "📉" if ret_1m < 0 else "➡️"
            print(f"   1M Return: {direction} {ret_1m:+.2f}%")
        
        volatility = pm.get('volatility', {})
        if volatility.get('21D_annualized') is not None:
            vol = volatility['21D_annualized'] * 100
            print(f"   Volatility (21D): {vol:.1f}%")
        
        # Institutional metrics
        im = metrics.get('institutional_metrics')
        if im:
            total_value = im.get('total_13f_value_usd', 0)
            if total_value > 0:
                print(f"   13F Holdings: ${total_value/1e9:.1f}B ({im.get('total_13f_holders', 0)} institutions)")
            
            concentration = im.get('concentration', {})
            if concentration.get('cr1') is not None:
                cr1_pct = concentration['cr1'] * 100
                print(f"   Top Holder: {cr1_pct:.1f}% of 13F value")
        
        print()
        
    except Exception as e:
        print(f"⚠️  Could not show summary: {e}")


if __name__ == '__main__':
    main()
