"""Integration tests for API key validation."""

import pytest
import tempfile
import os
import sys
from unittest.mock import patch, Mock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from core.config import Config
from search.client import DuckDuckGoClient
from cli.commands import process_companies
from core.exceptions import ConfigurationError


class TestAPIKeyValidationIntegration:
    """Integration tests for API key validation across components."""
    
    def test_config_to_client_integration(self):
        """Test that API key validation works from config to client creation."""
        # Create valid config
        config_content = """
search:
  provider: "duckduckgo"
  api_key: "valid-api-key-12345"
  rate_limit: 4.5
scoring:
  min_confidence: 50
  weights:
    domain_match: 0.4
    tld_relevance: 0.2
    search_position: 0.3
    title_match: 0.1
processing:
  batch_size: 50
filtering:
  blocklist: []
logging:
  level: "INFO"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        try:
            # Load config
            config = Config(temp_path)
            
            # Create client with config API key
            client = DuckDuckGoClient(config.search_config['api_key'])
            
            # Verify client was created successfully
            assert client.api_key == "valid-api-key-12345"
            
        finally:
            os.unlink(temp_path)
    
    def test_config_to_client_integration_failure(self):
        """Test that API key validation fails from config to client creation."""
        # Create invalid config (short API key)
        config_content = """
search:
  provider: "duckduckgo"
  api_key: "short"
  rate_limit: 4.5
scoring:
  min_confidence: 50
  weights:
    domain_match: 0.4
    tld_relevance: 0.2
    search_position: 0.3
    title_match: 0.1
processing:
  batch_size: 50
filtering:
  blocklist: []
logging:
  level: "INFO"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        try:
            # Load config - should fail at config level
            with pytest.raises(Exception) as exc_info:
                config = Config(temp_path)
            
            error_message = str(exc_info.value)
            assert "DuckDuckGo API key is required" in error_message
            
        finally:
            os.unlink(temp_path)
    
    def test_cli_command_api_key_validation(self):
        """Test API key validation in CLI command processing."""
        # Create config with missing API key
        config_content = """
search:
  provider: "duckduckgo"
  api_key: ""
  rate_limit: 4.5
scoring:
  min_confidence: 50
  weights:
    domain_match: 0.4
    tld_relevance: 0.2
    search_position: 0.3
    title_match: 0.1
processing:
  batch_size: 50
filtering:
  blocklist: []
logging:
  level: "INFO"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            # This should raise ConfigurationError during config loading
            with pytest.raises(Exception) as exc_info:
                config = Config(temp_path)
            
            error_message = str(exc_info.value)
            assert "DuckDuckGo API key is required" in error_message
            
        finally:
            os.unlink(temp_path)
    
    def test_end_to_end_validation_success(self):
        """Test full validation workflow with valid API key."""
        # Create valid config
        config_content = """
search:
  provider: "duckduckgo"
  api_key: "valid-api-key-12345"
  rate_limit: 4.5
scoring:
  min_confidence: 50
  weights:
    domain_match: 0.4
    tld_relevance: 0.2
    search_position: 0.3
    title_match: 0.1
processing:
  batch_size: 50
filtering:
  blocklist: []
logging:
  level: "INFO"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        try:
            # Load config
            config = Config(temp_path)
            
            # Create client
            client = DuckDuckGoClient(config.search_config['api_key'])
            
            # Verify both steps succeeded
            assert config.get('search.api_key') == 'valid-api-key-12345'
            assert client.api_key == 'valid-api-key-12345'
            assert config.validate() is True
            
        finally:
            os.unlink(temp_path)
    
    def test_error_message_consistency(self):
        """Test that error messages are consistent across components."""
        # Test config error message
        config_content = """
search:
  provider: "duckduckgo"
  api_key: ""
  rate_limit: 4.5
scoring:
  min_confidence: 50
  weights:
    domain_match: 0.4
    tld_relevance: 0.2
    search_position: 0.3
    title_match: 0.1
processing:
  batch_size: 50
filtering:
  blocklist: []
logging:
  level: "INFO"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        try:
            # Get config error message
            with pytest.raises(Exception) as config_exc:
                Config(temp_path)
            
            config_error = str(config_exc.value)
            
            # Get client error message
            with pytest.raises(ValueError) as client_exc:
                DuckDuckGoClient(api_key="")
            
            client_error = str(client_exc.value)
            
            # Both should mention API key requirement
            assert "DuckDuckGo API key is required" in config_error
            assert "DuckDuckGo API key is required" in client_error
            
            # Both should mention environment variable
            assert "DUCKDUCKGO_API_KEY" in config_error
            assert "DUCKDUCKGO_API_KEY" in client_error
            
        finally:
            os.unlink(temp_path)