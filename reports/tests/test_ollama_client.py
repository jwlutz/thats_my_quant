"""
Tests for Ollama client - mock server, timeouts, error paths.
No retry loops - fail closed if model unavailable.
"""

import pytest
import json
import os
from unittest.mock import patch, Mock
import requests
from dotenv import load_dotenv

# Load environment for testing
load_dotenv()

# Import Ollama client (will be created next)
from reports.ollama_client import (
    ollama_request,
    check_model_availability,
    OllamaError,
    OllamaTimeoutError,
    OllamaUnavailableError
)


class TestOllamaClient:
    """Tests for Ollama client functionality."""
    
    @patch('reports.ollama_client.check_model_availability', return_value=True)
    @patch('requests.post')
    def test_ollama_request_success(self, mock_post, mock_check_model):
        """Test successful Ollama request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': 'This is a test response from the model.'
        }
        mock_post.return_value = mock_response
        
        # Make request
        response = ollama_request(
            prompt="Test prompt",
            system_prompt="Test system prompt",
            model="llama3.1:8b"
        )
        
        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check URL
        assert 'localhost:11434' in call_args[0][0]
        
        # Check payload
        payload = call_args[1]['json']
        assert payload['model'] == 'llama3.1:8b'
        assert payload['prompt'] == 'Test prompt'
        assert payload['system'] == 'Test system prompt'
        assert payload['stream'] is False
        
        # Verify response
        assert response == 'This is a test response from the model.'
    
    @patch('reports.ollama_client.check_model_availability', return_value=True)
    @patch('requests.post')
    def test_ollama_request_timeout(self, mock_post, mock_check_model):
        """Test Ollama request timeout handling."""
        # Mock timeout
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        with pytest.raises(OllamaTimeoutError, match="Request timed out"):
            ollama_request(
                prompt="Test prompt",
                system_prompt="System prompt",
                timeout=30
            )
    
    @patch('reports.ollama_client.check_model_availability', return_value=True)
    @patch('requests.post')
    def test_ollama_request_connection_error(self, mock_post, mock_check_model):
        """Test Ollama connection error handling."""
        # Mock connection error
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        with pytest.raises(OllamaUnavailableError, match="Ollama service unavailable"):
            ollama_request(
                prompt="Test prompt",
                system_prompt="System prompt"
            )
    
    @patch('reports.ollama_client.check_model_availability', return_value=True)
    @patch('requests.post')
    def test_ollama_request_http_error(self, mock_post, mock_check_model):
        """Test Ollama HTTP error handling."""
        # Mock HTTP error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_post.return_value = mock_response
        
        with pytest.raises(OllamaError, match="HTTP 500"):
            ollama_request(
                prompt="Test prompt",
                system_prompt="System prompt"
            )
    
    @patch('reports.ollama_client.check_model_availability', return_value=True)
    @patch('requests.post')
    def test_ollama_request_invalid_json_response(self, mock_post, mock_check_model):
        """Test handling of invalid JSON response."""
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Invalid response"
        mock_post.return_value = mock_response
        
        with pytest.raises(OllamaError, match="Invalid JSON response"):
            ollama_request(
                prompt="Test prompt",
                system_prompt="System prompt"
            )
    
    @patch('requests.post')
    def test_ollama_request_missing_response_field(self, mock_post):
        """Test handling of response missing 'response' field."""
        # Mock response without 'response' field
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'model': 'llama3.1:8b',
            'created_at': '2025-09-06T14:30:00Z'
            # Missing 'response' field
        }
        mock_post.return_value = mock_response
        
        with pytest.raises(OllamaError, match="Missing 'response' field"):
            ollama_request(
                prompt="Test prompt",
                system_prompt="System prompt"
            )
    
    @patch('requests.post')
    def test_ollama_request_empty_response(self, mock_post):
        """Test handling of empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': ''  # Empty response
        }
        mock_post.return_value = mock_response
        
        with pytest.raises(OllamaError, match="Empty response from model"):
            ollama_request(
                prompt="Test prompt",
                system_prompt="System prompt"
            )


class TestModelAvailability:
    """Tests for model availability checking."""
    
    @patch('requests.get')
    def test_check_model_availability_success(self, mock_get):
        """Test successful model availability check."""
        # Mock successful tags response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [
                {'name': 'llama3.1:8b'},
                {'name': 'llama2:7b'},
                {'name': 'codellama:7b'}
            ]
        }
        mock_get.return_value = mock_response
        
        # Check availability
        available = check_model_availability('llama3.1:8b')
        
        assert available is True
        
        # Verify API call
        mock_get.assert_called_once()
        assert 'localhost:11434/api/tags' in mock_get.call_args[0][0]
    
    @patch('requests.get')
    def test_check_model_availability_model_not_found(self, mock_get):
        """Test model not available."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [
                {'name': 'llama2:7b'},  # Different model
                {'name': 'codellama:7b'}
            ]
        }
        mock_get.return_value = mock_response
        
        available = check_model_availability('llama3.1:8b')
        
        assert available is False
    
    @patch('requests.get')
    def test_check_model_availability_service_down(self, mock_get):
        """Test Ollama service unavailable."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        available = check_model_availability('llama3.1:8b')
        
        assert available is False
    
    @patch('requests.get')
    def test_check_model_availability_http_error(self, mock_get):
        """Test HTTP error from Ollama."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        available = check_model_availability('llama3.1:8b')
        
        assert available is False


class TestOllamaConfiguration:
    """Tests for Ollama configuration handling."""
    
    @patch.dict(os.environ, {
        'OLLAMA_BASE_URL': 'http://custom:8080',
        'OLLAMA_MODEL': 'custom-model:latest',
        'OLLAMA_TIMEOUT_S': '120',
        'OLLAMA_OPTIONS_JSON': '{"temperature": 0.7, "top_p": 0.9}'
    })
    @patch('requests.post')
    def test_ollama_request_custom_config(self, mock_post):
        """Test Ollama request with custom configuration."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'response': 'Custom response'}
        mock_post.return_value = mock_response
        
        response = ollama_request(
            prompt="Test with custom config",
            system_prompt="System prompt"
        )
        
        # Verify custom configuration used
        call_args = mock_post.call_args
        assert 'custom:8080' in call_args[0][0]
        
        payload = call_args[1]['json']
        assert payload['model'] == 'custom-model:latest'
        assert payload['options']['temperature'] == 0.7
        assert payload['options']['top_p'] == 0.9
        
        # Verify custom timeout
        assert call_args[1]['timeout'] == 120
    
    @patch.dict(os.environ, {'OLLAMA_OPTIONS_JSON': 'invalid json'})
    def test_ollama_request_invalid_options_json(self):
        """Test handling of invalid OLLAMA_OPTIONS_JSON."""
        with pytest.raises(OllamaError, match="Invalid OLLAMA_OPTIONS_JSON"):
            ollama_request(
                prompt="Test prompt",
                system_prompt="System prompt"
            )
    
    def test_ollama_request_missing_env_uses_defaults(self):
        """Test that missing environment variables use sensible defaults."""
        # Clear Ollama env vars
        with patch.dict(os.environ, {}, clear=True):
            with patch('requests.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {'response': 'Default response'}
                mock_post.return_value = mock_response
                
                ollama_request("Test", "System")
                
                # Should use defaults
                call_args = mock_post.call_args
                assert 'localhost:11434' in call_args[0][0]
                assert call_args[1]['timeout'] == 60  # Default timeout


class TestOllamaErrorHandling:
    """Tests for comprehensive error handling."""
    
    def test_ollama_clear_user_instructions(self):
        """Test that unavailable model gives clear user instructions."""
        with patch('reports.ollama_client.check_model_availability', return_value=False):
            with pytest.raises(OllamaUnavailableError) as exc_info:
                ollama_request("Test", "System", model="missing-model")
            
            error_msg = str(exc_info.value)
            assert 'ollama pull missing-model' in error_msg
            assert 'Model not available' in error_msg
    
    @patch('requests.post')
    def test_ollama_request_no_retries(self, mock_post):
        """Test that client doesn't retry on failure (fail closed)."""
        # Mock failure
        mock_post.side_effect = requests.exceptions.RequestException("Network error")
        
        with pytest.raises(OllamaError):
            ollama_request("Test", "System")
        
        # Should only call once (no retries)
        assert mock_post.call_count == 1
