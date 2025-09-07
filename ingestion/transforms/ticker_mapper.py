"""
Comprehensive ticker mapping system using US-Stock-Symbols data.
Maps company names to ticker symbols for 13F normalization.
"""

import json
import os
from typing import Dict, Optional, Set
from pathlib import Path


class TickerMapper:
    """
    Maps company names to ticker symbols using comprehensive exchange data.
    """
    
    def __init__(self, symbols_dir: Optional[str] = None):
        """
        Initialize with path to US-Stock-Symbols directory.
        
        Args:
            symbols_dir: Path to US-Stock-Symbols-main directory
        """
        if symbols_dir is None:
            # Default to relative path from repo root
            repo_root = Path(__file__).parent.parent.parent
            symbols_dir = repo_root / "US-Stock-Symbols-main"
        
        self.symbols_dir = Path(symbols_dir)
        self._symbol_to_name: Dict[str, str] = {}
        self._name_to_symbol: Dict[str, str] = {}
        self._loaded = False
    
    def _load_exchange_data(self):
        """Load symbol mappings from all exchange files."""
        if self._loaded:
            return
        
        exchanges = ['nasdaq', 'nyse', 'amex']
        
        for exchange in exchanges:
            full_file = self.symbols_dir / exchange / f"{exchange}_full_tickers.json"
            
            if not full_file.exists():
                continue
                
            try:
                with open(full_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for entry in data:
                    symbol = entry.get('symbol', '').strip().upper()
                    name = entry.get('name', '').strip().upper()
                    
                    if symbol and name:
                        # Store both directions
                        self._symbol_to_name[symbol] = name
                        self._name_to_symbol[name] = symbol
                        
                        # Also store cleaned versions for better matching
                        cleaned_name = self._clean_company_name(name)
                        if cleaned_name != name:
                            self._name_to_symbol[cleaned_name] = symbol
                            
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Warning: Could not load {full_file}: {e}")
                continue
        
        self._loaded = True
        print(f"Loaded {len(self._symbol_to_name)} ticker mappings from US-Stock-Symbols")
    
    def _clean_company_name(self, name: str) -> str:
        """
        Clean company name for better matching.
        
        Args:
            name: Raw company name
            
        Returns:
            Cleaned company name
        """
        # Remove common suffixes and noise (order matters - longer first)
        suffixes_to_remove = [
            'CLASS A ORDINARY SHARES',
            'CLASS A COMMON STOCK',
            'CLASS B COMMON STOCK', 
            'COMMON STOCK',
            'ORDINARY SHARES',
            'CORPORATION',
            'CLASS A',
            'CLASS B',
            'INC.',
            'INC',
            'CORP.',
            'CORP',
            'LTD.',
            'LTD',
            'LLC',
            'LP',
            'CO.',
            'CO',
            'THE',
        ]
        
        cleaned = name.upper().strip()
        
        for suffix in suffixes_to_remove:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
        
        # Handle special cases
        cleaned = cleaned.replace('.COM', ' COM')  # Amazon.com -> Amazon COM
        
        # Remove extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def get_ticker(self, company_name: str) -> Optional[str]:
        """
        Get ticker symbol for a company name.
        
        Args:
            company_name: Company name from 13F filing
            
        Returns:
            Ticker symbol or None if not found
        """
        self._load_exchange_data()
        
        if not company_name:
            return None
        
        # Try exact match first
        name_upper = company_name.upper().strip()
        if name_upper in self._name_to_symbol:
            return self._name_to_symbol[name_upper]
        
        # Try cleaned match
        cleaned = self._clean_company_name(name_upper)
        if cleaned in self._name_to_symbol:
            return self._name_to_symbol[cleaned]
        
        # Try partial matching for common cases
        for known_name, symbol in self._name_to_symbol.items():
            if self._names_match(cleaned, known_name):
                return symbol
        
        return None
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """
        Check if two company names match using fuzzy logic.
        
        Args:
            name1: First company name (cleaned)
            name2: Second company name (cleaned)
            
        Returns:
            True if names likely refer to same company
        """
        # Simple fuzzy matching - can be enhanced later
        name1_words = set(name1.split())
        name2_words = set(name2.split())
        
        # Skip very short names to avoid false positives
        if len(name1_words) < 2 or len(name2_words) < 2:
            return False
        
        # Check if most significant words overlap
        common_words = name1_words.intersection(name2_words)
        
        # Require at least 70% word overlap
        min_words = min(len(name1_words), len(name2_words))
        overlap_ratio = len(common_words) / min_words if min_words > 0 else 0
        
        return overlap_ratio >= 0.7
    
    def get_all_tickers(self) -> Set[str]:
        """Get all known ticker symbols."""
        self._load_exchange_data()
        return set(self._symbol_to_name.keys())
    
    def get_stats(self) -> Dict[str, int]:
        """Get mapping statistics."""
        self._load_exchange_data()
        return {
            'total_symbols': len(self._symbol_to_name),
            'total_name_mappings': len(self._name_to_symbol),
        }


# Global instance for easy import
ticker_mapper = TickerMapper()


def infer_ticker_from_name(company_name: str) -> str:
    """
    Infer ticker from company name using comprehensive mapping.
    
    Args:
        company_name: Company name from 13F filing
        
    Returns:
        Ticker symbol or "UNKNOWN" if not found
    """
    ticker = ticker_mapper.get_ticker(company_name)
    return ticker if ticker else "UNKNOWN"
