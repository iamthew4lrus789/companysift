"""Integration tests for dynamic aggregator filtering system."""

import pytest
import tempfile
import os
from pathlib import Path

from src.filtering.domain_frequency import DomainFrequencyTracker, EnhancedBlocklistFilter, DomainCachePersistence
from src.search.client import SearchResult


class TestDynamicFilteringIntegration:
    """Integration tests for dynamic aggregator filtering."""

    @pytest.fixture
    def sample_search_data(self):
        """Create sample search data simulating real aggregator patterns."""
        # Simulate searches for 10 different companies
        companies = [f"Company {i}" for i in range(10)]
        
        search_data = []
        
        for company in companies:
            # Aggregator sites appear in most searches
            aggregator_results = [
                SearchResult(
                    url=f"https://companycheck.co.uk/company/{hash(company)}",
                    title="Company Check",
                    snippet="Company information",
                    position=1
                ),
                SearchResult(
                    url=f"https://www.globaldatabase.com/company/{hash(company)}",
                    title="Global Database",
                    snippet="Business data",
                    position=2
                )
            ]
            
            # Genuine company site appears only for its own company
            if "5" in company:  # Only Company 5 has this site
                aggregator_results.append(SearchResult(
                    url="https://company5-official.co.uk",
                    title="Company 5 Official",
                    snippet="Official site",
                    position=3
                ))
            
            # Some companies have unique sites
            if company in ["Company 1", "Company 3", "Company 7"]:
                company_id = company.split()[1]
                aggregator_results.append(SearchResult(
                    url=f"https://{company_id}-unique-site.co.uk",
                    title=f"{company} Official",
                    snippet="Unique company site",
                    position=4
                ))
            
            search_data.append((company, aggregator_results))
        
        return search_data

    def test_dynamic_aggregator_detection(self, sample_search_data):
        """Test that system correctly identifies frequent aggregator domains."""
        tracker = DomainFrequencyTracker()
        
        # Process all search data
        for company, results in sample_search_data:
            tracker.track_search_results(company, results)
        
        # Identify aggregators (appear in >50% of searches)
        aggregators = tracker.identify_aggregators(threshold=0.5)
        
        # Verify known aggregators are detected (www. is stripped)
        assert "companycheck.co.uk" in aggregators
        assert "globaldatabase.com" in aggregators
        
        # Verify genuine sites are NOT detected as aggregators
        assert "company5-official.co.uk" not in aggregators
        assert "1-unique-site.co.uk" not in aggregators
        assert "3-unique-site.co.uk" not in aggregators
        assert "7-unique-site.co.uk" not in aggregators

    def test_combined_filtering_effectiveness(self, sample_search_data):
        """Test combined static and dynamic filtering effectiveness."""
        tracker = DomainFrequencyTracker()
        
        # Process all search data
        for company, results in sample_search_data:
            tracker.track_search_results(company, results)
        
        # Create enhanced filter
        static_blocklist = ["known-aggregator.com"]  # Not in our test data
        filter_instance = EnhancedBlocklistFilter(static_blocklist, tracker)
        
        # Test filtering on a typical result set
        test_results = [
            SearchResult(
                url="https://companycheck.co.uk/company/123",
                title="Company Check",
                snippet="Info",
                position=1
            ),
            SearchResult(
                url="https://www.globaldatabase.com/company/456",
                title="Global Database",
                snippet="Data",
                position=2
            ),
            SearchResult(
                url="https://genuine-company.co.uk",
                title="Genuine Company",
                snippet="Real site",
                position=3
            ),
            SearchResult(
                url="https://known-aggregator.com/company/789",
                title="Known Aggregator",
                snippet="Info",
                position=4
            )
        ]
        
        filtered = filter_instance.filter_results(test_results, "Test Company")
        
        # Should filter out:
        # - companycheck.co.uk (dynamic)
        # - www.globaldatabase.com (dynamic)
        # - known-aggregator.com (static)
        # Should keep:
        # - genuine-company.co.uk (only appears once)
        
        assert len(filtered) == 1
        assert filtered[0].url == "https://genuine-company.co.uk"

    def test_filtering_report(self, sample_search_data):
        """Test filtering report generation."""
        tracker = DomainFrequencyTracker()
        
        # Process all search data
        for company, results in sample_search_data:
            tracker.track_search_results(company, results)
        
        # Create enhanced filter
        static_blocklist = ["static-blocked.com"]
        filter_instance = EnhancedBlocklistFilter(static_blocklist, tracker)
        
        # Get report
        report = filter_instance.get_filtering_report()
        
        # Verify report contents
        assert report['static_blocklist_size'] == 1
        assert report['dynamic_aggregators_detected'] >= 2  # companycheck and globaldatabase
        assert report['total_blocked_domains'] >= 3
        assert report['frequency_summary']['total_searches'] == 10

    def test_suspected_aggregators_detection(self, sample_search_data):
        """Test detection of suspected aggregators (not yet confirmed)."""
        tracker = DomainFrequencyTracker()
        
        # Process all search data
        for company, results in sample_search_data:
            tracker.track_search_results(company, results)
        
        # Create enhanced filter
        filter_instance = EnhancedBlocklistFilter([], tracker)
        
        # Get suspected aggregators (appear in 10-49% of searches)
        suspected = filter_instance.get_suspected_aggregators(min_suspicion=0.1)
        
        # Should find domains that appear in some but not most searches
        suspected_domains = [item['domain'] for item in suspected]
        
        # Unique company sites should be in suspected list
        assert any('unique-site' in domain for domain in suspected_domains)
        
        # Verify suspected aggregators have proper stats
        for item in suspected:
            assert 'domain' in item
            assert 'count' in item
            assert 'frequency' in item
            assert 'companies' in item
            assert 0.1 <= item['frequency'] < 0.5

    def test_persistence_integration(self, sample_search_data):
        """Test integration with persistence layer."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            cache_file = f.name
        
        try:
            # Create persistence layer
            persistence = DomainCachePersistence(cache_file)
            
            # Process some data
            tracker = DomainFrequencyTracker()
            for company, results in sample_search_data[:5]:  # First 5 companies
                tracker.track_search_results(company, results)
            
            # Save to persistence - need to track searches properly
            # For this test, we'll simulate the actual search tracking
            for company, results in sample_search_data[:5]:
                persistence.increment_search_count()  # Increment for each search
                for result in results:
                    domain = tracker._extract_domain(result.url)
                    persistence.update_cache(domain, company)
            
            # Load into new tracker
            new_tracker = DomainFrequencyTracker()
            persistence.load_into_tracker(new_tracker)
            
            # Verify data was loaded
            assert new_tracker.total_searches == 5
            assert len(new_tracker.domain_counts) > 0
            assert "companycheck.co.uk" in new_tracker.domain_counts
            
            # Continue processing with loaded data
            for company, results in sample_search_data[5:]:  # Remaining companies
                new_tracker.track_search_results(company, results)
            
            # Verify aggregator detection works with loaded data
            aggregators = new_tracker.identify_aggregators()
            assert "companycheck.co.uk" in aggregators
            
        finally:
            # Cleanup
            if Path(cache_file).exists():
                os.unlink(cache_file)

    def test_real_world_scenario(self):
        """Test with realistic search patterns."""
        tracker = DomainFrequencyTracker()
        
        # Simulate realistic search patterns
        search_patterns = [
            ("Acme Ltd", [
                SearchResult("https://companycheck.co.uk/company/1", "Check", "Info", 1),
                SearchResult("https://www.endole.co.uk/company/1", "Endole", "Data", 2),
                SearchResult("https://acme-official.co.uk", "Acme", "Real", 3)
            ]),
            ("Beta Corp", [
                SearchResult("https://companycheck.co.uk/company/2", "Check", "Info", 1),
                SearchResult("https://www.endole.co.uk/company/2", "Endole", "Data", 2),
                SearchResult("https://beta-corp.co.uk", "Beta", "Real", 3)
            ]),
            ("Gamma Inc", [
                SearchResult("https://companycheck.co.uk/company/3", "Check", "Info", 1),
                SearchResult("https://www.endole.co.uk/company/3", "Endole", "Data", 2),
                SearchResult("https://gamma-inc.co.uk", "Gamma", "Real", 3)
            ])
        ]
        
        # Process all searches
        for company, results in search_patterns:
            tracker.track_search_results(company, results)
        
        # Verify aggregator detection
        aggregators = tracker.identify_aggregators(threshold=0.5)
        
        assert "companycheck.co.uk" in aggregators
        assert "endole.co.uk" in aggregators
        assert "acme-official.co.uk" not in aggregators
        assert "beta-corp.co.uk" not in aggregators
        assert "gamma-inc.co.uk" not in aggregators
        
        # Test filtering
        filter_instance = EnhancedBlocklistFilter([], tracker)
        
        # Filter a typical result set
        mixed_results = [
            SearchResult("https://companycheck.co.uk/company/4", "Check", "Info", 1),
            SearchResult("https://www.endole.co.uk/company/4", "Endole", "Data", 2),
            SearchResult("https://delta-ltd.co.uk", "Delta", "Real", 3)
        ]
        
        filtered = filter_instance.filter_results(mixed_results, "Delta Ltd")
        
        # Should keep only the genuine site
        assert len(filtered) == 1
        assert filtered[0].url == "https://delta-ltd.co.uk"

    def test_threshold_sensitivity(self, sample_search_data):
        """Test how different thresholds affect aggregator detection."""
        tracker = DomainFrequencyTracker()
        
        # Process all search data
        for company, results in sample_search_data:
            tracker.track_search_results(company, results)
        
        # Test different thresholds
        strict_aggregators = tracker.identify_aggregators(threshold=0.8)  # Very frequent
        normal_aggregators = tracker.identify_aggregators(threshold=0.5)  # Moderately frequent
        lenient_aggregators = tracker.identify_aggregators(threshold=0.3)  # Somewhat frequent
        
        # Strict should find fewer aggregators
        assert len(strict_aggregators) <= len(normal_aggregators)
        assert len(normal_aggregators) <= len(lenient_aggregators)
        
        # Known aggregators should be in all lists
        assert "companycheck.co.uk" in lenient_aggregators
        assert "globaldatabase.com" in lenient_aggregators
        
        # Unique sites should not be in any list
        assert not any("unique-site" in domain for domain in lenient_aggregators)