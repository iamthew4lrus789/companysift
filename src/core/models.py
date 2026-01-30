"""Data models for Company Website Discovery Tool."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class Company:
    """Represents a company from the input CSV."""
    company_number: str
    company_name: str
    postcode: str
    sic_codes: Optional[str] = None
    # Allow additional fields from input CSV
    extra_data: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_csv_row(cls, row: Dict[str, str]) -> 'Company':
        """Create Company from CSV row.
        
        Args:
            row: Dictionary representing CSV row
            
        Returns:
            Company instance
        """
        # Extract known fields with multiple fallback options
        company_number = (
            row.get('CompanyNumber', '') or
            row.get('company_number', '') or
            row.get('companynumber', '')
        )
        company_name = (
            row.get('CompanyName', '') or
            row.get('company_name', '') or
            row.get('companyname', '')
        )
        postcode = (
            row.get('Postcode', '') or
            row.get('postcode', '') or
            row.get('postcode', '')
        )
        sic_codes = (
            row.get('SICCodes', None) or
            row.get('sic_codes', None) or
            row.get('siccodes', None)
        )
        # Convert empty string to None for SIC codes
        if sic_codes == '':
            sic_codes = None
        
        # Store any extra fields
        known_fields = {
            'CompanyNumber', 'CompanyName', 'Postcode', 'SICCodes',
            'company_number', 'company_name', 'postcode', 'sic_codes',
            'companynumber', 'companyname', 'siccodes'
        }
        extra_data = {k: v for k, v in row.items() if k not in known_fields}
        
        return cls(
            company_number=company_number,
            company_name=company_name,
            postcode=postcode,
            sic_codes=sic_codes,
            extra_data=extra_data if extra_data else None
        )


@dataclass
class SearchResult:
    """Represents a search result for a company."""
    url: str
    title: str
    snippet: str
    position: int  # Position in search results (1-based)
    
    def __post_init__(self):
        """Validate and normalize data after initialization."""
        if self.position < 0:
            raise ValueError("Search position must be 0 or greater")


@dataclass
class ScoredResult:
    """Represents a search result with confidence scoring."""
    company: Company
    search_result: SearchResult
    confidence_score: float  # 0-100
    scoring_details: Dict[str, float]  # Breakdown of scoring factors
    error_flag: bool = False
    error_message: Optional[str] = None
    
    def __post_init__(self):
        """Validate confidence score."""
        if not (0 <= self.confidence_score <= 100):
            raise ValueError("Confidence score must be between 0 and 100")


@dataclass
class ProcessingState:
    """Represents the current processing state for checkpointing."""
    input_file: str
    output_file: str
    total_companies: int
    processed_companies: int
    current_batch: int
    last_processed_row: int
    start_time: datetime
    last_update: datetime
    status: str  # 'running', 'completed', 'error', 'interrupted'
    error_count: int = 0
    
    def __post_init__(self):
        """Validate processing state."""
        if self.processed_companies > self.total_companies:
            raise ValueError("Processed companies cannot exceed total companies")
        if self.current_batch < 0:
            raise ValueError("Current batch cannot be negative")


@dataclass
class BatchResult:
    """Represents the result of processing a batch of companies."""
    batch_number: int
    start_row: int
    end_row: int
    companies_processed: int
    results: List[ScoredResult]
    errors: List[Dict[str, str]]  # List of error records
    processing_time: float  # seconds
    timestamp: datetime
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate for this batch."""
        if self.companies_processed == 0:
            return 0.0
        successful = len([r for r in self.results if not r.error_flag])
        return successful / self.companies_processed


@dataclass
class FilteredResult:
    """Represents a result after filtering (e.g., removing aggregators)."""
    original_result: SearchResult
    filtered_reason: Optional[str] = None  # Why this was filtered out
    is_aggregator: bool = False
    
    @property
    def should_include(self) -> bool:
        """Whether this result should be included in final output."""
        return self.filtered_reason is None and not self.is_aggregator