"""
Tests for RSS ingestion pipeline.
"""

import pytest
import tempfile
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from sentiment.rss_ingestion import (
    load_rss_config,
    normalize_url,
    create_url_hash,
    extract_ticker_hints,
    process_rss_entry,
    detect_near_duplicates,
    filter_relevant_news,
    validate_news_item,
    RSSIngestionError
)


class TestLoadRSSConfig:
    """Test RSS configuration loading."""
    
    def test_load_valid_config(self):
        """Test loading valid RSS configuration."""
        config_data = {
            'sources': {
                'test_source': {
                    'url': 'https://example.com/feed.xml',
                    'name': 'Test Source',
                    'enabled': True
                }
            },
            'settings': {
                'user_agent': 'test-agent/1.0'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            result = load_rss_config(config_path)
            
            assert 'sources' in result
            assert 'test_source' in result['sources']
            assert result['sources']['test_source']['url'] == 'https://example.com/feed.xml'
        finally:
            Path(config_path).unlink()
    
    def test_load_missing_file(self):
        """Test loading non-existent config file."""
        with pytest.raises(RSSIngestionError) as exc_info:
            load_rss_config('/nonexistent/path.yml')
        
        assert "not found" in str(exc_info.value)
    
    def test_load_invalid_yaml(self):
        """Test loading invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            config_path = f.name
        
        try:
            with pytest.raises(RSSIngestionError) as exc_info:
                load_rss_config(config_path)
            
            assert "Failed to load RSS config" in str(exc_info.value)
        finally:
            Path(config_path).unlink()
    
    def test_load_missing_sources_section(self):
        """Test loading config without sources section."""
        config_data = {'settings': {'user_agent': 'test'}}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            with pytest.raises(RSSIngestionError) as exc_info:
                load_rss_config(config_path)
            
            assert "missing 'sources' section" in str(exc_info.value)
        finally:
            Path(config_path).unlink()


class TestNormalizeUrl:
    """Test URL normalization."""
    
    def test_basic_normalization(self):
        """Test basic URL normalization."""
        url = "HTTPS://Example.COM/Article"
        result = normalize_url(url)
        
        assert result == "https://example.com/article"
    
    def test_remove_tracking_params(self):
        """Test removal of tracking parameters."""
        url = "https://example.com/article?utm_source=google&utm_medium=cpc&id=123"
        result = normalize_url(url)
        
        assert result == "https://example.com/article?id=123"
    
    def test_remove_fragment(self):
        """Test removal of URL fragment."""
        url = "https://example.com/article#section1"
        result = normalize_url(url)
        
        assert result == "https://example.com/article"
    
    def test_remove_all_tracking_params(self):
        """Test removal when all params are tracking."""
        url = "https://example.com/article?utm_source=google&fbclid=123&gclid=456"
        result = normalize_url(url)
        
        assert result == "https://example.com/article"
    
    def test_preserve_non_tracking_params(self):
        """Test preservation of non-tracking parameters."""
        url = "https://example.com/article?id=123&category=finance&utm_source=google"
        result = normalize_url(url)
        
        assert result == "https://example.com/article?id=123&category=finance"


class TestCreateUrlHash:
    """Test URL hashing."""
    
    def test_consistent_hashing(self):
        """Test that same URL produces same hash."""
        url1 = "https://example.com/article?id=123"
        url2 = "HTTPS://EXAMPLE.COM/article?id=123&utm_source=test"
        
        hash1 = create_url_hash(url1)
        hash2 = create_url_hash(url2)
        
        assert hash1 == hash2  # Should be same after normalization
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_different_urls_different_hashes(self):
        """Test that different URLs produce different hashes."""
        url1 = "https://example.com/article1"
        url2 = "https://example.com/article2"
        
        hash1 = create_url_hash(url1)
        hash2 = create_url_hash(url2)
        
        assert hash1 != hash2


class TestExtractTickerHints:
    """Test ticker hint extraction."""
    
    def test_extract_from_title(self):
        """Test ticker extraction from title."""
        title = "AAPL Reports Strong Q4 Earnings"
        url = "https://example.com/news/article"
        
        result = extract_ticker_hints(title, url)
        
        assert "AAPL" in result
        assert "Q4" not in result  # Too short
    
    def test_extract_from_url(self):
        """Test ticker extraction from URL."""
        title = "Company Reports Earnings"
        url = "https://finance.yahoo.com/news/MSFT-earnings-123456"
        
        result = extract_ticker_hints(title, url)
        
        assert "MSFT" in result
    
    def test_filter_false_positives(self):
        """Test filtering of common false positives."""
        title = "RSS News API Reports HTTP GET Success"
        url = "https://www.example.com/api/news.xml"
        
        result = extract_ticker_hints(title, url)
        
        # Should not include common false positives
        false_positives = {'RSS', 'NEWS', 'API', 'HTTP', 'GET', 'WWW', 'COM', 'XML'}
        for fp in false_positives:
            assert fp not in result
    
    def test_limit_hints(self):
        """Test limiting number of hints returned."""
        title = "AAPL MSFT GOOGL AMZN TSLA NVDA Reports"
        url = "https://example.com/news"
        
        result = extract_ticker_hints(title, url)
        
        assert len(result) <= 5  # Should be limited to 5


class TestProcessRSSEntry:
    """Test RSS entry processing."""
    
    def test_process_valid_entry(self):
        """Test processing valid RSS entry."""
        # Mock feedparser entry
        entry = MagicMock()
        entry.title = "AAPL Reports Strong Q4 Earnings"
        entry.link = "https://example.com/aapl-earnings"
        entry.published_parsed = (2025, 1, 15, 14, 30, 0, 1, 15, 0)  # struct_time format
        entry.summary = "Apple Inc reported strong quarterly earnings..."
        entry.author = "Financial Reporter"
        
        source_config = {
            'name': 'Test Source',
            'priority': 'high'
        }
        
        result = process_rss_entry(entry, source_config)
        
        assert result is not None
        assert result['title'] == "AAPL Reports Strong Q4 Earnings"
        assert result['canonical_url'] == "https://example.com/aapl-earnings"
        assert result['source'] == "Test Source"
        assert result['author'] == "Financial Reporter"
        assert result['ticker_hint'] == "AAPL"
        assert isinstance(result['published_at'], datetime)
        assert isinstance(result['fetched_at'], datetime)
        assert len(result['url_hash']) == 64
    
    def test_process_entry_missing_title(self):
        """Test processing entry without title."""
        entry = MagicMock()
        entry.title = ""
        entry.link = "https://example.com/article"
        
        source_config = {'name': 'Test Source'}
        
        result = process_rss_entry(entry, source_config)
        
        assert result is None
    
    def test_process_entry_missing_link(self):
        """Test processing entry without link."""
        entry = MagicMock()
        entry.title = "Test Article"
        entry.link = ""
        
        source_config = {'name': 'Test Source'}
        
        result = process_rss_entry(entry, source_config)
        
        assert result is None
    
    def test_process_entry_fallback_date(self):
        """Test processing entry with missing publication date."""
        entry = MagicMock()
        entry.title = "Test Article"
        entry.link = "https://example.com/article"
        # No published_parsed or published attributes
        del entry.published_parsed
        del entry.published
        
        source_config = {'name': 'Test Source'}
        
        with patch('sentiment.rss_ingestion.datetime') as mock_datetime:
            mock_now = datetime(2025, 1, 15, 12, 0, 0)
            mock_datetime.utcnow.return_value = mock_now
            
            result = process_rss_entry(entry, source_config)
            
            assert result is not None
            assert result['published_at'] == mock_now


class TestDetectNearDuplicates:
    """Test near-duplicate detection."""
    
    def test_detect_similar_titles(self):
        """Test detection of similar article titles."""
        items = [
            {
                'title': 'AAPL Reports Strong Q4 Earnings',
                'published_at': datetime(2025, 1, 15, 10, 0),
                'url_hash': 'hash1'
            },
            {
                'title': 'Apple Reports Strong Q4 Earnings Results',
                'published_at': datetime(2025, 1, 15, 11, 0),
                'url_hash': 'hash2'
            },
            {
                'title': 'Completely Different News Article',
                'published_at': datetime(2025, 1, 15, 12, 0),
                'url_hash': 'hash3'
            }
        ]
        
        result = detect_near_duplicates(items, threshold=0.75)  # Lower threshold to catch the similarity
        
        # Should find one duplicate group with the similar AAPL articles
        assert len(result) == 1
        group_items = list(result.values())[0]
        assert len(group_items) == 2
        
        # Check that duplicate items were marked with same dedupe_group
        assert items[0]['dedupe_group'] == items[1]['dedupe_group']
        # Non-duplicate item should not have dedupe_group
        assert 'dedupe_group' not in items[2]
    
    def test_time_window_filtering(self):
        """Test that duplicates outside time window are not grouped."""
        items = [
            {
                'title': 'AAPL Reports Earnings',
                'published_at': datetime(2025, 1, 15, 10, 0),
                'url_hash': 'hash1'
            },
            {
                'title': 'AAPL Reports Earnings',  # Identical title
                'published_at': datetime(2025, 1, 17, 10, 0),  # 48 hours later
                'url_hash': 'hash2'
            }
        ]
        
        result = detect_near_duplicates(items, threshold=0.9, time_window_hours=24)
        
        # Should not group items outside 24-hour window
        assert len(result) == 0
        assert 'dedupe_group' not in items[0]
        assert 'dedupe_group' not in items[1]
    
    def test_no_duplicates(self):
        """Test with no duplicate items."""
        items = [
            {
                'title': 'AAPL Reports Earnings',
                'published_at': datetime(2025, 1, 15, 10, 0),
                'url_hash': 'hash1'
            },
            {
                'title': 'MSFT Announces Dividend',
                'published_at': datetime(2025, 1, 15, 11, 0),
                'url_hash': 'hash2'
            }
        ]
        
        result = detect_near_duplicates(items, threshold=0.9)
        
        assert len(result) == 0


class TestFilterRelevantNews:
    """Test news relevance filtering."""
    
    def test_filter_for_specific_ticker(self):
        """Test filtering news for specific ticker."""
        items = [
            {
                'title': 'AAPL Reports Strong Earnings',
                'body': 'Apple Inc announced quarterly results...',
                'ticker_hint': 'AAPL'
            },
            {
                'title': 'MSFT Announces Dividend',
                'body': 'Microsoft declared a dividend...',
                'ticker_hint': 'MSFT'
            },
            {
                'title': 'General Market Update',
                'body': 'The market showed mixed signals...',
                'ticker_hint': None
            }
        ]
        
        relevance_config = {
            'financial_terms': ['earnings', 'dividend', 'results'],
            'exclusion_terms': ['sports', 'entertainment']
        }
        
        result = filter_relevant_news(items, target_ticker='AAPL', relevance_config=relevance_config)
        
        assert len(result) == 1
        assert result[0]['title'] == 'AAPL Reports Strong Earnings'
    
    def test_filter_financial_relevance(self):
        """Test filtering based on financial terms."""
        items = [
            {
                'title': 'Company Reports Earnings',
                'body': 'Quarterly results were strong...',
                'ticker_hint': 'TEST'
            },
            {
                'title': 'Celebrity News Update',
                'body': 'Entertainment industry gossip...',
                'ticker_hint': 'TEST'
            }
        ]
        
        relevance_config = {
            'financial_terms': ['earnings', 'results'],
            'exclusion_terms': ['entertainment', 'celebrity']
        }
        
        result = filter_relevant_news(items, target_ticker='TEST', relevance_config=relevance_config)
        
        assert len(result) == 1  # First item passes (has financial terms), second excluded by exclusion terms
        assert result[0]['title'] == 'Company Reports Earnings'
    
    def test_filter_without_target_ticker(self):
        """Test filtering without specific ticker (general relevance)."""
        items = [
            {
                'title': 'AAPL Reports Earnings',
                'body': 'Apple quarterly results...',
                'ticker_hint': 'AAPL'
            },
            {
                'title': 'General News Article',
                'body': 'Non-financial content...',
                'ticker_hint': None
            }
        ]
        
        relevance_config = {
            'financial_terms': ['earnings', 'results'],
            'exclusion_terms': []
        }
        
        result = filter_relevant_news(items, target_ticker=None, relevance_config=relevance_config)
        
        assert len(result) == 1
        assert result[0]['ticker_hint'] == 'AAPL'


class TestValidateNewsItem:
    """Test news item validation."""
    
    def test_valid_news_item(self):
        """Test validation of valid news item."""
        item = {
            'url_hash': 'a' * 64,  # 64-char hash
            'canonical_url': 'https://example.com/article',
            'title': 'Valid News Article Title',
            'published_at': datetime(2025, 1, 15, 12, 0),
            'source': 'Test Source',
            'fetched_at': datetime(2025, 1, 15, 12, 30),
            'body': 'Article content...',
            'author': 'Test Author'
        }
        
        result = validate_news_item(item)
        
        assert result is True
    
    def test_missing_required_field(self):
        """Test validation fails for missing required field."""
        item = {
            'url_hash': 'a' * 64,
            'canonical_url': 'https://example.com/article',
            # Missing title
            'published_at': datetime(2025, 1, 15, 12, 0),
            'source': 'Test Source',
            'fetched_at': datetime(2025, 1, 15, 12, 30)
        }
        
        result = validate_news_item(item)
        
        assert result is False
    
    def test_invalid_date_type(self):
        """Test validation fails for invalid date type."""
        item = {
            'url_hash': 'a' * 64,
            'canonical_url': 'https://example.com/article',
            'title': 'Valid Title',
            'published_at': '2025-01-15',  # String instead of datetime
            'source': 'Test Source',
            'fetched_at': datetime(2025, 1, 15, 12, 30)
        }
        
        result = validate_news_item(item)
        
        assert result is False
    
    def test_title_too_short(self):
        """Test validation fails for too short title."""
        item = {
            'url_hash': 'a' * 64,
            'canonical_url': 'https://example.com/article',
            'title': 'Hi',  # Too short
            'published_at': datetime(2025, 1, 15, 12, 0),
            'source': 'Test Source',
            'fetched_at': datetime(2025, 1, 15, 12, 30)
        }
        
        result = validate_news_item(item)
        
        assert result is False
    
    def test_future_publication_date(self):
        """Test validation fails for future publication date."""
        future_time = datetime.utcnow() + timedelta(days=1)
        
        item = {
            'url_hash': 'a' * 64,
            'canonical_url': 'https://example.com/article',
            'title': 'Valid Title',
            'published_at': future_time,
            'source': 'Test Source',
            'fetched_at': datetime.utcnow()
        }
        
        result = validate_news_item(item)
        
        assert result is False
    
    def test_very_old_publication_date(self):
        """Test validation fails for very old publication date."""
        old_time = datetime.utcnow() - timedelta(days=400)
        
        item = {
            'url_hash': 'a' * 64,
            'canonical_url': 'https://example.com/article',
            'title': 'Valid Title',
            'published_at': old_time,
            'source': 'Test Source',
            'fetched_at': datetime.utcnow()
        }
        
        result = validate_news_item(item)
        
        assert result is False
    
    def test_invalid_hash_length(self):
        """Test validation fails for invalid hash length."""
        item = {
            'url_hash': 'short_hash',  # Wrong length
            'canonical_url': 'https://example.com/article',
            'title': 'Valid Title',
            'published_at': datetime(2025, 1, 15, 12, 0),
            'source': 'Test Source',
            'fetched_at': datetime(2025, 1, 15, 12, 30)
        }
        
        result = validate_news_item(item)
        
        assert result is False
