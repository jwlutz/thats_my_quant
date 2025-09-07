"""
Metrics aggregator - composes all financial calculations into MetricsJSON.
Pure function that combines price analysis, volatility, drawdown, and 13F concentration.
"""

import pandas as pd
from datetime import date, datetime
from typing import Dict, Any, Optional, List

# Import all calculation modules
from analysis.calculations.returns import calculate_period_returns
from analysis.calculations.volatility import calculate_volatility_metrics
from analysis.calculations.drawdown import calculate_drawdown_metrics
from analysis.calculations.concentration import analyze_13f_holdings


class MetricsAggregatorError(Exception):
    """Raised when metrics aggregation fails."""
    pass


def compose_metrics(
    price_df: pd.DataFrame,
    holdings_df: Optional[pd.DataFrame],
    ticker: str,
    as_of_date: date
) -> Dict[str, Any]:
    """
    Compose all financial metrics into standardized JSON format.
    
    Args:
        price_df: DataFrame with price data for ticker
        holdings_df: DataFrame with 13F holdings for ticker (optional)
        ticker: Stock ticker symbol
        as_of_date: Date for which metrics are calculated
        
    Returns:
        Complete MetricsJSON dictionary
        
    Raises:
        MetricsAggregatorError: If composition fails
    """
    if price_df.empty:
        raise MetricsAggregatorError("Empty price data provided")
    
    if ticker not in price_df['ticker'].values:
        raise MetricsAggregatorError(f"Ticker {ticker} not found in price data")
    
    # Filter data for the specific ticker
    ticker_prices = price_df[price_df['ticker'] == ticker].copy()
    ticker_prices = ticker_prices.sort_values('date').reset_index(drop=True)
    
    if ticker_prices.empty:
        raise MetricsAggregatorError(f"No price data for ticker {ticker}")
    
    # Extract price and date series
    prices = ticker_prices['close'].tolist()
    dates = ticker_prices['date'].tolist()
    
    # Convert date strings to date objects if needed
    if isinstance(dates[0], str):
        dates = [date.fromisoformat(d) if isinstance(d, str) else d for d in dates]
    
    # Calculate data period info
    data_period = {
        'start_date': dates[0].isoformat(),
        'end_date': dates[-1].isoformat(), 
        'trading_days': len(dates)
    }
    
    # Calculate price metrics
    price_metrics = _calculate_price_metrics(prices, dates)
    
    # Calculate institutional metrics (if 13F data available)
    institutional_metrics = None
    if holdings_df is not None and not holdings_df.empty:
        ticker_holdings = holdings_df[holdings_df['ticker'] == ticker]
        if not ticker_holdings.empty:
            institutional_metrics = _calculate_institutional_metrics(ticker_holdings.to_dict('records'))
    
    # Calculate data quality metrics
    data_quality = _calculate_data_quality_metrics(ticker_prices, holdings_df, ticker)
    
    # Generate metadata
    metadata = {
        'calculated_at': datetime.now().isoformat(),
        'calculation_version': '1.0.0',
        'data_sources': _determine_data_sources(ticker_prices, holdings_df)
    }
    
    return {
        'ticker': ticker,
        'as_of_date': as_of_date.isoformat(),
        'data_period': data_period,
        'price_metrics': price_metrics,
        'institutional_metrics': institutional_metrics,
        'data_quality': data_quality,
        'metadata': metadata
    }


def _calculate_price_metrics(prices: List[float], dates: List[date]) -> Dict[str, Any]:
    """Calculate all price-based metrics."""
    # Returns calculation
    returns = calculate_period_returns(prices, dates, windows=[1, 5, 21, 63, 126, 252])
    
    # Map to standard names
    returns_formatted = {
        '1D': returns.get('1D'),
        '1W': returns.get('5D'), 
        '1M': returns.get('21D'),
        '3M': returns.get('63D'),
        '6M': returns.get('126D'),
        '1Y': returns.get('252D')
    }
    
    # Volatility calculation
    volatility = calculate_volatility_metrics(prices, windows=[21, 63, 252])
    
    # Drawdown calculation
    drawdown = calculate_drawdown_metrics(prices, dates, min_periods=10)
    
    # Current price info
    current_price = {
        'close': prices[-1],
        'date': dates[-1].isoformat()
    }
    
    return {
        'returns': returns_formatted,
        'volatility': volatility,
        'drawdown': {
            'max_drawdown_pct': drawdown['max_drawdown_pct'],
            'peak_date': drawdown['peak_date'].isoformat() if drawdown['peak_date'] else None,
            'trough_date': drawdown['trough_date'].isoformat() if drawdown['trough_date'] else None,
            'recovery_date': drawdown['recovery_date'].isoformat() if drawdown['recovery_date'] else None,
            'drawdown_days': drawdown['drawdown_days'],
            'recovery_days': drawdown['recovery_days']
        },
        'current_price': current_price
    }


def _calculate_institutional_metrics(holdings_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate 13F-based institutional metrics."""
    if not holdings_list:
        return None
    
    # Get concentration metrics
    concentration_metrics = analyze_13f_holdings(holdings_list)
    
    # Build top holders list
    top_holders = []
    sorted_holdings = sorted(holdings_list, key=lambda x: x.get('value_usd', 0), reverse=True)
    
    total_value = sum(h.get('value_usd', 0) for h in holdings_list)
    
    for i, holding in enumerate(sorted_holdings[:10]):  # Top 10
        top_holders.append({
            'rank': i + 1,
            'filer': holding.get('filer', 'Unknown'),
            'value_usd': holding.get('value_usd', 0.0),
            'shares': holding.get('shares', 0.0),
            'pct_of_13f_total': (holding.get('value_usd', 0.0) / total_value) if total_value > 0 else 0.0
        })
    
    # Get quarter info from first holding
    quarter_end = None
    filing_lag_days = None
    if holdings_list:
        first_holding = holdings_list[0]
        if 'as_of' in first_holding:
            quarter_end = first_holding['as_of']
            if isinstance(quarter_end, str):
                quarter_end_date = date.fromisoformat(quarter_end)
            else:
                quarter_end_date = quarter_end
            
            # Calculate filing lag (rough estimate)
            filing_lag_days = (date.today() - quarter_end_date).days
    
    return {
        'total_13f_value_usd': concentration_metrics.get('total_value', 0.0),
        'total_13f_holders': concentration_metrics.get('num_holders', 0),
        'concentration': {
            'cr1': concentration_metrics.get('cr1'),
            'cr5': concentration_metrics.get('cr5'),
            'cr10': concentration_metrics.get('cr10'),
            'hhi': concentration_metrics.get('hhi')
        },
        'top_holders': top_holders,
        'quarter_end': quarter_end.isoformat() if isinstance(quarter_end, date) else quarter_end,
        'filing_lag_days': filing_lag_days
    }


def _calculate_data_quality_metrics(
    price_df: pd.DataFrame, 
    holdings_df: Optional[pd.DataFrame],
    ticker: str
) -> Dict[str, Any]:
    """Calculate data quality and coverage metrics."""
    # Price data quality
    if not price_df.empty:
        dates = pd.to_datetime(price_df['date'])
        date_range = (dates.max() - dates.min()).days
        actual_days = len(dates)
        
        # Estimate expected trading days (rough: 5/7 of calendar days)
        expected_trading_days = max(1, int(date_range * 5 / 7))
        coverage_pct = min(100.0, (actual_days / expected_trading_days) * 100)
        missing_days = max(0, expected_trading_days - actual_days)
    else:
        coverage_pct = 0.0
        missing_days = 0
    
    # 13F data quality
    latest_13f_quarter = None
    age_days = None
    
    if holdings_df is not None and not holdings_df.empty:
        ticker_holdings = holdings_df[holdings_df['ticker'] == ticker]
        if not ticker_holdings.empty:
            # Get most recent quarter
            as_of_dates = pd.to_datetime(ticker_holdings['as_of'])
            latest_quarter = as_of_dates.max()
            latest_13f_quarter = latest_quarter.strftime('%Y-%m-%d')
            age_days = (datetime.now().date() - latest_quarter.date()).days
    
    return {
        'price_coverage_pct': coverage_pct,
        'missing_price_days': missing_days,
        'latest_13f_quarter': latest_13f_quarter,
        '13f_data_age_days': age_days
    }


def _determine_data_sources(
    price_df: pd.DataFrame, 
    holdings_df: Optional[pd.DataFrame]
) -> List[str]:
    """Determine which data sources were used."""
    sources = []
    
    if not price_df.empty and 'source' in price_df.columns:
        price_sources = price_df['source'].unique()
        sources.extend(price_sources)
    
    if holdings_df is not None and not holdings_df.empty and 'source' in holdings_df.columns:
        holdings_sources = holdings_df['source'].unique() 
        sources.extend(holdings_sources)
    
    return list(set(sources))  # Remove duplicates
