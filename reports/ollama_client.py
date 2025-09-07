"""
Ollama client for LLM narrative generation.
Minimal client with timeout and options. Fail closed if model unavailable.
"""

import os
import json
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class OllamaError(Exception):
    """Base exception for Ollama client errors."""
    pass


class OllamaTimeoutError(OllamaError):
    """Raised when Ollama request times out."""
    pass


class OllamaUnavailableError(OllamaError):
    """Raised when Ollama service or model is unavailable."""
    pass


def ollama_request(
    prompt: str,
    system_prompt: str,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
    options: Optional[Dict[str, Any]] = None
) -> str:
    """
    Make request to Ollama for text generation.
    
    Args:
        prompt: User prompt for the model
        system_prompt: System prompt for context
        model: Model name (defaults to env OLLAMA_MODEL)
        timeout: Request timeout in seconds (defaults to env OLLAMA_TIMEOUT_S)
        options: Model options (defaults to env OLLAMA_OPTIONS_JSON)
        
    Returns:
        Generated text response
        
    Raises:
        OllamaError: If request fails
        OllamaTimeoutError: If request times out
        OllamaUnavailableError: If service or model unavailable
    """
    # Get configuration from environment
    base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    model = model or os.getenv('OLLAMA_MODEL', 'llama3.1:8b')
    timeout = timeout or int(os.getenv('OLLAMA_TIMEOUT_S', '60'))
    
    # Parse options from environment
    if options is None:
        options_json = os.getenv('OLLAMA_OPTIONS_JSON', '{}')
        try:
            options = json.loads(options_json) if options_json else {}
        except json.JSONDecodeError:
            raise OllamaError(f"Invalid OLLAMA_OPTIONS_JSON: {options_json}")
    
    # Check model availability first
    if not check_model_availability(model, base_url):
        raise OllamaUnavailableError(
            f"Model '{model}' not available. "
            f"Please run: ollama pull {model}"
        )
    
    # Prepare request
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        'model': model,
        'prompt': prompt,
        'system': system_prompt,
        'stream': False,
        'options': options
    }
    
    try:
        # Make request
        response = requests.post(
            url,
            json=payload,
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )
        
        # Check HTTP status
        if response.status_code != 200:
            raise OllamaError(f"HTTP {response.status_code}: {response.text}")
        
        # Parse JSON response
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            raise OllamaError(f"Invalid JSON response: {response.text}")
        
        # Extract generated text
        if 'response' not in response_data:
            raise OllamaError(f"Missing 'response' field in: {response_data}")
        
        generated_text = response_data['response']
        
        if not generated_text or generated_text.strip() == '':
            raise OllamaError("Empty response from model")
        
        return generated_text.strip()
        
    except requests.exceptions.Timeout:
        raise OllamaTimeoutError(f"Request timed out after {timeout}s")
    
    except requests.exceptions.ConnectionError:
        raise OllamaUnavailableError(
            f"Ollama service unavailable at {base_url}. "
            f"Please ensure Ollama is running: ollama serve"
        )
    
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"Request failed: {e}")


def check_model_availability(
    model: str,
    base_url: Optional[str] = None
) -> bool:
    """
    Check if specified model is available in Ollama.
    
    Args:
        model: Model name to check
        base_url: Ollama base URL (defaults to env)
        
    Returns:
        True if model is available, False otherwise
    """
    if base_url is None:
        base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    
    try:
        # Get list of available models
        url = f"{base_url.rstrip('/')}/api/tags"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return False
        
        data = response.json()
        models = data.get('models', [])
        
        # Check if our model is in the list
        for model_info in models:
            if model_info.get('name') == model:
                return True
        
        return False
        
    except Exception:
        return False


def get_ollama_status() -> Dict[str, Any]:
    """
    Get comprehensive Ollama service status.
    
    Returns:
        Dictionary with service and model status
    """
    base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    model = os.getenv('OLLAMA_MODEL', 'llama3.1:8b')
    
    status = {
        'service_url': base_url,
        'service_available': False,
        'model_name': model,
        'model_available': False,
        'available_models': [],
        'error': None
    }
    
    try:
        # Check service availability
        response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=10)
        
        if response.status_code == 200:
            status['service_available'] = True
            
            # Get available models
            data = response.json()
            models = data.get('models', [])
            status['available_models'] = [m.get('name') for m in models]
            
            # Check if our model is available
            status['model_available'] = model in status['available_models']
            
        else:
            status['error'] = f"HTTP {response.status_code}: {response.text}"
            
    except requests.exceptions.ConnectionError:
        status['error'] = f"Cannot connect to Ollama at {base_url}"
    except Exception as e:
        status['error'] = str(e)
    
    return status


def validate_ollama_setup() -> Dict[str, Any]:
    """
    Validate complete Ollama setup for report generation.
    
    Returns:
        Dictionary with validation results and user instructions
    """
    validation = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'instructions': []
    }
    
    # Check environment variables
    base_url = os.getenv('OLLAMA_BASE_URL')
    model = os.getenv('OLLAMA_MODEL')
    
    if not base_url:
        validation['warnings'].append("OLLAMA_BASE_URL not set, using default: http://localhost:11434")
    
    if not model:
        validation['warnings'].append("OLLAMA_MODEL not set, using default: llama3.1:8b")
        model = 'llama3.1:8b'
    
    # Check service status
    status = get_ollama_status()
    
    if not status['service_available']:
        validation['valid'] = False
        validation['errors'].append(f"Ollama service not available: {status['error']}")
        validation['instructions'].append("Start Ollama service: ollama serve")
    
    elif not status['model_available']:
        validation['valid'] = False
        validation['errors'].append(f"Model '{model}' not available")
        validation['instructions'].append(f"Pull model: ollama pull {model}")
        
        if status['available_models']:
            validation['instructions'].append(f"Available models: {', '.join(status['available_models'])}")
    
    return validation
