"""Configuration management for Company Website Discovery Tool."""

import os
import yaml
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from src.core.exceptions import ConfigurationError


class Config:
    """Configuration manager for the application."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to YAML configuration file
        """
        # Track API key source and file path
        env_api_key = os.getenv('DUCKDUCKGO_API_KEY')
        dotenv_path = os.path.join(os.getcwd(), '.env')
        
        load_dotenv()  # Load environment variables from .env file
        self.config_path = config_path
        
        # Log API key source for debugging with file path
        api_key_after_dotenv = os.getenv('DUCKDUCKGO_API_KEY')
        
        import logging
        logger = logging.getLogger('company_sift')
        
        if env_api_key and not api_key_after_dotenv:
            logger.info("✅ API key loaded from environment variable")
        elif not env_api_key and api_key_after_dotenv:
            logger.info(f"✅ API key loaded from .env file: {dotenv_path}")
        elif env_api_key and api_key_after_dotenv:
            logger.info("✅ API key loaded from environment (already set)")
        else:
            logger.warning("⚠️  DUCKDUCKGO_API_KEY not found in environment or .env file")
        
        if api_key_after_dotenv:
            logger.info(f"   API key length: {len(api_key_after_dotenv)} characters")
        
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file)
            return self._process_env_variables(config)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")
    
    def _process_env_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Process environment variable placeholders in configuration."""
        def process_value(value):
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                env_value = os.getenv(env_var)
                if env_value is None:
                    raise ValueError(f"Environment variable not set: {env_var}")
                return env_value
            elif isinstance(value, dict):
                return {k: process_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            return value
         
        processed_config = process_value(config)  # type: ignore
        
        # Validate API key specifically
        search_config = processed_config.get('search', {})
        api_key = search_config.get('api_key', '')
        if api_key and len(api_key.strip()) >= 10:
            # API key is valid, continue
            pass
        elif api_key:
            # API key exists but is too short
            raise ConfigurationError(
                "DuckDuckGo API key is required but not properly configured. "
                "Please set the DUCKDUCKGO_API_KEY environment variable. "
                "Get your API key from: https://rapidapi.com/duckduckgo/api/duckduckgo8"
            )
        else:
            # API key is missing or empty
            raise ConfigurationError(
                "DuckDuckGo API key is required but not properly configured. "
                "Please set the DUCKDUCKGO_API_KEY environment variable. "
                "Get your API key from: https://rapidapi.com/duckduckgo/api/duckduckgo8"
            )
        
        return processed_config  # type: ignore
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated key path (e.g., 'search.rate_limit')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    @property
    def search_config(self) -> Dict[str, Any]:
        """Get search configuration section."""
        return self._config.get('search', {})
    
    @property
    def scoring_config(self) -> Dict[str, Any]:
        """Get scoring configuration section."""
        return self._config.get('scoring', {})
    
    @property
    def processing_config(self) -> Dict[str, Any]:
        """Get processing configuration section."""
        return self._config.get('processing', {})
    
    @property
    def filtering_config(self) -> Dict[str, Any]:
        """Get filtering configuration section."""
        return self._config.get('filtering', {})
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Get logging configuration section."""
        return self._config.get('logging', {})

    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration as dictionary.
        
        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()
    
    def validate(self) -> bool:
        """Validate configuration completeness.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        required_sections = ['search', 'scoring', 'processing', 'filtering', 'logging']
        
        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"Missing configuration section: {section}")
        
        # Validate search configuration
        search = self.search_config
        if 'api_key' not in search or not search['api_key']:
            raise ValueError("Search API key is required")
        
        if 'rate_limit' not in search or search['rate_limit'] <= 0:
            raise ValueError("Search rate limit must be positive")
        
        # Validate scoring configuration
        scoring = self.scoring_config
        if 'min_confidence' not in scoring or not (0 <= scoring['min_confidence'] <= 100):
            raise ValueError("Min confidence must be between 0 and 100")
        
        if 'weights' not in scoring:
            raise ValueError("Scoring weights configuration is required")
        
        weights = scoring['weights']
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.01:  # Allow small floating point errors
            raise ValueError(f"Scoring weights must sum to 1.0, got {weight_sum}")
        
        # Validate processing configuration
        processing = self.processing_config
        if 'batch_size' not in processing or processing['batch_size'] <= 0:
            raise ValueError("Batch size must be positive")
        
        return True