"""
Legal Website Research Agent for Family Law Practice

This module researches and identifies valuable legal websites for scraping,
with focus on:
1. Virginia Circuit Court family law practice
2. Universal family law principles and procedures
3. Legal education and practical guidance
4. Forms, templates, and procedural resources
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re

import httpx
from bs4 import BeautifulSoup
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LegalWebsiteCandidate:
    """Potential legal website for scraping."""
    url: str
    domain: str
    title: str
    description: str
    relevance_score: float
    content_types: List[str] = field(default_factory=list)
    virginia_specific: bool = False
    family_law_focus: bool = False
    practice_oriented: bool = False
    has_forms: bool = False
    has_procedures: bool = False
    has_case_law: bool = False
    authority_level: str = "unknown"  # official, academic, practitioner, commercial
    last_updated: Optional[datetime] = None
    scraping_complexity: str = "unknown"  # simple, moderate, complex, restricted


@dataclass
class WebsiteAnalysis:
    """Analysis of a website's content and scraping potential."""
    candidate: LegalWebsiteCandidate
    content_areas: Dict[str, float] = field(default_factory=dict)
    technical_analysis: Dict[str, any] = field(default_factory=dict)
    recommended_approach: str = "unknown"
    estimated_value: float = 0.0
    scraping_notes: List[str] = field(default_factory=list)


class LegalWebsiteResearcher:
    """Research agent for discovering valuable legal websites."""
    
    def __init__(self):
        """Initialize the research agent."""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        
        # Virginia-specific legal resources
        self.virginia_seeds = [
            # Official Virginia Courts
            "https://www.vacourts.gov/",
            "https://www.courts.state.va.us/",
            
            # Virginia State Bar
            "https://www.vsb.org/",
            
            # Virginia Legal Aid
            "https://www.valegalaid.org/",
            "https://www.virginialegalaid.org/",
            
            # Virginia Circuit Courts
            "https://www.fairfaxcounty.gov/circuit/",
            "https://www.chesterfield.gov/government/departments-services/courts/circuit-court",
            "https://www.henrico.us/services/circuit-court/",
            
            # Virginia Family Law Resources  
            "https://www.vafamilylaw.org/",
            "https://law.lis.virginia.gov/",
            
            # Virginia Legal Forms
            "https://www.courts.state.va.us/forms/home.html",
        ]
        
        # National legal education resources
        self.national_seeds = [
            # Legal Education & Training
            "https://www.nita.org/",  # National Institute for Trial Advocacy
            "https://www.americanbar.org/",  # ABA
            "https://www.lawpracticetoday.org/",
            "https://www.law360.com/",
            
            # Family Law Specific
            "https://www.americanbar.org/groups/family_law/",
            "https://www.aaml.org/",  # American Academy of Matrimonial Lawyers
            "https://www.afccnet.org/",  # Association of Family and Conciliation Courts
            
            # Legal Practice Resources
            "https://www.lawpracticetoday.org/",
            "https://www.attorney-cle.com/",
            "https://www.lexisnexis.com/",
            "https://www.westlaw.com/",
            
            # Practical Legal Resources
            "https://www.justia.com/",
            "https://www.findlaw.com/",
            "https://www.martindale.com/",
            "https://www.avvo.com/",
            
            # Academic & Research
            "https://www.law.cornell.edu/",
            "https://www.law.georgetown.edu/",
            "https://www.law.virginia.edu/",
        ]
        
        # Family law content keywords
        self.family_law_keywords = [
            "divorce", "custody", "child support", "spousal support", "alimony",
            "separation", "property division", "marital property", "domestic relations",
            "family court", "guardian ad litem", "mediation", "collaborative law",
            "adoption", "paternity", "visitation", "parenting plan", "contempt",
            "modification", "enforcement", "protective order", "domestic violence",
            "prenuptial", "postnuptial", "equitable distribution", "temporary orders"
        ]
        
        # Virginia-specific keywords
        self.virginia_keywords = [
            "virginia", "va", "circuit court", "general district court", "jdr court",
            "virginia code", "va code", "virginia supreme court", "virginia bar",
            "fairfax", "richmond", "norfolk", "virginia beach", "chesapeake",
            "alexandria", "arlington", "loudoun", "prince william", "henrico"
        ]
        
        # Practice-oriented keywords
        self.practice_keywords = [
            "practice", "procedure", "pleading", "motion", "discovery", "trial",
            "evidence", "strategy", "tactics", "forms", "template", "checklist",
            "how to", "guide", "tutorial", "training", "cle", "continuing education",
            "practical", "hands-on", "step-by-step", "workflow", "process"
        ]
    
    async def research_legal_websites(self, max_sites: int = 100) -> List[LegalWebsiteCandidate]:
        """Discover and research valuable legal websites.
        
        Args:
            max_sites: Maximum number of sites to research
            
        Returns:
            List of researched website candidates
        """
        logger.info(f"Starting legal website research for family law practice")
        
        candidates = []
        discovered_urls = set()
        
        # Start with seed URLs
        all_seeds = self.virginia_seeds + self.national_seeds
        
        for seed_url in all_seeds:
            if len(candidates) >= max_sites:
                break
                
            try:
                # Research seed website
                candidate = await self._research_website(seed_url)
                if candidate and candidate.url not in discovered_urls:
                    candidates.append(candidate)
                    discovered_urls.add(candidate.url)
                    logger.info(f"Added seed candidate: {candidate.domain} (score: {candidate.relevance_score:.2f})")
                
                # Discover related websites from seed
                related_urls = await self._discover_related_sites(seed_url)
                
                for related_url in related_urls:
                    if len(candidates) >= max_sites:
                        break
                        
                    if related_url not in discovered_urls:
                        related_candidate = await self._research_website(related_url)
                        if related_candidate and related_candidate.relevance_score > 0.3:
                            candidates.append(related_candidate)
                            discovered_urls.add(related_url)
                            logger.info(f"Added related candidate: {related_candidate.domain} (score: {related_candidate.relevance_score:.2f})")
                
            except Exception as e:
                logger.error(f"Error researching {seed_url}: {e}")
                continue
        
        # Sort by relevance score
        candidates.sort(key=lambda x: x.relevance_score, reverse=True)
        
        logger.info(f"Research complete: {len(candidates)} legal websites discovered")
        return candidates
    
    async def _research_website(self, url: str) -> Optional[LegalWebsiteCandidate]:
        """Research a single website for legal content value.
        
        Args:
            url: Website URL to research
            
        Returns:
            Website candidate if valuable, None otherwise
        """
        try:
            # Fetch homepage
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            domain = urlparse(url).netloc
            
            # Extract basic info
            title = self._extract_title(soup)
            description = self._extract_description(soup)
            
            # Analyze content
            content_analysis = await self._analyze_content(soup, url)
            
            # Calculate relevance score
            relevance_score = self._calculate_relevance_score(
                title, description, content_analysis, domain
            )
            
            # Only consider sites with minimum relevance
            if relevance_score < 0.2:
                return None
            
            # Create candidate
            candidate = LegalWebsiteCandidate(
                url=url,
                domain=domain,
                title=title,
                description=description,
                relevance_score=relevance_score,
                content_types=content_analysis['content_types'],
                virginia_specific=content_analysis['virginia_specific'],
                family_law_focus=content_analysis['family_law_focus'],
                practice_oriented=content_analysis['practice_oriented'],
                has_forms=content_analysis['has_forms'],
                has_procedures=content_analysis['has_procedures'],
                has_case_law=content_analysis['has_case_law'],
                authority_level=content_analysis['authority_level'],
                scraping_complexity=content_analysis['scraping_complexity']
            )
            
            return candidate
            
        except Exception as e:
            logger.debug(f"Error researching {url}: {e}")
            return None
    
    async def _analyze_content(self, soup: BeautifulSoup, url: str) -> Dict[str, any]:
        """Analyze website content for legal value.
        
        Args:
            soup: BeautifulSoup object of webpage
            url: Website URL
            
        Returns:
            Dictionary of content analysis results
        """
        text_content = soup.get_text().lower()
        domain = urlparse(url).netloc.lower()
        
        analysis = {
            'content_types': [],
            'virginia_specific': False,
            'family_law_focus': False,
            'practice_oriented': False,
            'has_forms': False,
            'has_procedures': False,
            'has_case_law': False,
            'authority_level': 'unknown',
            'scraping_complexity': 'moderate'
        }
        
        # Check for Virginia-specific content
        virginia_count = sum(1 for keyword in self.virginia_keywords if keyword in text_content)
        analysis['virginia_specific'] = virginia_count > 2
        
        # Check for family law focus
        family_law_count = sum(1 for keyword in self.family_law_keywords if keyword in text_content)
        analysis['family_law_focus'] = family_law_count > 3
        
        # Check for practice-oriented content
        practice_count = sum(1 for keyword in self.practice_keywords if keyword in text_content)
        analysis['practice_oriented'] = practice_count > 2
        
        # Check for specific content types
        if any(term in text_content for term in ['form', 'template', 'document', 'pdf']):
            analysis['has_forms'] = True
            analysis['content_types'].append('forms')
        
        if any(term in text_content for term in ['procedure', 'process', 'step', 'guide', 'how to']):
            analysis['has_procedures'] = True
            analysis['content_types'].append('procedures')
        
        if any(term in text_content for term in ['case law', 'decision', 'opinion', 'ruling', 'precedent']):
            analysis['has_case_law'] = True
            analysis['content_types'].append('case_law')
        
        # Determine authority level
        if any(gov_domain in domain for gov_domain in ['.gov', 'courts', 'virginia']):
            analysis['authority_level'] = 'official'
        elif any(edu_domain in domain for edu_domain in ['.edu', 'law.', 'university']):
            analysis['authority_level'] = 'academic'
        elif any(bar_domain in domain for bar_domain in ['bar', 'aaml', 'afcc']):
            analysis['authority_level'] = 'professional'
        else:
            analysis['authority_level'] = 'commercial'
        
        # Assess scraping complexity
        if soup.find_all('script', src=re.compile(r'.*react.*|.*angular.*|.*vue.*')):
            analysis['scraping_complexity'] = 'complex'
        elif soup.find_all(['form', 'input']) and 'login' in text_content:
            analysis['scraping_complexity'] = 'restricted'
        elif len(soup.find_all('a')) > 100:
            analysis['scraping_complexity'] = 'moderate'
        else:
            analysis['scraping_complexity'] = 'simple'
        
        return analysis
    
    def _calculate_relevance_score(self, title: str, description: str, content_analysis: Dict, domain: str) -> float:
        """Calculate relevance score for a website.
        
        Args:
            title: Website title
            description: Website description
            content_analysis: Content analysis results
            domain: Website domain
            
        Returns:
            Relevance score between 0 and 1
        """
        score = 0.0
        text = f"{title} {description}".lower()
        
        # Base legal relevance
        if any(legal_term in text for legal_term in ['law', 'legal', 'court', 'attorney', 'lawyer']):
            score += 0.2
        
        # Family law bonus
        if content_analysis['family_law_focus']:
            score += 0.3
        
        # Virginia-specific bonus
        if content_analysis['virginia_specific']:
            score += 0.2
        
        # Practice-oriented bonus
        if content_analysis['practice_oriented']:
            score += 0.15
        
        # Content type bonuses
        if content_analysis['has_forms']:
            score += 0.1
        if content_analysis['has_procedures']:
            score += 0.1
        if content_analysis['has_case_law']:
            score += 0.05
        
        # Authority level bonuses
        authority_bonuses = {
            'official': 0.2,
            'academic': 0.15,
            'professional': 0.1,
            'commercial': 0.05
        }
        score += authority_bonuses.get(content_analysis['authority_level'], 0)
        
        # Domain-specific bonuses
        if '.gov' in domain:
            score += 0.1
        if 'virginia' in domain or 'va' in domain:
            score += 0.1
        if any(edu in domain for edu in ['.edu', 'law']):
            score += 0.05
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract website title."""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text().strip()
        
        return "Unknown Title"
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract website description."""
        # Try meta description first
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'].strip()
        
        # Try first paragraph
        first_p = soup.find('p')
        if first_p:
            text = first_p.get_text().strip()
            if len(text) > 50:
                return text[:200] + "..." if len(text) > 200 else text
        
        return "No description available"
    
    async def _discover_related_sites(self, seed_url: str) -> List[str]:
        """Discover related legal websites from seed URL.
        
        Args:
            seed_url: Starting URL to discover from
            
        Returns:
            List of related URLs
        """
        try:
            response = await self.client.get(seed_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            related_urls = set()
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    href = urljoin(seed_url, href)
                
                # Skip if not HTTP/HTTPS
                if not href.startswith(('http://', 'https://')):
                    continue
                
                # Skip if same domain as seed
                if urlparse(href).netloc == urlparse(seed_url).netloc:
                    continue
                
                # Check if link text suggests legal relevance
                link_text = link.get_text().lower()
                if any(term in link_text for term in ['law', 'legal', 'court', 'attorney', 'bar', 'family']):
                    related_urls.add(href)
                
                # Limit discoveries per seed
                if len(related_urls) >= 10:
                    break
            
            return list(related_urls)
            
        except Exception as e:
            logger.debug(f"Error discovering related sites from {seed_url}: {e}")
            return []
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Factory function
def get_legal_website_researcher() -> LegalWebsiteResearcher:
    """Get configured legal website researcher."""
    return LegalWebsiteResearcher()