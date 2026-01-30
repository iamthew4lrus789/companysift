"""
Domain frequency tracking system for dynamic aggregator detection.

This module implements a system that tracks domain appearances across multiple
company searches to identify aggregator sites that appear frequently versus
genuine company websites that appear rarely.
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Set, List, Any, Optional

from src.search.client import SearchResult


class DomainFrequencyTracker:
    """
    Track domain frequencies across multiple searches to identify aggregators.
    
    Aggregator sites tend to appear in searches for many different companies,
    while genuine company websites appear only for their specific company.
    """

    def __init__(self):
        """Initialize domain frequency tracker."""
        self.domain_counts = defaultdict(int)  # domain -> appearance count
        self.company_domains = defaultdict(set)  # domain -> set of company names
        self.total_searches = 0  # total number of searches tracked

    def track_search_results(self, company_name: str, search_results: List[SearchResult]) -> None:
        """
        Track domains from search results for frequency analysis.
        
        Args:
            company_name: Name of the company being searched
            search_results: List of SearchResult objects from the search
        """
        self.total_searches += 1
        
        for result in search_results:
            domain = self._extract_domain(result.url)
            self.domain_counts[domain] += 1
            self.company_domains[domain].add(company_name)

    def _extract_domain(self, url: str) -> str:
        """
        Extract base domain from URL, handling various formats.
        
        Args:
            url: Full URL
            
        Returns:
            Base domain (without www. prefix, keeping meaningful subdomains)
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # Remove port numbers
        domain = domain.split(':')[0]
        
        # For now, keep the full domain as extracted
        # Subdomain handling can be enhanced later based on specific needs
        return domain

    def identify_aggregators(self, threshold: float = 0.3, min_occurrences: int = 3) -> Set[str]:
        """
        Identify potential aggregator domains based on frequency patterns.
        
        Args:
            threshold: Minimum frequency threshold (0-1) for domain to be considered aggregator
            min_occurrences: Minimum number of times domain must appear
            
        Returns:
            Set of domains identified as aggregators
        """
        aggregators = set()
        
        if self.total_searches == 0:
            return aggregators
            
        for domain, count in self.domain_counts.items():
            frequency = count / self.total_searches
            
            # Domain is an aggregator if it appears frequently across searches
            if count >= min_occurrences and frequency >= threshold:
                aggregators.add(domain)
        
        return aggregators

    def get_domain_stats(self, domain: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific domain.
        
        Args:
            domain: Domain to get statistics for
            
        Returns:
            Dictionary containing domain statistics
        """
        count = self.domain_counts.get(domain, 0)
        frequency = count / self.total_searches if self.total_searches > 0 else 0
        companies = list(self.company_domains.get(domain, set()))
        
        return {
            'count': count,
            'frequency': frequency,
            'companies': companies,
            'is_aggregator': self._is_aggregator(domain)
        }

    def _is_aggregator(self, domain: str, threshold: float = 0.3, min_occurrences: int = 3) -> bool:
        """
        Check if a domain is likely an aggregator.
        
        Args:
            domain: Domain to check
            threshold: Frequency threshold
            min_occurrences: Minimum occurrences
            
        Returns:
            True if domain is likely an aggregator
        """
        count = self.domain_counts.get(domain, 0)
        frequency = count / self.total_searches if self.total_searches > 0 else 0
        return count >= min_occurrences and frequency >= threshold

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of domain tracking.
        
        Returns:
            Summary statistics dictionary
        """
        aggregators = self.identify_aggregators()
        unique_domains = len(self.domain_counts)
        
        return {
            'total_searches': self.total_searches,
            'unique_domains': unique_domains,
            'identified_aggregators': len(aggregators),
            'aggregator_domains': list(aggregators),
            'average_domains_per_search': unique_domains / self.total_searches if self.total_searches > 0 else 0
        }

    def reset(self) -> None:
        """Reset all tracking data."""
        self.domain_counts.clear()
        self.company_domains.clear()
        self.total_searches = 0


class DomainCachePersistence:
    """
    Persist domain frequency data to disk for use across processing sessions.
    """

    def __init__(self, cache_file: str = 'data/domain_cache.json'):
        """
        Initialize domain cache persistence.
        
        Args:
            cache_file: Path to cache file
        """
        self.cache_file = cache_file
        self.cache = self._load_cache()
        
        # Ensure data directory exists
        cache_path = Path(cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> Dict[str, Any]:
        """
        Load domain cache from file.
        
        Returns:
            Loaded cache data or empty cache if file doesn't exist
        """
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Return empty cache structure
            return {
                'domain_counts': {},
                'company_domains': {},
                'total_searches': 0
            }

    def save_cache(self) -> None:
        """Save domain cache to file."""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)

    def update_cache(self, domain: str, company_name: str) -> None:
        """
        Update cache with new domain sighting.
        
        Args:
            domain: Domain that was sighted
            company_name: Company associated with this sighting
        """
        # Update domain count
        self.cache['domain_counts'][domain] = self.cache['domain_counts'].get(domain, 0) + 1
        
        # Update company association (avoid duplicates)
        if company_name not in self.cache['company_domains'].get(domain, []):
            self.cache['company_domains'][domain] = self.cache['company_domains'].get(domain, []) + [company_name]
        
        # Save to disk
        self.save_cache()
    
    def increment_search_count(self) -> None:
        """Increment the total searches count."""
        self.cache['total_searches'] += 1
        self.save_cache()

    def load_into_tracker(self, tracker: DomainFrequencyTracker) -> None:
        """
        Load cached data into a DomainFrequencyTracker instance.
        
        Args:
            tracker: DomainFrequencyTracker instance to load data into
        """
        tracker.domain_counts = defaultdict(int, self.cache['domain_counts'])
        
        # Convert lists to sets for company_domains
        company_domains = defaultdict(set)
        for domain, companies in self.cache['company_domains'].items():
            company_domains[domain] = set(companies)
        
        tracker.company_domains = company_domains
        tracker.total_searches = self.cache['total_searches']

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.cache = {
            'domain_counts': {},
            'company_domains': {},
            'total_searches': 0
        }
        self.save_cache()


class EnhancedBlocklistFilter:
    """
    Enhanced blocklist filter that combines static blocklist with dynamic aggregator detection.
    """

    def __init__(self, static_blocklist: List[str], frequency_tracker: DomainFrequencyTracker):
        """
        Initialize enhanced blocklist filter.
        
        Args:
            static_blocklist: List of statically blocked domains
            frequency_tracker: DomainFrequencyTracker instance for dynamic detection
        """
        self.static_blocklist = static_blocklist
        self.frequency_tracker = frequency_tracker

    def filter_results(self, results: List[SearchResult], company_name: str) -> List[SearchResult]:
        """
        Filter search results using both static and dynamic blocklists.
        
        Args:
            results: List of SearchResult objects to filter
            company_name: Name of company being processed
            
        Returns:
            Filtered list of SearchResult objects
        """
        # First pass: static blocklist filtering
        filtered = self._apply_static_filter(results)
        
        # Second pass: dynamic aggregator filtering
        filtered = self._apply_dynamic_filter(filtered, company_name)
        
        return filtered

    def _apply_static_filter(self, results: List[SearchResult]) -> List[SearchResult]:
        """Apply static blocklist filtering."""
        filtered = []
        for result in results:
            domain = self.frequency_tracker._extract_domain(result.url)
            if domain not in self.static_blocklist:
                filtered.append(result)
        return filtered

    def _apply_dynamic_filter(self, results: List[SearchResult], company_name: str) -> List[SearchResult]:
        """Apply dynamic aggregator filtering."""
        # Track these results first
        self.frequency_tracker.track_search_results(company_name, results)
        
        # Identify current aggregators
        aggregators = self.frequency_tracker.identify_aggregators()
        
        # Filter out dynamic aggregators
        filtered = []
        for result in results:
            domain = self.frequency_tracker._extract_domain(result.url)
            if domain not in aggregators:
                filtered.append(result)
        
        return filtered

    def get_filtering_report(self) -> Dict[str, Any]:
        """
        Generate report on filtering effectiveness.
        
        Returns:
            Filtering report dictionary
        """
        static_blocked = len(self.static_blocklist)
        dynamic_aggregators = len(self.frequency_tracker.identify_aggregators())
        
        return {
            'static_blocklist_size': static_blocked,
            'dynamic_aggregators_detected': dynamic_aggregators,
            'total_blocked_domains': static_blocked + dynamic_aggregators,
            'frequency_summary': self.frequency_tracker.get_summary()
        }

    def get_suspected_aggregators(self, min_suspicion: float = 0.1) -> List[Dict[str, Any]]:
        """
        Get list of domains that are suspected aggregators but not yet confirmed.
        
        Args:
            min_suspicion: Minimum frequency to be considered suspicious
            
        Returns:
            List of suspected aggregator domains with statistics
        """
        suspected = []
        confirmed_aggregators = self.frequency_tracker.identify_aggregators()
        
        for domain, count in self.frequency_tracker.domain_counts.items():
            if domain in self.static_blocklist or domain in confirmed_aggregators:
                continue
                
            frequency = count / self.frequency_tracker.total_searches
            if frequency >= min_suspicion:
                suspected.append({
                    'domain': domain,
                    'count': count,
                    'frequency': frequency,
                    'companies': list(self.frequency_tracker.company_domains[domain])
                })
        
        # Sort by frequency (most suspicious first)
        suspected.sort(key=lambda x: x['frequency'], reverse=True)
        return suspected