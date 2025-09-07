"""
Google Trends integration for search interest abnormality detection.
Uses pytrends library with rate limiting and caching.
"""

import os
import time
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from pytrends.request import TrendReq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)


class GoogleTrendsError(Exception):
    """Raised when Google Trends operations fail."""
    pass


def create_trends_client() -> TrendReq:
    """
    Create pytrends client with proper configuration.
    
    Returns:
        Configured TrendReq client
        
    Raises:
        GoogleTrendsError: If client creation fails
    """
    try:
        # Create client with rate limiting
        pytrends = TrendReq(
            hl='en-US',  # Language
            tz=360,      # Timezone offset
            timeout=(10, 25),  # (connect, read) timeouts
            retries=2,   # Number of retries
            backoff_factor=0.1  # Backoff between retries
        )
        return pytrends
    except Exception as e:
        raise GoogleTrendsError(f"Failed to create Google Trends client: {e}")


def fetch_search_interest(
    ticker: str,
    timeframe: str = 'today 7-d',
    geo: str = 'US',
    company_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch Google Trends search interest data for ticker.
    
    Args:
        ticker: Stock ticker symbol
        timeframe: Google Trends timeframe (e.g., 'today 7-d', 'today 1-m')
        geo: Geographic region (default: 'US')
        company_name: Optional company name for additional search terms
        
    Returns:
        Dictionary with search interest data
        
    Raises:
        GoogleTrendsError: If fetch fails
    """
    try:
        pytrends = create_trends_client()
        
        # Prepare search terms
        search_terms = [ticker]
        if company_name:
            # Add company name if provided
            search_terms.append(company_name)
        
        # Limit to 5 terms (Google Trends API limit)
        search_terms = search_terms[:5]
        
        logger.info(f"Fetching Google Trends data: {search_terms}, timeframe={timeframe}, geo={geo}")
        
        # Build payload and fetch data
        pytrends.build_payload(
            kw_list=search_terms,
            cat=0,  # All categories
            timeframe=timeframe,
            geo=geo,
            gprop=''  # Web search
        )
        
        # Get interest over time
        interest_over_time = pytrends.interest_over_time()
        
        if interest_over_time.empty:
            logger.warning(f"No Google Trends data found for {ticker}")
            return {
                'status': 'no_data',
                'ticker': ticker,
                'search_terms': search_terms,
                'timeframe': timeframe,
                'geo': geo
            }
        
        # Get related queries
        related_queries = {}
        rising_queries = {}
        
        try:
            related_data = pytrends.related_queries()
            if related_data and ticker in related_data:
                if related_data[ticker]['top'] is not None:
                    related_queries = related_data[ticker]['top'].to_dict('records')
                if related_data[ticker]['rising'] is not None:
                    rising_queries = related_data[ticker]['rising'].to_dict('records')
        except Exception as e:
            logger.warning(f"Failed to fetch related queries for {ticker}: {e}")
        
        # Process interest over time data
        processed_data = []
        for date_idx, row in interest_over_time.iterrows():
            # Get the primary ticker's search volume
            search_volume = row[ticker] if ticker in row else 0
            
            processed_data.append({
                'date': date_idx.date(),
                'search_volume': int(search_volume),
                'search_term': ticker,
                'related_queries': related_queries if date_idx == interest_over_time.index[-1] else None,
                'rising_queries': rising_queries if date_idx == interest_over_time.index[-1] else None
            })
        
        logger.info(f"Successfully fetched {len(processed_data)} data points for {ticker}")
        
        return {
            'status': 'success',
            'ticker': ticker,
            'search_terms': search_terms,
            'timeframe': timeframe,
            'geo': geo,
            'data_points': processed_data,
            'fetched_at': datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Google Trends fetch failed for {ticker}: {e}")
        raise GoogleTrendsError(f"Failed to fetch trends data for {ticker}: {e}")


def normalize_trends_data(
    trends_result: Dict[str, Any],
    ticker: str
) -> List[Dict[str, Any]]:
    """
    Normalize Google Trends data to canonical format.
    
    Args:
        trends_result: Result from fetch_search_interest
        ticker: Stock ticker symbol
        
    Returns:
        List of normalized trends records
    """
    if trends_result['status'] != 'success':
        return []
    
    normalized_records = []
    
    for data_point in trends_result['data_points']:
        record = {
            'id': str(uuid.uuid4()),
            'ticker': ticker,
            'search_term': data_point['search_term'],
            'date': data_point['date'],
            'search_volume': data_point['search_volume'],
            'geo': trends_result['geo'],
            'timeframe': trends_result['timeframe'],
            'related_queries': data_point.get('related_queries'),
            'rising_queries': data_point.get('rising_queries'),
            'fetched_at': trends_result['fetched_at']
        }
        normalized_records.append(record)
    
    return normalized_records


def calculate_search_baseline(
    historical_data: List[Dict[str, Any]],
    baseline_days: int = 365
) -> Dict[str, Any]:
    """
    Calculate statistical baseline for search volume abnormality detection.
    
    Args:
        historical_data: List of historical trends records
        baseline_days: Number of days for baseline calculation
        
    Returns:
        Dictionary with baseline statistics
    """
    if not historical_data:
        return {
            'status': 'insufficient_data',
            'data_points': 0
        }
    
    # Extract search volumes
    volumes = [record['search_volume'] for record in historical_data]
    
    if len(volumes) < 7:  # Minimum 7 days for baseline
        return {
            'status': 'insufficient_data',
            'data_points': len(volumes)
        }
    
    # Calculate statistics
    import numpy as np
    from scipy import stats
    
    volumes_array = np.array(volumes)
    
    # Basic statistics
    mean_volume = float(np.mean(volumes_array))
    std_volume = float(np.std(volumes_array, ddof=1))  # Sample standard deviation
    median_volume = float(np.median(volumes_array))
    
    # Percentiles
    percentiles = {}
    for p in [10, 25, 50, 75, 90, 95, 99]:
        percentiles[f'p{p}'] = float(np.percentile(volumes_array, p))
    
    return {
        'status': 'success',
        'data_points': len(volumes),
        'mean_value': mean_volume,
        'std_value': std_volume,
        'median_value': median_volume,
        'min_value': float(np.min(volumes_array)),
        'max_value': float(np.max(volumes_array)),
        'percentiles': percentiles,
        'baseline_period_days': baseline_days,
        'computed_at': datetime.utcnow()
    }


def detect_search_abnormality(
    current_volume: int,
    baseline: Dict[str, Any],
    z_score_cap: float = 3.0
) -> Dict[str, Any]:
    """
    Detect abnormality in current search volume vs baseline.
    
    Args:
        current_volume: Current search volume (0-100)
        baseline: Baseline statistics from calculate_search_baseline
        z_score_cap: Maximum absolute Z-score value
        
    Returns:
        Dictionary with abnormality analysis
    """
    if baseline['status'] != 'success':
        return {
            'status': 'no_baseline',
            'current_volume': current_volume,
            'baseline_available': False
        }
    
    # Calculate Z-score
    if baseline['std_value'] > 0:
        z_score = (current_volume - baseline['mean_value']) / baseline['std_value']
        z_score = max(-z_score_cap, min(z_score_cap, z_score))  # Cap extreme values
    else:
        z_score = 0.0  # No variation in baseline
    
    # Calculate percentile
    # Approximate percentile using normal distribution
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
    
    # Determine direction
    if z_score > 0.1:
        direction = 'above_normal'
    elif z_score < -0.1:
        direction = 'below_normal'
    else:
        direction = 'normal'
    
    # Calculate confidence based on baseline data quality
    confidence = min(1.0, baseline['data_points'] / 30.0)  # Full confidence at 30+ data points
    
    return {
        'status': 'success',
        'current_volume': current_volume,
        'baseline_mean': baseline['mean_value'],
        'baseline_std': baseline['std_value'],
        'z_score': float(z_score),
        'percentile': percentile,
        'classification': classification,
        'direction': direction,
        'confidence': confidence,
        'baseline_data_points': baseline['data_points']
    }


def fetch_trends_for_ticker(
    ticker: str,
    timeframes: List[str] = None,
    geo: str = None,
    company_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch Google Trends data for ticker across multiple timeframes.
    
    Args:
        ticker: Stock ticker symbol
        timeframes: List of timeframes to fetch (default: ['today 7-d', 'today 1-m', 'today 3-m'])
        geo: Geographic region (default: from env)
        company_name: Optional company name for additional searches
        
    Returns:
        Dictionary with trends data for all timeframes
    """
    if timeframes is None:
        timeframes = ['today 7-d', 'today 1-m', 'today 3-m']
    
    if geo is None:
        geo = os.getenv('GOOGLE_TRENDS_GEO', 'US')
    
    results = {}
    
    # Rate limiting between requests
    request_delay = 1.0  # 1 second between requests
    
    for timeframe in timeframes:
        try:
            # Rate limiting
            time.sleep(request_delay)
            
            # Fetch data for this timeframe
            trends_result = fetch_search_interest(
                ticker=ticker,
                timeframe=timeframe,
                geo=geo,
                company_name=company_name
            )
            
            results[timeframe] = trends_result
            
        except GoogleTrendsError as e:
            logger.error(f"Failed to fetch trends for {ticker} {timeframe}: {e}")
            results[timeframe] = {
                'status': 'error',
                'error': str(e),
                'ticker': ticker,
                'timeframe': timeframe
            }
        except Exception as e:
            logger.error(f"Unexpected error fetching trends for {ticker} {timeframe}: {e}")
            results[timeframe] = {
                'status': 'error',
                'error': str(e),
                'ticker': ticker,
                'timeframe': timeframe
            }
    
    return results


def validate_trends_record(record: Dict[str, Any]) -> bool:
    """
    Validate Google Trends record has required fields and reasonable values.
    
    Args:
        record: Trends record dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['id', 'ticker', 'search_term', 'date', 'search_volume', 'geo', 'timeframe', 'fetched_at']
    
    # Check required fields
    for field in required_fields:
        if field not in record:
            logger.warning(f"Trends record missing required field: {field}")
            return False
        if record[field] is None:
            logger.warning(f"Trends record has None value for required field: {field}")
            return False
    
    # Validate types
    if not isinstance(record['date'], date):
        logger.warning(f"Invalid date type: {type(record['date'])}")
        return False
    
    if not isinstance(record['fetched_at'], datetime):
        logger.warning(f"Invalid fetched_at type: {type(record['fetched_at'])}")
        return False
    
    # Validate search volume range (Google Trends is 0-100)
    if not (0 <= record['search_volume'] <= 100):
        logger.warning(f"Search volume out of range: {record['search_volume']}")
        return False
    
    # Validate ticker format
    ticker = record['ticker']
    if not (1 <= len(ticker) <= 5) or not ticker.isalpha():
        logger.warning(f"Invalid ticker format: {ticker}")
        return False
    
    # Validate UUID format
    try:
        uuid.UUID(record['id'])
    except ValueError:
        logger.warning(f"Invalid UUID format: {record['id']}")
        return False
    
    return True


def get_company_name_for_ticker(ticker: str) -> Optional[str]:
    """
    Get company name for ticker to improve search accuracy.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Company name if found, None otherwise
    """
    # Common ticker to company name mappings
    ticker_mappings = {
        'AAPL': 'Apple',
        'MSFT': 'Microsoft', 
        'GOOGL': 'Google',
        'AMZN': 'Amazon',
        'TSLA': 'Tesla',
        'META': 'Meta',
        'NVDA': 'Nvidia',
        'NFLX': 'Netflix',
        'CRM': 'Salesforce',
        'ORCL': 'Oracle'
    }
    
    return ticker_mappings.get(ticker.upper())


def calculate_search_volume_trend(
    current_data: List[Dict[str, Any]],
    baseline_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate search volume trend vs baseline period.
    
    Args:
        current_data: Recent search volume data
        baseline_data: Historical baseline data
        
    Returns:
        Dictionary with trend analysis
    """
    if not current_data or not baseline_data:
        return {
            'status': 'insufficient_data',
            'current_data_points': len(current_data) if current_data else 0,
            'baseline_data_points': len(baseline_data) if baseline_data else 0
        }
    
    # Calculate averages
    current_avg = sum(record['search_volume'] for record in current_data) / len(current_data)
    baseline_avg = sum(record['search_volume'] for record in baseline_data) / len(baseline_data)
    
    # Calculate trend
    if baseline_avg > 0:
        trend_pct = ((current_avg - baseline_avg) / baseline_avg) * 100
    else:
        trend_pct = 0.0
    
    # Classify trend magnitude
    abs_trend = abs(trend_pct)
    if abs_trend <= 20:
        trend_magnitude = 'minimal'
    elif abs_trend <= 50:
        trend_magnitude = 'moderate'
    elif abs_trend <= 100:
        trend_magnitude = 'significant'
    else:
        trend_magnitude = 'extreme'
    
    # Determine direction
    if trend_pct > 5:
        trend_direction = 'increasing'
    elif trend_pct < -5:
        trend_direction = 'decreasing'
    else:
        trend_direction = 'stable'
    
    return {
        'status': 'success',
        'current_avg_volume': current_avg,
        'baseline_avg_volume': baseline_avg,
        'trend_percent': trend_pct,
        'trend_magnitude': trend_magnitude,
        'trend_direction': trend_direction,
        'current_data_points': len(current_data),
        'baseline_data_points': len(baseline_data)
    }
