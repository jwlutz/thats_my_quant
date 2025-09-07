"""
Tests for LangChain setup and environment validation.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
import warnings

from reports.langchain_setup import (
    validate_langchain_env,
    setup_langchain_env,
    check_langchain_imports,
    ensure_langchain_ready,
    get_langchain_status,
    LangChainSetupError
)


class TestValidateLangChainEnv:
    """Test LangChain environment validation."""
    
    def test_default_config_valid(self):
        """Test default configuration is valid."""
        with patch.dict(os.environ, {}, clear=True):
            result = validate_langchain_env()
            
            assert result['valid'] is True
            assert result['telemetry_enabled'] is False
            assert len(result['errors']) == 0
            assert len(result['warnings']) == 1  # Tracing disabled warning
    
    def test_tracing_enabled_with_api_key(self):
        """Test tracing enabled with valid API key."""
        env = {
            'LANGSMITH_TRACING': 'true',
            'LANGSMITH_API_KEY': 'test-key',
            'LANGSMITH_PROJECT': 'test-project'
        }
        
        with patch.dict(os.environ, env, clear=True):
            result = validate_langchain_env()
            
            assert result['valid'] is True
            assert result['telemetry_enabled'] is True
            assert len(result['errors']) == 0
            assert len(result['warnings']) == 1  # Tracing enabled warning
    
    def test_tracing_enabled_without_api_key(self):
        """Test tracing enabled without API key fails."""
        env = {
            'LANGSMITH_TRACING': 'true',
            'LANGSMITH_API_KEY': '',
            'LANGSMITH_PROJECT': 'test-project'
        }
        
        with patch.dict(os.environ, env, clear=True):
            result = validate_langchain_env()
            
            assert result['valid'] is False
            assert result['telemetry_enabled'] is True
            assert len(result['errors']) == 1
            assert "LANGSMITH_API_KEY is empty" in result['errors'][0]
    
    def test_tracing_enabled_without_project(self):
        """Test tracing enabled without project shows warning."""
        env = {
            'LANGSMITH_TRACING': 'true',
            'LANGSMITH_API_KEY': 'test-key',
            'LANGSMITH_PROJECT': ''
        }
        
        with patch.dict(os.environ, env, clear=True):
            result = validate_langchain_env()
            
            assert result['valid'] is True
            assert result['telemetry_enabled'] is True
            assert len(result['errors']) == 0
            assert len(result['warnings']) == 2  # Project warning + tracing warning


class TestSetupLangChainEnv:
    """Test LangChain environment setup."""
    
    def test_setup_default_env(self):
        """Test setup with default environment."""
        with patch.dict(os.environ, {}, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                setup_langchain_env()
                
                # Should show warning about disabled tracing
                assert len(w) == 1
                assert "tracing is disabled" in str(w[0].message)
                
                # Should set tracing to false
                assert os.environ.get('LANGSMITH_TRACING') == 'false'
    
    def test_setup_with_invalid_config(self):
        """Test setup fails with invalid configuration."""
        env = {
            'LANGSMITH_TRACING': 'true',
            'LANGSMITH_API_KEY': ''  # Invalid - empty key
        }
        
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(LangChainSetupError) as exc_info:
                setup_langchain_env()
            
            assert "LANGSMITH_API_KEY is empty" in str(exc_info.value)
    
    def test_setup_with_valid_tracing(self):
        """Test setup with valid tracing configuration."""
        env = {
            'LANGSMITH_TRACING': 'true',
            'LANGSMITH_API_KEY': 'test-key',
            'LANGSMITH_PROJECT': 'test-project'
        }
        
        with patch.dict(os.environ, env, clear=True):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                setup_langchain_env()
                
                # Should show warning about enabled tracing
                assert len(w) == 1
                assert "tracing is ENABLED" in str(w[0].message)


class TestCheckLangChainImports:
    """Test LangChain import checking."""
    
    def test_imports_available(self):
        """Test when all imports are available."""
        with patch('builtins.__import__') as mock_import:
            # Mock successful imports
            mock_import.return_value = MagicMock()
            
            result = check_langchain_imports()
            
            assert result['langchain_core'] is True
            assert result['langchain_ollama'] is True
            assert result['all_available'] is True
            assert len(result['errors']) == 0
    
    def test_imports_missing(self):
        """Test when imports are missing."""
        def mock_import_error(name, *args, **kwargs):
            if 'langchain' in name:
                raise ImportError(f"No module named '{name}'")
            return MagicMock()
        
        with patch('builtins.__import__', side_effect=mock_import_error):
            result = check_langchain_imports()
            
            assert result['langchain_core'] is False
            assert result['langchain_ollama'] is False
            assert result['all_available'] is False
            assert len(result['errors']) == 2
    
    def test_partial_imports_available(self):
        """Test when only some imports are available."""
        def mock_partial_import(name, *args, **kwargs):
            if 'langchain_ollama' in name:
                raise ImportError(f"No module named '{name}'")
            return MagicMock()
        
        with patch('builtins.__import__', side_effect=mock_partial_import):
            result = check_langchain_imports()
            
            assert result['langchain_core'] is True
            assert result['langchain_ollama'] is False
            assert result['all_available'] is False
            assert len(result['errors']) == 1


class TestEnsureLangChainReady:
    """Test comprehensive LangChain readiness check."""
    
    @patch('reports.langchain_setup.check_langchain_imports')
    @patch('reports.langchain_setup.setup_langchain_env')
    def test_ready_success(self, mock_setup, mock_imports):
        """Test successful readiness check."""
        mock_imports.return_value = {
            'langchain_core': True,
            'langchain_ollama': True,
            'all_available': True,
            'errors': []
        }
        
        # Should not raise
        ensure_langchain_ready()
        
        mock_imports.assert_called_once()
        mock_setup.assert_called_once()
    
    @patch('reports.langchain_setup.check_langchain_imports')
    def test_ready_imports_missing(self, mock_imports):
        """Test readiness check fails when imports missing."""
        mock_imports.return_value = {
            'langchain_core': False,
            'langchain_ollama': True,
            'all_available': False,
            'errors': ['langchain-core: No module named langchain_core']
        }
        
        with pytest.raises(LangChainSetupError) as exc_info:
            ensure_langchain_ready()
        
        assert "dependencies not available" in str(exc_info.value)
        assert "pip install" in str(exc_info.value)
    
    @patch('reports.langchain_setup.check_langchain_imports')
    @patch('reports.langchain_setup.setup_langchain_env')
    def test_ready_env_setup_fails(self, mock_setup, mock_imports):
        """Test readiness check fails when environment setup fails."""
        mock_imports.return_value = {
            'langchain_core': True,
            'langchain_ollama': True,
            'all_available': True,
            'errors': []
        }
        mock_setup.side_effect = LangChainSetupError("Test error")
        
        with pytest.raises(LangChainSetupError):
            ensure_langchain_ready()


class TestGetLangChainStatus:
    """Test comprehensive status reporting."""
    
    @patch('reports.langchain_setup.check_langchain_imports')
    @patch('reports.langchain_setup.validate_langchain_env')
    def test_status_ready(self, mock_env, mock_imports):
        """Test status when everything is ready."""
        mock_imports.return_value = {
            'langchain_core': True,
            'langchain_ollama': True,
            'all_available': True,
            'errors': []
        }
        mock_env.return_value = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'telemetry_enabled': False
        }
        
        result = get_langchain_status()
        
        assert result['ready'] is True
        assert result['imports']['all_available'] is True
        assert result['environment']['valid'] is True
    
    @patch('reports.langchain_setup.check_langchain_imports')
    @patch('reports.langchain_setup.validate_langchain_env')
    def test_status_not_ready(self, mock_env, mock_imports):
        """Test status when not ready."""
        mock_imports.return_value = {
            'langchain_core': False,
            'langchain_ollama': True,
            'all_available': False,
            'errors': ['Missing langchain-core']
        }
        mock_env.return_value = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'telemetry_enabled': False
        }
        
        result = get_langchain_status()
        
        assert result['ready'] is False
        assert result['imports']['all_available'] is False
        assert result['environment']['valid'] is True
