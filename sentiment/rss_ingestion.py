"""
RSS news ingestion pipeline with conditional gets and deduplication.
Follows RSS best practices with ETag/Last-Modified caching.
"""

import os
import hashlib
import logging
import time
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import feedparser
import requests
from dateutil import parser as date_parser
from rapidfuzz import fuzz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)


class RSSIngestionError(Exception):
    """Raised when RSS ingestion fails."""
    pass


def load_rss_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load RSS sources configuration from YAML file.
    
    Args:
        config_path: Path to RSS sources config file
        
    Returns:
        Dictionary with RSS configuration
        
    Raises:
        RSSIngestionError: If config file cannot be loaded
    """
    if config_path is None:
        config_path = os.getenv('NEWS_RSS_SOURCES_BASE', './config/rss_sources.yml')
    
    config_file = Path(config_path)
    if not config_file.exists():
        raise RSSIngestionError(f"RSS config file not found: {config_path}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Validate config structure
        if 'sources' not in config:
            raise RSSIngestionError("RSS config missing 'sources' section")
        
        return config
    except Exception as e:
        raise RSSIngestionError(f"Failed to load RSS config: {e}")


def normalize_url(url: str) -> str:
    """
    Normalize URL for consistent hashing and deduplication.
    
    Args:
        url: Raw URL
        
    Returns:
        Normalized URL
    """
    # Remove common tracking parameters
    tracking_params = [
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
        'ref', 'referrer', 'source', 'campaign', 'fbclid', 'gclid'
    ]
    
    # Basic normalization
    normalized = url.strip().lower()
    
    # Remove fragment
    if '#' in normalized:
        normalized = normalized.split('#')[0]
    
    # Remove tracking parameters (simplified approach)
    if '?' in normalized:
        base_url, params = normalized.split('?', 1)
        param_pairs = params.split('&')
        filtered_params = []
        
        for param in param_pairs:
            if '=' in param:
                key, _ = param.split('=', 1)
                if key not in tracking_params:
                    filtered_params.append(param)
        
        if filtered_params:
            normalized = base_url + '?' + '&'.join(filtered_params)
        else:
            normalized = base_url
    
    return normalized


def create_url_hash(url: str) -> str:
    """
    Create deterministic hash for URL.
    
    Args:
        url: URL to hash
        
    Returns:
        SHA-256 hash of normalized URL
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def extract_ticker_hints(title: str, url: str) -> List[str]:
    """
    Extract potential ticker symbols from title and URL.
    
    Args:
        title: Article title
        url: Article URL
        
    Returns:
        List of potential ticker symbols found
    """
    import re
    
    ticker_hints = []
    
    # Pattern for ticker symbols (basic)
    ticker_pattern = r'\b[A-Z]{1,5}\b'
    
    # Extract from title
    title_tickers = re.findall(ticker_pattern, title.upper())
    ticker_hints.extend(title_tickers)
    
    # Extract from URL path
    url_tickers = re.findall(ticker_pattern, url.upper())
    ticker_hints.extend(url_tickers)
    
    # Remove common false positives
    false_positives = {
        'RSS', 'XML', 'HTTP', 'HTTPS', 'WWW', 'COM', 'NET', 'ORG',
        'NEWS', 'API', 'JSON', 'HTML', 'PDF', 'JPG', 'PNG', 'GIF',
        'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'UTC', 'GMT', 'EST',
        'PST', 'CST', 'MST', 'EDT', 'PDT', 'CDT', 'MDT'
    }
    
    # Filter and deduplicate
    filtered_hints = []
    for hint in ticker_hints:
        if hint not in false_positives and len(hint) >= 2:
            if hint not in filtered_hints:
                filtered_hints.append(hint)
    
    return filtered_hints[:5]  # Limit to 5 hints per article


def fetch_rss_feed(
    source_config: Dict[str, Any],
    cache_info: Optional[Dict[str, str]] = None
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Fetch RSS feed with conditional gets (ETag/Last-Modified).
    
    Args:
        source_config: RSS source configuration
        cache_info: Previous cache info with 'etag' and 'modified' keys
        
    Returns:
        Tuple of (feed_data, new_cache_info)
        
    Raises:
        RSSIngestionError: If fetch fails
    """
    url = source_config['url']
    user_agent = source_config.get('user_agent', 'ai-research-workbench/1.0')
    timeout = int(os.getenv('REQUESTS_TIMEOUT_S', '30'))
    
    # Prepare headers
    headers = {
        'User-Agent': user_agent,
        'Accept': 'application/rss+xml, application/xml, text/xml'
    }
    
    # Add conditional get headers if available
    if cache_info:
        if cache_info.get('etag'):
            headers['If-None-Match'] = cache_info['etag']
        if cache_info.get('modified'):
            headers['If-Modified-Since'] = cache_info['modified']
    
    try:
        # Use feedparser with conditional gets
        if cache_info:
            feed_data = feedparser.parse(
                url,
                etag=cache_info.get('etag'),
                modified=cache_info.get('modified'),
                request_headers=headers
            )
        else:
            feed_data = feedparser.parse(url, request_headers=headers)
        
        # Check for 304 Not Modified
        if hasattr(feed_data, 'status') and feed_data.status == 304:
            logger.info(f"RSS feed not modified: {source_config['name']}")
            return {'status': 'not_modified', 'entries': []}, cache_info or {}
        
        # Extract new cache info
        new_cache_info = {}
        if hasattr(feed_data, 'etag'):
            new_cache_info['etag'] = feed_data.etag
        if hasattr(feed_data, 'modified'):
            new_cache_info['modified'] = feed_data.modified
        
        # Process entries
        processed_entries = []
        for entry in feed_data.entries:
            processed_entry = process_rss_entry(entry, source_config)
            if processed_entry:
                processed_entries.append(processed_entry)
        
        logger.info(f"Fetched {len(processed_entries)} entries from {source_config['name']}")
        
        return {
            'status': 'success',
            'entries': processed_entries,
            'feed_title': getattr(feed_data.feed, 'title', source_config['name']),
            'feed_updated': getattr(feed_data.feed, 'updated', None)
        }, new_cache_info
        
    except Exception as e:
        logger.error(f"Failed to fetch RSS feed {source_config['name']}: {e}")
        raise RSSIngestionError(f"RSS fetch failed for {source_config['name']}: {e}")


def process_rss_entry(entry: Any, source_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process individual RSS entry into canonical format.
    
    Args:
        entry: feedparser entry object
        source_config: RSS source configuration
        
    Returns:
        Processed news item or None if invalid
    """
    try:
        # Extract basic fields
        title = getattr(entry, 'title', '').strip()
        if not title:
            return None
        
        # Get URL
        link = getattr(entry, 'link', '').strip()
        if not link:
            return None
        
        # Parse publication date
        published_at = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'published'):
            try:
                published_at = date_parser.parse(entry.published)
            except Exception:
                pass
        
        if not published_at:
            # Use current time as fallback
            published_at = datetime.utcnow()
        
        # Extract content
        body = None
        if hasattr(entry, 'summary'):
            body = entry.summary.strip()
        elif hasattr(entry, 'description'):
            body = entry.description.strip()
        
        # Extract author
        author = None
        if hasattr(entry, 'author'):
            author = entry.author.strip()
        
        # Create canonical URL and hash
        canonical_url = normalize_url(link)
        url_hash = create_url_hash(canonical_url)
        
        # Extract ticker hints
        ticker_hints = extract_ticker_hints(title, link)
        ticker_hint = ticker_hints[0] if ticker_hints else None
        
        return {
            'url_hash': url_hash,
            'canonical_url': canonical_url,
            'title': title,
            'body': body,
            'published_at': published_at,
            'source': source_config['name'],
            'author': author,
            'fetched_at': datetime.utcnow(),
            'ticker_hint': ticker_hint
        }
        
    except Exception as e:
        logger.warning(f"Failed to process RSS entry: {e}")
        return None


def detect_near_duplicates(
    news_items: List[Dict[str, Any]], 
    threshold: float = 0.9,
    time_window_hours: int = 24
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Detect near-duplicate news items using title similarity and time proximity.
    
    Args:
        news_items: List of news item dictionaries
        threshold: Similarity threshold (0.0-1.0)
        time_window_hours: Time window for duplicate detection
        
    Returns:
        Dictionary mapping dedupe_group_id to list of duplicate items
    """
    if not news_items:
        return {}
    
    # Sort by publication time
    sorted_items = sorted(news_items, key=lambda x: x['published_at'])
    
    duplicate_groups = {}
    group_counter = 0
    time_window = timedelta(hours=time_window_hours)
    
    for i, item in enumerate(sorted_items):
        if item.get('dedupe_group'):
            continue  # Already assigned to a group
        
        # Look for duplicates in time window
        duplicates_found = []
        item_time = item['published_at']
        
        for j, other_item in enumerate(sorted_items[i+1:], i+1):
            if other_item.get('dedupe_group'):
                continue  # Already assigned
            
            # Check time proximity
            time_diff = abs(other_item['published_at'] - item_time)
            if time_diff > time_window:
                break  # Items are sorted, so no more matches
            
            # Check title similarity
            similarity = fuzz.ratio(item['title'], other_item['title']) / 100.0
            if similarity >= threshold:
                duplicates_found.append(other_item)
        
        # Only create group if duplicates were found
        if duplicates_found:
            group_id = f"group_{group_counter:04d}"
            group_counter += 1
            
            # Add original item and all duplicates to group
            group_items = [item] + duplicates_found
            duplicate_groups[group_id] = group_items
            
            # Mark all items with group ID
            for group_item in group_items:
                group_item['dedupe_group'] = group_id
    
    return duplicate_groups


def fetch_all_rss_sources(
    config: Optional[Dict[str, Any]] = None,
    cache_store: Optional[Dict[str, Dict[str, str]]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    """
    Fetch news from all enabled RSS sources.
    
    Args:
        config: RSS configuration (loads from file if None)
        cache_store: Cache information for conditional gets
        
    Returns:
        Tuple of (all_news_items, updated_cache_store)
    """
    if config is None:
        config = load_rss_config()
    
    if cache_store is None:
        cache_store = {}
    
    all_news_items = []
    updated_cache_store = cache_store.copy()
    
    # Rate limiting setup
    rps_limit = int(os.getenv('RPS_LIMIT', '5'))
    request_interval = 1.0 / rps_limit if rps_limit > 0 else 0.1
    
    for source_id, source_config in config['sources'].items():
        if not source_config.get('enabled', False):
            logger.info(f"Skipping disabled RSS source: {source_config['name']}")
            continue
        
        try:
            # Rate limiting
            time.sleep(request_interval)
            
            # Get cache info for this source
            source_cache = cache_store.get(source_id, {})
            
            # Fetch feed
            feed_result, new_cache = fetch_rss_feed(source_config, source_cache)
            
            if feed_result['status'] == 'success':
                # Add source metadata to each entry
                for entry in feed_result['entries']:
                    entry['source_id'] = source_id
                    entry['source_priority'] = source_config.get('priority', 'medium')
                
                all_news_items.extend(feed_result['entries'])
                updated_cache_store[source_id] = new_cache
                
                logger.info(f"Successfully fetched {len(feed_result['entries'])} items from {source_config['name']}")
            
            elif feed_result['status'] == 'not_modified':
                # Keep existing cache info
                updated_cache_store[source_id] = source_cache
                logger.info(f"RSS feed not modified: {source_config['name']}")
            
        except RSSIngestionError as e:
            logger.error(f"RSS ingestion failed for {source_config['name']}: {e}")
            # Continue with other sources
            continue
        except Exception as e:
            logger.error(f"Unexpected error fetching {source_config['name']}: {e}")
            continue
    
    # Detect and mark near-duplicates
    if all_news_items:
        duplicate_groups = detect_near_duplicates(all_news_items)
        logger.info(f"Detected {len(duplicate_groups)} duplicate groups from {len(all_news_items)} total items")
    
    return all_news_items, updated_cache_store


def filter_relevant_news(
    news_items: List[Dict[str, Any]],
    target_ticker: Optional[str] = None,
    relevance_config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Filter news items for relevance to financial analysis.
    
    Args:
        news_items: List of news item dictionaries
        target_ticker: Specific ticker to filter for (optional)
        relevance_config: Relevance filtering configuration
        
    Returns:
        List of relevant news items
    """
    if relevance_config is None:
        config = load_rss_config()
        relevance_config = config.get('relevance_keywords', {})
    
    financial_terms = relevance_config.get('financial_terms', [])
    exclusion_terms = relevance_config.get('exclusion_terms', [])
    
    relevant_items = []
    
    for item in news_items:
        title_lower = item['title'].lower()
        body_lower = (item.get('body') or '').lower()
        combined_text = title_lower + ' ' + body_lower
        
        # Check for exclusion terms first
        if any(term.lower() in combined_text for term in exclusion_terms):
            continue
        
        # Check for financial relevance
        has_financial_terms = any(term.lower() in combined_text for term in financial_terms)
        
        # Check for ticker relevance
        has_ticker_relevance = False
        if target_ticker:
            ticker_lower = target_ticker.lower()
            ticker_hint = item.get('ticker_hint') or ''
            has_ticker_relevance = (
                ticker_lower in title_lower or 
                ticker_lower in body_lower or
                ticker_hint.lower() == ticker_lower
            )
        else:
            # If no specific ticker, check for any ticker hints
            has_ticker_relevance = bool(item.get('ticker_hint'))
        
        # Include if relevant
        if has_financial_terms and has_ticker_relevance:
            relevant_items.append(item)
    
    logger.info(f"Filtered {len(relevant_items)} relevant items from {len(news_items)} total")
    return relevant_items


def validate_news_item(news_item: Dict[str, Any]) -> bool:
    """
    Validate news item has required fields and reasonable values.
    
    Args:
        news_item: News item dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['url_hash', 'canonical_url', 'title', 'published_at', 'source', 'fetched_at']
    
    # Check required fields
    for field in required_fields:
        if field not in news_item:
            logger.warning(f"News item missing required field: {field}")
            return False
        if news_item[field] is None:
            logger.warning(f"News item has None value for required field: {field}")
            return False
    
    # Validate types
    if not isinstance(news_item['published_at'], datetime):
        logger.warning(f"Invalid published_at type: {type(news_item['published_at'])}")
        return False
    
    if not isinstance(news_item['fetched_at'], datetime):
        logger.warning(f"Invalid fetched_at type: {type(news_item['fetched_at'])}")
        return False
    
    # Check reasonable values
    if len(news_item['title']) < 5:
        logger.warning(f"Title too short: {news_item['title']}")
        return False
    
    if len(news_item['url_hash']) != 64:  # SHA-256 hex length
        logger.warning(f"Invalid url_hash length: {len(news_item['url_hash'])}")
        return False
    
    # Check publication date is reasonable (not future, not too old)
    now = datetime.utcnow()
    pub_time = news_item['published_at']
    
    if pub_time > now + timedelta(hours=1):  # Allow 1 hour clock skew
        logger.warning(f"Publication date in future: {pub_time}")
        return False
    
    if pub_time < now - timedelta(days=365):  # Don't accept news older than 1 year
        logger.warning(f"Publication date too old: {pub_time}")
        return False
    
    return True
