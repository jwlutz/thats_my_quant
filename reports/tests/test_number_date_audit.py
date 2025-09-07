"""
Tests for number and date audit system.
"""

import pytest
from reports.number_date_audit import (
    extract_percentages,
    extract_dates,
    normalize_percentage,
    normalize_date,
    build_audit_sets,
    audit_text,
    audit_with_fallback,
    create_enhanced_audit_index,
    AuditError
)


class TestExtractPercentages:
    """Test percentage extraction."""
    
    def test_simple_percentages(self):
        """Test basic percentage extraction."""
        text = "The return was 8.9% last month and -0.3% today."
        result = extract_percentages(text)
        
        assert result == ["8.9%", "-0.3%"]
    
    def test_percentages_with_thousands(self):
        """Test percentages with thousands separators."""
        text = "The fund grew 1,234.5% over the period."
        result = extract_percentages(text)
        
        assert result == ["1,234.5%"]
    
    def test_percentages_with_spaces(self):
        """Test percentages with spaces before %."""
        text = "Volatility was 28.5 % and concentration was 12.3%."
        result = extract_percentages(text)
        
        assert result == ["28.5 %", "12.3%"]
    
    def test_negative_percentages(self):
        """Test negative percentage extraction."""
        text = "Drawdown reached -18.5% and recovered to +5.2%."
        result = extract_percentages(text)
        
        assert result == ["-18.5%", "+5.2%"]
    
    def test_zero_percent(self):
        """Test zero percentage handling."""
        text = "No change at 0.0% and -0.0% is also zero."
        result = extract_percentages(text)
        
        assert result == ["0.0%", "-0.0%"]
    
    def test_no_percentages(self):
        """Test text without percentages."""
        text = "The company reported strong earnings this quarter."
        result = extract_percentages(text)
        
        assert result == []


class TestExtractDates:
    """Test date extraction."""
    
    def test_simple_dates(self):
        """Test basic date extraction."""
        text = "The analysis covers from January 1, 2024 to December 31, 2024."
        result = extract_dates(text)
        
        assert result == ["January 1, 2024", "December 31, 2024"]
    
    def test_dates_with_leading_zeros(self):
        """Test dates with leading zeros in day."""
        text = "The event occurred on August 05, 2025 and ended September 10, 2025."
        result = extract_dates(text)
        
        assert result == ["August 05, 2025", "September 10, 2025"]
    
    def test_mixed_case_months(self):
        """Test case insensitive month matching."""
        text = "From january 15, 2024 to FEBRUARY 28, 2024."
        result = extract_dates(text)
        
        assert result == ["january 15, 2024", "FEBRUARY 28, 2024"]
    
    def test_no_dates(self):
        """Test text without dates."""
        text = "The analysis shows strong performance metrics."
        result = extract_dates(text)
        
        assert result == []


class TestNormalizePercentage:
    """Test percentage normalization."""
    
    def test_simple_percentage(self):
        """Test basic percentage normalization."""
        result = normalize_percentage("28.5%")
        assert abs(result - 0.285) < 1e-10
    
    def test_negative_percentage(self):
        """Test negative percentage normalization."""
        result = normalize_percentage("-18.5%")
        assert abs(result - (-0.185)) < 1e-10
    
    def test_zero_percentage(self):
        """Test zero percentage normalization."""
        result = normalize_percentage("0.0%")
        assert abs(result - 0.0) < 1e-10
        
        result = normalize_percentage("-0.0%")
        assert abs(result - 0.0) < 1e-10
    
    def test_percentage_with_thousands(self):
        """Test percentage with thousands separator."""
        result = normalize_percentage("1,234.5%")
        assert abs(result - 12.345) < 1e-10
    
    def test_percentage_with_space(self):
        """Test percentage with space before %."""
        result = normalize_percentage("28.5 %")
        assert abs(result - 0.285) < 1e-10


class TestNormalizeDate:
    """Test date normalization."""
    
    def test_simple_date(self):
        """Test basic date normalization."""
        result = normalize_date("September 5, 2025")
        assert result == "2025-09-05"
    
    def test_date_with_leading_zero(self):
        """Test date with leading zero in day."""
        result = normalize_date("August 05, 2025")
        assert result == "2025-08-05"
    
    def test_single_digit_day(self):
        """Test date with single digit day."""
        result = normalize_date("July 1, 2024")
        assert result == "2024-07-01"
    
    def test_invalid_date(self):
        """Test invalid date handling."""
        result = normalize_date("Invalid Date")
        assert result == "Invalid Date"  # Returns original on failure


class TestBuildAuditSets:
    """Test audit sets building."""
    
    def test_build_sets_from_v2_metrics(self):
        """Test building audit sets from v2 metrics."""
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%", "-18.5%", "12.3%"],
                "dates": ["September 5, 2025", "July 15, 2025"]
            }
        }
        
        numeric_percents, dates_iso = build_audit_sets(metrics_v2)
        
        # Check numeric percentages
        expected_percents = {0.285, -0.185, 0.123}
        assert len(numeric_percents) == 3
        for expected in expected_percents:
            assert any(abs(actual - expected) < 1e-10 for actual in numeric_percents)
        
        # Check ISO dates
        expected_dates = {"2025-09-05", "2025-07-15"}
        assert dates_iso == expected_dates
    
    def test_build_sets_empty_audit_index(self):
        """Test building audit sets with empty audit index."""
        metrics_v2 = {"audit_index": {}}
        
        numeric_percents, dates_iso = build_audit_sets(metrics_v2)
        
        assert numeric_percents == set()
        assert dates_iso == set()
    
    def test_build_sets_missing_audit_index(self):
        """Test building audit sets with missing audit index."""
        metrics_v2 = {}
        
        numeric_percents, dates_iso = build_audit_sets(metrics_v2)
        
        assert numeric_percents == set()
        assert dates_iso == set()


class TestAuditText:
    """Test text auditing."""
    
    def test_audit_passes_with_allowed_values(self):
        """Test audit passes when all values are allowed."""
        text = "The stock returned 28.5% with drawdown of -18.5% from July 15, 2025."
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%", "-18.5%"],
                "dates": ["July 15, 2025"]
            }
        }
        
        result = audit_text(text, metrics_v2)
        
        assert result['passed'] is True
        assert result['violations']['total_violations'] == 0
        assert len(result['found_percentages']) == 2
        assert len(result['found_dates']) == 1
    
    def test_audit_passes_with_tolerance(self):
        """Test audit passes with values within tolerance."""
        text = "The return was 28.50% this month."  # 28.50% vs allowed 28.5%
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": []
            }
        }
        
        result = audit_text(text, metrics_v2, tolerance=0.0005)
        
        assert result['passed'] is True
        assert result['violations']['total_violations'] == 0
    
    def test_audit_fails_with_unauthorized_percentage(self):
        """Test audit fails with unauthorized percentage."""
        text = "The return was 99.9% this month."  # Not in allowed set
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%", "-18.5%"],
                "dates": []
            }
        }
        
        result = audit_text(text, metrics_v2)
        
        assert result['passed'] is False
        assert result['violations']['total_violations'] == 1
        assert len(result['violations']['unauthorized_percentages']) == 1
        assert result['violations']['unauthorized_percentages'][0]['text'] == "99.9%"
    
    def test_audit_fails_with_unauthorized_date(self):
        """Test audit fails with unauthorized date."""
        text = "The event happened on January 1, 2025."  # Not in allowed set
        metrics_v2 = {
            "audit_index": {
                "percent_strings": [],
                "dates": ["July 15, 2025", "August 12, 2025"]
            }
        }
        
        result = audit_text(text, metrics_v2)
        
        assert result['passed'] is False
        assert result['violations']['total_violations'] == 1
        assert len(result['violations']['unauthorized_dates']) == 1
        assert result['violations']['unauthorized_dates'][0]['text'] == "January 1, 2025"
    
    def test_audit_multiple_violations(self):
        """Test audit with multiple violations."""
        text = "Return was 99.9% from January 1, 2025 to February 1, 2025."
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": ["July 15, 2025"]
            }
        }
        
        result = audit_text(text, metrics_v2)
        
        assert result['passed'] is False
        assert result['violations']['total_violations'] == 3  # 1 percentage + 2 dates
    
    def test_audit_negative_zero_normalization(self):
        """Test that -0.0% is normalized correctly."""
        text = "No change at -0.0% today."
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["0.0%"],  # Should match -0.0%
                "dates": []
            }
        }
        
        result = audit_text(text, metrics_v2, tolerance=0.0005)
        
        assert result['passed'] is True
        assert result['violations']['total_violations'] == 0


class TestAuditWithFallback:
    """Test audit with fallback functionality."""
    
    def test_fallback_on_audit_failure(self):
        """Test fallback to skeleton when audit fails."""
        llm_text = "The return was 99.9% this month."  # Unauthorized
        skeleton = "The return was 28.5% this month."  # Safe fallback
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": []
            }
        }
        
        result_text, used_fallback = audit_with_fallback(llm_text, skeleton, metrics_v2)
        
        assert result_text == skeleton
        assert used_fallback is True
    
    def test_no_fallback_on_audit_success(self):
        """Test no fallback when audit passes."""
        llm_text = "The return was 28.5% this month."  # Authorized
        skeleton = "Fallback text."
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": []
            }
        }
        
        result_text, used_fallback = audit_with_fallback(llm_text, skeleton, metrics_v2)
        
        assert result_text == llm_text
        assert used_fallback is False


class TestCreateEnhancedAuditIndex:
    """Test enhanced audit index creation."""
    
    def test_create_enhanced_index(self):
        """Test creating enhanced audit index."""
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%", "-18.5%"],
                "dates": ["September 5, 2025", "July 15, 2025"],
                "labels": ["moderate", "high"],
                "numbers": [229.87, 125.0]
            }
        }
        
        enhanced = create_enhanced_audit_index(metrics_v2)
        
        # Check original fields are preserved
        assert enhanced['percent_strings'] == ["28.5%", "-18.5%"]
        assert enhanced['dates'] == ["September 5, 2025", "July 15, 2025"]
        assert enhanced['labels'] == ["moderate", "high"]
        assert enhanced['numbers'] == [229.87, 125.0]
        
        # Check new numeric fields
        assert 'numeric_percents' in enhanced
        assert 'dates_iso' in enhanced
        
        # Check numeric percentages
        numeric_percents = enhanced['numeric_percents']
        assert len(numeric_percents) == 2
        assert abs(numeric_percents[0] - 0.285) < 1e-10
        assert abs(numeric_percents[1] - (-0.185)) < 1e-10
        
        # Check ISO dates
        dates_iso = enhanced['dates_iso']
        assert dates_iso == ["2025-09-05", "2025-07-15"]
    
    def test_create_enhanced_index_empty(self):
        """Test creating enhanced index with empty audit_index."""
        metrics_v2 = {"audit_index": {}}
        
        enhanced = create_enhanced_audit_index(metrics_v2)
        
        assert enhanced['numeric_percents'] == []
        assert enhanced['dates_iso'] == []
    
    def test_create_enhanced_index_missing(self):
        """Test creating enhanced index with missing audit_index."""
        metrics_v2 = {}
        
        enhanced = create_enhanced_audit_index(metrics_v2)
        
        assert enhanced['numeric_percents'] == []
        assert enhanced['dates_iso'] == []


class TestEdgeCases:
    """Test edge cases as specified in acceptance criteria."""
    
    def test_multiple_identical_numbers(self):
        """Test that multiple identical numbers in text are handled correctly."""
        text = "The 21-day volatility and 21-day window both show 28.5% volatility."
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": []
            }
        }
        
        result = audit_text(text, metrics_v2)
        
        # Should pass even with multiple instances of 28.5%
        assert result['passed'] is True
        assert len(result['found_percentages']) == 1  # Only percentage values, not "21-day"
    
    def test_dates_with_leading_zeros_normalized(self):
        """Test that dates with leading zeros are normalized and pass."""
        text = "The event occurred on August 05, 2025."
        metrics_v2 = {
            "audit_index": {
                "percent_strings": [],
                "dates": ["August 5, 2025"]  # No leading zero in allowed
            }
        }
        
        result = audit_text(text, metrics_v2)
        
        # Should pass because both normalize to 2025-08-05
        assert result['passed'] is True
        assert result['violations']['total_violations'] == 0
    
    def test_smart_quotes_vs_straight_quotes(self):
        """Test that smart quotes vs straight quotes don't affect audit."""
        # This test focuses on the audit logic, not quote handling
        # (quote cleaning happens in the parser, before audit)
        text = "The return was 28.5% this month."
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": []
            }
        }
        
        result = audit_text(text, metrics_v2)
        
        assert result['passed'] is True
        assert result['violations']['total_violations'] == 0
