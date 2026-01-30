"""
URL quality scoring system for better aggregator detection.

This module analyzes URL patterns to distinguish genuine company websites
from aggregator sites based on domain structure, path patterns, and
other URL characteristics.
"""

import re
from urllib.parse import urlparse
from typing import Optional


class URLQualityAnalyzer:
    """
    Analyze URL patterns to determine likelihood of being a genuine company website.
    
    Uses multiple factors including domain structure, path patterns, parameters,
    and TLD analysis to score URLs on a 0-100 scale.
    """

    def __init__(self, min_quality_threshold: float = 60.0):
        """
        Initialize URL quality analyzer.
        
        Args:
            min_quality_threshold: Minimum score to consider URL high-quality (0-100)
        """
        self.min_quality_threshold = min_quality_threshold
        
        # Compile regex patterns for performance
        self._company_word_regex = re.compile(r'[A-Z][a-z]+|[a-z]+')
        
        # Aggregator keywords
        self._aggregator_keywords = [
            'company', 'business', 'data', 'check', 'directory',
            'search', 'info', 'profile', 'register', 'database',
            'browse', 'insight', 'report', 'detail', 'find',
            'check', 'verify', 'search', 'lookup', 'directory'
        ]
        
        # Genuine path patterns
        self._genuine_paths = ['/about', '/company', '/about-us', '/contact', '/team']
        
        # Aggregator path patterns
        self._aggregator_paths = [
            '/company/', '/companies/', '/business/', '/profile/',
            '/search/', '/insight/', '/report/', '/detail.php',
            '/browse/', '/company-profiles', '/directory/',
            '/company_number', '/companyname', '/comp/'
        ]

    def calculate_url_quality(self, company_name: str, url: str) -> float:
        """
        Calculate quality score for URL based on multiple factors.
        
        Args:
            company_name: Name of the company
            url: URL to analyze
            
        Returns:
            Quality score (0-100) where higher is better
        """
        try:
            parsed = urlparse(url)
            domain = self._clean_domain(parsed.netloc)
            
            # Calculate component scores
            domain_score = self._analyze_domain(company_name, domain)
            path_score = self._analyze_path(parsed.path)
            param_score = self._analyze_parameters(parsed.query)
            tld_score = self._analyze_tld(domain)
            
            # Weighted average (domain most important, parameters least)
            final_score = (
                domain_score * 0.4 +
                path_score * 0.3 +
                param_score * 0.2 +
                tld_score * 0.1
            )
            
            return round(final_score, 1)
            
        except Exception:
            # If URL parsing fails, assume medium quality
            return 50.0

    def _clean_domain(self, domain: str) -> str:
        """Clean domain by removing www. prefix and port numbers."""
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Remove port numbers
        domain = domain.split(':')[0]
        
        return domain

    def _analyze_domain(self, company_name: str, domain: str) -> float:
        """Analyze domain for genuine company website indicators."""
        score = 100.0
        
        # Extract words from company name and domain
        company_words = self._company_word_regex.findall(company_name.lower())
        domain_words = self._company_word_regex.findall(domain.lower())
        
        # Check if any company name words appear in domain
        name_match = any(word in domain.lower() for word in company_words)
        
        if not name_match:
            score -= 50.0  # Major penalty for no name match
        
        # Check for aggregator keywords in domain
        for keyword in self._aggregator_keywords:
            if keyword in domain.lower():
                score -= 20.0
        
        # Bonus for exact or close matches
        if domain.lower().startswith(company_name.lower().replace(' ', '')):
            score += 10.0
        elif any(word in domain.lower() for word in company_words):
            score += 5.0
        
        return max(0.0, min(100.0, score))

    def _analyze_path(self, path: str) -> float:
        """Analyze URL path for aggregator patterns."""
        score = 100.0
        path_lower = path.lower()
        
        # Check for aggregator path patterns
        for pattern in self._aggregator_paths:
            if pattern.lower() in path_lower:
                score -= 30.0
                break
        
        # Bonus for genuine paths
        for pattern in self._genuine_paths:
            if pattern.lower() in path_lower:
                score += 10.0
                break
        
        return max(0.0, min(100.0, score))

    def _analyze_parameters(self, query: str) -> float:
        """Analyze URL parameters for aggregator patterns."""
        score = 100.0
        
        if not query:
            return score  # No parameters is good
        
        query_lower = query.lower()
        
        # Check for company identifiers in parameters
        if any(param in query_lower for param in 
               ['company', 'comp', 'business', 'id', 'number']):
            score -= 40.0
        
        return max(0.0, min(100.0, score))

    def _analyze_tld(self, domain: str) -> float:
        """Analyze TLD for trustworthiness."""
        try:
            # Get TLD (last part of domain)
            parts = domain.split('.')
            tld = parts[-1].lower()
            
            # Trusted TLDs
            trusted_tlds = ['co.uk', 'com', 'uk', 'org', 'net', 'io', 'ai', 'uk']
            
            if tld in trusted_tlds:
                return 100.0
            elif len(tld) <= 3:  # Short TLDs are usually OK
                return 90.0
            else:  # Country codes or new TLDs
                return 70.0
        
        except:
            return 70.0

    def is_high_quality(self, company_name: str, url: str) -> bool:
        """Check if URL meets minimum quality threshold."""
        score = self.calculate_url_quality(company_name, url)
        return score >= self.min_quality_threshold

    def get_score_breakdown(self, company_name: str, url: str) -> dict:
        """Get detailed score breakdown for debugging."""
        parsed = urlparse(url)
        domain = self._clean_domain(parsed.netloc)
        
        return {
            'url': url,
            'domain': domain,
            'domain_score': self._analyze_domain(company_name, domain),
            'path_score': self._analyze_path(parsed.path),
            'param_score': self._analyze_parameters(parsed.query),
            'tld_score': self._analyze_tld(domain),
            'final_score': self.calculate_url_quality(company_name, url),
            'is_high_quality': self.is_high_quality(company_name, url)
        }


class URLQualityCache:
    """
    Cache URL quality scores to avoid recomputation.
    """

    def __init__(self):
        self._cache = {}

    def get_score(self, company_name: str, url: str, analyzer: URLQualityAnalyzer) -> float:
        """Get cached score or compute and cache it."""
        cache_key = (company_name.lower(), url)
        
        if cache_key not in self._cache:
            self._cache[cache_key] = analyzer.calculate_url_quality(company_name, url)
        
        return self._cache[cache_key]

    def is_high_quality(self, company_name: str, url: str, analyzer: URLQualityAnalyzer) -> bool:
        """Check if URL is high quality using cache."""
        score = self.get_score(company_name, url, analyzer)
        return score >= analyzer.min_quality_threshold

    def clear_cache(self):
        """Clear all cached scores."""
        self._cache.clear()

    def get_cache_size(self) -> int:
        """Get number of cached scores."""
        return len(self._cache)