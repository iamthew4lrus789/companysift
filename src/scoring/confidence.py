"""
Confidence scoring system for search results.
"""

from typing import List, Dict, Optional
from urllib.parse import urlparse
import re

from src.search.client import SearchResult
from src.core.models import Company
from src.filtering.blocklist import BlocklistFilter


class ConfidenceScorer:
    """
    Calculate confidence scores for search results based on multiple factors.
    
    The confidence score (0-100) indicates how likely a search result is to be
    the actual company website rather than an aggregator site or unrelated page.
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize the confidence scorer.
        
        Args:
            weights: Custom weights for scoring factors. If None, uses defaults.
        """
        self.weights = weights or {
            "domain_match": 0.4,      # Domain-company name similarity
            "tld_relevance": 0.4,     # UK TLD preference for UK companies (INCREASED)
            "search_position": 0.1,   # Search result ranking position (DECREASED)
            "title_match": 0.1       # Page title match to company name
        }
        
        # Normalize weights to sum to 1.0
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            for key in self.weights:
                self.weights[key] /= total_weight
    
    def _clean_company_name_for_matching(self, company_name: str) -> str:
        """
        Clean company name by removing common suffixes for better domain matching.
        
        Args:
            company_name: Original company name
            
        Returns:
            Cleaned company name with common suffixes removed
        """
        # Convert to uppercase and remove special characters
        clean_name = re.sub(r'[^\w]', ' ', company_name).upper()
        words = clean_name.split()
        
        if len(words) > 1:
            # Check if last word is a common suffix
            last_word = words[-1]
            common_suffixes = {'LIMITED', 'LTD', 'PLC', 'LLC', 'INC', 'CORP', 'CO', 'GROUP'}
            
            if last_word in common_suffixes:
                # Remove suffix and return cleaned name
                return ' '.join(words[:-1])
        
        return company_name

    def calculate_score(self, company: Company, result: SearchResult) -> float:
        """Calculate confidence score for a search result.
        
        Args:
            company: Company object with name and other details
            result: SearchResult object to score
            
        Returns:
            Confidence score (0-100)
        """
        # Calculate individual component scores (0-1.0)
        domain_score = self._calculate_domain_match(company, result)
        tld_score = self._calculate_tld_relevance(result, company)
        position_score = self._calculate_position_score(result)
        title_score = self._calculate_title_match(company, result)
        
        # Store individual scores for get_scoring_details()
        self._last_domain_score = domain_score
        self._last_tld_score = tld_score
        self._last_position_score = position_score
        self._last_title_score = title_score
          
        # Weighted sum
        confidence = (
            domain_score * self.weights["domain_match"] +
            tld_score * self.weights["tld_relevance"] +
            position_score * self.weights["search_position"] +
            title_score * self.weights["title_match"]
        )
          
        # Convert to 0-100 scale
        return round(confidence * 100, 2)

    def _calculate_domain_match(self, company: Company, result: SearchResult) -> float:
        """Calculate domain-company name match score (0-1.0)."""
        if not result.url:
            return 0.0
            
        try:
            # Extract domain from URL
            domain = urlparse(result.url).netloc.lower()
            
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
                 
            # Extract main domain (remove subdomains)
            domain_parts = domain.split('.')
            if len(domain_parts) > 2:
                # For domains like 'sub.example.co.uk', keep 'example.co.uk'
                # But for 'acmesoftware.co.uk', keep 'acmesoftware.co.uk'
                if domain_parts[-2] in ['co', 'com', 'org', 'net'] and domain_parts[-1] in ['uk']:
                    # Keep the full domain for UK domains
                    domain = '.'.join(domain_parts[-3:])
                else:
                    domain = '.'.join(domain_parts[-2:])
            
            # Clean company name - use suffix stripping method
            company_name_cleaned = self._clean_company_name_for_matching(company.company_name)
            company_name = re.sub(r'[^\w]', ' ', company_name_cleaned).lower()
            company_words = set(company_name.split())
            
            # Check if company name words appear in domain
            domain_words = re.sub(r'[^\w]', ' ', domain).split()
            domain_words = [word for word in domain_words if len(word) > 2]
            
            # Calculate match score
            matches = sum(1 for word in company_words if word in domain_words)
            
            if not company_words:
                return 0.0
                 
            # Score based on percentage of company words found in domain
            match_ratio = matches / len(company_words)
            
            # Boost for exact matches
            first_word = company_words.pop() if company_words else ''
            if isinstance(first_word, str) and domain.startswith(first_word):
                match_ratio = min(1.0, match_ratio + 0.2)
                 
            # Also check for fuzzy matches (e.g., 'acme' in 'acmesoftware')
            company_name_clean = ''.join(c for c in company_name if c.isalnum())
            domain_clean = ''.join(c for c in domain if c.isalnum())
            
            # Check if company name is in domain or vice versa
            if company_name_clean in domain_clean or domain_clean in company_name_clean:
                # Apply edit distance check for potential false positives
                length_diff = abs(len(company_name_clean) - len(domain_clean))
                if length_diff > 0:
                    matches = sum(1 for ca, cb in zip(company_name_clean, domain_clean) if ca == cb)
                    edit_dist = length_diff + (len(company_name_clean) - matches) * 0.5
                    edit_distance_ratio = edit_dist / max(len(company_name_clean), len(domain_clean))
                    
                    # High edit distance with high match ratio suggests false positive
                    # Example: "SENTINALL" vs "SENTINEL" (edit distance ratio: 0.222)
                    if edit_distance_ratio > 0.2:
                        match_ratio = max(match_ratio, 0.6)  # Reduced for likely false positive
                    else:
                        match_ratio = max(match_ratio, 0.9)  # Legitimate match
                else:
                    match_ratio = max(match_ratio, 0.9)  # Exact match
            # Check if main company word is in domain
            elif company_words and any(word in domain_clean for word in company_words):
                match_ratio = max(match_ratio, 0.7)
            # Check if domain contains acronym or abbreviation
            elif len(domain_clean) >= 3 and domain_clean in company_name_clean:
                match_ratio = max(match_ratio, 0.8)
            # Check if domain starts with company name or vice versa
            elif domain_clean.startswith(company_name_clean[:4]) or company_name_clean.startswith(domain_clean[:4]):
                match_ratio = max(match_ratio, 0.5)
            
            # ENHANCED MATCHING LOGIC
            # 1. Prefix matching - "mgs" should match "mgstech"
            company_prefix = company_name_clean[:min(4, len(company_name_clean))]
            if domain_clean.startswith(company_prefix):
                # Apply edit distance check to prevent false positives like SENTINALL vs SENTINEL
                length_diff = abs(len(company_name_clean) - len(domain_clean))
                if length_diff > 0:
                    matches = sum(1 for ca, cb in zip(company_name_clean, domain_clean) if ca == cb)
                    edit_dist = length_diff + (len(company_name_clean) - matches) * 0.5
                    edit_distance_ratio = edit_dist / max(len(company_name_clean), len(domain_clean))
                    
                    # High edit distance suggests false positive
                    if edit_distance_ratio > 0.2:  # Even more aggressive
                        match_ratio = max(match_ratio, 0.3)  # More significantly reduced
                    else:
                        match_ratio = max(match_ratio, 0.8)  # Normal confidence
                else:
                    match_ratio = max(match_ratio, 0.8)
            
            # 2. Hyphen normalization - "mgs-tech" == "mgstech"
            domain_no_hyphen = domain_clean.replace('-', '')
            company_no_hyphen = company_name_clean.replace('-', '')
            if (company_no_hyphen in domain_no_hyphen or 
                domain_no_hyphen in company_no_hyphen):
                match_ratio = max(match_ratio, 0.95)
            
            # 3. Acronym matching - "MGS" should match "mgstech"
            if len(company_name_clean) <= 4 and company_name_clean.lower() in domain_clean:
                match_ratio = max(match_ratio, 0.9)
            
            # 4. Initialism matching - first letters (more conservative)
            company_initials = ''.join(word[0] for word in company_words if len(word) > 0)
            if (len(company_initials) >= 2 and 
                company_initials.lower() in domain_clean and
                len(company_words) >= 2):  # Only for multi-word company names
                # Reduce score for initials-only matches and add edit distance check
                initials_score = 0.5  # Reduced from 0.75
                
                # Penalize if domain is very different from company name
                # Use simple edit distance approximation
                if len(company_name_clean) > 0 and len(domain_clean) > 0:
                    # Count character overlaps
                    overlap = len(set(company_name_clean) & set(domain_clean))
                    similarity = overlap / max(len(company_name_clean), len(domain_clean))
                    
                    # If similarity is low, reduce initials score further
                    if similarity < 0.4:  # Less than 40% character overlap
                        initials_score = max(0.2, initials_score * similarity * 1.5)
                
                match_ratio = max(match_ratio, initials_score)
            
            # 5. Edit distance check to prevent false positives like "drumaline" vs "drumlevel"
            # Only apply this check if we have a moderate match ratio
            if match_ratio >= 0.5 and match_ratio <= 0.75:  # Narrower moderate confidence range
                 # Calculate simple edit distance
                def simple_edit_distance(a, b):
                    """Simple edit distance approximation."""
                    # Ensure strings
                    a_str = str(a) if a is not None else ""
                    b_str = str(b) if b is not None else ""
                    
                    if not a_str or not b_str:
                        return max(len(a_str), len(b_str))
                    
                    # Use length difference as proxy for edit distance
                    length_diff = abs(len(a_str) - len(b_str))
                    
                    # Count matching characters in same positions
                    matches = sum(1 for ca, cb in zip(a_str, b_str) if ca == cb)
                    max_len = max(len(a_str), len(b_str))
                    match_percentage = matches / max_len if max_len > 0 else 0.0
                    
                    # Approximate edit distance
                    approx_distance = length_diff + (len(a_str) - matches) * 0.5
                    
                    return approx_distance, match_percentage
                
                 # Ensure we have string values for edit distance
                company_clean_str = str(company_name_clean) if company_name_clean is not None else ""
                domain_clean_str = str(domain_clean) if domain_clean is not None else ""
                edit_dist, match_pct = simple_edit_distance(company_clean_str, domain_clean_str)
                
                 # If edit distance is high relative to length, penalize
                max_length = max(len(company_clean_str), len(domain_clean_str))
                if max_length > 0:
                    edit_distance_ratio = edit_dist / max_length
                    
                    # Significant differences should reduce confidence
                    if edit_distance_ratio > 0.5:  # More than 50% different
                        penalty = min(0.6, edit_distance_ratio * 1.5)
                        match_ratio = max(0.15, match_ratio * (1.0 - penalty))
                        
                    # Very similar names should get slight boost
                    elif edit_distance_ratio < 0.1 and match_pct > 0.8:
                        match_ratio = min(0.95, match_ratio * 1.1)
            
        except (ValueError, AttributeError):
            return 0.0
        
        return match_ratio

    def _calculate_tld_relevance(self, result: SearchResult, company: Optional[Company] = None) -> float:
        """Calculate TLD relevance score (0-1.0)."""
        if not result.url:
            return 0.0
            
        try:
            # Extract TLD
            domain = urlparse(result.url).netloc.lower()
            
            # Check if this is a UK company (has UK postcode format)
            is_uk_company = False
            if company and hasattr(company, 'postcode') and company.postcode:
                # UK postcode pattern: A9 9AA, A99 9AA, AA9 9AA, AA99 9AA, A9A 9AA, AA9A 9AA
                is_uk_company = bool(re.match(
                    r'^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$', 
                    company.postcode.upper().strip()
                ))
            
            # UK TLDs get highest score
            uk_tlds = ['.co.uk', '.uk', '.org.uk', '.me.uk', '.net.uk']
            for tld in uk_tlds:
                if domain.endswith(tld):
                    return 1.0 if is_uk_company else 0.8  # Boost for UK companies
            
            # For UK companies, penalize non-UK domains
            if is_uk_company:
                # Indian domains - VERY heavily penalize for UK companies
                if domain.endswith('.in'):
                    return 0.05  # Almost zero - should never rank above UK domains
                # Other country-specific domains
                country_tlds = ['.us', '.ca', '.au', '.de', '.fr', '.jp', '.cn', '.ae', '.sg']
                for tld in country_tlds:
                    if domain.endswith(tld):
                        return 0.1  # Still very low - should not compete with UK domains
            
            # Other common TLDs
            common_tlds = ['.com', '.org', '.net', '.io', '.biz']
            for tld in common_tlds:
                if domain.endswith(tld):
                    return 0.5 if is_uk_company else 0.7
             
            # Unknown TLDs
            return 0.2
             
        except (ValueError, AttributeError):
            return 0.2

    def _calculate_position_score(self, result: SearchResult) -> float:
        """Calculate position-based score (0-1.0)."""
        if result.position <= 0:
            return 0.0
            
        # Less aggressive decay - position 5 should get 0.6, not 0.2
        # This prevents good matches from being penalized too heavily just for position
        if result.position == 1:
            return 1.0
        elif result.position == 2:
            return 0.8
        elif result.position <= 5:
            return 0.6  # Much less penalty for positions 3-5
        elif result.position <= 10:
            return 0.4  # Moderate penalty for positions 6-10
        else:
            return max(0.0, 0.7 - (result.position * 0.05))

    def _calculate_title_match(self, company: Company, result: SearchResult) -> float:
        """Calculate title match score (0-1.0)."""
        if not result.title:
            return 0.0
            
        try:
            # Clean both strings
            company_name = re.sub(r'[^\w]', ' ', company.company_name).lower()
            title = re.sub(r'[^\w]', ' ', result.title).lower()
            
            # Remove common stop words
            stop_words = {'the', 'and', 'of', 'for', 'a', 'an', 'in', 'on', 'at', 'to'}
            company_words = {word for word in company_name.split() if word not in stop_words and len(word) > 2}
            title_words = {word for word in title.split() if word not in stop_words and len(word) > 2}
            
            if not company_words:
                return 0.0
                
            # Calculate Jaccard similarity
            intersection = company_words.intersection(title_words)
            union = company_words.union(title_words)
            
            if not union:
                return 0.0
                
            similarity = len(intersection) / len(union)
            
            # Boost for exact company name match in title
            if company_name in title:
                similarity = min(1.0, similarity + 0.3)
                
            return similarity
            
        except (ValueError, AttributeError):
            return 0.0

    def get_scoring_details(self) -> Dict[str, float]:
        """Get detailed scoring components from the last calculation.
        
        Returns:
            Dictionary with individual scoring components
        """
        return {
            'domain_match': getattr(self, '_last_domain_score', 0.0),
            'tld_relevance': getattr(self, '_last_tld_score', 0.0),
            'search_position': getattr(self, '_last_position_score', 0.0),
            'title_match': getattr(self, '_last_title_score', 0.0)
        }

    def filter_by_confidence(self, results: List[SearchResult], company: Company, threshold: float = 50.0) -> List[SearchResult]:
        """Filter results by confidence threshold.
        
        Args:
            results: List of SearchResult objects
            company: Company object for scoring
            threshold: Minimum confidence score (0-100)
            
        Returns:
            List of SearchResult objects that meet the threshold
        """
        if not results:
            return []
            
        filtered = []
        for result in results:
            score = self.calculate_score(company, result)
            if score >= threshold:
                filtered.append(result)
        return filtered
        
    def _approximate_confidence(self, result: SearchResult) -> float:
        """Approximate confidence score for filtering (simplified version)."""
        if not result.title or not result.url:
            return 0.0
            
        # Score components
        title_quality = min(1.0, len(result.title.split()) / 5.0)  # 0-1.0 based on title length
        position_quality = max(0.0, 1.0 - (result.position - 1) * 0.2)  # 0-1.0 based on position
        
        # Domain quality
        domain = urlparse(result.url).netloc.lower()
        domain_quality = 0.5  # Base score
        if 'companycheck' in domain or 'globaldatabase' in domain:
            domain_quality = 0.1  # Aggregator sites
        elif any(ext in domain for ext in ['.co.uk', '.com', '.org']):
            domain_quality = 0.8  # Professional domains
            
        # Weighted average
        confidence = (title_quality * 0.4 + position_quality * 0.4 + domain_quality * 0.2) * 100
        return confidence