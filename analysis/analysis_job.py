"""
Orchestrated analysis job - SQLite to MetricsJSON pipeline.
Queries database, calls pure functions, persists analysis JSON.
"""

import sqlite3
import json
import pandas as pd
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# Import the metrics aggregator
from analysis.metrics_aggregator import compose_metrics


class AnalysisJobError(Exception):
    """Raised when analysis job fails."""
    pass


def analyze_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    output_path: Path,
    as_of_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Run complete analysis for a ticker and save results to JSON.
    
    Args:
        conn: SQLite database connection
        ticker: Stock ticker to analyze
        output_path: Path to save MetricsJSON file
        as_of_date: Date for analysis (defaults to today)
        start_date: Start of price data window (optional filter)
        end_date: End of price data window (optional filter)
        
    Returns:
        Dictionary with job results and summary
        
    Raises:
        AnalysisJobError: If analysis fails
    """
    if as_of_date is None:
        as_of_date = date.today()
    
    start_time = datetime.now()
    
    try:
        # Query price data
        price_df = _query_price_data(conn, ticker, start_date, end_date)
        
        if price_df.empty:
            return {
                'ticker': ticker,
                'status': 'failed',
                'error_message': f'No price data found for ticker {ticker}',
                'output_path': None,
                'metrics_calculated': 0,
                'duration_seconds': (datetime.now() - start_time).total_seconds()
            }
        
        # Query 13F holdings data
        holdings_df = _query_holdings_data(conn, ticker)
        
        # Compose all metrics
        metrics_json = compose_metrics(
            price_df=price_df,
            holdings_df=holdings_df if not holdings_df.empty else None,
            ticker=ticker,
            as_of_date=as_of_date
        )
        
        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save metrics to file
        with open(output_path, 'w') as f:
            json.dump(metrics_json, f, indent=2, default=str)
        
        # Count calculated metrics
        metrics_count = _count_calculated_metrics(metrics_json)
        
        return {
            'ticker': ticker,
            'status': 'completed',
            'output_path': str(output_path),
            'metrics_calculated': metrics_count,
            'price_data_points': len(price_df),
            'holdings_data_points': len(holdings_df) if not holdings_df.empty else 0,
            'duration_seconds': (datetime.now() - start_time).total_seconds()
        }
        
    except Exception as e:
        return {
            'ticker': ticker,
            'status': 'failed', 
            'error_message': str(e),
            'output_path': None,
            'metrics_calculated': 0,
            'duration_seconds': (datetime.now() - start_time).total_seconds()
        }


def _query_price_data(
    conn: sqlite3.Connection,
    ticker: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> pd.DataFrame:
    """
    Query price data for ticker from database.
    
    Args:
        conn: SQLite connection
        ticker: Stock ticker
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        DataFrame with price data
    """
    # Build query with optional date filters
    base_query = """
        SELECT ticker, date, open, high, low, close, adj_close, volume, source, as_of
        FROM prices 
        WHERE ticker = ?
    """
    params = [ticker]
    
    if start_date is not None:
        base_query += " AND date >= ?"
        params.append(start_date)
    
    if end_date is not None:
        base_query += " AND date <= ?"
        params.append(end_date)
    
    base_query += " ORDER BY date ASC"
    
    # Execute query
    df = pd.read_sql_query(base_query, conn, params=params)
    
    # Convert date strings to date objects if needed
    if not df.empty and 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.date
    
    return df


def _query_holdings_data(
    conn: sqlite3.Connection,
    ticker: str,
    quarter_end: Optional[date] = None
) -> pd.DataFrame:
    """
    Query 13F holdings data for ticker from database.
    
    Args:
        conn: SQLite connection
        ticker: Stock ticker
        quarter_end: Optional quarter filter (gets most recent if not specified)
        
    Returns:
        DataFrame with holdings data
    """
    if quarter_end is not None:
        # Query specific quarter
        query = """
            SELECT cik, filer, ticker, name, cusip, value_usd, shares, as_of, source
            FROM holdings_13f
            WHERE ticker = ? AND as_of = ?
            ORDER BY value_usd DESC
        """
        params = [ticker, quarter_end]
    else:
        # Get most recent quarter for ticker
        query = """
            SELECT cik, filer, ticker, name, cusip, value_usd, shares, as_of, source
            FROM holdings_13f
            WHERE ticker = ? AND as_of = (
                SELECT MAX(as_of) FROM holdings_13f WHERE ticker = ?
            )
            ORDER BY value_usd DESC
        """
        params = [ticker, ticker]
    
    df = pd.read_sql_query(query, conn, params=params)
    
    # Convert date strings if needed
    if not df.empty and 'as_of' in df.columns:
        df['as_of'] = pd.to_datetime(df['as_of']).dt.date
    
    return df


def _count_calculated_metrics(metrics_json: Dict[str, Any]) -> int:
    """
    Count how many metrics were successfully calculated (not None).
    
    Args:
        metrics_json: Complete MetricsJSON dictionary
        
    Returns:
        Number of non-null metrics
    """
    count = 0
    
    # Count price metrics
    price_metrics = metrics_json.get('price_metrics', {})
    
    # Count returns
    returns = price_metrics.get('returns', {})
    count += sum(1 for v in returns.values() if v is not None)
    
    # Count volatility
    volatility = price_metrics.get('volatility', {})
    count += sum(1 for v in volatility.values() if v is not None)
    
    # Count drawdown (count as 1 if max_drawdown_pct is not None)
    drawdown = price_metrics.get('drawdown', {})
    if drawdown.get('max_drawdown_pct') is not None:
        count += 1
    
    # Count current price (always present if we have data)
    if price_metrics.get('current_price'):
        count += 1
    
    # Count institutional metrics
    inst_metrics = metrics_json.get('institutional_metrics')
    if inst_metrics is not None:
        concentration = inst_metrics.get('concentration', {})
        count += sum(1 for v in concentration.values() if v is not None)
        
        if inst_metrics.get('total_13f_value_usd'):
            count += 1  # Count total value as one metric
    
    return count


def batch_analyze_tickers(
    conn: sqlite3.Connection,
    tickers: List[str],
    output_dir: Path,
    as_of_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Run analysis for multiple tickers.
    
    Args:
        conn: SQLite connection
        tickers: List of ticker symbols
        output_dir: Directory to save JSON files
        as_of_date: Analysis date
        
    Returns:
        Summary of batch analysis results
    """
    if as_of_date is None:
        as_of_date = date.today()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    start_time = datetime.now()
    
    for ticker in tickers:
        output_path = output_dir / f'{ticker}.json'
        
        result = analyze_ticker(
            conn=conn,
            ticker=ticker,
            output_path=output_path,
            as_of_date=as_of_date
        )
        
        results.append(result)
    
    # Calculate summary statistics
    completed = [r for r in results if r['status'] == 'completed']
    failed = [r for r in results if r['status'] == 'failed']
    
    total_metrics = sum(r.get('metrics_calculated', 0) for r in completed)
    total_duration = (datetime.now() - start_time).total_seconds()
    
    return {
        'total_tickers': len(tickers),
        'completed': len(completed),
        'failed': len(failed),
        'success_rate': len(completed) / len(tickers) if tickers else 0,
        'total_metrics_calculated': total_metrics,
        'duration_seconds': total_duration,
        'results': results
    }
