"""
Custom exceptions for the Company Website Discovery Tool.
"""


class CompanySiftError(Exception):
    """Base exception for all Company Website Discovery Tool errors."""
    pass


class ConfigurationError(CompanySiftError):
    """Raised when there's an error in configuration loading or validation."""
    pass


class CSVProcessingError(CompanySiftError):
    """Raised when there's an error processing CSV files."""
    pass


class SearchAPIError(CompanySiftError):
    """Raised when there's an error with the search API."""
    pass


class RateLimitError(SearchAPIError):
    """Raised when API rate limit is exceeded."""
    pass


class FilteringError(CompanySiftError):
    """Raised when there's an error in filtering logic."""
    pass


class ScoringError(CompanySiftError):
    """Raised when there's an error in confidence scoring."""
    pass


class StateError(CompanySiftError):
    """Raised when there's an error in state management or checkpointing."""
    pass