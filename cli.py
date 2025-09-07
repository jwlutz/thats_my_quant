#!/usr/bin/env python3
"""
Main CLI for AI Stock Market Research Workbench.
Usage: python cli.py report TICKER [--llm=on|off]
"""

import sys
import json
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import all report components
from reports.v1_to_v2_builder import build_enhanced_metrics_v2
from reports.skeleton_builder import build_exec_summary_skeleton
from reports.langchain_chains import generate_exec_summary, generate_risk_bullets
from reports.atomic_writer import write_both_atomic
from reports.latest_pointer import update_latest_pointer
from reports.cross_ticker_index import update_cross_ticker_index
from reports.path_policy import create_report_paths


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='AI Stock Market Research Workbench',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python cli.py report AAPL                  # Generate report with deterministic tables only (default)
  python cli.py report AAPL --llm=off        # Explicit deterministic mode
  python cli.py report AAPL --llm=on         # Enable LLM narrative generation
  python cli.py report MSFT --llm=on         # Generate MSFT report with LLM"""
    )
    
    parser.add_argument('command', choices=['report'], help='Command to execute')
    parser.add_argument('ticker', help='Stock ticker symbol (e.g., AAPL, MSFT)')
    parser.add_argument('--llm', choices=['on', 'off'], default='off',
                       help='Enable LLM narrative generation (default: off)')
    
    args = parser.parse_args()
    
    if args.command == 'report':
        generate_report(args.ticker, llm_enabled=(args.llm == 'on'))
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


def generate_report(ticker: str, llm_enabled: bool = False):
    """
    Generate complete research report for ticker.
    
    Args:
        ticker: Stock ticker symbol
        llm_enabled: Whether to enable LLM narrative generation
    """
    print(f"Generating research report for {ticker}")
    print()
    
    try:
        # 1. Load existing MetricsJSON v1
        metrics_path = Path(f'./data/processed/metrics/{ticker}.json')
        
        if not metrics_path.exists():
            print(f"ERROR: No metrics found for {ticker}")
            print(f"💡 Run analysis first: python analysis/analyze_ticker.py {ticker}")
            sys.exit(1)
        
        with open(metrics_path, 'r') as f:
            v1_metrics = json.load(f)
        
        print(f"Loaded metrics for {ticker}")
        
        # 2. Convert to Enhanced v2
        v2_metrics = build_enhanced_metrics_v2(v1_metrics)
        print(f"Enhanced to v2 format")
        
        # 3. Generate executive summary
        if llm_enabled:
            print("LLM enabled - generating narrative with audit")
            try:
                final_summary = generate_exec_summary(v2_metrics)
                print(f"Executive summary generated ({len(final_summary.split())} words)")
            except Exception as e:
                print(f"WARNING: LLM generation failed - using skeleton: {e}")
                skeleton = build_exec_summary_skeleton(v2_metrics)
                final_summary = skeleton
                print(f"Using skeleton fallback ({len(skeleton.split())} words)")
        else:
            print("LLM disabled - using deterministic skeleton")
            skeleton = build_exec_summary_skeleton(v2_metrics)
            final_summary = skeleton
            print(f"Built skeleton ({len(skeleton.split())} words)")
        
        # 4. Generate risk bullets (if LLM enabled)
        if llm_enabled:
            try:
                risk_bullets = generate_risk_bullets(v2_metrics)
                print(f"Risk bullets generated ({len(risk_bullets)} bullets)")
            except Exception as e:
                print(f"WARNING: Risk bullets generation failed: {e}")
                risk_bullets = [
                    "Market volatility risk based on observed price movements",
                    "Concentration risk in institutional ownership structure",
                    "Liquidity risk during market stress periods"
                ]
                print("Using fallback risk bullets")
        else:
            risk_bullets = None  # No risk bullets in deterministic mode
        
        # 5. Create complete report
        report_content = _build_complete_report(final_summary, v2_metrics, risk_bullets)
        
        # 7. Write report atomically
        timestamp = datetime.now()
        paths = create_report_paths(ticker, timestamp)
        
        write_result = write_both_atomic(
            report_content=report_content,
            metrics=v2_metrics,
            report_path=paths['report_path'],
            metrics_path=paths['metrics_path']
        )
        
        if write_result['status'] != 'completed':
            print(f"ERROR: Write failed: {write_result['error']}")
            sys.exit(1)
        
        print(f"Report written ({write_result['report_bytes']} bytes)")
        
        # 8. Update latest pointer
        pointer_result = update_latest_pointer(
            ticker_dir=paths['ticker_dir'],
            report_path=paths['report_path']
        )
        
        if pointer_result['status'] == 'completed':
            print(f"Latest pointer updated ({pointer_result['strategy']})")
        else:
            print(f"WARNING: Pointer update failed: {pointer_result['error']}")
        
        # 9. Update cross-ticker index
        index_result = update_cross_ticker_index(
            index_path=Path('./reports/latest_reports.json'),
            ticker=ticker,
            report_path=str(paths['report_path']),
            latest_path=str(paths['latest_path']),
            run_id=v1_metrics.get('metadata', {}).get('run_id'),
            timestamp_local=timestamp,
            pointer_strategy=pointer_result.get('strategy', 'unknown')
        )
        
        if index_result['status'] == 'completed':
            print(f"Index updated ({index_result['entries_count']} total entries)")
        
        # 10. Success summary
        print()
        print(f"Report generation complete!")
        print(f"Report: {paths['report_path']}")
        print(f"Latest: {paths['latest_path']}")
        print(f"Metrics: {paths['metrics_path']}")
        
    except Exception as e:
        print(f"ERROR: Report generation failed: {e}")
        sys.exit(1)


def _build_complete_report(executive_summary: str, metrics_v2: Dict[str, Any], risk_bullets: list = None) -> str:
    """
    Build complete Markdown report with all sections.
    
    Args:
        executive_summary: Generated executive summary
        metrics_v2: Enhanced MetricsJSON v2
        risk_bullets: Optional list of risk bullet strings
        
    Returns:
        Complete Markdown report content
    """
    meta = metrics_v2['meta']
    price = metrics_v2['price']
    ownership = metrics_v2.get('ownership_13f')
    
    # Build report sections
    sections = []
    
    # Title block
    sections.append(f"""# Stock Research Report: {meta['ticker']}

**Company:** {meta['company']}
**Currency:** {meta['currency']}
**Current Price:** {price['current']['display']} ({price['current']['date_display']})
**Generated:** {meta['as_of_local']}
**Report ID:** {meta['run_id']}

---""")
    
    # Executive Summary
    sections.append(f"""## Executive Summary

{executive_summary}

---""")
    
    # Risk Analysis (if LLM enabled)
    if risk_bullets:
        risk_section = """## Risk Analysis

Key risk factors identified from the analysis:

"""
        for i, bullet in enumerate(risk_bullets, 1):
            risk_section += f"{i}. {bullet}\n"
        
        risk_section += "\n---"
        sections.append(risk_section)
    
    # Price Snapshot
    sections.append(_build_price_snapshot_table(price))
    
    # Ownership Snapshot
    if ownership:
        sections.append(_build_ownership_snapshot_table(ownership))
    else:
        sections.append("""## Ownership Snapshot

*Institutional ownership data not available.*

---""")
    
    # Appendix
    sections.append(_build_appendix(metrics_v2))
    
    return '\n\n'.join(sections)


def _build_price_snapshot_table(price_data: Dict[str, Any]) -> str:
    """Build price snapshot table section."""
    returns = price_data['returns']
    volatility = price_data['volatility']
    drawdown = price_data['drawdown']
    
    # Returns table
    returns_table = """## Price Snapshot

### Returns by Period

| Period | Return |
|--------|--------|"""
    
    for period in ['1D', '1W', '1M', '3M', '6M', '1Y']:
        if period in returns['display']:
            display_val = returns['display'][period]
            period_name = _format_period_name(period)
            returns_table += f"\n| {period_name} | {display_val} |"
    
    # Volatility and drawdown
    vol_section = f"""
### Volatility & Risk

**Volatility {volatility['window_display']}:** {volatility['display']} ({volatility['level']} level)

**Maximum Drawdown:** {drawdown['max_dd_display']}"""
    
    if drawdown.get('peak_date_display') and drawdown.get('trough_date_display'):
        vol_section += f"\n**Drawdown Period:** {drawdown['peak_date_display']} to {drawdown['trough_date_display']}"
        vol_section += f"\n**Recovery Status:** {drawdown['recovery_status']}"
    
    return returns_table + vol_section + "\n\n---"


def _build_ownership_snapshot_table(ownership_data: Dict[str, Any]) -> str:
    """Build ownership snapshot table section."""
    concentration = ownership_data['concentration']
    top_holders = ownership_data['top_holders']
    
    # Concentration table
    conc_table = f"""## Ownership Snapshot

**Total 13F Holdings:** {ownership_data['total_value']['display']} ({ownership_data['total_holders']} institutions)
**Reporting Quarter:** {ownership_data['as_of_display']}

### Concentration Analysis

| Metric | Value | Level |
|--------|-------|-------|"""
    
    if 'cr1' in concentration:
        conc_table += f"\n| Top 1 Holder | {concentration['cr1']['display']} | {concentration['level']} |"
    if 'cr5' in concentration:
        conc_table += f"\n| Top 5 Holders | {concentration['cr5']['display']} | {concentration['level']} |"
    if 'cr10' in concentration:
        conc_table += f"\n| Top 10 Holders | {concentration['cr10']['display']} | {concentration['level']} |"
    
    # Top holders table
    holders_table = """
### Top Institutional Holders

| Rank | Institution | Value | % of Total |
|------|-------------|-------|------------|"""
    
    for holder in top_holders[:5]:  # Top 5
        holders_table += f"\n| {holder['rank']} | {holder['filer'][:40]} | {holder['value_display']} | {holder['share_of_total_display']} |"
    
    disclaimer = f"\n\n*{ownership_data['disclaimer']}*"
    
    return conc_table + holders_table + disclaimer + "\n\n---"


def _build_appendix(metrics_v2: Dict[str, Any]) -> str:
    """Build appendix section."""
    meta = metrics_v2['meta']
    data_quality = metrics_v2.get('data_quality', {})
    
    return f"""## Appendix

### Data Sources
- **Price Data:** {', '.join(meta['sources'])}
- **Analysis Engine:** v{meta['schema_version']}

### Data Quality
- **Price Coverage:** {data_quality.get('price_coverage', {}).get('display', 'Not available')}
- **Missing Days:** {data_quality.get('missing_days', 'Unknown')}
- **13F Data Age:** {data_quality.get('13f_age_days', 'Unknown')} days

### Report Metadata
- **Generated:** {meta['as_of_local']}
- **Run ID:** {meta['run_id']}
- **Timezone:** {meta['timezone']}

---

*This report is for informational purposes only. Not investment advice. Always conduct your own research before making investment decisions.*"""


def _format_period_name(period_key: str) -> str:
    """Format period key for table display."""
    period_map = {
        '1D': '1 Day',
        '1W': '1 Week',
        '1M': '1 Month',
        '3M': '3 Month', 
        '6M': '6 Month',
        '1Y': '1 Year'
    }
    return period_map.get(period_key, period_key)


if __name__ == '__main__':
    main()
