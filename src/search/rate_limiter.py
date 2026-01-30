"""
Rate limiting implementation for API requests.
"""

import time
from typing import Optional


class RateLimiter:
    """
    Simple rate limiter that enforces minimum time intervals between requests.
    
    This implementation uses a simple timing-based approach where it tracks
    the last request time and sleeps if necessary to maintain the desired
    request rate.
    """
    
    def __init__(self, rate_limit: float):
        """
        Initialize the rate limiter.
        
        Args:
            rate_limit: Maximum requests per second (0.0 = no limit)
        """
        self.rate_limit = max(0.0, rate_limit)  # Ensure non-negative
        self.min_interval = 1.0 / self.rate_limit if self.rate_limit > 0 else 0.0
        self._last_request_time = 0.0

    def wait_if_needed(self) -> None:
        """
        Wait if necessary to maintain the rate limit.
        
        This method should be called before each request. It will sleep
        for the minimum time required to maintain the configured rate limit.
        """
        if self.rate_limit <= 0:
            return  # No rate limiting
            
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()

    def update_rate(self, new_rate: float) -> None:
        """
        Update the rate limit dynamically.
        
        Args:
            new_rate: New maximum requests per second
        """
        self.rate_limit = max(0.0, new_rate)
        self.min_interval = 1.0 / self.rate_limit if self.rate_limit > 0 else 0.0