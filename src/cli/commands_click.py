"""
CLI commands for Company Website Discovery Tool (Click implementation).
"""

import click
import tempfile
import os
import yaml
import sys
from pathlib import Path
from typing import Optional, List
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from src.csv_processor.reader import CSVReader
from src.search.client import DuckDuckGoClient
from src.filtering.blocklist import BlocklistFilter
from src.scoring.confidence import ConfidenceScorer
from src.csv_processor.writer import CSVWriter
from src.core.models import ScoredResult, SearchResult
from src.core.config import Config


# Load configuration for blocklist
try:
    config = Config("config/config.yaml")
    _BLOCKLIST = config.get("filtering.blocklist", [
        "companycheck.co.uk", 
        "globaldatabase.com", 
        "companieshouse.gov.uk", 
        "endole.co.uk"
    ])
except Exception as e:
    print(f"Warning: Could not load config file, using default blocklist: {e}")
    _BLOCKLIST = ["companycheck.co.uk", "globaldatabase.com", "companieshouse.gov.uk", "endole.co.uk"]


@click.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True), 
              help='Path to input CSV file with company data')
@click.option('--output', '-o', required=True, type=click.Path(), 
              help='Path to output CSV file for results')
@click.option('--api-key', required=True, 
              help='DuckDuckGo RapidAPI key')
@click.option('--batch-size', default=50, type=int,
              help='Number of companies to process per batch')
@click.option('--min-confidence', default=50, type=int,
              help='Minimum confidence score (0-100) for results')
@click.option('--verbose', '-v', is_flag=True,
              help='Enable verbose output')
def process_companies(input: str, output: str, api_key: str, batch_size: int, 
                     min_confidence: int, verbose: bool):
    """Process companies from CSV file to discover websites."""
    
    try:
        # Validate API key presence and format
        env_api_key = os.getenv('DUCKDUCKGO_API_KEY')
        
        if not api_key or len(api_key.strip()) < 10:
            click.echo("❌ ERROR: DuckDuckGo API key is required but not configured.", err=True)
            click.echo("Please set the DUCKDUCKGO_API_KEY environment variable:", err=True)
            click.echo("  export DUCKDUCKGO_API_KEY=\"your-rapidapi-key-here\"", err=True)
            click.echo("Get your API key from: https://rapidapi.com/duckduckgo/api/duckduckgo8", err=True)
            sys.exit(1)
        else:
            # Determine API key source
            if api_key == env_api_key:
                click.echo(f"✅ API key loaded from environment variable (length: {len(api_key.strip())} chars)")
            else:
                click.echo(f"✅ API key provided via CLI parameter (length: {len(api_key.strip())} chars)")
        
        # Validate input file
        input_path = Path(input)
        if not input_path.exists():
            click.echo(f"❌ Error: Input file not found: {input}", err=True)
            click.echo("Tip: Check the file path and ensure the file exists.", err=True)
            return 1
             
        if input_path.suffix.lower() != '.csv':
            click.echo(f"❌ Error: Input file must be CSV format: {input}", err=True)
            click.echo("Tip: Convert your file to CSV format and try again.", err=True)
            sys.exit(1)
        
        # Check for large files and warn user
        file_size = input_path.stat().st_size
        large_file_threshold = 10 * 1024  # 10KB for testing, 10MB for production
        if file_size > large_file_threshold:
            click.echo(f"⚠️  Warning: Large file detected ({file_size:,} bytes)")
            click.echo("Processing large files may take significant time and API credits.")
            if not click.confirm("Do you want to continue?", default=False):
                click.echo("Operation cancelled by user.")
                return 0
        
        # Initialize components
        if verbose:
            click.echo(f"Loading companies from {input}...")
            
        reader = CSVReader(str(input_path))
        companies = list(reader.read_companies())
        
        if verbose:
            click.echo(f"Loaded {len(companies)} companies")
            
        # Initialize search client
        search_client = DuckDuckGoClient(api_key=api_key, rate_limit=4.5)
        
        # Initialize blocklist filter
        blocklist_filter = BlocklistFilter(_BLOCKLIST)
        
        # Initialize confidence scorer
        scorer = ConfidenceScorer()
        
        # Initialize CSV writer and handle output directory creation
        output_path = Path(output)
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if verbose:
                click.echo(f"Created output directory: {output_path.parent}")
        
        # Check for overwrite protection
        if output_path.exists():
            if verbose:
                click.echo(f"⚠️  Warning: Output file already exists: {output}")
            if not click.confirm("Do you want to overwrite the existing file?", default=False):
                click.echo("Operation cancelled by user.")
                return 0
        
        writer = CSVWriter(str(output_path))
        
        # Process companies in batches
        total_processed = 0
        results = []
        
        # Use tqdm for progress bar if available and verbose
        progress_bar = None
        if verbose and tqdm:
            progress_bar = tqdm(companies, desc="Processing companies", unit="company")
        
        for i, company in enumerate(companies, 1):
            if verbose and not tqdm:
                click.echo(f"Processing company {i}/{len(companies)}: {company.company_name}")
            elif progress_bar:
                progress_bar.set_description(f"Processing {company.company_name}")
                 
            try:
                # Search for company website
                search_results = search_client.search(company.company_name)
                 
                # Filter aggregator sites
                filtered_results = blocklist_filter.filter_results(search_results)
                 
                # Score and filter by confidence
                scored_results = []
                for result in filtered_results:
                    confidence = scorer.calculate_score(company, result)
                    if confidence >= min_confidence:
                        # Create proper ScoredResult object
                        # Ensure position is at least 1
                        position = max(1, getattr(result, 'position', 1))
                        search_result = SearchResult(
                            url=result.url,
                            title=result.title,
                            snippet=result.snippet,
                            position=position
                        )
                        scored_result = ScoredResult(
                            company=company,
                            search_result=search_result,
                            confidence_score=confidence,
                            scoring_details={
                                'domain_match': 0.4 * confidence / 100,
                                'tld_relevance': 0.2 * confidence / 100,
                                'search_position': 0.3 * confidence / 100,
                                'title_match': 0.1 * confidence / 100
                            }
                        )
                        scored_results.append(scored_result)
                 
                # Add to results - use ScoredResult objects directly
                results.extend(scored_results)
                 
                total_processed += 1
                
                # Update progress bar
                if progress_bar:
                    progress_bar.update(1)
                    
            except Exception as e:
                if verbose:
                    click.echo(f"Error processing {company.company_name}: {e}", err=True)
                
                # Add error entry as ScoredResult
                empty_search_result = SearchResult(
                    url='',
                    title='',
                    snippet='',
                    position=1  # Position must be at least 1
                )
                error_result = ScoredResult(
                    company=company,
                    search_result=empty_search_result,
                    confidence_score=0,
                    scoring_details={
                        'domain_match': 0,
                        'tld_relevance': 0,
                        'search_position': 0,
                        'title_match': 0
                    },
                    error_flag=True,
                    error_message=str(e)
                )
                results.append(error_result)
        
        # Write results
        if verbose:
            click.echo(f"Writing results to {output}...")
            
        writer.write_results(results)
        
        # Close progress bar if it was used
        if progress_bar:
            progress_bar.close()
        
        # Final status message with colored output
        if total_processed == len(companies):
            status_msg = click.style("✅ SUCCESS", fg="green", bold=True)
            summary = f"{status_msg}: Processed {total_processed}/{len(companies)} companies"
        else:
            status_msg = click.style("⚠️  PARTIAL", fg="yellow", bold=True)
            summary = f"{status_msg}: Processed {total_processed}/{len(companies)} companies"
            
        click.echo(summary)
        
        if verbose:
            click.echo(f"Details: {total_processed} companies processed successfully")
            
        return 0
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@click.group()
def manage_blocklist():
    """Manage aggregator site blocklist."""
    pass


@manage_blocklist.command('add')
@click.argument('domain')
def add_to_blocklist(domain: str):
    """Add domain to blocklist."""
    global _BLOCKLIST
    
    if domain in _BLOCKLIST:
        click.echo(f"Domain {domain} is already in blocklist")
        return 0
        
    _BLOCKLIST.append(domain)
    click.echo(f"Added {domain} to blocklist")
    return 0


@manage_blocklist.command('remove')
@click.argument('domain')
def remove_from_blocklist(domain: str):
    """Remove domain from blocklist."""
    global _BLOCKLIST
    
    if domain not in _BLOCKLIST:
        click.echo(f"Domain {domain} is not in blocklist")
        return 0
        
    _BLOCKLIST.remove(domain)
    click.echo(f"Removed {domain} from blocklist")
    return 0


@manage_blocklist.command('list')
def list_blocklist():
    """List blocked domains."""
    if not _BLOCKLIST:
        click.echo("Blocklist is empty")
        return 0
        
    click.echo("Blocklist:")
    for domain in _BLOCKLIST:
        click.echo(f"  - {domain}")
        
    return 0


@manage_blocklist.command('clear')
def clear_blocklist():
    """Clear blocklist."""
    global _BLOCKLIST
    
    _BLOCKLIST = []
    click.echo("Blocklist cleared")
    return 0


@click.group()
def config_commands():
    """Configuration management commands."""
    pass


@config_commands.command('show')
def config_show():
    """Show current configuration."""
    try:
        config = Config("config/config.yaml")
        config_dict = config.get_all()
        
        click.echo("Current Configuration:")
        click.echo(yaml.dump(config_dict, default_flow_style=False, sort_keys=False))
        return 0
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        return 1


@config_commands.command('validate')
def config_validate():
    """Validate configuration file."""
    try:
        config = Config("config/config.yaml")
        config.validate()
        click.echo("✅ Configuration is valid")
        return 0
    except Exception as e:
        click.echo(f"❌ Configuration validation failed: {e}", err=True)
        return 1


@config_commands.command('example')
def config_example():
    """Show example configuration."""
    example_config = {
        'search': {
            'provider': 'duckduckgo',
            'api_key': '${DUCKDUCKGO_API_KEY}',
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
            'file': 'company_sift.log'
        }
    }
    
    click.echo("Example Configuration:")
    click.echo(yaml.dump(example_config, default_flow_style=False, sort_keys=False))
    click.echo("\nTo use this configuration:")
    click.echo("1. Save to config/config.yaml")
    click.echo("2. Set DUCKDUCKGO_API_KEY environment variable")
    click.echo("3. Adjust parameters as needed")
    return 0