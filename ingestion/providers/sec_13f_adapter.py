"""
SEC 13F adapter - wrapper around existing data_extraction.py scraper.
Provides stable interface without modifying the original scraper.
"""

import os
import sys
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import the existing scraper
# Add the project root to path to import data_extraction
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import data_extraction
from data_extraction import download_13f_in_date_range


class SEC13FError(Exception):
    """Raised when SEC 13F operations fail."""
    pass


def fetch_13f_quarter(
    quarter_end: date,
    entity_name: Optional[str] = None,
    cik: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch 13F holdings for a quarter using existing scraper.
    
    Args:
        quarter_end: End date of quarter (must be actual quarter end)
        entity_name: Institution name for CIK lookup (if cik not provided)
        cik: CIK directly (if entity_name not provided)
        
    Returns:
        List of raw holding dictionaries in scraper format
        
    Raises:
        SEC13FError: If fetch fails or validation fails
    """
    # Validate inputs
    _validate_quarter_end(quarter_end)
    
    if not entity_name and not cik:
        raise SEC13FError("Must provide either entity_name or cik")
    
    if entity_name and cik:
        raise SEC13FError("Provide either entity_name or cik, not both")
    
    # Configure scraper with environment variables
    _configure_scraper_env()
    
    # Calculate date range for the quarter
    quarter_start, filing_deadline = _get_quarter_date_range(quarter_end)
    
    try:
        # Call existing scraper
        if cik:
            # Use CIK directly via data parameter
            data_dict = {'CIK': cik}
            df = download_13f_in_date_range(
                start_date=quarter_start.strftime('%Y-%m-%d'),
                end_date=filing_deadline.strftime('%Y-%m-%d'),
                entity_name=None,
                save=False,  # Don't save CSV files
                data=data_dict
            )
        else:
            # Use entity name for CIK lookup
            df = download_13f_in_date_range(
                start_date=quarter_start.strftime('%Y-%m-%d'),
                end_date=filing_deadline.strftime('%Y-%m-%d'),
                entity_name=entity_name,
                save=False  # Don't save CSV files
            )
        
        # Convert DataFrame to list of dictionaries
        if df.empty:
            return []
        
        # Return raw dictionaries - no normalization here
        return df.to_dict('records')
        
    except Exception as e:
        entity_id = cik or entity_name
        raise SEC13FError(f"Failed to fetch 13F for {entity_id}: {str(e)}") from e


def _validate_quarter_end(quarter_end: date) -> None:
    """
    Validate that date is a valid quarter end.
    
    Args:
        quarter_end: Date to validate
        
    Raises:
        SEC13FError: If not a valid quarter end
    """
    # Check if it's a valid quarter end date
    valid_quarter_ends = [
        (3, 31),   # Q1
        (6, 30),   # Q2
        (9, 30),   # Q3
        (12, 31),  # Q4
    ]
    
    month_day = (quarter_end.month, quarter_end.day)
    if month_day not in valid_quarter_ends:
        raise SEC13FError(f"Invalid quarter end date: {quarter_end}. Must be 3/31, 6/30, 9/30, or 12/31")
    
    # Don't allow future dates
    if quarter_end > date.today():
        raise SEC13FError("Future quarter end dates not allowed")
    
    # Don't allow very old dates (13F electronic filing started ~2013)
    if quarter_end < date(2013, 1, 1):
        raise SEC13FError("Quarter end too old (pre-2013)")


def _get_quarter_date_range(quarter_end: date) -> tuple[date, date]:
    """
    Get the date range for fetching 13F filings for a quarter.
    
    Args:
        quarter_end: End date of the quarter
        
    Returns:
        Tuple of (quarter_start, filing_deadline)
    """
    year = quarter_end.year
    month = quarter_end.month
    
    # Determine quarter start
    if month == 3:  # Q1
        quarter_start = date(year, 1, 1)
        filing_deadline = date(year, 6, 30)  # 45 days after Q1 end
    elif month == 6:  # Q2
        quarter_start = date(year, 4, 1)
        filing_deadline = date(year, 9, 30)  # 45 days after Q2 end
    elif month == 9:  # Q3
        quarter_start = date(year, 7, 1)
        filing_deadline = date(year, 12, 31)  # 45 days after Q3 end
    elif month == 12:  # Q4
        quarter_start = date(year, 10, 1)
        filing_deadline = date(year + 1, 3, 31)  # 45 days after Q4 end (next year)
    else:
        raise SEC13FError(f"Invalid quarter end month: {month}")
    
    return quarter_start, filing_deadline


def _configure_scraper_env() -> None:
    """
    Configure the existing scraper with environment variables.
    Updates the scraper's global variables without modifying its code.
    """
    # Required environment variables
    user_agent = os.getenv('SEC_USER_AGENT')
    if not user_agent:
        raise SEC13FError(
            "SEC_USER_AGENT environment variable is required. "
            "Set it to 'Your Name your.email@example.com'"
        )
    
    # Update scraper's headers
    data_extraction.HEADERS = {
        'User-Agent': user_agent
    }
    
    # Update rate limiter if specified
    rate_limit_rps = os.getenv('SEC_RATE_LIMIT_RPS')
    if rate_limit_rps:
        try:
            rps = int(rate_limit_rps)
            # Update the existing rate limiter
            data_extraction.RATE_LIMITER.max_calls = rps
            data_extraction.RATE_LIMITER.period = 1.0
        except ValueError:
            raise SEC13FError(f"Invalid SEC_RATE_LIMIT_RPS: {rate_limit_rps}. Must be integer.")
    
    # Validate user agent format (basic check)
    if '@' not in user_agent or len(user_agent.split()) < 2:
        raise SEC13FError(
            "SEC_USER_AGENT should be in format 'Your Name your.email@example.com'. "
            "SEC requires proper identification for API access."
        )
