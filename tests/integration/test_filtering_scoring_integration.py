import pytest
from unittest.mock import Mock
from src.filtering.blocklist import BlocklistFilter
from src.scoring.confidence import ConfidenceScorer
from src.search.client import SearchResult
from src.core.models import Company


class TestFilteringAndScoringIntegration:
    """Integration tests for the complete filtering and scoring pipeline."""

    def test_complete_pipeline(self):
        """Test the complete filtering and scoring pipeline."""
        # Create test data
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        # Mock search results (mix of good and bad)
        results = [
            SearchResult("https://acmesoftware.co.uk", "Acme Software Ltd", "Official website", 1),
            SearchResult("https://companycheck.co.uk/company/123", "Company Check - Acme Software", "Aggregator site", 2),
            SearchResult("https://globaldatabase.com/company/456", "Global Database - Acme Software", "Aggregator site", 3),
            SearchResult("https://acme-software.com", "Acme Software Solutions", "Software company", 4),
            SearchResult("https://random-site.com/acme", "Page about Acme", "Mentions Acme Software", 5),
        ]
        
        # Step 1: Blocklist filtering
        blocklist = ["companycheck.co.uk", "globaldatabase.com"]
        blocklist_filter = BlocklistFilter(blocklist)
        filtered_results = blocklist_filter.filter_results(results)
        
        # Should remove aggregator sites
        assert len(filtered_results) == 3
        blocked_urls = [r.url for r in results if r.url not in [f.url for f in filtered_results]]
        assert any("companycheck.co.uk" in url for url in blocked_urls)
        assert any("globaldatabase.com" in url for url in blocked_urls)
        
        # Step 2: Confidence scoring
        scorer = ConfidenceScorer()
        scored_results = []
        for result in filtered_results:
            score = scorer.calculate_score(company, result)
            setattr(result, 'confidence_score', score)  # Add score to result
            scored_results.append(result)
            
        # Step 3: Verify scoring
        scores = [getattr(r, 'confidence_score', 0) for r in scored_results]
        assert all(0 <= score <= 100 for score in scores)
        
        # Top result should have highest confidence
        top_result = max(scored_results, key=lambda r: getattr(r, 'confidence_score', 0))
        assert "acmesoftware.co.uk" in top_result.url
        assert getattr(top_result, 'confidence_score', 0) >= 80
        
        # Step 4: Confidence threshold filtering
        high_confidence = scorer.filter_by_confidence(scored_results, threshold=70)
        assert len(high_confidence) >= 1  # At least the top result should pass
        
        # Low threshold should include more results
        low_confidence = scorer.filter_by_confidence(scored_results, threshold=30)
        assert len(low_confidence) >= len(high_confidence)

    def test_real_world_scenario(self):
        """Test with real-world company data from sample file."""
        from src.csv_processor.reader import CSVReader
        
        # Load real company data
        reader = CSVReader('companies_20251231_085147.csv')
        companies = list(reader.read_companies())
        
        if not companies:
            pytest.skip("No companies found in sample file")
            
        # Pick a company for testing
        test_company = companies[0]
        
        # Create mock search results
        results = [
            SearchResult(
                url=f"https://{test_company.company_name.lower().replace(' ', '')}.co.uk",
                title=f"{test_company.company_name} - Official Website",
                snippet=f"Official website of {test_company.company_name}",
                position=1
            ),
            SearchResult(
                url="https://companycheck.co.uk/company/123",
                title=f"Company Check - {test_company.company_name}",
                snippet="Aggregator site with company information",
                position=2
            ),
            SearchResult(
                url="https://random-site.com/about",
                title="About Us",
                snippet=f"Page mentioning {test_company.company_name}",
                position=3
            ),
        ]
        
        # Apply filtering and scoring
        blocklist_filter = BlocklistFilter(["companycheck.co.uk", "globaldatabase.com"])
        filtered_results = blocklist_filter.filter_results(results)
        
        # Should remove aggregator site
        assert len(filtered_results) == 2
        assert not any("companycheck.co.uk" in r.url for r in filtered_results)
        
        # Score remaining results
        scorer = ConfidenceScorer()
        for result in filtered_results:
            score = scorer.calculate_score(test_company, result)
            setattr(result, 'confidence_score', score)
            
        # Verify scoring
        scores = [getattr(r, 'confidence_score', 0) for r in filtered_results]
        assert all(0 <= score <= 100 for score in scores)
        
        # Official website should have higher score
        official_site = next((r for r in filtered_results if "official" in r.snippet.lower()), None)
        random_site = next((r for r in filtered_results if "random-site" in r.url), None)
        
        if official_site and random_site:
            official_score = getattr(official_site, 'confidence_score', 0)
            random_score = getattr(random_site, 'confidence_score', 0)
            assert official_score > random_score, f"Official site ({official_score}) should score higher than random site ({random_score})"

    def test_blocklist_and_scorer_integration(self):
        """Test integration between blocklist filter and confidence scorer."""
        # Create components
        blocklist = ["companycheck.co.uk", "globaldatabase.com", "endole.co.uk"]
        blocklist_filter = BlocklistFilter(blocklist)
        scorer = ConfidenceScorer()
        
        # Test company
        company = Company(
            company_number="12345678",
            company_name="TEST COMPANY LIMITED",
            postcode="SW1A 1AA"
        )
        
        # Test results
        results = [
            SearchResult("https://testcompany.co.uk", "Test Company Ltd", "Official site", 1),
            SearchResult("https://companycheck.co.uk/company/123", "Company Check", "Aggregator", 2),
            SearchResult("https://globaldatabase.com/company/456", "Global Database", "Aggregator", 3),
            SearchResult("https://endole.co.uk/company/789", "Endole", "Aggregator", 4),
            SearchResult("https://test-company.com", "Test Company Solutions", "Alternative site", 5),
        ]
        
        # Apply filtering
        filtered = blocklist_filter.filter_results(results)
        assert len(filtered) == 2  # Should remove 3 aggregator sites
        
        # Apply scoring
        scored = []
        for result in filtered:
            score = scorer.calculate_score(company, result)
            scored.append((result, score))
            
        # Verify all scores are reasonable
        for result, score in scored:
            assert 0 <= score <= 100
            
        # Official site should score higher
        official_score = next((score for r, score in scored if "testcompany.co.uk" in r.url), 0)
        alternative_score = next((score for r, score in scored if "test-company.com" in r.url), 0)
        
        assert official_score > alternative_score

    def test_edge_cases_in_pipeline(self):
        """Test edge cases in the filtering and scoring pipeline."""
        blocklist_filter = BlocklistFilter(["companycheck.co.uk"])
        scorer = ConfidenceScorer()
        
        company = Company(
            company_number="12345678",
            company_name="EDGE CASE COMPANY LIMITED",
            postcode="SW1A 1AA"
        )
        
        # Test with empty results
        empty_results = []
        filtered = blocklist_filter.filter_results(empty_results)
        assert filtered == []
        
        # Test with all blocked results
        blocked_results = [
            SearchResult("https://companycheck.co.uk/company/123", "Company Check", "Aggregator", 1),
            SearchResult("https://companycheck.co.uk/company/456", "Company Check 2", "Aggregator", 2),
        ]
        filtered = blocklist_filter.filter_results(blocked_results)
        assert filtered == []
        
        # Test with invalid URLs
        invalid_results = [
            SearchResult("", "Empty URL", "Test", 1),
            SearchResult("not-a-url", "Invalid URL", "Test", 2),
        ]
        filtered = blocklist_filter.filter_results(invalid_results)
        assert len(filtered) == 2  # Should not block invalid URLs
        
        # Test scoring with edge cases
        for result in filtered:
            score = scorer.calculate_score(company, result)
            assert 0 <= score <= 100  # Should handle gracefully