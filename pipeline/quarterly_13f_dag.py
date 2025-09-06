"""
Quarterly 13F DAG - orchestrates the complete 13F holdings pipeline.
Composes: Provider → Transform → Validate → Store → Track.
"""

import sqlite3
from datetime import date, datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Import all pipeline components
from ingestion.providers.sec_13f_adapter import fetch_13f_quarter
from ingestion.transforms.normalizers import normalize_13f
from ingestion.transforms.validators import validate_13f_row, ValidationError
from storage.loaders import upsert_13f
from storage.run_registry import start_run, finish_run, RunStatus


class PipelineError(Exception):
    """Raised when pipeline execution fails."""
    pass


@dataclass
class Quarterly13FConfig:
    """Configuration for quarterly 13F pipeline."""
    quarter_end: date
    entity_name: Optional[str] = None
    cik: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration."""
        # Must provide either entity_name or cik
        if not self.entity_name and not self.cik:
            raise ValueError("Must provide either entity_name or cik")
        
        if self.entity_name and self.cik:
            raise ValueError("Provide either entity_name or cik, not both")
        
        # Validate quarter end date
        if not self._is_quarter_end(self.quarter_end):
            raise ValueError(f"Invalid quarter end date: {self.quarter_end}")
    
    def _is_quarter_end(self, date_val: date) -> bool:
        """Check if date is a valid quarter end."""
        valid_quarter_ends = [
            (3, 31),   # Q1
            (6, 30),   # Q2  
            (9, 30),   # Q3
            (12, 31),  # Q4
        ]
        return (date_val.month, date_val.day) in valid_quarter_ends


def run_quarterly_13f(config: Quarterly13FConfig, conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Run the complete quarterly 13F pipeline.
    
    Pipeline stages:
    1. Start run tracking
    2. Fetch raw 13F data from SEC via existing scraper
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
    run_id = start_run(conn, 'quarterly_13f')
    start_time = datetime.now()
    
    result = {
        'entity_name': config.entity_name,
        'cik': config.cik,
        'quarter_end': config.quarter_end,
        'run_id': run_id,
        'status': 'running',
        'rows_fetched': 0,
        'rows_stored': 0,
        'validation_warnings': 0,
        'error_message': None
    }
    
    try:
        # Stage 1: Fetch raw 13F data from SEC
        if config.cik:
            raw_data = fetch_13f_quarter(
                cik=config.cik,
                quarter_end=config.quarter_end
            )
        else:
            raw_data = fetch_13f_quarter(
                entity_name=config.entity_name,
                quarter_end=config.quarter_end
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
        normalized_data = normalize_13f(
            raw_rows=raw_data,
            source='sec_edgar',
            as_of=config.quarter_end,  # Reporting period end
            ingested_at=ingested_at
        )
        
        # Stage 3: Validate each row
        valid_rows = []
        validation_warnings = 0
        
        for row in normalized_data:
            try:
                validate_13f_row(row)
                valid_rows.append(row)
            except ValidationError as e:
                validation_warnings += 1
                # Log validation warning but continue processing
                entity_id = config.cik or config.entity_name
                print(f"Validation warning for {entity_id} {row.get('cusip', 'unknown')}: {e}")
        
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
        inserted, updated = upsert_13f(conn, valid_rows)
        result['rows_stored'] = len(valid_rows)
        result['rows_inserted'] = inserted
        result['rows_updated'] = updated
        
        # Stage 5: Calculate summary metrics
        result.update(_calculate_13f_metrics(valid_rows))
        
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


def _calculate_13f_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate summary metrics from 13F holdings data.
    
    Args:
        rows: List of validated 13F dictionaries
        
    Returns:
        Dictionary with calculated metrics
    """
    if not rows:
        return {}
    
    # Aggregate by position
    total_value = sum(row['value_usd'] for row in rows)
    total_positions = len(rows)
    
    # Find largest position
    largest = max(rows, key=lambda r: r['value_usd'])
    
    # Group by ticker for concentration analysis
    ticker_values = {}
    for row in rows:
        ticker = row['ticker']
        if ticker in ticker_values:
            ticker_values[ticker] += row['value_usd']
        else:
            ticker_values[ticker] = row['value_usd']
    
    # Sort by value
    top_tickers = sorted(ticker_values.items(), key=lambda x: x[1], reverse=True)
    
    metrics = {
        'holdings_summary': {
            'total_positions': total_positions,
            'total_value_usd': total_value,
            'avg_position_value_usd': total_value / total_positions if total_positions > 0 else 0,
            'largest_position': {
                'ticker': largest['ticker'],
                'name': largest['name'],
                'value_usd': largest['value_usd'],
                'shares': largest['shares'],
                'pct_of_portfolio': (largest['value_usd'] / total_value * 100) if total_value > 0 else 0
            }
        },
        'concentration': {
            'top_5_tickers': [
                {
                    'ticker': ticker,
                    'value_usd': value,
                    'pct_of_portfolio': (value / total_value * 100) if total_value > 0 else 0
                }
                for ticker, value in top_tickers[:5]
            ],
            'top_10_concentration_pct': sum(value for _, value in top_tickers[:10]) / total_value * 100 if total_value > 0 else 0
        }
    }
    
    return metrics
