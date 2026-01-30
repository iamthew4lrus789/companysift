"""End-to-end integration tests for Company Website Discovery Tool."""

import pytest
import tempfile
import os
import yaml
from unittest.mock import patch, Mock
from pathlib import Path

from src.core.config import Config
from src.csv_processor.reader import CSVReader
from src.csv_processor.writer import CSVWriter
from src.search.client import DuckDuckGoClient
from src.filtering.blocklist import BlocklistFilter
from src.scoring.confidence import ConfidenceScorer
from src.state.checkpoint import CheckpointManager


class TestEndToEndIntegration:
    """End-to-end integration tests covering the full processing pipeline."""

    @pytest.fixture
    def sample_config_file(self):
        """Create a temporary config file for testing."""
        config_data = {
            'search': {
                'provider': 'duckduckgo',
                'api_key': 'test_api_key_123',
                'rate_limit': 4.5,
                'timeout': 30,
                'max_retries': 3,
                'retry_delay': 2
            },
            'scoring': {
                'min_confidence': 50,
                'weights': {
                    'domain_match': 0.4,
                    'tld_relevance': 0.2,
                    'search_position': 0.3,
                    'title_match': 0.1
                }
            },
            'processing': {
                'batch_size': 50,
                'max_candidates': 3
            },
            'filtering': {
                'blocklist': [
                    'companycheck.co.uk',
                    'globaldatabase.com',
                    'companieshouse.gov.uk',
                    'endole.co.uk'
                ]
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file': 'logs/company_sift.log'
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        yield temp_path

        # Cleanup
        os.unlink(temp_path)

    @pytest.fixture
    def sample_csv_file(self):
        """Create a temporary CSV file with sample company data."""
        csv_content = """CompanyNumber,CompanyName,Postcode,SICCode01,SICCode02
01234567,ACME Manufacturing Ltd,SW1A 1AA,25990,25990
12345678,Tech Innovations Limited,M1 1AE,62012,62012
23456789,Global Solutions PLC,E1 6AN,70229,70229
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        yield temp_path

        # Cleanup
        os.unlink(temp_path)

    @patch('src.search.client.requests.get')
    def test_full_processing_pipeline(self, mock_get, sample_config_file, sample_csv_file):
        """Test the complete processing pipeline from CSV input to enriched output."""
        # Mock API responses for search results
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "url": "https://acme-manufacturing.co.uk",
                    "title": "ACME Manufacturing Ltd - Precision Engineering",
                    "description": "ACME Manufacturing Ltd provides precision engineering services"
                },
                {
                    "url": "https://companycheck.co.uk/company/01234567",
                    "title": "ACME Manufacturing Ltd - Company Check",
                    "description": "Company information for ACME Manufacturing Ltd"
                },
                {
                    "url": "https://tech-innovations.com",
                    "title": "Tech Innovations Limited - Software Solutions",
                    "description": "Cutting-edge software solutions from Tech Innovations Limited"
                }
            ]
        }
        mock_get.return_value = mock_response

        # Load configuration
        config = Config(sample_config_file)
        config.validate()

        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            # Step 1: Read CSV input
            csv_reader = CSVReader(sample_csv_file)
            companies = list(csv_reader.read_companies())
            
            assert len(companies) == 3
            assert companies[0].company_name == "ACME Manufacturing Ltd"
            assert companies[1].company_name == "Tech Innovations Limited"

            # Step 2: Search for each company
            search_client = DuckDuckGoClient(
                api_key=config.get('search.api_key'),
                rate_limit=config.get('search.rate_limit')
            )
            
            all_search_results = []
            for company in companies:
                results = search_client.search(company.company_name)
                all_search_results.extend([(company, results)])
            
            assert len(all_search_results) == 3
            assert all(results for _, results in all_search_results)

            # Step 3: Filter aggregator sites
            blocklist_filter = BlocklistFilter(config.get('filtering.blocklist', []))
            
            filtered_results = []
            for company, results in all_search_results:
                filtered = blocklist_filter.filter_results(results)
                filtered_results.append((company, filtered))
            
            # Verify aggregator sites were filtered out
            for _, results in filtered_results:
                for result in results:
                    assert 'companycheck.co.uk' not in result.url

            # Step 4: Score remaining URLs using the confidence scorer
            scorer = ConfidenceScorer(config.scoring_config.get('weights'))
            
            scored_results = []
            for company, results in filtered_results:
                # Use the filter_by_confidence method which handles scoring internally
                high_confidence_results = scorer.filter_by_confidence(results, config.get('scoring.min_confidence', 50))
                scored_results.append((company, high_confidence_results))
            
            # Verify scoring produced results
            assert len(scored_results) == 3
            for company, scored_results_list in scored_results:
                assert len(scored_results_list) > 0  # Should have at least one high-confidence result

            # Step 5: Write enriched CSV output
            csv_writer = CSVWriter(output_path)
            
            # Convert to the expected format for writing
            from src.core.models import ScoredResult, Company
            output_results = []
            for company, scored_results_list in scored_results:
                for result in scored_results_list:
                    scored_result = ScoredResult(
                        company=company,
                        search_result=result,
                        confidence_score=getattr(result, 'confidence_score', 80.0),  # Default high score
                        scoring_details={
                            'domain_match': 0.8,
                            'tld_relevance': 0.7,
                            'search_position': 0.6,
                            'title_match': 0.5
                        },
                        error_flag=False,
                        error_message=None
                    )
                    output_results.append(scored_result)
            
            csv_writer.write_results(output_results)
            
            # Verify output file was created and contains data
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0
            
            # Read and verify output content
            with open(output_path, 'r') as f:
                output_content = f.read()
                assert 'ACME Manufacturing Ltd' in output_content
                assert 'acme-manufacturing.co.uk' in output_content
                assert 'Tech Innovations Limited' in output_content
                assert 'tech-innovations.com' in output_content

        finally:
            # Cleanup output file
            if Path(output_path).exists():
                os.unlink(output_path)

    @patch('src.search.client.requests.get')
    def test_processing_with_checkpoint(self, mock_get, sample_config_file, sample_csv_file):
        """Test processing with checkpoint management."""
        # Mock API response
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

        # Load configuration
        config = Config(sample_config_file)
        
        # Create temporary checkpoint database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            checkpoint_path = f.name

        try:
            # Initialize checkpoint manager
            checkpoint_manager = CheckpointManager(checkpoint_path)
            
            # Read companies
            csv_reader = CSVReader(sample_csv_file)
            companies = list(csv_reader.read_companies())
            
            # Process first batch
            batch_size = 2
            first_batch = companies[:batch_size]
            
            # Simulate processing first batch
            processed_count = 0
            for company in first_batch:
                # Simulate search and processing
                search_client = DuckDuckGoClient(
                    api_key=config.get('search.api_key'),
                    rate_limit=config.get('search.rate_limit')
                )
                results = search_client.search(company.company_name)
                
                # Create checkpoint
                checkpoint_manager.create_checkpoint(
                    batch_number=processed_count + 1,
                    companies_processed=processed_count + 1
                )
                processed_count += 1
            
            # Verify checkpoint was created
            latest = checkpoint_manager.get_latest_checkpoint()
            assert latest is not None
            assert latest["batch_number"] == batch_size
            assert latest["companies_processed"] == batch_size
            
            # Verify can get processing stats
            stats = checkpoint_manager.get_processing_stats()
            assert stats["total_checkpoints"] == batch_size

        finally:
            # Cleanup checkpoint database
            if Path(checkpoint_path).exists():
                os.unlink(checkpoint_path)

    def test_error_handling_in_pipeline(self, sample_config_file, sample_csv_file):
        """Test error handling throughout the processing pipeline."""
        # Load configuration
        config = Config(sample_config_file)
        
        # Test with invalid CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("Invalid,CSV,Format,Without,Proper,Headers")
            invalid_csv_path = f.name
        
        try:
            csv_reader = CSVReader(invalid_csv_path)
            
            # Should handle malformed CSV gracefully
            companies = list(csv_reader.read_companies())
            
            # Should return empty list for completely invalid format
            assert len(companies) == 0
            
        finally:
            if Path(invalid_csv_path).exists():
                os.unlink(invalid_csv_path)

    def test_configuration_validation_integration(self, sample_config_file):
        """Test that configuration validation works correctly in integration."""
        # Test with valid configuration
        config = Config(sample_config_file)
        
        # Should validate successfully
        assert config.validate() is True
        
        # Test validation catches invalid configurations
        config._config['search']['api_key'] = ''
        
        with pytest.raises(ValueError, match="Search API key is required"):
            config.validate()

    def test_blocklist_filtering_comprehensive(self, sample_config_file):
        """Test comprehensive blocklist filtering functionality."""
        config = Config(sample_config_file)
        blocklist = config.get('filtering.blocklist', [])
        
        filter_manager = BlocklistFilter(blocklist)
        
        # Test URLs to filter
        test_urls = [
            "https://companycheck.co.uk/company/12345678",
            "https://globaldatabase.com/company/acme-ltd",
            "https://companieshouse.gov.uk/company/01234567",
            "https://endole.co.uk/company/12345678",
            "https://acme-manufacturing.co.uk",  # Should NOT be filtered
            "https://tech-innovations.com/about",  # Should NOT be filtered
            "https://subdomain.companycheck.co.uk/page",  # Should be filtered
        ]
        
        # Convert URLs to SearchResult objects for filtering
        from src.search.client import SearchResult
        search_results = [SearchResult(url=url, title="Test", snippet="Test", position=1) for url in test_urls]
        filtered_results = filter_manager.filter_results(search_results)
        filtered_urls = [result.url for result in filtered_results]
        
        # Should filter out all aggregator sites
        assert len(filtered_urls) == 2
        assert "https://acme-manufacturing.co.uk" in filtered_urls
        assert "https://tech-innovations.com/about" in filtered_urls
        
        # Should NOT contain any aggregator sites
        for url in filtered_urls:
            for blocked_domain in blocklist:
                assert blocked_domain not in url

    @patch('src.search.client.requests.get')
    def test_rate_limiting_in_integration(self, mock_get, sample_config_file):
        """Test that rate limiting works correctly in integration."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response
        
        config = Config(sample_config_file)
        
        # Create search client with rate limiting
        search_client = DuckDuckGoClient(
            api_key=config.get('search.api_key'),
            rate_limit=2.0  # 2 requests per second for testing
        )
        
        with patch('time.sleep') as mock_sleep:
            # Perform multiple searches
            for i in range(5):
                search_client.search(f"Test Company {i}")
            
            # Should have slept 4 times (between requests)
            assert mock_sleep.call_count == 4
            
            # Verify API was called 5 times
            assert mock_get.call_count == 5