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
from pipeline.quarterly_13f_dag import run_quarterly_13f, Quarterly13FConfig
from storage.loaders import init_database, get_connection


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python pipeline/run.py daily_prices TICKER [days]")
        print("  python pipeline/run.py quarterly_13f ENTITY_NAME QUARTER_END")
        print()
        print("Examples:")
        print("  python pipeline/run.py daily_prices AAPL 30")
        print("  python pipeline/run.py quarterly_13f 'BERKSHIRE HATHAWAY INC' 2024-12-31")
        sys.exit(1)
    
    dag_name = sys.argv[1]
    
    if dag_name not in ['daily_prices', 'quarterly_13f']:
        print(f"Unknown DAG: {dag_name}")
        print("Available DAGs: daily_prices, quarterly_13f")
        sys.exit(1)
    
    # Setup database
    db_path = project_root / 'data' / 'research.db'
    db_path.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    init_database(conn)
    
    if dag_name == 'daily_prices':
        # Parse daily_prices arguments
        ticker = sys.argv[2]
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        
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
        
    elif dag_name == 'quarterly_13f':
        # Parse quarterly_13f arguments
        if len(sys.argv) < 4:
            print("Usage: python pipeline/run.py quarterly_13f ENTITY_NAME QUARTER_END")
            print("Example: python pipeline/run.py quarterly_13f 'BERKSHIRE HATHAWAY INC' 2024-12-31")
            sys.exit(1)
        
        entity_name = sys.argv[2]
        quarter_end_str = sys.argv[3]
        
        # Parse quarter end date
        try:
            quarter_end = date.fromisoformat(quarter_end_str)
        except ValueError:
            print(f"Invalid date format: {quarter_end_str}. Use YYYY-MM-DD")
            sys.exit(1)
        
        config = Quarterly13FConfig(
            entity_name=entity_name,
            quarter_end=quarter_end
        )
        
        print(f"🚀 Running quarterly_13f pipeline for {entity_name}")
        print(f"📅 Quarter end: {quarter_end}")
        print()
        
        # Run pipeline
        result = run_quarterly_13f(config, conn)
    
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
        
        # Display pipeline-specific results
        if dag_name == 'daily_prices':
            _display_price_results(result)
        elif dag_name == 'quarterly_13f':
            _display_13f_results(result)
        
        print(f"💾 Data stored in: {db_path}")
        
    else:  # failed
        print("❌ Pipeline Failed:")
        print(f"   Error: {result.get('error_message', 'Unknown error')}")
        print(f"   Rows fetched: {result['rows_fetched']}")
        print(f"   Rows stored: {result['rows_stored']}")
    
    conn.close()


def _display_price_results(result: dict):
    """Display price-specific results."""
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


def _display_13f_results(result: dict):
    """Display 13F-specific results."""
    if 'holdings_summary' in result:
        hs = result['holdings_summary']
        print("🏢 Holdings Summary:")
        print(f"   Total positions: {hs['total_positions']}")
        print(f"   Total value: ${hs['total_value_usd']:,.0f}")
        print(f"   Average position: ${hs['avg_position_value_usd']:,.0f}")
        print()
        
        if 'largest_position' in hs:
            lp = hs['largest_position']
            print("🎯 Largest Position:")
            print(f"   {lp['ticker']} ({lp['name']})")
            print(f"   Value: ${lp['value_usd']:,.0f}")
            print(f"   Shares: {lp['shares']:,.0f}")
            print(f"   % of portfolio: {lp['pct_of_portfolio']:.1f}%")
            print()
    
    if 'concentration' in result:
        conc = result['concentration']
        print("📊 Concentration:")
        print(f"   Top 10 concentration: {conc['top_10_concentration_pct']:.1f}%")
        
        if conc['top_5_tickers']:
            print("   Top 5 holdings:")
            for i, holding in enumerate(conc['top_5_tickers'][:5], 1):
                print(f"      {i}. {holding['ticker']}: ${holding['value_usd']:,.0f} ({holding['pct_of_portfolio']:.1f}%)")
        print()


if __name__ == '__main__':
    main()
