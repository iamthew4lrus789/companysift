import pytest
import time
from unittest.mock import patch, Mock
from src.search.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test suite for RateLimiter."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(rate_limit=2.0)
        assert limiter.rate_limit == 2.0
        assert limiter.min_interval == 0.5  # 1/2.0

    def test_rate_limiter_wait_enforcement(self):
        """Test that rate limiter enforces minimum intervals."""
        limiter = RateLimiter(rate_limit=10.0)  # 0.1 second intervals
        
        with patch('time.sleep') as mock_sleep:
            # First call should not sleep
            limiter.wait_if_needed()
            mock_sleep.assert_not_called()
            
            # Immediate second call should sleep
            limiter.wait_if_needed()
            mock_sleep.assert_called_once()



    def test_rate_limiter_with_zero_rate(self):
        """Test that zero rate limit means no throttling."""
        limiter = RateLimiter(rate_limit=0.0)
        
        with patch('time.sleep') as mock_sleep:
            limiter.wait_if_needed()
            limiter.wait_if_needed()
            mock_sleep.assert_not_called()

    def test_rate_limiter_update_rate(self):
        """Test updating rate limit dynamically."""
        limiter = RateLimiter(rate_limit=2.0)
        assert limiter.min_interval == 0.5
        
        limiter.update_rate(4.0)
        assert limiter.rate_limit == 4.0
        assert limiter.min_interval == 0.25

    def test_rate_limiter_negative_rate(self):
        """Test that negative rate limit is treated as zero."""
        limiter = RateLimiter(rate_limit=-1.0)
        assert limiter.rate_limit == 0.0
        assert limiter.min_interval == 0.0

    def test_rate_limiter_actual_timing(self):
        """Test actual timing behavior (integration test)."""
        limiter = RateLimiter(rate_limit=5.0)  # 0.2 second intervals
        
        start_time = time.time()
        limiter.wait_if_needed()  # First call - no wait
        time1 = time.time()
        
        limiter.wait_if_needed()  # Second call - should wait
        time2 = time.time()
        
        # Second interval should be at least 0.2 seconds
        interval = time2 - time1
        assert interval >= 0.19  # Allow small margin for timing

    def test_rate_limiter_concurrent_access(self):
        """Test rate limiter behavior with rapid successive calls."""
        limiter = RateLimiter(rate_limit=100.0)  # 0.01 second intervals
        
        with patch('time.sleep') as mock_sleep:
            # Make multiple rapid calls
            for _ in range(5):
                limiter.wait_if_needed()
            
            # Should have slept 4 times (first call doesn't sleep)
            assert mock_sleep.call_count == 4