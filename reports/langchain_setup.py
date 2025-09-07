"""
LangChain setup and environment guard for polish-only LLM chains.
Ensures telemetry is disabled by default and validates dependencies.
"""

import os
import warnings
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LangChainSetupError(Exception):
    """Raised when LangChain setup fails."""
    pass


def validate_langchain_env() -> Dict[str, Any]:
    """
    Validate LangChain environment configuration.
    
    Returns:
        Dictionary with validation results and warnings
    """
    validation = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'telemetry_enabled': False
    }
    
    # Check telemetry settings
    tracing_enabled = os.getenv('LANGSMITH_TRACING', 'false').lower() == 'true'
    
    if tracing_enabled:
        validation['telemetry_enabled'] = True
        api_key = os.getenv('LANGSMITH_API_KEY', '').strip()
        project = os.getenv('LANGSMITH_PROJECT', '').strip()
        
        if not api_key:
            validation['errors'].append("LANGSMITH_TRACING=true but LANGSMITH_API_KEY is empty")
            validation['valid'] = False
        
        if not project:
            validation['warnings'].append("LANGSMITH_PROJECT not set, using default project name")
        
        validation['warnings'].append(
            "LangSmith tracing is ENABLED. This may send data to external services. "
            "Set LANGSMITH_TRACING=false to disable."
        )
    else:
        validation['warnings'].append("LangSmith tracing is disabled (recommended for local-first usage)")
    
    return validation


def setup_langchain_env() -> None:
    """
    Set up LangChain environment with proper defaults.
    Ensures telemetry is disabled unless explicitly enabled.
    """
    validation = validate_langchain_env()
    
    # Show warnings
    for warning in validation['warnings']:
        warnings.warn(f"LangChain Setup: {warning}", UserWarning)
    
    # Fail on errors
    if not validation['valid']:
        error_msg = "LangChain setup failed:\n" + "\n".join(f"- {err}" for err in validation['errors'])
        raise LangChainSetupError(error_msg)
    
    # Ensure telemetry is disabled if not explicitly enabled
    if not validation['telemetry_enabled']:
        os.environ['LANGSMITH_TRACING'] = 'false'
        # Clear any existing keys to be safe
        os.environ.pop('LANGSMITH_API_KEY', None)


def check_langchain_imports() -> Dict[str, Any]:
    """
    Check if required LangChain packages can be imported.
    
    Returns:
        Dictionary with import status
    """
    import_status = {
        'langchain_core': False,
        'langchain_ollama': False,
        'all_available': False,
        'errors': []
    }
    
    try:
        import langchain_core  # noqa: F401
        import_status['langchain_core'] = True
    except ImportError as e:
        import_status['errors'].append(f"langchain-core: {e}")
    
    try:
        import langchain_ollama  # noqa: F401
        import_status['langchain_ollama'] = True
    except ImportError as e:
        import_status['errors'].append(f"langchain-ollama: {e}")
    
    import_status['all_available'] = (
        import_status['langchain_core'] and 
        import_status['langchain_ollama']
    )
    
    return import_status


def ensure_langchain_ready() -> None:
    """
    Ensure LangChain is properly set up and ready to use.
    
    Raises:
        LangChainSetupError: If setup fails
    """
    # Check imports first
    import_status = check_langchain_imports()
    
    if not import_status['all_available']:
        error_msg = "LangChain dependencies not available:\n"
        error_msg += "\n".join(f"- {err}" for err in import_status['errors'])
        error_msg += "\n\nInstall with: pip install langchain-core langchain-ollama"
        raise LangChainSetupError(error_msg)
    
    # Set up environment
    setup_langchain_env()


def get_langchain_status() -> Dict[str, Any]:
    """
    Get comprehensive LangChain setup status.
    
    Returns:
        Dictionary with complete status information
    """
    status = {
        'imports': check_langchain_imports(),
        'environment': validate_langchain_env(),
        'ready': False
    }
    
    status['ready'] = (
        status['imports']['all_available'] and 
        status['environment']['valid']
    )
    
    return status
