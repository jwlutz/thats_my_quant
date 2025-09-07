#!/usr/bin/env python3
"""
CLI tool for displaying calculated metrics.
Usage: python analysis/show_metrics.py TICKER [options]
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Display calculated metrics for a ticker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analysis/show_metrics.py AAPL
  python analysis/show_metrics.py MSFT --metrics-dir ./custom/metrics/
        """
    )
    
    parser.add_argument('ticker', help='Stock ticker symbol (e.g., AAPL)')
    parser.add_argument('--metrics-dir',
                       default='./data/processed/metrics',
                       help='Directory containing metrics JSON files')
    parser.add_argument('--format',
                       choices=['summary', 'full', 'json'],
                       default='summary',
                       help='Output format (default: summary)')
    
    args = parser.parse_args()
    
    # Find metrics file
    metrics_dir = Path(args.metrics_dir)
    metrics_file = metrics_dir / f'{args.ticker}.json'
    
    if not metrics_file.exists():
        print(f"❌ No metrics found for {args.ticker}", file=sys.stderr)
        print(f"📁 Looked in: {metrics_file}", file=sys.stderr)
        print(f"💡 Run analysis first: python analysis/analyze_ticker.py {args.ticker}", file=sys.stderr)
        sys.exit(1)
    
    # Load metrics
    try:
        with open(metrics_file, 'r') as f:
            metrics = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load metrics: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Display based on format
    if args.format == 'json':
        print(json.dumps(metrics, indent=2))
    elif args.format == 'full':
        _display_full_metrics(metrics)
    else:  # summary
        _display_summary_metrics(metrics)


def _display_summary_metrics(metrics: dict):
    """Display concise summary of key metrics."""
    ticker = metrics['ticker']
    as_of = metrics['as_of_date']
    
    print(f"📊 {ticker} Financial Metrics (as of {as_of})")
    print("=" * 50)
    
    # Current price
    pm = metrics.get('price_metrics', {})
    current = pm.get('current_price', {})
    if current:
        print(f"💰 Current Price: ${current['close']:.2f} ({current['date']})")
    
    # Returns
    returns = pm.get('returns', {})
    print("\n📈 Returns:")
    for period, label in [('1D', '1 Day'), ('1W', '1 Week'), ('1M', '1 Month'), ('3M', '3 Month'), ('6M', '6 Month'), ('1Y', '1 Year')]:
        if returns.get(period) is not None:
            ret_pct = returns[period] * 100
            direction = "📈" if ret_pct > 0 else "📉" if ret_pct < 0 else "➡️"
            print(f"   {label:8}: {direction} {ret_pct:+6.2f}%")
        else:
            print(f"   {label:8}: Not available")
    
    # Volatility
    volatility = pm.get('volatility', {})
    print("\n📊 Volatility (Annualized):")
    for period, label in [('21D_annualized', '21 Day'), ('63D_annualized', '3 Month'), ('252D_annualized', '1 Year')]:
        if volatility.get(period) is not None:
            vol_pct = volatility[period] * 100
            print(f"   {label:8}: {vol_pct:6.1f}%")
        else:
            print(f"   {label:8}: Not available")
    
    # Drawdown
    drawdown = pm.get('drawdown', {})
    if drawdown.get('max_drawdown_pct') is not None:
        dd_pct = abs(drawdown['max_drawdown_pct'] * 100)
        print(f"\n📉 Max Drawdown: -{dd_pct:.1f}%")
        if drawdown.get('peak_date') and drawdown.get('trough_date'):
            print(f"   Period: {drawdown['peak_date']} to {drawdown['trough_date']}")
        if drawdown.get('recovery_date'):
            print(f"   Recovered: {drawdown['recovery_date']}")
        else:
            print("   Recovery: Not yet recovered")
    
    # Institutional metrics
    im = metrics.get('institutional_metrics')
    if im:
        print(f"\n🏢 Institutional Holdings:")
        total_value = im.get('total_13f_value_usd', 0)
        if total_value > 0:
            print(f"   Total 13F Value: ${total_value/1e9:.1f}B")
            print(f"   Number of Holders: {im.get('total_13f_holders', 0)}")
            
            concentration = im.get('concentration', {})
            if concentration.get('cr1') is not None:
                cr1_pct = concentration['cr1'] * 100
                cr5_pct = concentration.get('cr5', 0) * 100
                print(f"   Top 1 Holder: {cr1_pct:.1f}%")
                print(f"   Top 5 Holders: {cr5_pct:.1f}%")
    else:
        print("\n🏢 Institutional Holdings: No 13F data available")
    
    # Data quality
    dq = metrics.get('data_quality', {})
    print(f"\n📋 Data Quality:")
    if dq.get('price_coverage_pct') is not None:
        print(f"   Price Coverage: {dq['price_coverage_pct']:.1f}%")
    if dq.get('latest_13f_quarter'):
        age_days = dq.get('13f_data_age_days', 0)
        print(f"   Latest 13F: {dq['latest_13f_quarter']} ({age_days} days ago)")


def _display_full_metrics(metrics: dict):
    """Display complete metrics in detailed format."""
    print(json.dumps(metrics, indent=2, default=str))


if __name__ == '__main__':
    main()
