import pytest
import requests
from unittest.mock import Mock, patch
from src.search.client import DuckDuckGoClient, SearchResult
from src.core.exceptions import SearchAPIError, RateLimitError


class TestDuckDuckGoClient:
    """Test suite for DuckDuckGo RapidAPI client."""

    def test_client_initialization(self):
        """Test client initialization with API key."""
        client = DuckDuckGoClient(api_key="test_key_12345")
        assert client.api_key == "test_key_12345"
        assert client.base_url == "https://duckduckgo8.p.rapidapi.com"
        assert client.rate_limit == 4.5

    def test_search_result_model(self):
        """Test SearchResult data model."""
        result = SearchResult(
            url="https://example.com",
            title="Example Company",
            snippet="Company description",
            position=1
        )
        assert result.url == "https://example.com"
        assert result.title == "Example Company"
        assert result.snippet == "Company description"
        assert result.position == 1

    @patch('src.search.client.requests.get')
    def test_successful_search(self, mock_get):
        """Test successful search query."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Example Company Ltd",
                    "description": "Leading example company"
                },
                {
                    "url": "https://another-example.co.uk",
                    "title": "Another Example",
                    "description": "Another company"
                }
            ]
        }
        mock_get.return_value = mock_response

        client = DuckDuckGoClient(api_key="test_key")
        results = client.search("Example Company Ltd")

        assert len(results) == 2
        assert results[0].url == "https://example.com"
        assert results[0].title == "Example Company Ltd"
        assert results[0].snippet == "Leading example company"
        assert results[0].position == 1

        assert results[1].url == "https://another-example.co.uk"
        assert results[1].position == 2

    @patch('src.search.client.requests.get')
    def test_empty_search_results(self, mock_get):
        """Test handling of empty search results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        client = DuckDuckGoClient(api_key="test_key")
        results = client.search("Nonexistent Company")

        assert results == []

    @patch('src.search.client.requests.get')
    def test_api_error_handling(self, mock_get):
        """Test handling of API errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        client = DuckDuckGoClient(api_key="test_key")
        
        with pytest.raises(SearchAPIError) as exc_info:
            client.search("Test Company")
        
        assert "API request failed" in str(exc_info.value)
        assert "500" in str(exc_info.value)

    @patch('src.search.client.requests.get')
    def test_rate_limit_error(self, mock_get):
        """Test handling of rate limit errors (429)."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_get.return_value = mock_response

        client = DuckDuckGoClient(api_key="test_key")
        
        with pytest.raises(RateLimitError) as exc_info:
            client.search("Test Company")
        
        assert "Rate limit exceeded" in str(exc_info.value)

    @patch('src.search.client.requests.get')
    def test_network_error_handling(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = requests.RequestException("Network error")

        client = DuckDuckGoClient(api_key="test_key")
        
        with pytest.raises(SearchAPIError) as exc_info:
            client.search("Test Company")
        
        assert "Network error" in str(exc_info.value)

    @patch('src.search.client.requests.get')
    def test_invalid_json_response(self, mock_get):
        """Test handling of invalid JSON responses."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not valid JSON"
        mock_get.return_value = mock_response

        client = DuckDuckGoClient(api_key="test_key")
        
        with pytest.raises(SearchAPIError) as exc_info:
            client.search("Test Company")
        
        assert "Invalid JSON response" in str(exc_info.value)

    @patch('src.search.client.requests.get')
    def test_malformed_result_data(self, mock_get):
        """Test handling of malformed result data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://valid.com",
                    "title": "Valid Company"
                    # Missing description
                },
                {
                    # Missing required fields
                    "title": "Incomplete"
                }
            ]
        }
        mock_get.return_value = mock_response

        client = DuckDuckGoClient(api_key="test_key")
        results = client.search("Test Company")

        # Should only include valid results
        assert len(results) == 1
        assert results[0].url == "https://valid.com"
        assert results[0].title == "Valid Company"
        assert results[0].snippet == ""  # Empty description

    @patch('src.search.client.requests.get')
    def test_request_headers(self, mock_get):
        """Test that correct headers are sent with requests."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        client = DuckDuckGoClient(api_key="test_key_123")
        client.search("Test Company")

        # Verify the request was made with correct headers
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        assert "headers" in call_args.kwargs
        headers = call_args.kwargs["headers"]
        assert headers["X-RapidAPI-Key"] == "test_key_123"
        assert headers["X-RapidAPI-Host"] == "duckduckgo8.p.rapidapi.com"

    @patch('src.search.client.requests.get')
    def test_query_parameters(self, mock_get):
        """Test that correct query parameters are sent."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        client = DuckDuckGoClient(api_key="test_key")
        client.search("Acme Corporation")

        # Verify the request was made with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        assert "params" in call_args.kwargs
        params = call_args.kwargs["params"]
        assert params["q"] == "Acme Corporation"

    def test_rate_limiting_property(self):
        """Test that rate limit can be configured."""
        client = DuckDuckGoClient(api_key="test_key_12345", rate_limit=3.0)
        assert client.rate_limit == 3.0
    
    def test_client_initialization_empty_api_key(self):
        """Test that empty API key raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DuckDuckGoClient(api_key="")
        
        error_message = str(exc_info.value)
        assert "DuckDuckGo API key is required" in error_message
        assert "DUCKDUCKGO_API_KEY" in error_message
        assert "https://rapidapi.com/duckduckgo/api/duckduckgo8" in error_message
    
    def test_client_initialization_short_api_key(self):
        """Test that short API key raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DuckDuckGoClient(api_key="short")
        
        error_message = str(exc_info.value)
        assert "DuckDuckGo API key is required" in error_message
        assert "at least 10 characters" in error_message
    
    def test_client_initialization_whitespace_api_key(self):
        """Test that whitespace-only API key raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            DuckDuckGoClient(api_key="   ")
        
        error_message = str(exc_info.value)
        assert "DuckDuckGo API key is required" in error_message
    
    def test_client_initialization_valid_api_key(self):
        """Test that valid API key allows client creation."""
        # This should not raise any exceptions
        client = DuckDuckGoClient(api_key="valid-api-key-12345")
        assert client.api_key == "valid-api-key-12345"
        assert client.base_url == "https://duckduckgo8.p.rapidapi.com"
        assert client.rate_limit == 4.5
    
    def test_client_initialization_boundary_length(self):
        """Test API key with exactly 10 characters (minimum valid length)."""
        # 10 character API key should be valid
        client = DuckDuckGoClient(api_key="1234567890")
        assert client.api_key == "1234567890"
    
    def test_client_initialization_nine_characters(self):
        """Test API key with 9 characters (should fail)."""
        with pytest.raises(ValueError) as exc_info:
            DuckDuckGoClient(api_key="123456789")
        
        error_message = str(exc_info.value)
        assert "DuckDuckGo API key is required" in error_message