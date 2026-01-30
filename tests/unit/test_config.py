"""Tests for configuration management."""

import pytest
import yaml
import tempfile
import os
from pathlib import Path

from src.core.config import Config


class TestConfig:
    """Test configuration management functionality."""
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration data."""
        return {
            'search': {
                'provider': 'duckduckgo',
                'api_key': '${TEST_API_KEY}',
                'rate_limit': 4.5,
                'timeout': 30,
                'max_retries': 3,
                'retry_delay': 2
            },
            'scoring': {
                'min_confidence': 50,
                'weights': {
                    'domain_match': 0.4,
                    'tld_relevance': 0.2,
                    'search_position': 0.3,
                    'title_match': 0.1
                }
            },
            'processing': {
                'batch_size': 50,
                'max_candidates': 3
            },
            'filtering': {
                'blocklist': [
                    'companycheck.co.uk',
                    'globaldatabase.com'
                ]
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file': 'logs/company_sift.log'
            }
        }
    
    @pytest.fixture
    def config_file(self, sample_config):
        """Create temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)
    
    @pytest.fixture
    def mock_env_vars(self):
        """Set up environment variables for testing."""
        os.environ['TEST_API_KEY'] = 'test_key_123'
        yield
        # Cleanup
        if 'TEST_API_KEY' in os.environ:
            del os.environ['TEST_API_KEY']
    
    def test_config_loading(self, config_file, mock_env_vars):
        """Test basic configuration loading."""
        config = Config(config_file)
        
        assert config.get('search.provider') == 'duckduckgo'
        assert config.get('search.api_key') == 'test_key_123'
        assert config.get('search.rate_limit') == 4.5
    
    def test_environment_variable_substitution(self, config_file, mock_env_vars):
        """Test environment variable substitution."""
        config = Config(config_file)
        
        # API key should be substituted from environment
        assert config.get('search.api_key') == 'test_key_123'
    
    def test_missing_environment_variable(self, config_file):
        """Test handling of missing environment variables."""
        with pytest.raises(ValueError, match="Environment variable not set: TEST_API_KEY"):
            Config(config_file)
    
    def test_config_validation_success(self, config_file, mock_env_vars):
        """Test successful configuration validation."""
        config = Config(config_file)
        
        # Should not raise any exceptions
        assert config.validate() is True
    
    def test_config_validation_missing_section(self, config_file, mock_env_vars):
        """Test validation with missing configuration section."""
        config = Config(config_file)
        
        # Remove a required section
        config._config.pop('search')
        
        with pytest.raises(ValueError, match="Missing configuration section: search"):
            config.validate()
    
    def test_config_validation_invalid_weights(self, config_file, mock_env_vars):
        """Test validation with invalid scoring weights."""
        config = Config(config_file)
        
        # Make weights sum to more than 1.0
        config._config['scoring']['weights']['domain_match'] = 0.8
        
        with pytest.raises(ValueError, match="Scoring weights must sum to 1.0"):
            config.validate()
    
    def test_config_validation_invalid_confidence(self, config_file, mock_env_vars):
        """Test validation with invalid confidence threshold."""
        config = Config(config_file)
        
        # Set confidence outside valid range
        config._config['scoring']['min_confidence'] = 150
        
        with pytest.raises(ValueError, match="Min confidence must be between 0 and 100"):
            config.validate()
    
    def test_config_property_accessors(self, config_file, mock_env_vars):
        """Test configuration property accessors."""
        config = Config(config_file)
        
        search_config = config.search_config
        assert search_config['provider'] == 'duckduckgo'
        assert search_config['api_key'] == 'test_key_123'
        
        scoring_config = config.scoring_config
        assert scoring_config['min_confidence'] == 50
        assert len(scoring_config['weights']) == 4
    
    def test_get_with_default(self, config_file, mock_env_vars):
        """Test getting configuration values with defaults."""
        config = Config(config_file)
        
        # Existing key
        assert config.get('search.provider') == 'duckduckgo'
        
        # Non-existing key with default
        assert config.get('search.nonexistent', 'default_value') == 'default_value'
        
        # Non-existing nested key
        assert config.get('nonexistent.section.key') is None
    
    def test_invalid_yaml_file(self):
        """Test handling of invalid YAML files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid YAML configuration"):
                Config(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_missing_config_file(self):
        """Test handling of missing configuration files."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            Config("nonexistent/config.yaml")
    
    def test_api_key_validation_missing(self):
        """Test that missing API key raises ConfigurationError."""
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
            with pytest.raises(Exception) as exc_info:
                Config(temp_path)
            
            # Should raise either ConfigurationError or ValueError
            error_message = str(exc_info.value)
            assert "DuckDuckGo API key is required" in error_message
            assert "DUCKDUCKGO_API_KEY" in error_message
            
        finally:
            os.unlink(temp_path)
    
    def test_api_key_validation_too_short(self):
        """Test that short API key raises ConfigurationError."""
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
            with pytest.raises(Exception) as exc_info:
                Config(temp_path)
            
            # Should raise ConfigurationError for short API key
            error_message = str(exc_info.value)
            assert "DuckDuckGo API key is required" in error_message
            assert "DUCKDUCKGO_API_KEY" in error_message
            
        finally:
            os.unlink(temp_path)
    
    def test_api_key_validation_valid(self):
        """Test that valid API key passes validation."""
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
            # Should not raise any exceptions
            config = Config(temp_path)
            assert config.get('search.api_key') == 'valid-api-key-12345'
            assert config.validate() is True
            
        finally:
            os.unlink(temp_path)
    
    def test_api_key_validation_whitespace_only(self):
        """Test that whitespace-only API key raises ConfigurationError."""
        config_content = """
search:
  provider: "duckduckgo"
  api_key: "   "
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
            with pytest.raises(Exception) as exc_info:
                Config(temp_path)
            
            # Should raise ConfigurationError for whitespace-only API key
            error_message = str(exc_info.value)
            assert "DuckDuckGo API key is required" in error_message
            
        finally:
            os.unlink(temp_path)