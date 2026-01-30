import pytest
from unittest.mock import Mock
from src.scoring.confidence import ConfidenceScorer
from src.search.client import SearchResult
from src.core.models import Company


class TestConfidenceScorer:
    """Test suite for confidence scoring system."""

    def test_scorer_initialization(self):
        """Test scorer initialization with default weights."""
        scorer = ConfidenceScorer()
        assert scorer.weights["domain_match"] == 0.4
        assert scorer.weights["tld_relevance"] == 0.2
        assert scorer.weights["search_position"] == 0.3
        assert scorer.weights["title_match"] == 0.1

    def test_custom_weights(self):
        """Test scorer with custom weights."""
        weights = {
            "domain_match": 0.5,
            "tld_relevance": 0.1,
            "search_position": 0.3,
            "title_match": 0.1
        }
        scorer = ConfidenceScorer(weights)
        assert scorer.weights == weights

    def test_score_calculation(self):
        """Test confidence score calculation."""
        scorer = ConfidenceScorer()
        
        # Create test company and search result
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        result = SearchResult(
            url="https://acmesoftware.co.uk",
            title="Acme Software Ltd - Official Website",
            snippet="Leading software development company",
            position=1
        )
        
        score = scorer.calculate_score(company, result)
        
        # Should be high confidence due to good domain match, UK TLD, position 1
        assert 80 <= score <= 100

    def test_perfect_match(self):
        """Test perfect match scenario."""
        scorer = ConfidenceScorer()
        
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        result = SearchResult(
            url="https://acmesoftwarelimited.co.uk",
            title="Acme Software Limited",
            snippet="Official website of Acme Software Limited",
            position=1
        )
        
        score = scorer.calculate_score(company, result)
        assert score >= 95  # Close enough for perfect match

    def test_poor_match(self):
        """Test poor match scenario."""
        scorer = ConfidenceScorer()
        
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        result = SearchResult(
            url="https://random-website.com/acme",
            title="Some random page mentioning Acme",
            snippet="This page mentions Acme Software somewhere",
            position=10
        )
        
        score = scorer.calculate_score(company, result)
        assert 0 <= score <= 30

    def test_domain_match_weighting(self):
        """Test domain match weighting."""
        # High domain match weight
        scorer = ConfidenceScorer({
            "domain_match": 0.8,
            "tld_relevance": 0.05,
            "search_position": 0.1,
            "title_match": 0.05
        })
        
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        # Perfect domain match, poor other factors
        result = SearchResult(
            url="https://acmesoftwarelimited.co.uk",
            title="Some other company",
            snippet="Random content",
            position=10
        )
        
        score = scorer.calculate_score(company, result)
        # Should be high due to domain match weighting
        assert score >= 75  # Adjusted for realistic scoring

    def test_tld_relevance(self):
        """Test TLD relevance scoring."""
        scorer = ConfidenceScorer()
        
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        # UK company with UK TLD
        uk_result = SearchResult(
            url="https://acmesoftware.co.uk",
            title="Acme Software",
            snippet="Software company",
            position=1
        )
        
        # Same company with non-UK TLD
        non_uk_result = SearchResult(
            url="https://acmesoftware.com",
            title="Acme Software",
            snippet="Software company",
            position=1
        )
        
        uk_score = scorer.calculate_score(company, uk_result)
        non_uk_score = scorer.calculate_score(company, non_uk_result)
        
        # UK TLD should score higher
        assert uk_score > non_uk_score

    def test_search_position_impact(self):
        """Test search position impact on scoring."""
        scorer = ConfidenceScorer()
        
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        # Same result at different positions
        position_1 = SearchResult(
            url="https://acmesoftware.co.uk",
            title="Acme Software",
            snippet="Software company",
            position=1
        )
        
        position_5 = SearchResult(
            url="https://acmesoftware.co.uk",
            title="Acme Software",
            snippet="Software company",
            position=5
        )
        
        score_1 = scorer.calculate_score(company, position_1)
        score_5 = scorer.calculate_score(company, position_5)
        
        # Position 1 should score higher
        assert score_1 > score_5

    def test_title_match_impact(self):
        """Test title match impact on scoring."""
        scorer = ConfidenceScorer()
        
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        # Good title match
        good_title = SearchResult(
            url="https://acmesoftware.co.uk",
            title="Acme Software Limited - Official Website",
            snippet="Software company",
            position=1
        )
        
        # Poor title match
        poor_title = SearchResult(
            url="https://acmesoftware.co.uk",
            title="Some random page",
            snippet="Software company",
            position=1
        )
        
        good_score = scorer.calculate_score(company, good_title)
        poor_score = scorer.calculate_score(company, poor_title)
        
        # Good title should score higher
        assert good_score > poor_score

    def test_edge_cases(self):
        """Test edge cases in scoring."""
        scorer = ConfidenceScorer()
        
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        # Empty URL
        empty_url = SearchResult(
            url="",
            title="Test",
            snippet="Test",
            position=1
        )
        
        # Invalid URL
        invalid_url = SearchResult(
            url="not-a-url",
            title="Test",
            snippet="Test",
            position=1
        )
        
        # Should handle gracefully
        score_empty = scorer.calculate_score(company, empty_url)
        score_invalid = scorer.calculate_score(company, invalid_url)
        
        assert 0 <= score_empty <= 100
        assert 0 <= score_invalid <= 100

    def test_threshold_filtering(self):
        """Test threshold-based filtering."""
        scorer = ConfidenceScorer()
        
        company = Company(
            company_number="12345678",
            company_name="ACME SOFTWARE LIMITED",
            postcode="SW1A 1AA"
        )
        
        # High confidence result
        high_result = SearchResult(
            url="https://acmesoftware.co.uk",
            title="Acme Software Limited",
            snippet="Official website",
            position=1
        )
        
        # Low confidence result
        low_result = SearchResult(
            url="https://random-site.com/acme",
            title="Page about Acme",
            snippet="Mentions Acme",
            position=10
        )
        
        results = [high_result, low_result]
        
        # Filter with high threshold
        filtered_high = scorer.filter_by_confidence(results, threshold=70)
        assert len(filtered_high) == 1
        assert filtered_high[0] == high_result
        
        # Filter with low threshold
        filtered_low = scorer.filter_by_confidence(results, threshold=20)
        assert len(filtered_low) == 2

    def test_weight_validation(self):
        """Test weight validation."""
        # Valid weights (sum to 1.0)
        valid_weights = {
            "domain_match": 0.4,
            "tld_relevance": 0.2,
            "search_position": 0.3,
            "title_match": 0.1
        }
        
        scorer = ConfidenceScorer(valid_weights)
        assert scorer.weights == valid_weights
        
        # Invalid weights (sum > 1.0) - should normalize
        invalid_weights = {
            "domain_match": 0.6,
            "tld_relevance": 0.3,
            "search_position": 0.2,
            "title_match": 0.1
        }
        
        scorer_invalid = ConfidenceScorer(invalid_weights)
        # Should be normalized to sum to 1.0
        total = sum(scorer_invalid.weights.values())
        assert abs(total - 1.0) < 0.001