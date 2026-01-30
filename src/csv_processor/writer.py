"""CSV writer module for Company Website Discovery Tool."""

import logging
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Sequence, Union
from datetime import datetime

from src.core.models import ScoredResult


logger = logging.getLogger(__name__)


class CSVWriter:
    """CSV writer for enriched company data with discovered websites."""
    
    def __init__(self, output_path: str):
        """Initialize CSV writer.
        
        Args:
            output_path: Path to the output CSV file
        """
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Define output columns
        self.columns = [
            'CompanyNumber',
            'CompanyName', 
            'Postcode',
            'SICCodes',
            'DiscoveredURL',
            'ConfidenceScore',
            'SearchPosition',
            'PageTitle',
            'PageSnippet',
            'DomainMatchScore',
            'TLDRelevanceScore',
            'SearchPositionScore',
            'TitleMatchScore',
            'ErrorFlag',
            'ErrorMessage',
            'ProcessingTimestamp'
        ]
    
    def _scored_result_to_dict(self, result: Union[ScoredResult, Any]) -> Dict[str, Any]:
        """Convert ScoredResult to dictionary for CSV writing.
        
        Args:
            result: ScoredResult object
            
        Returns:
            Dictionary representation for CSV
        """
        base_data = {
            'CompanyNumber': result.company.company_number,
            'CompanyName': result.company.company_name,
            'Postcode': result.company.postcode,
            'SICCodes': result.company.sic_codes or '',
            'ConfidenceScore': result.confidence_score,
            'ErrorFlag': result.error_flag,
            'ErrorMessage': result.error_message or '',
            'ProcessingTimestamp': datetime.now().isoformat()
        }
        
        if result.error_flag or not result.search_result:
            # Error case - no search result
            base_data.update({
                'DiscoveredURL': '',
                'SearchPosition': '',
                'PageTitle': '',
                'PageSnippet': '',
                'DomainMatchScore': '',
                'TLDRelevanceScore': '',
                'SearchPositionScore': '',
                'TitleMatchScore': ''
            })
        else:
            # Success case - has search result
            base_data.update({
                'DiscoveredURL': result.search_result.url,
                'SearchPosition': result.search_result.position,
                'PageTitle': result.search_result.title,
                'PageSnippet': result.search_result.snippet,
                'DomainMatchScore': result.scoring_details.get('domain_match', ''),
                'TLDRelevanceScore': result.scoring_details.get('tld_relevance', ''),
                'SearchPositionScore': result.scoring_details.get('search_position', ''),
                'TitleMatchScore': result.scoring_details.get('title_match', '')
            })
        
        return base_data
    
    def write_results(self, results: Sequence[Union[ScoredResult, Any]]) -> None:
        """Write scored results to CSV file.
        
        Args:
            results: List of ScoredResult objects
        """
        if not results:
            logger.warning("No results to write")
            return
        
        logger.info(f"Writing {len(results)} results to {self.output_path}")
        
        try:
            # Convert results to dictionaries
            rows = [self._scored_result_to_dict(result) for result in results]
            
            # Create DataFrame
            df = pd.DataFrame(rows)
            
            # Write to CSV (append if file exists)
            if self.output_path.exists():
                logger.info("Appending to existing CSV file")
                df.to_csv(self.output_path, mode='a', header=False, index=False)
            else:
                logger.info("Creating new CSV file")
                df.to_csv(self.output_path, mode='w', header=True, index=False)
            
            logger.info(f"Successfully wrote {len(rows)} rows to {self.output_path}")
            
        except Exception as e:
            logger.error(f"Error writing results to CSV: {e}")
            raise
    
    def write_batch_results(self, batch_results: List[ScoredResult], batch_number: int) -> None:
        """Write batch results with timestamped filename.
        
        Args:
            batch_results: List of ScoredResult objects for this batch
            batch_number: Batch number for timestamping
        """
        if not batch_results:
            logger.warning(f"No results in batch {batch_number}")
            return
        
        # Create timestamped filename for batch
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_filename = f"batch_{batch_number}_{timestamp}.csv"
        batch_path = self.output_path.parent / batch_filename
        
        logger.info(f"Writing batch {batch_number} results to {batch_path}")
        
        try:
            # Convert results to dictionaries
            rows = [self._scored_result_to_dict(result) for result in batch_results]
            
            # Create DataFrame
            df = pd.DataFrame(rows)
            
            # Write to new CSV file (never append for batch files)
            df.to_csv(batch_path, mode='w', header=True, index=False)
            
            logger.info(f"Successfully wrote batch {batch_number} with {len(rows)} rows to {batch_path}")
            
        except Exception as e:
            logger.error(f"Error writing batch results to CSV: {e}")
            raise