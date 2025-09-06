"""
Daily prices DAG - orchestrates the complete price data pipeline.
Composes: Provider → Transform → Validate → Store → Track.
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Import all pipeline components
from ingestion.providers.yfinance_adapter import fetch_prices_window
from ingestion.transforms.normalizers import normalize_prices
from ingestion.transforms.validators import validate_prices_row, ValidationError
from storage.loaders import upsert_prices
from storage.run_registry import start_run, finish_run, RunStatus


class PipelineError(Exception):
    """Raised when pipeline execution fails."""
    pass


@dataclass
class DailyPricesConfig:
    """Configuration for daily prices pipeline."""
    ticker: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    def __post_init__(self):
        """Validate and set defaults."""
        if not self.ticker or not isinstance(self.ticker, str):
            raise ValueError("ticker must be non-empty string")
        
        # Set default date range (last 365 days)
        if self.end_date is None:
            self.end_date = date.today()
        
        if self.start_date is None:
            self.start_date = self.end_date - timedelta(days=365)
        
        # Validate date range
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
    
    @property
    def days_range(self) -> int:
        """Calculate number of days in range."""
        return (self.end_date - self.start_date).days


def run_daily_prices(config: DailyPricesConfig, conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Run the complete daily prices pipeline.
    
    Pipeline stages:
    1. Start run tracking
    2. Fetch raw data from provider
    3. Normalize to canonical format
    4. Validate each row
    5. Store valid rows
    6. Finish run tracking with metrics
    
    Args:
        config: Pipeline configuration
        conn: SQLite database connection
        
    Returns:
        Dictionary with run results and metrics
    """
    # Start run tracking
    run_id = start_run(conn, 'daily_prices')
    start_time = datetime.now()
    
    result = {
        'ticker': config.ticker,
        'start_date': config.start_date,
        'end_date': config.end_date,
        'run_id': run_id,
        'status': 'running',
        'rows_fetched': 0,
        'rows_stored': 0,
        'validation_warnings': 0,
        'error_message': None
    }
    
    try:
        # Stage 1: Fetch raw data from provider
        raw_data = fetch_prices_window(
            ticker=config.ticker,
            start=config.start_date,
            end=config.end_date
        )
        
        result['rows_fetched'] = len(raw_data)
        
        if not raw_data:
            # Empty data is not an error - complete successfully
            finish_run(
                conn=conn,
                run_id=run_id,
                status=RunStatus.COMPLETED,
                finished_at=datetime.now(),
                rows_in=0,
                rows_out=0
            )
            result['status'] = 'completed'
            result['duration_seconds'] = (datetime.now() - start_time).total_seconds()
            return result
        
        # Stage 2: Normalize to canonical format
        ingested_at = datetime.now()
        normalized_data = normalize_prices(
            raw_rows=raw_data,
            ticker=config.ticker,
            source='yfinance',
            as_of=config.end_date,  # When we fetched the data
            ingested_at=ingested_at
        )
        
        # Stage 3: Validate each row
        valid_rows = []
        validation_warnings = 0
        
        for row in normalized_data:
            try:
                validate_prices_row(row)
                valid_rows.append(row)
            except ValidationError as e:
                validation_warnings += 1
                # Log validation warning but continue processing
                print(f"Validation warning for {config.ticker} {row.get('date', 'unknown')}: {e}")
        
        result['validation_warnings'] = validation_warnings
        
        if not valid_rows:
            # All rows failed validation - this is an error
            error_msg = f"All {len(normalized_data)} rows failed validation"
            finish_run(
                conn=conn,
                run_id=run_id,
                status=RunStatus.FAILED,
                finished_at=datetime.now(),
                rows_in=len(raw_data),
                rows_out=0
            )
            result['status'] = 'failed'
            result['error_message'] = error_msg
            result['duration_seconds'] = (datetime.now() - start_time).total_seconds()
            return result
        
        # Stage 4: Store valid rows
        inserted, updated = upsert_prices(conn, valid_rows)
        result['rows_stored'] = len(valid_rows)
        result['rows_inserted'] = inserted
        result['rows_updated'] = updated
        
        # Stage 5: Calculate summary metrics
        result.update(_calculate_price_metrics(valid_rows))
        
        # Stage 6: Finish run tracking
        finish_run(
            conn=conn,
            run_id=run_id,
            status=RunStatus.COMPLETED,
            finished_at=datetime.now(),
            rows_in=len(raw_data),
            rows_out=len(valid_rows)
        )
        
        result['status'] = 'completed'
        result['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        
        return result
        
    except Exception as e:
        # Pipeline failed - record failure
        error_message = str(e)
        
        finish_run(
            conn=conn,
            run_id=run_id,
            status=RunStatus.FAILED,
            finished_at=datetime.now(),
            rows_in=result['rows_fetched'],
            rows_out=result['rows_stored']
        )
        
        result['status'] = 'failed'
        result['error_message'] = error_message
        result['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        
        return result


def _calculate_price_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate summary metrics from price data.
    
    Args:
        rows: List of validated price dictionaries
        
    Returns:
        Dictionary with calculated metrics
    """
    if not rows:
        return {}
    
    closes = [row['close'] for row in rows]
    volumes = [row['volume'] for row in rows]
    
    metrics = {
        'price_range': {
            'min_close': min(closes),
            'max_close': max(closes),
            'first_close': closes[0] if rows else None,
            'last_close': closes[-1] if rows else None
        },
        'total_volume': sum(volumes),
        'avg_volume': sum(volumes) / len(volumes) if volumes else 0,
        'date_range': {
            'first_date': rows[0]['date'] if rows else None,
            'last_date': rows[-1]['date'] if rows else None,
            'trading_days': len(rows)
        }
    }
    
    # Calculate simple return if we have multiple days
    if len(closes) > 1:
        total_return = (closes[-1] - closes[0]) / closes[0]
        metrics['total_return_pct'] = round(total_return * 100, 2)
    
    return metrics
