"""
SEC Form 4 insider trading integration for sentiment analysis.
Uses existing SEC EDGAR infrastructure with transaction pattern analysis.
"""

import os
import re
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)


class InsiderTradingError(Exception):
    """Raised when insider trading operations fail."""
    pass


def fetch_form4_filings(
    ticker: str,
    lookback_days: int = None,
    min_value_usd: float = None
) -> List[Dict[str, Any]]:
    """
    Fetch SEC Form 4 insider trading filings for ticker.
    
    Args:
        ticker: Stock ticker symbol
        lookback_days: Days to look back (default: from env)
        min_value_usd: Minimum transaction value (default: from env)
        
    Returns:
        List of insider trading records
        
    Raises:
        InsiderTradingError: If fetch fails
    """
    if lookback_days is None:
        lookback_days = int(os.getenv('INSIDER_TRADING_LOOKBACK_DAYS', '90'))
    
    if min_value_usd is None:
        min_value_usd = float(os.getenv('INSIDER_TRADING_MIN_VALUE_USD', '10000'))
    
    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)
    
    logger.info(f"Fetching Form 4 filings for {ticker}: {start_date} to {end_date}")
    
    try:
        # Use SEC EDGAR search for Form 4 filings
        sec_user_agent = os.getenv('SEC_USER_AGENT')
        if not sec_user_agent:
            raise InsiderTradingError("SEC_USER_AGENT environment variable required")
        
        headers = {
            'User-Agent': sec_user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'www.sec.gov'
        }
        
        # Search for Form 4 filings
        # This is a simplified implementation - in production would use more robust SEC API
        filings = _search_form4_filings(ticker, start_date, end_date, headers)
        
        # Process and filter filings
        processed_filings = []
        for filing in filings:
            try:
                processed_filing = _process_form4_filing(filing, ticker, min_value_usd)
                if processed_filing:
                    processed_filings.append(processed_filing)
            except Exception as e:
                logger.warning(f"Failed to process Form 4 filing {filing.get('accession_number', 'unknown')}: {e}")
                continue
        
        logger.info(f"Successfully processed {len(processed_filings)} Form 4 filings for {ticker}")
        return processed_filings
        
    except Exception as e:
        logger.error(f"Failed to fetch Form 4 filings for {ticker}: {e}")
        raise InsiderTradingError(f"Form 4 fetch failed for {ticker}: {e}")


def _search_form4_filings(
    ticker: str,
    start_date: date,
    end_date: date,
    headers: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Search for Form 4 filings using SEC EDGAR.
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date for search
        end_date: End date for search
        headers: HTTP headers for SEC requests
        
    Returns:
        List of filing metadata
    """
    # This is a simplified mock implementation
    # In production, would use SEC's company search API and filing search
    
    # Mock filings for testing - replace with real SEC API calls
    mock_filings = [
        {
            'accession_number': '0001234567-25-000001',
            'filing_date': date(2025, 1, 10),
            'form_type': '4',
            'ticker': ticker,
            'company_name': f'{ticker} Inc.',
            'document_url': f'https://www.sec.gov/Archives/edgar/data/1234567/000123456725000001/form4.xml'
        },
        {
            'accession_number': '0001234567-25-000002',
            'filing_date': date(2025, 1, 8),
            'form_type': '4',
            'ticker': ticker,
            'company_name': f'{ticker} Inc.',
            'document_url': f'https://www.sec.gov/Archives/edgar/data/1234567/000123456725000002/form4.xml'
        }
    ]
    
    # Filter by date range
    filtered_filings = []
    for filing in mock_filings:
        if start_date <= filing['filing_date'] <= end_date:
            filtered_filings.append(filing)
    
    return filtered_filings


def _process_form4_filing(
    filing: Dict[str, Any],
    ticker: str,
    min_value_usd: float
) -> Optional[Dict[str, Any]]:
    """
    Process individual Form 4 filing into canonical format.
    
    Args:
        filing: Filing metadata
        ticker: Stock ticker symbol  
        min_value_usd: Minimum transaction value threshold
        
    Returns:
        Processed insider trading record or None if invalid
    """
    # This is a simplified mock implementation
    # In production, would parse actual Form 4 XML documents
    
    # Mock transaction data - replace with real XML parsing
    mock_transaction = {
        'form_id': filing['accession_number'],
        'ticker': ticker,
        'company_name': filing['company_name'],
        'insider_name': 'John Doe',  # Would extract from XML
        'insider_title': 'Chief Executive Officer',  # Would extract from XML
        'transaction_date': filing['filing_date'] - timedelta(days=2),  # Usually filed within 2 days
        'transaction_type': 'sell',  # Would extract from XML
        'shares': 10000.0,
        'price_per_share': 150.0,
        'total_value': 1500000.0,  # shares * price
        'shares_owned_after': 500000.0,  # Would extract from XML
        'filing_date': filing['filing_date'],
        'source': 'sec_edgar',
        'fetched_at': datetime.utcnow()
    }
    
    # Filter by minimum value
    if mock_transaction['total_value'] and mock_transaction['total_value'] < min_value_usd:
        logger.debug(f"Filtering out small transaction: ${mock_transaction['total_value']:,.0f}")
        return None
    
    return mock_transaction


def calculate_insider_sentiment(
    transactions: List[Dict[str, Any]],
    window_days: int = 7
) -> Dict[str, Any]:
    """
    Calculate insider sentiment score from transaction patterns.
    
    Args:
        transactions: List of insider trading transactions
        window_days: Analysis window in days
        
    Returns:
        Dictionary with insider sentiment analysis
    """
    if not transactions:
        return {
            'status': 'no_data',
            'transaction_count': 0
        }
    
    # Filter transactions to window
    cutoff_date = date.today() - timedelta(days=window_days)
    windowed_transactions = [
        tx for tx in transactions 
        if tx['transaction_date'] >= cutoff_date
    ]
    
    if not windowed_transactions:
        return {
            'status': 'no_recent_data',
            'transaction_count': 0,
            'window_days': window_days
        }
    
    # Analyze transaction patterns
    buy_value = 0.0
    sell_value = 0.0
    buy_count = 0
    sell_count = 0
    
    for tx in windowed_transactions:
        if tx['transaction_type'] == 'buy':
            buy_value += tx['total_value'] or 0.0
            buy_count += 1
        elif tx['transaction_type'] == 'sell':
            sell_value += tx['total_value'] or 0.0
            sell_count += 1
    
    # Calculate net sentiment
    total_value = buy_value + sell_value
    net_value = buy_value - sell_value
    
    if total_value > 0:
        # Sentiment score: -1.0 (all selling) to +1.0 (all buying)
        sentiment_score = net_value / total_value
    else:
        sentiment_score = 0.0
    
    # Calculate transaction intensity (transactions per day)
    intensity = len(windowed_transactions) / window_days
    
    # Determine sentiment classification
    abs_sentiment = abs(sentiment_score)
    if abs_sentiment <= 0.2:
        sentiment_class = 'neutral'
    elif abs_sentiment <= 0.6:
        sentiment_class = 'moderate'
    else:
        sentiment_class = 'strong'
    
    # Determine direction
    if sentiment_score > 0.1:
        direction = 'bullish'  # Net buying
    elif sentiment_score < -0.1:
        direction = 'bearish'  # Net selling
    else:
        direction = 'neutral'
    
    return {
        'status': 'success',
        'window_days': window_days,
        'transaction_count': len(windowed_transactions),
        'buy_count': buy_count,
        'sell_count': sell_count,
        'buy_value': buy_value,
        'sell_value': sell_value,
        'net_value': net_value,
        'total_value': total_value,
        'sentiment_score': sentiment_score,
        'sentiment_class': sentiment_class,
        'direction': direction,
        'transaction_intensity': intensity,
        'confidence': min(1.0, len(windowed_transactions) / 5.0)  # Full confidence at 5+ transactions
    }


def detect_insider_patterns(
    transactions: List[Dict[str, Any]],
    lookback_days: int = 90
) -> Dict[str, Any]:
    """
    Detect unusual patterns in insider trading activity.
    
    Args:
        transactions: List of insider trading transactions
        lookback_days: Days to analyze for patterns
        
    Returns:
        Dictionary with pattern analysis
    """
    if not transactions:
        return {
            'status': 'no_data',
            'patterns': []
        }
    
    # Filter to lookback period
    cutoff_date = date.today() - timedelta(days=lookback_days)
    recent_transactions = [
        tx for tx in transactions
        if tx['transaction_date'] >= cutoff_date
    ]
    
    patterns = []
    
    # Pattern 1: Clustering (multiple transactions in short period)
    clustering_threshold = 3  # 3+ transactions in 5 days
    clustering_window = 5
    
    for i, tx in enumerate(recent_transactions):
        cluster_transactions = [tx]
        tx_date = tx['transaction_date']
        
        # Find transactions within clustering window
        for other_tx in recent_transactions[i+1:]:
            if abs((other_tx['transaction_date'] - tx_date).days) <= clustering_window:
                cluster_transactions.append(other_tx)
        
        if len(cluster_transactions) >= clustering_threshold:
            total_value = sum(t['total_value'] or 0 for t in cluster_transactions)
            patterns.append({
                'type': 'transaction_clustering',
                'description': f'{len(cluster_transactions)} transactions in {clustering_window} days',
                'transaction_count': len(cluster_transactions),
                'total_value': total_value,
                'start_date': min(t['transaction_date'] for t in cluster_transactions),
                'end_date': max(t['transaction_date'] for t in cluster_transactions),
                'abnormality_score': min(3.0, len(cluster_transactions) / 2.0)  # Rough abnormality
            })
    
    # Pattern 2: Large single transactions (>90th percentile of historical values)
    if len(recent_transactions) >= 5:
        values = [tx['total_value'] or 0 for tx in recent_transactions if tx['total_value']]
        if values:
            import numpy as np
            p90_threshold = np.percentile(values, 90)
            
            large_transactions = [tx for tx in recent_transactions if (tx['total_value'] or 0) > p90_threshold]
            
            for tx in large_transactions:
                patterns.append({
                    'type': 'large_transaction',
                    'description': f'${tx["total_value"]:,.0f} transaction by {tx["insider_name"]}',
                    'transaction_value': tx['total_value'],
                    'transaction_date': tx['transaction_date'],
                    'insider_name': tx['insider_name'],
                    'abnormality_score': min(3.0, (tx['total_value'] or 0) / p90_threshold)
                })
    
    # Pattern 3: Directional consensus (all insiders buying or selling)
    if len(recent_transactions) >= 3:
        buy_transactions = [tx for tx in recent_transactions if tx['transaction_type'] == 'buy']
        sell_transactions = [tx for tx in recent_transactions if tx['transaction_type'] == 'sell']
        
        total_transactions = len(buy_transactions) + len(sell_transactions)
        
        if total_transactions >= 3:
            buy_ratio = len(buy_transactions) / total_transactions
            
            if buy_ratio >= 0.8:  # 80%+ buying
                patterns.append({
                    'type': 'directional_consensus',
                    'description': f'{len(buy_transactions)}/{total_transactions} transactions are buys',
                    'direction': 'bullish',
                    'consensus_ratio': buy_ratio,
                    'abnormality_score': (buy_ratio - 0.5) * 4.0  # Scale 0.5-1.0 to 0-2.0
                })
            elif buy_ratio <= 0.2:  # 80%+ selling
                patterns.append({
                    'type': 'directional_consensus',
                    'description': f'{len(sell_transactions)}/{total_transactions} transactions are sells',
                    'direction': 'bearish',
                    'consensus_ratio': 1.0 - buy_ratio,
                    'abnormality_score': (0.5 - buy_ratio) * 4.0  # Scale 0.0-0.5 to 0-2.0
                })
    
    return {
        'status': 'success',
        'lookback_days': lookback_days,
        'total_transactions': len(recent_transactions),
        'patterns': patterns,
        'pattern_count': len(patterns)
    }


def calculate_insider_baseline(
    historical_transactions: List[Dict[str, Any]],
    baseline_days: int = 365
) -> Dict[str, Any]:
    """
    Calculate statistical baseline for insider trading abnormality detection.
    
    Args:
        historical_transactions: List of historical transactions
        baseline_days: Number of days for baseline calculation
        
    Returns:
        Dictionary with baseline statistics
    """
    if not historical_transactions:
        return {
            'status': 'insufficient_data',
            'data_points': 0
        }
    
    # Calculate daily transaction metrics
    cutoff_date = date.today() - timedelta(days=baseline_days)
    recent_transactions = [
        tx for tx in historical_transactions
        if tx['transaction_date'] >= cutoff_date
    ]
    
    if len(recent_transactions) < 5:  # Minimum transactions for baseline
        return {
            'status': 'insufficient_data',
            'data_points': len(recent_transactions)
        }
    
    # Group transactions by day
    daily_metrics = {}
    for tx in recent_transactions:
        tx_date = tx['transaction_date']
        if tx_date not in daily_metrics:
            daily_metrics[tx_date] = {
                'transaction_count': 0,
                'total_value': 0.0,
                'net_shares': 0.0,
                'buy_count': 0,
                'sell_count': 0
            }
        
        metrics = daily_metrics[tx_date]
        metrics['transaction_count'] += 1
        metrics['total_value'] += tx['total_value'] or 0.0
        
        if tx['transaction_type'] == 'buy':
            metrics['net_shares'] += tx['shares']
            metrics['buy_count'] += 1
        elif tx['transaction_type'] == 'sell':
            metrics['net_shares'] -= tx['shares']
            metrics['sell_count'] += 1
    
    # Calculate baseline statistics
    import numpy as np
    
    daily_counts = [metrics['transaction_count'] for metrics in daily_metrics.values()]
    daily_values = [metrics['total_value'] for metrics in daily_metrics.values()]
    daily_net_shares = [metrics['net_shares'] for metrics in daily_metrics.values()]
    
    # Transaction count baseline
    count_mean = float(np.mean(daily_counts))
    count_std = float(np.std(daily_counts, ddof=1))
    
    # Transaction value baseline
    value_mean = float(np.mean(daily_values))
    value_std = float(np.std(daily_values, ddof=1))
    
    # Net shares baseline
    shares_mean = float(np.mean(daily_net_shares))
    shares_std = float(np.std(daily_net_shares, ddof=1))
    
    # Percentiles for each metric
    count_percentiles = {}
    value_percentiles = {}
    shares_percentiles = {}
    
    for p in [10, 25, 50, 75, 90, 95, 99]:
        count_percentiles[f'p{p}'] = float(np.percentile(daily_counts, p))
        value_percentiles[f'p{p}'] = float(np.percentile(daily_values, p))
        shares_percentiles[f'p{p}'] = float(np.percentile(daily_net_shares, p))
    
    return {
        'status': 'success',
        'data_points': len(recent_transactions),
        'daily_data_points': len(daily_metrics),
        'baseline_period_days': baseline_days,
        
        'transaction_count': {
            'mean': count_mean,
            'std': count_std,
            'percentiles': count_percentiles
        },
        
        'transaction_value': {
            'mean': value_mean,
            'std': value_std,
            'percentiles': value_percentiles
        },
        
        'net_shares': {
            'mean': shares_mean,
            'std': shares_std,
            'percentiles': shares_percentiles
        },
        
        'computed_at': datetime.utcnow()
    }


def detect_insider_abnormality(
    current_metrics: Dict[str, Any],
    baseline: Dict[str, Any],
    z_score_cap: float = 3.0
) -> Dict[str, Any]:
    """
    Detect abnormality in current insider trading vs baseline.
    
    Args:
        current_metrics: Current period insider metrics
        baseline: Baseline statistics from calculate_insider_baseline
        z_score_cap: Maximum absolute Z-score value
        
    Returns:
        Dictionary with abnormality analysis
    """
    if baseline['status'] != 'success':
        return {
            'status': 'no_baseline',
            'baseline_available': False
        }
    
    abnormality_results = {}
    
    # Analyze each metric
    metrics = ['transaction_count', 'transaction_value', 'net_shares']
    
    for metric in metrics:
        current_value = current_metrics.get(metric, 0.0)
        baseline_stats = baseline[metric]
        
        # Calculate Z-score
        if baseline_stats['std'] > 0:
            z_score = (current_value - baseline_stats['mean']) / baseline_stats['std']
            z_score = max(-z_score_cap, min(z_score_cap, z_score))
        else:
            z_score = 0.0
        
        # Calculate percentile (approximate using normal distribution)
        from scipy import stats
        percentile = float(stats.norm.cdf(z_score))
        
        # Classify abnormality
        abs_z = abs(z_score)
        if abs_z <= 1.0:
            classification = 'normal'
        elif abs_z <= 2.0:
            classification = 'unusual'
        else:
            classification = 'extreme'
        
        abnormality_results[metric] = {
            'current_value': current_value,
            'baseline_mean': baseline_stats['mean'],
            'baseline_std': baseline_stats['std'],
            'z_score': float(z_score),
            'percentile': percentile,
            'classification': classification
        }
    
    # Calculate composite abnormality (average of absolute Z-scores)
    z_scores = [abs(abnormality_results[m]['z_score']) for m in metrics]
    composite_z = sum(z_scores) / len(z_scores)
    
    # Overall classification based on composite
    if composite_z <= 1.0:
        overall_classification = 'normal'
    elif composite_z <= 2.0:
        overall_classification = 'unusual'
    else:
        overall_classification = 'extreme'
    
    return {
        'status': 'success',
        'metrics': abnormality_results,
        'composite_abnormality': float(composite_z),
        'overall_classification': overall_classification,
        'confidence': min(1.0, baseline['data_points'] / 20.0),  # Full confidence at 20+ transactions
        'baseline_data_points': baseline['data_points']
    }


def validate_insider_record(record: Dict[str, Any]) -> bool:
    """
    Validate insider trading record has required fields and reasonable values.
    
    Args:
        record: Insider trading record dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        'form_id', 'ticker', 'company_name', 'insider_name', 
        'transaction_date', 'transaction_type', 'shares', 'filing_date', 'fetched_at'
    ]
    
    # Check required fields
    for field in required_fields:
        if field not in record:
            logger.warning(f"Insider record missing required field: {field}")
            return False
        if record[field] is None:
            logger.warning(f"Insider record has None value for required field: {field}")
            return False
    
    # Validate transaction type
    valid_types = ['buy', 'sell', 'grant', 'exercise', 'option']
    if record['transaction_type'] not in valid_types:
        logger.warning(f"Invalid transaction type: {record['transaction_type']}")
        return False
    
    # Validate shares > 0
    if record['shares'] <= 0:
        logger.warning(f"Invalid share count: {record['shares']}")
        return False
    
    # Validate dates
    if not isinstance(record['transaction_date'], date):
        logger.warning(f"Invalid transaction_date type: {type(record['transaction_date'])}")
        return False
    
    if not isinstance(record['filing_date'], date):
        logger.warning(f"Invalid filing_date type: {type(record['filing_date'])}")
        return False
    
    # Check filing date is after transaction date (SEC requirement)
    if record['filing_date'] < record['transaction_date']:
        logger.warning(f"Filing date before transaction date: {record['filing_date']} < {record['transaction_date']}")
        return False
    
    # Check reasonable filing delay (SEC requires filing within 2 business days)
    filing_delay = (record['filing_date'] - record['transaction_date']).days
    if filing_delay > 10:  # Allow some flexibility for weekends/holidays
        logger.warning(f"Excessive filing delay: {filing_delay} days")
        return False
    
    return True
