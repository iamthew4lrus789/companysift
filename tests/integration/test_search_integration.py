import pytest
from unittest.mock import patch, Mock
from src.search.client import DuckDuckGoClient
from src.search.rate_limiter import RateLimiter


class TestSearchIntegration:
    """Integration tests for search functionality."""

    @patch('src.search.client.requests.get')
    def test_search_with_rate_limiting(self, mock_get):
        """Test that search client properly uses rate limiting."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Example Company",
                    "description": "Test company"
                }
            ]
        }
        mock_get.return_value = mock_response

        # Create client with rate limiting
        client = DuckDuckGoClient(api_key="test_key", rate_limit=2.0)  # 2 req/sec
        
        # Perform multiple searches
        results1 = client.search("Company One")
        results2 = client.search("Company Two")
        
        # Verify both searches returned results
        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0].url == "https://example.com"
        assert results2[0].url == "https://example.com"
        
        # Verify API was called twice
        assert mock_get.call_count == 2

    @patch('src.search.client.requests.get')
    def test_search_rate_limiting_enforced(self, mock_get):
        """Test that rate limiting is actually enforced between requests."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        client = DuckDuckGoClient(api_key="test_key", rate_limit=5.0)  # 5 req/sec
        
        with patch('time.sleep') as mock_sleep:
            # Perform multiple rapid searches
            client.search("Company One")
            client.search("Company Two")
            client.search("Company Three")
            
            # Should have slept twice (between 1st-2nd and 2nd-3rd calls)
            assert mock_sleep.call_count == 2

    @patch('src.search.client.requests.get')
    def test_search_error_recovery(self, mock_get):
        """Test that search client handles errors and continues working."""
        # First call fails, second call succeeds
        mock_error_response = Mock()
        mock_error_response.status_code = 500
        mock_error_response.text = "Server Error"
        
        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {
            "results": [{"url": "https://success.com", "title": "Success", "description": "OK"}]
        }
        
        mock_get.side_effect = [mock_error_response, mock_success_response]

        client = DuckDuckGoClient(api_key="test_key")
        
        # First search should fail
        from src.core.exceptions import SearchAPIError
        with pytest.raises(SearchAPIError):
            client.search("Failing Company")
        
        # Second search should succeed
        results = client.search("Successful Company")
        assert len(results) == 1
        assert results[0].url == "https://success.com"

    def test_client_integration_with_rate_limiter(self):
        """Test that client properly integrates with rate limiter."""
        client = DuckDuckGoClient(api_key="test_key", rate_limit=3.0)
        
        # Verify rate limiter is configured correctly
        assert client.rate_limit == 3.0
        assert client._last_request_time == 0.0
        
        # Rate limiter should be enforced on each search
        with patch.object(client, '_enforce_rate_limit') as mock_enforce:
            with patch('src.search.client.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"results": []}
                mock_get.return_value = mock_response
                
                client.search("Test Company")
                mock_enforce.assert_called_once()