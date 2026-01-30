"""CLI command implementations for Company Website Discovery Tool."""

import logging
from pathlib import Path
from typing import Dict, Any

from core.config import Config
from core.exceptions import ConfigurationError


def process_companies(args, config: Config, logger: logging.Logger) -> None:
    """Process companies from CSV file to discover websites.

    Args:
        args: Command line arguments
        config: Application configuration
        logger: Logger instance
    """
    logger.info(f"Processing companies from {args.input}")
    logger.info(f"Output will be written to {args.output}")
    
    # Import required modules
    from src.csv_processor.reader import CSVReader
    from src.csv_processor.writer import CSVWriter
    from src.search.client import DuckDuckGoClient, SearchResult as ClientSearchResult
    from src.filtering.blocklist import BlocklistFilter
    from src.scoring.confidence import ConfidenceScorer
    from src.core.models import ScoredResult, SearchResult as ModelSearchResult
    
    # Validate API key before initializing components
    api_key = config.search_config.get('api_key', '')
    if not api_key or len(api_key.strip()) < 10:
        logger.error("DuckDuckGo API key is required but not configured.")
        logger.error("Please set the DUCKDUCKGO_API_KEY environment variable.")
        logger.error("Get your API key from: https://rapidapi.com/duckduckgo/api/duckduckgo8")
        raise ConfigurationError(
            "DuckDuckGo API key is required but not configured. "
            "Please set the DUCKDUCKGO_API_KEY environment variable. "
            "Get your API key from: https://rapidapi.com/duckduckgo/api/duckduckgo8"
        )
    else:
        logger.info(f"✅ API key validation passed (length: {len(api_key.strip())} chars)")
    
    # Initialize components
    csv_reader = CSVReader(args.input)
    csv_writer = CSVWriter(args.output)
    search_client = DuckDuckGoClient(config.search_config['api_key'], config.search_config['rate_limit'])
    blocklist_filter = BlocklistFilter(config.filtering_config['blocklist'])
    confidence_scorer = ConfidenceScorer(config.scoring_config['weights'])
    
    def convert_search_result(client_result: ClientSearchResult) -> ModelSearchResult:
        """Convert between SearchResult types."""
        return ModelSearchResult(
            url=client_result.url,
            title=client_result.title,
            snippet=client_result.snippet,
            position=client_result.position
        )
    
    # Process companies
    processed_count = 0
    success_count = 0
    error_count = 0
    
    try:
        for company in csv_reader.read_companies():
            processed_count += 1
            
            try:
                # Search for company website
                logger.debug(f"Searching for {company.company_name}")
                search_results = search_client.search(company.company_name, max_results=10)
                
                # Filter out aggregator sites
                filtered_results = blocklist_filter.filter_results(search_results)
                
                # Score remaining results
                scored_results = []
                for result in filtered_results:
                    score = confidence_scorer.calculate_score(company, result)
                    if score >= config.scoring_config['min_confidence']:
                        # Create ScoredResult object
                        scored_result = ScoredResult(
                            company=company,
                            search_result=convert_search_result(result),
                            confidence_score=score,
                            scoring_details=confidence_scorer.get_scoring_details(),
                            error_flag=False,
                            error_message=None
                        )
                        scored_results.append(scored_result)
                
                # Write results (even if empty)
                if scored_results:
                    csv_writer.write_results(scored_results)
                    success_count += 1
                else:
                    # Create error result for no matches
                    dummy_result = ModelSearchResult(
                        url="",
                        title="",
                        snippet="",
                        position=0
                    )
                    error_result = ScoredResult(
                        company=company,
                        search_result=dummy_result,
                        confidence_score=0,
                        scoring_details={},
                        error_flag=True,
                        error_message="No high-confidence matches found"
                    )
                    csv_writer.write_results([error_result])
                    error_count += 1
                
                if processed_count % 10 == 0:
                    logger.info(f"Processed {processed_count} companies...")
                    
            except Exception as e:
                logger.error(f"Error processing {company.company_name}: {str(e)}")
                error_count += 1
                # Create error result
                dummy_result = ModelSearchResult(
                    url="",
                    title="",
                    snippet="",
                    position=0
                )
                error_result = ScoredResult(
                    company=company,
                    search_result=dummy_result,
                    confidence_score=0,
                    scoring_details={},
                    error_flag=True,
                    error_message=str(e)
                )
                csv_writer.write_results([error_result])
    
    except Exception as e:
        logger.error(f"Fatal error during processing: {str(e)}")
        raise
    
    logger.info(f"Processing completed: {success_count} successful, {error_count} errors out of {processed_count} total")
    print(f"Processing completed: {success_count} successful, {error_count} errors out of {processed_count} total")


def manage_blocklist(args, config: Config, logger: logging.Logger) -> None:
    """Manage aggregator site blocklist.
    
    Args:
        args: Command line arguments
        config: Application configuration
        logger: Logger instance
    """
    if args.blocklist_action == 'list':
        logger.info("Listing blocked domains")
        blocklist = config.get('filtering.blocklist', [])
        
        if blocklist:
            print("Blocked domains:")
            for domain in blocklist:
                print(f"  - {domain}")
        else:
            print("No domains in blocklist")
    
    elif args.blocklist_action == 'add':
        logger.info(f"Adding {args.domain} to blocklist")
        # TODO: Implement blocklist addition
        print(f"Adding {args.domain} to blocklist (implementation pending)")
    
    elif args.blocklist_action == 'remove':
        logger.info(f"Removing {args.domain} from blocklist")
        # TODO: Implement blocklist removal
        print(f"Removing {args.domain} from blocklist (implementation pending)")
    
    else:
        logger.error(f"Unknown blocklist action: {args.blocklist_action}")
        raise ValueError(f"Unknown blocklist action: {args.blocklist_action}")