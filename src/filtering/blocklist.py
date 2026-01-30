"""
Blocklist filtering for aggregator sites.
"""

from typing import List, Optional
from urllib.parse import urlparse

from src.search.client import SearchResult


class BlocklistFilter:
    """
    Filter search results to remove aggregator sites using a blocklist.
    
    This module blocks known aggregator sites like companycheck.co.uk,
    globaldatabase.com, etc. that scrape and republish company information.
    """
    
    def __init__(self, blocklist: List[str]):
        """
        Initialize the blocklist filter.
        
        Args:
            blocklist: List of domains to block (e.g., ["companycheck.co.uk", "globaldatabase.com"])
        """
        self.blocklist = [domain.lower().strip() for domain in blocklist if domain.strip()]

    def filter_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Filter search results to remove blocklisted domains.
        
        Args:
            results: List of SearchResult objects to filter
            
        Returns:
            List of SearchResult objects with blocklisted domains removed
        """
        if not results:
            return []
            
        return [result for result in results if not self._is_blocked(result.url)]

    def _is_blocked(self, url: Optional[str]) -> bool:
        """
        Check if a URL is blocklisted.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL is blocklisted, False otherwise
        """
        if not url:
            return False
            
        try:
            # Parse URL to extract domain
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix for matching
            if domain.startswith("www."):
                domain = domain[4:]
                
            # Check if domain or any subdomain is blocklisted
            for blocked_domain in self.blocklist:
                # Exact match or subdomain match
                if (domain == blocked_domain or 
                    domain.endswith("." + blocked_domain)):
                    return True
                    
            return False
            
        except (ValueError, AttributeError):
            # Invalid URL format - don't block
            return False

    def update_blocklist(self, new_blocklist: List[str]) -> None:
        """
        Update the blocklist with new domains.
        
        Args:
            new_blocklist: New list of domains to block
        """
        self.blocklist = [domain.lower().strip() for domain in new_blocklist if domain.strip()]