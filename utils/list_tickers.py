#!/usr/bin/env python3
"""
List available ticker symbols from US-Stock-Symbols repository.
Provides utilities to query and validate ticker symbols for analysis.
"""

import os
import json
from pathlib import Path
from typing import Set, List, Dict, Optional


def get_all_tickers() -> Set[str]:
    """
    Get all ticker symbols from US-Stock-Symbols repository.
    
    Returns:
        Set of all ticker symbols across NASDAQ, NYSE, and AMEX
    """
    repo_root = Path(__file__).parent.parent
    all_tickers_file = repo_root / "US-Stock-Symbols-main" / "all" / "all_tickers.txt"
    
    if not all_tickers_file.exists():
        raise FileNotFoundError(f"US-Stock-Symbols data not found at {all_tickers_file}")
    
    tickers = set()
    with open(all_tickers_file, 'r', encoding='utf-8') as f:
        for line in f:
            ticker = line.strip().upper()
            if ticker:
                tickers.add(ticker)
    
    return tickers


def get_exchange_tickers(exchange: str) -> Set[str]:
    """
    Get ticker symbols for a specific exchange.
    
    Args:
        exchange: Exchange name ('nasdaq', 'nyse', or 'amex')
        
    Returns:
        Set of ticker symbols for the specified exchange
    """
    if exchange.lower() not in ['nasdaq', 'nyse', 'amex']:
        raise ValueError(f"Invalid exchange: {exchange}. Must be 'nasdaq', 'nyse', or 'amex'")
    
    repo_root = Path(__file__).parent.parent
    exchange_file = repo_root / "US-Stock-Symbols-main" / exchange.lower() / f"{exchange.lower()}_tickers.txt"
    
    if not exchange_file.exists():
        raise FileNotFoundError(f"Exchange data not found at {exchange_file}")
    
    tickers = set()
    with open(exchange_file, 'r', encoding='utf-8') as f:
        for line in f:
            ticker = line.strip().upper()
            if ticker:
                tickers.add(ticker)
    
    return tickers


def get_ticker_details(ticker: str) -> Optional[Dict[str, str]]:
    """
    Get detailed information for a specific ticker.
    
    Args:
        ticker: Ticker symbol to lookup
        
    Returns:
        Dictionary with ticker details or None if not found
    """
    ticker = ticker.upper().strip()
    repo_root = Path(__file__).parent.parent
    
    # Check each exchange for ticker details
    for exchange in ['nasdaq', 'nyse', 'amex']:
        full_file = repo_root / "US-Stock-Symbols-main" / exchange / f"{exchange}_full_tickers.json"
        
        if not full_file.exists():
            continue
            
        try:
            with open(full_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for entry in data:
                if entry.get('symbol', '').upper() == ticker:
                    return {
                        'symbol': entry.get('symbol', ''),
                        'name': entry.get('name', ''),
                        'exchange': exchange.upper(),
                        'sector': entry.get('sector', 'Unknown'),
                        'industry': entry.get('industry', 'Unknown'),
                        'country': entry.get('country', 'Unknown')
                    }
                    
        except (json.JSONDecodeError, FileNotFoundError):
            continue
    
    return None


def is_valid_ticker(ticker: str) -> bool:
    """
    Check if a ticker symbol is valid (exists in US exchanges).
    
    Args:
        ticker: Ticker symbol to validate
        
    Returns:
        True if ticker exists in NASDAQ, NYSE, or AMEX
    """
    try:
        all_tickers = get_all_tickers()
        return ticker.upper().strip() in all_tickers
    except FileNotFoundError:
        return False


def get_stats() -> Dict[str, int]:
    """
    Get statistics about available ticker symbols.
    
    Returns:
        Dictionary with ticker count statistics
    """
    stats = {}
    
    try:
        stats['total'] = len(get_all_tickers())
        
        for exchange in ['nasdaq', 'nyse', 'amex']:
            try:
                stats[exchange] = len(get_exchange_tickers(exchange))
            except FileNotFoundError:
                stats[exchange] = 0
                
    except FileNotFoundError:
        stats = {'error': 'US-Stock-Symbols data not available'}
    
    return stats


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python utils/list_tickers.py <command> [args]")
        print("Commands:")
        print("  stats                    - Show ticker count statistics")
        print("  all                      - List all tickers (warning: 6000+ symbols)")
        print("  exchange <name>          - List tickers for specific exchange")
        print("  lookup <ticker>          - Get details for specific ticker")
        print("  validate <ticker>        - Check if ticker is valid")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    try:
        if command == "stats":
            stats = get_stats()
            if 'error' in stats:
                print(f"ERROR: {stats['error']}")
            else:
                print("US Stock Symbol Statistics:")
                print(f"  Total: {stats.get('total', 0):,}")
                print(f"  NASDAQ: {stats.get('nasdaq', 0):,}")
                print(f"  NYSE: {stats.get('nyse', 0):,}")
                print(f"  AMEX: {stats.get('amex', 0):,}")
        
        elif command == "all":
            tickers = sorted(get_all_tickers())
            print(f"All {len(tickers)} ticker symbols:")
            for ticker in tickers:
                print(ticker)
        
        elif command == "exchange":
            if len(sys.argv) < 3:
                print("ERROR: Exchange name required")
                sys.exit(1)
            
            exchange = sys.argv[2]
            tickers = sorted(get_exchange_tickers(exchange))
            print(f"{exchange.upper()} ticker symbols ({len(tickers)}):")
            for ticker in tickers:
                print(ticker)
        
        elif command == "lookup":
            if len(sys.argv) < 3:
                print("ERROR: Ticker symbol required")
                sys.exit(1)
            
            ticker = sys.argv[2]
            details = get_ticker_details(ticker)
            if details:
                print(f"Ticker: {details['symbol']}")
                print(f"Name: {details['name']}")
                print(f"Exchange: {details['exchange']}")
                print(f"Sector: {details['sector']}")
                print(f"Industry: {details['industry']}")
                print(f"Country: {details['country']}")
            else:
                print(f"Ticker '{ticker}' not found")
        
        elif command == "validate":
            if len(sys.argv) < 3:
                print("ERROR: Ticker symbol required")
                sys.exit(1)
            
            ticker = sys.argv[2]
            if is_valid_ticker(ticker):
                print(f"'{ticker}' is a valid ticker symbol")
            else:
                print(f"'{ticker}' is not a valid ticker symbol")
        
        else:
            print(f"ERROR: Unknown command '{command}'")
            sys.exit(1)
            
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
