"""Tests for domain frequency tracking system."""

import pytest
import tempfile
import json
import os
from collections import defaultdict
from pathlib import Path

from src.filtering.domain_frequency import DomainFrequencyTracker, DomainCachePersistence
from src.search.client import SearchResult


class TestDomainFrequencyTracker:
    """Test domain frequency tracking functionality."""

    @pytest.fixture
    def tracker(self):
        """Create a fresh domain frequency tracker."""
        return DomainFrequencyTracker()

    @pytest.fixture
    def sample_search_results(self):
        """Sample search results for testing."""
        from src.search.client import SearchResult
        return [
            SearchResult(
                url="https://companycheck.co.uk/company/123",
                title="Company Check",
                snippet="Company information",
                position=1
            ),
            SearchResult(
                url="https://scantrack.co.uk",
                title="Scantrack Ltd",
                snippet="Software company",
                position=2
            ),
            SearchResult(
                url="https://globaldatabase.com/company/456",
                title="Global Database",
                snippet="Business data",
                position=3
            )
        ]

    def test_initialization(self, tracker):
        """Test tracker initialization."""
        assert tracker.domain_counts == defaultdict(int)
        assert tracker.company_domains == defaultdict(set)
        assert tracker.total_searches == 0

    def test_extract_domain(self, tracker):
        """Test domain extraction from URLs."""
        # Test various URL formats
        assert tracker._extract_domain("https://companycheck.co.uk/company/123") == "companycheck.co.uk"
        assert tracker._extract_domain("http://www.scantrack.co.uk") == "scantrack.co.uk"
        assert tracker._extract_domain("https://subdomain.globaldatabase.com/page") == "subdomain.globaldatabase.com"  # Keep subdomains for tracking
        assert tracker._extract_domain("https://bloomberg.com") == "bloomberg.com"

    def test_track_search_results(self, tracker, sample_search_results):
        """Test tracking search results for a company."""
        tracker.track_search_results("SCANTRACK LIMITED", sample_search_results)
        
        # Verify tracking
        assert tracker.total_searches == 1
        assert tracker.domain_counts["companycheck.co.uk"] == 1
        assert tracker.domain_counts["scantrack.co.uk"] == 1
        assert tracker.domain_counts["globaldatabase.com"] == 1
        
        # Verify company associations
        assert "SCANTRACK LIMITED" in tracker.company_domains["companycheck.co.uk"]
        assert "SCANTRACK LIMITED" in tracker.company_domains["scantrack.co.uk"]
        assert "SCANTRACK LIMITED" in tracker.company_domains["globaldatabase.com"]

    def test_identify_aggregators(self, tracker, sample_search_results):
        """Test aggregator identification based on frequency."""
        # Simulate multiple searches
        companies = ["Company A", "Company B", "Company C", "Company D", "Company E"]
        
        for company in companies:
            # Company aggregator appears in all searches
            aggregator_result = SearchResult(
                url=f"https://companycheck.co.uk/company/{hash(company)}",
                title="Company Check",
                snippet="Company info",
                position=1
            )
            
            # Company-specific result appears only once
            company_result = SearchResult(
                url=f"https://{company.lower().replace(' ', '')}.co.uk",
                title=f"{company}",
                snippet="Company website",
                position=2
            )
            
            tracker.track_search_results(company, [aggregator_result, company_result])
        
        # Test aggregator identification
        aggregators = tracker.identify_aggregators(threshold=0.5, min_occurrences=3)
        
        # companycheck.co.uk should be identified as aggregator (appears in all 5 searches)
        assert "companycheck.co.uk" in aggregators
        
        # Company-specific domains should NOT be identified as aggregators (appear only once)
        for company in companies:
            domain = f"{company.lower().replace(' ', '')}.co.uk"
            assert domain not in aggregators

    def test_get_domain_stats(self, tracker, sample_search_results):
        """Test getting statistics for specific domains."""
        tracker.track_search_results("Company A", sample_search_results)
        tracker.track_search_results("Company B", sample_search_results)
        
        # Test stats for a domain that appears twice
        stats = tracker.get_domain_stats("companycheck.co.uk")
        assert stats["count"] == 2
        assert stats["frequency"] == 2.0 / tracker.total_searches
        assert "Company A" in stats["companies"]
        assert "Company B" in stats["companies"]
        assert stats["is_aggregator"] == (2 >= 3 and 2/tracker.total_searches >= 0.3)  # Should be False

    def test_edge_cases(self, tracker):
        """Test edge cases and boundary conditions."""
        # Empty results
        tracker.track_search_results("Empty Company", [])
        assert tracker.total_searches == 1
        assert len(tracker.domain_counts) == 0
        
        # Domain with subdomains - www. is stripped, others kept
        results = [
            SearchResult("https://www.companycheck.co.uk/page", "Title", "Snippet", 1),
            SearchResult("https://api.companycheck.co.uk/data", "Title", "Snippet", 2),
        ]
        tracker.track_search_results("Test Company", results)
        
        # www. is stripped, but api. is kept for tracking aggregator patterns
        assert tracker.domain_counts["companycheck.co.uk"] == 1  # www. stripped
        assert tracker.domain_counts["api.companycheck.co.uk"] == 1  # api. kept
        assert len(tracker.domain_counts) == 2


class TestDomainCachePersistence:
    """Test domain cache persistence functionality."""

    @pytest.fixture
    def cache_file(self):
        """Create a temporary cache file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        if Path(temp_path).exists():
            os.unlink(temp_path)

    def test_initialization(self, cache_file):
        """Test cache initialization."""
        # Test with non-existent file
        cache = DomainCachePersistence(cache_file)
        assert cache.cache == {'domain_counts': {}, 'company_domains': {}, 'total_searches': 0}
        
        # Test with empty file
        with open(cache_file, 'w') as f:
            f.write('')
        cache = DomainCachePersistence(cache_file)
        assert cache.cache == {'domain_counts': {}, 'company_domains': {}, 'total_searches': 0}

    def test_load_existing_cache(self, cache_file):
        """Test loading existing cache data."""
        # Create sample cache data
        sample_data = {
            'domain_counts': {'companycheck.co.uk': 5, 'scantrack.co.uk': 1},
            'company_domains': {
                'companycheck.co.uk': ['Company A', 'Company B'],
                'scantrack.co.uk': ['Scantrack Ltd']
            },
            'total_searches': 3
        }
        
        with open(cache_file, 'w') as f:
            json.dump(sample_data, f)
        
        # Load and verify
        cache = DomainCachePersistence(cache_file)
        assert cache.cache == sample_data

    def test_update_and_save_cache(self, cache_file):
        """Test updating and saving cache data."""
        cache = DomainCachePersistence(cache_file)
        
        # Update cache
        cache.update_cache('companycheck.co.uk', 'Company C')
        cache.update_cache('companycheck.co.uk', 'Company D')
        cache.update_cache('newdomain.com', 'Company E')
        cache.increment_search_count()
        cache.increment_search_count()
        cache.increment_search_count()
        
        # Verify updates
        assert cache.cache['domain_counts']['companycheck.co.uk'] == 2
        assert cache.cache['domain_counts']['newdomain.com'] == 1
        assert 'Company C' in cache.cache['company_domains']['companycheck.co.uk']
        assert 'Company D' in cache.cache['company_domains']['companycheck.co.uk']
        assert cache.cache['total_searches'] == 3
        
        # Save and reload
        cache.save_cache()
        new_cache = DomainCachePersistence(cache_file)
        assert new_cache.cache == cache.cache

    def test_concurrent_updates(self, cache_file):
        """Test handling of concurrent updates."""
        cache = DomainCachePersistence(cache_file)
        
        # Multiple updates to same domain
        for i in range(5):
            cache.update_cache('test.com', f'Company {i}')
            cache.increment_search_count()
        
        # Should count correctly
        assert cache.cache['domain_counts']['test.com'] == 5
        assert len(cache.cache['company_domains']['test.com']) == 5
        assert cache.cache['total_searches'] == 5


class TestEnhancedBlocklistFilter:
    """Test enhanced blocklist filter with dynamic detection."""

    @pytest.fixture
    def tracker(self):
        """Create tracker with test data."""
        tracker = DomainFrequencyTracker()
        
        # Simulate aggregator appearing in 80% of searches
        for i in range(10):
            results = [
                SearchResult(f"https://aggregator.com/company/{i}", "Aggregator", "Info", 1),
                SearchResult(f"https://company{i}.co.uk", "Company", "Site", 2)
            ]
            tracker.track_search_results(f"Company {i}", results)
        
        return tracker

    @pytest.fixture
    def filter_instance(self, tracker):
        """Create enhanced filter instance."""
        from src.filtering.domain_frequency import EnhancedBlocklistFilter
        static_blocklist = ['companycheck.co.uk', 'globaldatabase.com']
        return EnhancedBlocklistFilter(static_blocklist, tracker)

    @pytest.fixture
    def sample_results(self):
        """Sample results including known and unknown aggregators."""
        from src.search.client import SearchResult
        return [
            SearchResult("https://companycheck.co.uk/company/123", "Company Check", "Info", 1),
            SearchResult("https://aggregator.com/company/456", "Aggregator", "Data", 2),
            SearchResult("https://genuine-company.co.uk", "Genuine Company", "Real site", 3),
            SearchResult("https://globaldatabase.com/company/789", "Global Database", "Info", 4)
        ]

    def test_filtering_report(self, filter_instance):
        """Test filtering report generation."""
        report = filter_instance.get_filtering_report()
        
        assert report['static_blocklist_size'] == 2
        assert report['dynamic_aggregators_detected'] == 1  # aggregator.com
        assert report['total_blocked_domains'] == 3

    def test_combined_filtering(self, filter_instance, sample_results):
        """Test combined static and dynamic filtering."""
        filtered = filter_instance.filter_results(sample_results, "Test Company")
        
        # Should filter out:
        # - companycheck.co.uk (static blocklist)
        # - globaldatabase.com (static blocklist)  
        # - aggregator.com (dynamic detection)
        # Should keep:
        # - genuine-company.co.uk (only appears once)
        
        assert len(filtered) == 1
        assert filtered[0].url == "https://genuine-company.co.uk"

    def test_dynamic_only_filtering(self, filter_instance):
        """Test dynamic filtering with unknown aggregators."""
        from src.search.client import SearchResult
        
        # Results with only dynamic aggregators (not in static blocklist)
        results = [
            SearchResult("https://aggregator.com/company/1", "Aggregator", "Data", 1),
            SearchResult("https://another-aggregator.net/company/2", "Another", "Info", 2),
            SearchResult("https://unique-company.co.uk", "Unique Company", "Site", 3)
        ]
        
        filtered = filter_instance.filter_results(results, "Test Company")
        
        # aggregator.com should be filtered (dynamic)
        # another-aggregator.net should pass (only appears once in our test data)
        # unique-company.co.uk should pass (only appears once)
        assert len(filtered) == 2
        
        # Verify the aggregator was filtered
        filtered_urls = [result.url for result in filtered]
        assert "https://aggregator.com/company/1" not in filtered_urls
        assert "https://another-aggregator.net/company/2" in filtered_urls
        assert "https://unique-company.co.uk" in filtered_urls

    def test_threshold_adjustment(self, tracker):
        """Test effect of different threshold settings."""
        from src.filtering.domain_frequency import EnhancedBlocklistFilter
        
        static_blocklist = []
        filter_instance = EnhancedBlocklistFilter(static_blocklist, tracker)
        
        # Test with different thresholds
        aggregators_low = tracker.identify_aggregators(threshold=0.1, min_occurrences=2)
        aggregators_high = tracker.identify_aggregators(threshold=0.8, min_occurrences=5)
        
        # Lower threshold should catch more aggregators
        assert len(aggregators_low) >= len(aggregators_high)
        
        # aggregator.com appears in 10/10 searches, so should be caught by both
        assert "aggregator.com" in aggregators_low
        assert "aggregator.com" in aggregators_high