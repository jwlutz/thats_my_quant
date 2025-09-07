#!/usr/bin/env python3
"""
Update ticker symbols from NASDAQ API.
Adapted from US-Stock-Symbols GitHub workflow for local execution.
"""

import json
import os
import requests
import subprocess
from pathlib import Path
from typing import Dict, List
import time


class TickerUpdateError(Exception):
    """Raised when ticker update fails."""
    pass


def fetch_exchange_data(exchange: str) -> Dict:
    """
    Fetch ticker data from NASDAQ API for specified exchange.
    
    Args:
        exchange: Exchange name ('nasdaq', 'nyse', 'amex')
        
    Returns:
        Dictionary with ticker data
        
    Raises:
        TickerUpdateError: If API request fails
    """
    url = f"https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&exchange={exchange}&download=true"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:85.0) Gecko/20100101 Firefox/85.0'
    }
    
    try:
        print(f"Fetching {exchange.upper()} data from NASDAQ API...")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if 'data' not in data or 'rows' not in data['data']:
            raise TickerUpdateError(f"Unexpected API response format for {exchange}")
        
        return data
        
    except requests.RequestException as e:
        raise TickerUpdateError(f"Failed to fetch {exchange} data: {e}")
    except json.JSONDecodeError as e:
        raise TickerUpdateError(f"Failed to parse {exchange} JSON response: {e}")


def save_exchange_files(exchange: str, data: Dict, output_dir: Path) -> None:
    """
    Save exchange data to files in US-Stock-Symbols format.
    
    Args:
        exchange: Exchange name
        data: API response data
        output_dir: Output directory path
    """
    exchange_dir = output_dir / exchange
    exchange_dir.mkdir(exist_ok=True)
    
    rows = data['data']['rows']
    
    # Save full tickers JSON
    full_file = exchange_dir / f"{exchange}_full_tickers.json"
    with open(full_file, 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=2)
    print(f"  Saved {len(rows)} full records to {full_file}")
    
    # Save ticker symbols JSON
    symbols = [row['symbol'] for row in rows if 'symbol' in row]
    symbols_file = exchange_dir / f"{exchange}_tickers.json"
    with open(symbols_file, 'w', encoding='utf-8') as f:
        json.dump(symbols, f, indent=2)
    print(f"  Saved {len(symbols)} symbols to {symbols_file}")
    
    # Save ticker symbols TXT
    txt_file = exchange_dir / f"{exchange}_tickers.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        for symbol in symbols:
            f.write(f"{symbol}\n")
    print(f"  Saved {len(symbols)} symbols to {txt_file}")


def create_all_tickers_file(output_dir: Path) -> None:
    """
    Create combined all_tickers.txt file from individual exchanges.
    
    Args:
        output_dir: Output directory path
    """
    all_dir = output_dir / "all"
    all_dir.mkdir(exist_ok=True)
    
    all_symbols = set()
    
    # Collect symbols from all exchanges
    for exchange in ['nasdaq', 'nyse', 'amex']:
        txt_file = output_dir / exchange / f"{exchange}_tickers.txt"
        if txt_file.exists():
            with open(txt_file, 'r', encoding='utf-8') as f:
                for line in f:
                    symbol = line.strip()
                    if symbol:
                        all_symbols.add(symbol)
    
    # Save combined file (sorted and deduplicated)
    all_file = all_dir / "all_tickers.txt"
    with open(all_file, 'w', encoding='utf-8') as f:
        for symbol in sorted(all_symbols):
            f.write(f"{symbol}\n")
    
    print(f"  Saved {len(all_symbols)} unique symbols to {all_file}")


def update_ticker_symbols(output_dir: str = None) -> Dict[str, int]:
    """
    Update all ticker symbol files from NASDAQ API.
    
    Args:
        output_dir: Directory to save files (default: US-Stock-Symbols-main)
        
    Returns:
        Dictionary with update statistics
        
    Raises:
        TickerUpdateError: If update process fails
    """
    if output_dir is None:
        repo_root = Path(__file__).parent.parent
        output_dir = repo_root / "US-Stock-Symbols-main"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True)
    
    print(f"Updating ticker symbols in {output_dir}")
    
    stats = {}
    
    # Update each exchange
    for exchange in ['nasdaq', 'nyse', 'amex']:
        try:
            data = fetch_exchange_data(exchange)
            save_exchange_files(exchange, data, output_dir)
            stats[exchange] = len(data['data']['rows'])
            
            # Rate limiting - be nice to NASDAQ API
            time.sleep(2)
            
        except TickerUpdateError as e:
            print(f"WARNING: Failed to update {exchange}: {e}")
            stats[exchange] = 0
    
    # Create combined file
    try:
        create_all_tickers_file(output_dir)
        
        # Count total unique symbols
        all_file = output_dir / "all" / "all_tickers.txt"
        if all_file.exists():
            with open(all_file, 'r') as f:
                stats['total'] = len(f.readlines())
        
    except Exception as e:
        print(f"WARNING: Failed to create all_tickers.txt: {e}")
        stats['total'] = sum(stats.values())
    
    return stats


if __name__ == "__main__":
    import sys
    
    try:
        if len(sys.argv) > 1:
            output_dir = sys.argv[1]
        else:
            output_dir = None
        
        print("Starting ticker symbol update...")
        stats = update_ticker_symbols(output_dir)
        
        print("\nUpdate complete!")
        print("Statistics:")
        for exchange, count in stats.items():
            if exchange != 'total':
                print(f"  {exchange.upper()}: {count:,} symbols")
        print(f"  TOTAL: {stats.get('total', 0):,} unique symbols")
        
    except TickerUpdateError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nUpdate cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        sys.exit(1)
