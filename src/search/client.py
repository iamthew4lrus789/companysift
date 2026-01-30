"""
DuckDuckGo RapidAPI client for company website search.
"""

import requests
import time
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from src.core.exceptions import SearchAPIError, RateLimitError


@dataclass
class SearchResult:
    """Represents a single search result."""
    url: str
    title: str
    snippet: str
    position: int


class DuckDuckGoClient:
    """
    Client for DuckDuckGo RapidAPI search service.
    
    Provides rate-limited search functionality with retry logic
    and comprehensive error handling.
    """
    
    def __init__(self, api_key: str, rate_limit: float = 4.5):
        """
        Initialize the DuckDuckGo API client.
        
        Args:
            api_key: RapidAPI key for DuckDuckGo service
            rate_limit: Maximum requests per second (default: 4.5 for safety)
        
        Raises:
            ValueError: If API key is not provided or invalid
        """
        if not api_key or len(api_key.strip()) < 10:
            raise ValueError(
                "DuckDuckGo API key is required and must be at least 10 characters. "
                "Please set the DUCKDUCKGO_API_KEY environment variable. "
                "Get your API key from: https://rapidapi.com/duckduckgo/api/duckduckgo8"
            )
        
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.base_url = "https://duckduckgo8.p.rapidapi.com"
        self._last_request_time = 0.0
        self.max_retries = 5
        self.base_delay = 1
        self.max_delay = 120
        self.logger = logging.getLogger('company_sift')

    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search for company websites using DuckDuckGo API.
        
        Args:
            query: Search query (company name)
            max_results: Maximum number of results to return
            
        Returns:
            List of SearchResult objects
            
        Raises:
            SearchAPIError: For API errors, network issues, or invalid responses
            RateLimitError: When rate limit is exceeded
        """
        self._enforce_rate_limit()
        
        url = self.base_url  # RapidAPI uses base URL directly with query parameters
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "duckduckgo8.p.rapidapi.com"
        }
        params = {
            "q": query,
            "max_results": max_results
        }
        
        try:
            # Use retry logic for better resilience
            response = self._make_api_request_with_retry(url, headers, params)
            
            # Handle rate limiting
            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please wait before retrying.")
            
            # Handle other HTTP errors
            if response.status_code != 200:
                raise SearchAPIError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )
            
            # Parse JSON response
            try:
                data = response.json()
            except ValueError as e:
                raise SearchAPIError(f"Invalid JSON response: {e}")
            
            # Extract and validate results
            results = []
            raw_results = data.get("results", [])
            
            for position, result in enumerate(raw_results, 1):
                # Skip malformed results
                if not isinstance(result, dict):
                    continue
                
                url = result.get("url")
                title = result.get("title", "")
                description = result.get("description", "")
                
                # Skip results missing required URL
                if not url:
                    continue
                
                search_result = SearchResult(
                    url=url,
                    title=title,
                    snippet=description,
                    position=position
                )
                results.append(search_result)
            
            return results
            
        except requests.RequestException as e:
            raise SearchAPIError(f"Network error during search: {e}")
    
    def _make_api_request_with_retry(self, url: str, headers: Dict[str, str], params: Dict[str, str]) -> requests.Response:
        """
        Make API request with exponential backoff retry logic.
        
        Args:
            url: API endpoint URL
            headers: Request headers
            params: Query parameters
            
        Returns:
            Response object
            
        Raises:
            SearchAPIError: After all retries exhausted
        """
        attempt = 0
        last_exception = None
        
        while attempt <= self.max_retries:
            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
                # Check for rate limit response
                if response.status_code == 429:
                    self._adjust_rate_limit("429")
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    self.logger.warning(f"Rate limited. Retrying in {delay}s...")
                    time.sleep(delay)
                    attempt += 1
                    continue
                
                # Check for server errors
                if response.status_code >= 500:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    self.logger.warning(f"Server error {response.status_code}. Retrying in {delay}s...")
                    time.sleep(delay)
                    attempt += 1
                    continue
                
                return response
                
            except requests.RequestException as e:
                last_exception = e
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                self.logger.warning(f"Network error: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                attempt += 1
        
        raise SearchAPIError(f"API request failed after {self.max_retries} retries: {last_exception}")
    
    def _adjust_rate_limit(self, error_type: str) -> None:
        """
        Adjust rate limit based on error type.
        
        Args:
            error_type: Type of error ('429', '500', etc.)
        """
        if error_type == "429":
            # Rate limit error - reduce more aggressively
            self.rate_limit = max(2.0, self.rate_limit * 0.6)
            self.logger.warning(f"Reduced rate limit to {self.rate_limit} req/s due to rate limiting")
        elif error_type == "500":
            # Server error - reduce moderately
            self.rate_limit = max(3.0, self.rate_limit * 0.8)
            self.logger.warning(f"Reduced rate limit to {self.rate_limit} req/s due to server errors")
    
    def _enforce_rate_limit(self) -> None:
        """
        Enforce rate limiting by sleeping if necessary.
        """
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        min_interval = 1.0 / self.rate_limit
        
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()