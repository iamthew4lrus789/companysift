import pytest
from unittest.mock import Mock
from src.filtering.blocklist import BlocklistFilter
from src.search.client import SearchResult


class TestBlocklistFilter:
    """Test suite for aggregator site blocklist filtering."""

    def test_blocklist_initialization(self):
        """Test blocklist filter initialization."""
        blocklist = ["companycheck.co.uk", "globaldatabase.com"]
        filter_obj = BlocklistFilter(blocklist)
        assert filter_obj.blocklist == blocklist
        assert len(filter_obj.blocklist) == 2

    def test_blocklist_filtering(self):
        """Test filtering of aggregator sites."""
        blocklist = ["companycheck.co.uk", "globaldatabase.com"]
        filter_obj = BlocklistFilter(blocklist)

        # Create mock search results
        results = [
            SearchResult("https://example.com", "Example Company", "Good result", 1),
            SearchResult("https://companycheck.co.uk/company/123", "Company Check", "Aggregator", 2),
            SearchResult("https://globaldatabase.com/company/456", "Global Database", "Aggregator", 3),
            SearchResult("https://real-company.co.uk", "Real Company", "Real website", 4),
        ]

        filtered = filter_obj.filter_results(results)
        
        # Should only keep non-blocklisted results
        assert len(filtered) == 2
        assert filtered[0].url == "https://example.com"
        assert filtered[1].url == "https://real-company.co.uk"

    def test_empty_blocklist(self):
        """Test behavior with empty blocklist."""
        filter_obj = BlocklistFilter([])
        results = [
            SearchResult("https://companycheck.co.uk/company/123", "Company Check", "Aggregator", 1),
            SearchResult("https://example.com", "Example", "Good", 2),
        ]
        
        filtered = filter_obj.filter_results(results)
        # Should return all results when blocklist is empty
        assert len(filtered) == 2

    def test_domain_matching(self):
        """Test domain matching logic."""
        blocklist = ["companycheck.co.uk"]
        filter_obj = BlocklistFilter(blocklist)

        # Test various URL formats
        test_cases = [
            ("https://companycheck.co.uk/company/123", True),  # Exact match
            ("https://www.companycheck.co.uk/company/123", True),  # www subdomain
            ("https://api.companycheck.co.uk/data", True),  # api subdomain
            ("https://companycheck.co.uk", True),  # Root domain
            ("https://realcompany.co.uk", False),  # Different domain
            ("https://companycheck.com", False),  # Different TLD
            ("https://companycheck.org.uk", False),  # Different domain
        ]

        for url, should_block in test_cases:
            result = SearchResult(url, "Test", "Test", 1)
            is_blocked = filter_obj._is_blocked(url)
            assert is_blocked == should_block, f"Failed for URL: {url}"

    def test_case_insensitive_matching(self):
        """Test case-insensitive domain matching."""
        blocklist = ["CompanyCheck.co.uk"]  # Mixed case
        filter_obj = BlocklistFilter(blocklist)

        # Should match regardless of case
        assert filter_obj._is_blocked("https://companycheck.co.uk/company/123")
        assert filter_obj._is_blocked("https://COMPANYCHECK.CO.UK/company/123")
        assert filter_obj._is_blocked("https://CompanyCheck.Co.Uk/company/123")

    def test_subdomain_blocking(self):
        """Test blocking of subdomains."""
        blocklist = ["companycheck.co.uk"]
        filter_obj = BlocklistFilter(blocklist)

        # Should block all subdomains
        assert filter_obj._is_blocked("https://www.companycheck.co.uk/company/123")
        assert filter_obj._is_blocked("https://api.companycheck.co.uk/data")
        assert filter_obj._is_blocked("https://search.companycheck.co.uk/results")
        assert filter_obj._is_blocked("https://secure.companycheck.co.uk/login")

    def test_blocklist_update(self):
        """Test dynamic blocklist updates."""
        filter_obj = BlocklistFilter(["companycheck.co.uk"])
        
        # Should block companycheck.co.uk
        assert filter_obj._is_blocked("https://companycheck.co.uk/company/123")
        
        # Add new domain to blocklist
        filter_obj.update_blocklist(["companycheck.co.uk", "globaldatabase.com"])
        
        # Should now block both
        assert filter_obj._is_blocked("https://companycheck.co.uk/company/123")
        assert filter_obj._is_blocked("https://globaldatabase.com/company/456")

    def test_empty_results(self):
        """Test filtering of empty results."""
        filter_obj = BlocklistFilter(["companycheck.co.uk"])
        results = []
        
        filtered = filter_obj.filter_results(results)
        assert filtered == []

    def test_all_blocked_results(self):
        """Test case where all results are blocked."""
        blocklist = ["companycheck.co.uk", "globaldatabase.com"]
        filter_obj = BlocklistFilter(blocklist)
        
        results = [
            SearchResult("https://companycheck.co.uk/company/123", "Company Check", "Aggregator", 1),
            SearchResult("https://globaldatabase.com/company/456", "Global Database", "Aggregator", 2),
        ]
        
        filtered = filter_obj.filter_results(results)
        assert filtered == []

    def test_url_normalization(self):
        """Test URL normalization before matching."""
        blocklist = ["companycheck.co.uk"]
        filter_obj = BlocklistFilter(blocklist)

        # Should handle URLs with/without trailing slashes, query params, etc.
        assert filter_obj._is_blocked("https://companycheck.co.uk/company/123")
        assert filter_obj._is_blocked("https://companycheck.co.uk/company/123/")
        assert filter_obj._is_blocked("https://companycheck.co.uk/company/123?tab=overview")
        assert filter_obj._is_blocked("https://companycheck.co.uk/company/123#section")

    def test_invalid_urls(self):
        """Test handling of invalid URLs."""
        blocklist = ["companycheck.co.uk"]
        filter_obj = BlocklistFilter(blocklist)

        # Should handle invalid URLs gracefully
        assert not filter_obj._is_blocked("")
        assert not filter_obj._is_blocked("not-a-url")
        assert not filter_obj._is_blocked("https://")
        assert not filter_obj._is_blocked(None)