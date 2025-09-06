"""
Pipeline runner CLI - makes the daily_prices pipeline human-visible.
Usage: python pipeline/run.py daily_prices AAPL
"""

import sys
import sqlite3
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pipeline.daily_prices_dag import run_daily_prices, DailyPricesConfig
from storage.loaders import init_database, get_connection


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: python pipeline/run.py daily_prices TICKER [days]")
        print("Example: python pipeline/run.py daily_prices AAPL")
        print("Example: python pipeline/run.py daily_prices AAPL 30")
        sys.exit(1)
    
    dag_name = sys.argv[1]
    ticker = sys.argv[2]
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    
    if dag_name != 'daily_prices':
        print(f"Unknown DAG: {dag_name}")
        print("Available DAGs: daily_prices")
        sys.exit(1)
    
    # Setup database
    db_path = project_root / 'data' / 'research.db'
    db_path.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    init_database(conn)
    
    # Configure pipeline
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    config = DailyPricesConfig(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date
    )
    
    print(f"🚀 Running daily_prices pipeline for {ticker}")
    print(f"📅 Date range: {start_date} to {end_date} ({days} days)")
    print()
    
    # Run pipeline
    result = run_daily_prices(config, conn)
    
    # Display results
    print("📊 Pipeline Results:")
    print(f"   Status: {result['status'].upper()}")
    print(f"   Run ID: {result['run_id']}")
    print(f"   Duration: {result['duration_seconds']:.1f}s")
    print()
    
    if result['status'] == 'completed':
        print("✅ Data Processing:")
        print(f"   Rows fetched: {result['rows_fetched']}")
        print(f"   Rows stored: {result['rows_stored']}")
        if result.get('validation_warnings', 0) > 0:
            print(f"   Validation warnings: {result['validation_warnings']}")
        print()
        
        if 'price_range' in result:
            pr = result['price_range']
            print("💰 Price Summary:")
            print(f"   Price range: ${pr['min_close']:.2f} - ${pr['max_close']:.2f}")
            print(f"   First/Last: ${pr['first_close']:.2f} → ${pr['last_close']:.2f}")
            if 'total_return_pct' in result:
                return_pct = result['total_return_pct']
                direction = "📈" if return_pct > 0 else "📉" if return_pct < 0 else "➡️"
                print(f"   Total return: {direction} {return_pct:+.2f}%")
            print()
        
        if 'total_volume' in result:
            print("📊 Volume Summary:")
            print(f"   Total volume: {result['total_volume']:,}")
            print(f"   Average volume: {result['avg_volume']:,.0f}")
            print()
        
        print(f"💾 Data stored in: {db_path}")
        
    else:  # failed
        print("❌ Pipeline Failed:")
        print(f"   Error: {result.get('error_message', 'Unknown error')}")
        print(f"   Rows fetched: {result['rows_fetched']}")
        print(f"   Rows stored: {result['rows_stored']}")
    
    conn.close()


if __name__ == '__main__':
    main()
