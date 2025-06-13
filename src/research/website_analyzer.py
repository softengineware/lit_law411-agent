"""
Website Analysis Engine for Legal Content Scraping

This module analyzes legal websites to determine:
1. Optimal scraping strategies
2. Content extraction methods
3. Technical requirements and challenges
4. Expected content quality and structure
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
import json
import re

import httpx
from bs4 import BeautifulSoup, Comment
from src.research.legal_website_researcher import LegalWebsiteCandidate, WebsiteAnalysis
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScrapingStrategy:
    """Recommended scraping strategy for a website."""
    method: str  # static, dynamic, api, hybrid
    tools: List[str] = field(default_factory=list)  # scrapy, selenium, requests, etc.
    frequency: str = "weekly"  # daily, weekly, monthly
    complexity: str = "moderate"  # simple, moderate, complex
    requirements: List[str] = field(default_factory=list)
    challenges: List[str] = field(default_factory=list)
    success_probability: float = 0.7
    estimated_pages: int = 0
    expected_content_types: List[str] = field(default_factory=list)


@dataclass
class ContentStructure:
    """Analysis of website content structure."""
    navigation_pattern: str = "unknown"  # hierarchical, flat, dynamic
    content_containers: List[str] = field(default_factory=list)
    pagination_type: str = "none"  # none, numeric, infinite, load_more
    search_functionality: bool = False
    content_categories: Dict[str, int] = field(default_factory=dict)
    update_frequency: str = "unknown"  # daily, weekly, monthly, static
    content_quality_indicators: List[str] = field(default_factory=list)


class WebsiteAnalyzer:
    """Analyzes legal websites for optimal scraping strategies."""
    
    def __init__(self):
        """Initialize the website analyzer."""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        
        # Legal content indicators
        self.quality_indicators = [
            "author", "date", "citation", "jurisdiction", "court", "statute",
            "regulation", "published", "updated", "reviewed", "cle", "bar"
        ]
        
        # Technical complexity indicators
        self.complexity_indicators = {
            'simple': ['static html', 'basic css', 'simple links'],
            'moderate': ['javascript', 'ajax', 'forms', 'pagination'],
            'complex': ['react', 'angular', 'vue', 'spa', 'websockets', 'captcha'],
            'restricted': ['login', 'paywall', 'subscription', 'members only']
        }
    
    async def analyze_website(self, candidate: LegalWebsiteCandidate) -> WebsiteAnalysis:
        """Analyze a website candidate for scraping strategy.
        
        Args:
            candidate: Website candidate to analyze
            
        Returns:
            Complete website analysis with scraping recommendations
        """
        logger.info(f"Analyzing website: {candidate.domain}")
        
        try:
            # Fetch and parse the website
            response = await self.client.get(candidate.url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Perform comprehensive analysis
            technical_analysis = await self._analyze_technical_structure(soup, candidate.url)
            content_structure = await self._analyze_content_structure(soup, candidate.url)
            scraping_strategy = await self._determine_scraping_strategy(
                soup, candidate, technical_analysis, content_structure
            )
            content_areas = await self._analyze_content_areas(soup, candidate)
            
            # Calculate estimated value
            estimated_value = self._calculate_website_value(
                candidate, content_structure, scraping_strategy
            )
            
            # Create comprehensive analysis
            analysis = WebsiteAnalysis(
                candidate=candidate,
                content_areas=content_areas,
                technical_analysis={
                    'structure': technical_analysis,
                    'content': content_structure.__dict__,
                    'strategy': scraping_strategy.__dict__
                },
                recommended_approach=scraping_strategy.method,
                estimated_value=estimated_value,
                scraping_notes=self._generate_scraping_notes(
                    candidate, scraping_strategy, content_structure
                )
            )
            
            logger.info(f"Analysis complete for {candidate.domain}: {scraping_strategy.method} approach, value: {estimated_value:.2f}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing {candidate.url}: {e}")
            
            # Return basic analysis on error
            return WebsiteAnalysis(
                candidate=candidate,
                recommended_approach="unknown",
                estimated_value=0.0,
                scraping_notes=[f"Analysis failed: {str(e)}"]
            )
    
    async def _analyze_technical_structure(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Analyze technical structure of the website.
        
        Args:
            soup: BeautifulSoup object
            url: Website URL
            
        Returns:
            Technical analysis results
        """
        analysis = {
            'javascript_heavy': False,
            'spa_framework': None,
            'requires_interaction': False,
            'has_dynamic_content': False,
            'authentication_required': False,
            'rate_limiting': False,
            'robots_txt_exists': False,
            'sitemap_exists': False,
            'ssl_enabled': url.startswith('https://'),
            'responsive_design': False,
            'content_delivery': 'server',  # server, client, hybrid
            'api_endpoints': [],
            'forms_present': False,
            'cookies_required': False
        }
        
        # Check for JavaScript frameworks
        scripts = soup.find_all('script')
        for script in scripts:
            if script.get('src'):
                src = script['src'].lower()
                if any(framework in src for framework in ['react', 'angular', 'vue']):
                    analysis['spa_framework'] = next(fw for fw in ['react', 'angular', 'vue'] if fw in src)
                    analysis['javascript_heavy'] = True
                    analysis['content_delivery'] = 'client'
            
            # Check script content
            if script.string:
                content = script.string.lower()
                if any(term in content for term in ['ajax', 'fetch', 'xmlhttprequest']):
                    analysis['has_dynamic_content'] = True
        
        # Check for forms and authentication
        forms = soup.find_all('form')
        analysis['forms_present'] = len(forms) > 0
        
        for form in forms:
            if any(term in str(form).lower() for term in ['login', 'signin', 'password']):
                analysis['authentication_required'] = True
                break
        
        # Check for responsive design indicators
        viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
        css_media_queries = soup.find_all('link', attrs={'media': re.compile(r'.*screen.*')})
        analysis['responsive_design'] = bool(viewport_meta or css_media_queries)
        
        # Check for API endpoints in JavaScript
        script_texts = [script.string for script in scripts if script.string]
        for script_text in script_texts:
            if script_text:
                # Look for API endpoints
                api_patterns = re.findall(r'["\']\/api\/[^"\']*["\']', script_text)
                analysis['api_endpoints'].extend(api_patterns)
        
        # Check robots.txt and sitemap
        try:
            domain = urlparse(url).netloc
            robots_response = await self.client.get(f"https://{domain}/robots.txt")
            analysis['robots_txt_exists'] = robots_response.status_code == 200
            
            sitemap_response = await self.client.get(f"https://{domain}/sitemap.xml")
            analysis['sitemap_exists'] = sitemap_response.status_code == 200
        except:
            pass
        
        return analysis
    
    async def _analyze_content_structure(self, soup: BeautifulSoup, url: str) -> ContentStructure:
        """Analyze content structure and organization.
        
        Args:
            soup: BeautifulSoup object
            url: Website URL
            
        Returns:
            Content structure analysis
        """
        structure = ContentStructure()
        
        # Analyze navigation pattern
        nav_elements = soup.find_all(['nav', 'ul', 'ol'], class_=re.compile(r'.*nav.*|.*menu.*'))
        if nav_elements:
            total_links = sum(len(nav.find_all('a')) for nav in nav_elements)
            if total_links > 20:
                structure.navigation_pattern = "hierarchical"
            elif total_links > 5:
                structure.navigation_pattern = "moderate"
            else:
                structure.navigation_pattern = "flat"
        
        # Find content containers
        content_containers = []
        for container in soup.find_all(['div', 'section', 'article'], class_=re.compile(r'.*content.*|.*article.*|.*post.*')):
            if container.get('class'):
                content_containers.extend(container['class'])
        structure.content_containers = list(set(content_containers))
        
        # Check pagination
        pagination_indicators = soup.find_all(text=re.compile(r'next|previous|page \d+|\d+ of \d+'))
        load_more_buttons = soup.find_all(['button', 'a'], text=re.compile(r'load more|show more'))
        
        if pagination_indicators:
            structure.pagination_type = "numeric"
        elif load_more_buttons:
            structure.pagination_type = "load_more"
        elif soup.find_all('script', text=re.compile(r'infinite.*scroll|lazy.*load')):
            structure.pagination_type = "infinite"
        
        # Check search functionality
        search_forms = soup.find_all('form', action=re.compile(r'.*search.*'))
        search_inputs = soup.find_all('input', type='search')
        structure.search_functionality = bool(search_forms or search_inputs)
        
        # Analyze content categories
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        categories = {}
        for heading in headings:
            text = heading.get_text().lower()
            if any(term in text for term in ['family law', 'divorce', 'custody']):
                categories['family_law'] = categories.get('family_law', 0) + 1
            elif any(term in text for term in ['procedure', 'process', 'how to']):
                categories['procedures'] = categories.get('procedures', 0) + 1
            elif any(term in text for term in ['form', 'document', 'template']):
                categories['forms'] = categories.get('forms', 0) + 1
            elif any(term in text for term in ['case', 'decision', 'opinion']):
                categories['case_law'] = categories.get('case_law', 0) + 1
        
        structure.content_categories = categories
        
        # Check for quality indicators
        text_content = soup.get_text().lower()
        quality_indicators = []
        for indicator in self.quality_indicators:
            if indicator in text_content:
                quality_indicators.append(indicator)
        structure.content_quality_indicators = quality_indicators
        
        # Estimate update frequency based on dates
        date_patterns = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}', soup.get_text())
        if len(date_patterns) > 10:
            structure.update_frequency = "frequent"
        elif len(date_patterns) > 3:
            structure.update_frequency = "moderate"
        else:
            structure.update_frequency = "infrequent"
        
        return structure
    
    async def _determine_scraping_strategy(
        self, 
        soup: BeautifulSoup, 
        candidate: LegalWebsiteCandidate,
        technical_analysis: Dict[str, Any],
        content_structure: ContentStructure
    ) -> ScrapingStrategy:
        """Determine optimal scraping strategy.
        
        Args:
            soup: BeautifulSoup object
            candidate: Website candidate
            technical_analysis: Technical analysis results
            content_structure: Content structure analysis
            
        Returns:
            Recommended scraping strategy
        """
        # Determine method based on technical complexity
        if technical_analysis['authentication_required']:
            method = "restricted"
            complexity = "complex"
            success_probability = 0.3
            challenges = ["Authentication required"]
            tools = ["manual"]
            
        elif technical_analysis['spa_framework'] or technical_analysis['javascript_heavy']:
            method = "dynamic"
            tools = ["selenium", "playwright"]
            complexity = "complex"
            success_probability = 0.6
            challenges = ["JavaScript rendering required"]
            
        elif technical_analysis['has_dynamic_content'] or content_structure.pagination_type == "infinite":
            method = "hybrid"
            tools = ["scrapy", "selenium"]
            complexity = "moderate"
            success_probability = 0.7
            challenges = ["Dynamic content loading"]
            
        elif technical_analysis['api_endpoints']:
            method = "api"
            tools = ["httpx", "requests"]
            complexity = "simple"
            success_probability = 0.9
            challenges = []
            
        else:
            method = "static"
            tools = ["scrapy", "beautifulsoup"]
            complexity = "simple"
            success_probability = 0.8
            challenges = []
        
        # Create strategy with required method parameter
        strategy = ScrapingStrategy(
            method=method,
            tools=tools,
            complexity=complexity,
            success_probability=success_probability,
            challenges=challenges
        )
        
        # Determine frequency based on content update patterns
        if content_structure.update_frequency == "frequent":
            strategy.frequency = "daily"
        elif content_structure.update_frequency == "moderate":
            strategy.frequency = "weekly"
        else:
            strategy.frequency = "monthly"
        
        # Estimate pages to scrape
        links = soup.find_all('a', href=True)
        internal_links = [link for link in links if urlparse(link['href']).netloc in ['', candidate.domain]]
        strategy.estimated_pages = min(len(internal_links), 1000)  # Cap at reasonable limit
        
        # Expected content types
        if candidate.has_forms:
            strategy.expected_content_types.append("legal_forms")
        if candidate.has_procedures:
            strategy.expected_content_types.append("procedures")
        if candidate.has_case_law:
            strategy.expected_content_types.append("case_law")
        
        # Add Virginia-specific requirements
        if candidate.virginia_specific:
            strategy.requirements.append("Virginia jurisdiction filtering")
        
        # Add family law requirements
        if candidate.family_law_focus:
            strategy.requirements.append("Family law content classification")
        
        return strategy
    
    async def _analyze_content_areas(self, soup: BeautifulSoup, candidate: LegalWebsiteCandidate) -> Dict[str, float]:
        """Analyze specific content areas and their value.
        
        Args:
            soup: BeautifulSoup object
            candidate: Website candidate
            
        Returns:
            Dictionary of content areas with value scores
        """
        content_areas = {}
        text_content = soup.get_text().lower()
        
        # Family law content areas
        family_law_areas = {
            'divorce_proceedings': ['divorce', 'dissolution', 'marital', 'separation'],
            'child_custody': ['custody', 'visitation', 'parenting plan', 'guardian'],
            'child_support': ['child support', 'support calculation', 'support modification'],
            'spousal_support': ['alimony', 'spousal support', 'maintenance'],
            'property_division': ['property division', 'equitable distribution', 'marital property'],
            'domestic_relations_procedures': ['domestic relations', 'family court procedure', 'jdr court'],
            'protective_orders': ['protective order', 'restraining order', 'domestic violence'],
            'adoption': ['adoption', 'stepparent adoption', 'paternity'],
            'prenuptial_agreements': ['prenuptial', 'postnuptial', 'marital agreement']
        }
        
        for area, keywords in family_law_areas.items():
            score = sum(1 for keyword in keywords if keyword in text_content)
            if score > 0:
                content_areas[area] = min(score / len(keywords), 1.0)
        
        # Virginia-specific content
        if candidate.virginia_specific:
            va_areas = {
                'virginia_statutes': ['virginia code', 'va code', 'title 20'],
                'virginia_procedures': ['virginia rules', 'circuit court rules', 'jdr procedures'],
                'virginia_forms': ['virginia form', 'va form', 'circuit court form'],
                'local_rules': ['local rules', 'fairfax', 'richmond', 'norfolk']
            }
            
            for area, keywords in va_areas.items():
                score = sum(1 for keyword in keywords if keyword in text_content)
                if score > 0:
                    content_areas[area] = min(score / len(keywords), 1.0)
        
        # Practice-oriented content
        if candidate.practice_oriented:
            practice_areas = {
                'trial_practice': ['trial', 'evidence', 'objection', 'cross examination'],
                'pleading_practice': ['pleading', 'motion', 'discovery', 'deposition'],
                'client_counseling': ['client', 'counseling', 'interview', 'advice'],
                'case_management': ['case management', 'workflow', 'calendar', 'deadlines']
            }
            
            for area, keywords in practice_areas.items():
                score = sum(1 for keyword in keywords if keyword in text_content)
                if score > 0:
                    content_areas[area] = min(score / len(keywords), 1.0)
        
        return content_areas
    
    def _calculate_website_value(
        self, 
        candidate: LegalWebsiteCandidate,
        content_structure: ContentStructure,
        scraping_strategy: ScrapingStrategy
    ) -> float:
        """Calculate overall value of website for scraping.
        
        Args:
            candidate: Website candidate
            content_structure: Content structure analysis
            scraping_strategy: Scraping strategy
            
        Returns:
            Value score between 0 and 1
        """
        value = candidate.relevance_score  # Start with base relevance
        
        # Boost for high-quality content indicators
        quality_bonus = len(content_structure.content_quality_indicators) * 0.05
        value += min(quality_bonus, 0.2)
        
        # Boost for good content organization
        if content_structure.navigation_pattern in ['hierarchical', 'moderate']:
            value += 0.1
        
        if content_structure.search_functionality:
            value += 0.05
        
        # Adjust for scraping difficulty
        difficulty_penalties = {
            'simple': 0.0,
            'moderate': -0.05,
            'complex': -0.15,
            'restricted': -0.4
        }
        value += difficulty_penalties.get(scraping_strategy.complexity, 0)
        
        # Boost for high success probability
        if scraping_strategy.success_probability > 0.8:
            value += 0.1
        elif scraping_strategy.success_probability < 0.5:
            value -= 0.1
        
        # Boost for estimated content volume
        if scraping_strategy.estimated_pages > 100:
            value += 0.1
        elif scraping_strategy.estimated_pages > 500:
            value += 0.15
        
        return min(value, 1.0)  # Cap at 1.0
    
    def _generate_scraping_notes(
        self,
        candidate: LegalWebsiteCandidate,
        strategy: ScrapingStrategy,
        content_structure: ContentStructure
    ) -> List[str]:
        """Generate practical scraping notes and recommendations.
        
        Args:
            candidate: Website candidate
            strategy: Scraping strategy
            content_structure: Content structure
            
        Returns:
            List of practical notes
        """
        notes = []
        
        # Strategy-specific notes
        if strategy.method == "static":
            notes.append("Standard web scraping approach suitable")
            notes.append("Use respectful crawling delays (1-2 seconds)")
            
        elif strategy.method == "dynamic":
            notes.append("JavaScript rendering required - use Selenium/Playwright")
            notes.append("Consider headless browser for efficiency")
            notes.append("Watch for dynamic loading indicators")
            
        elif strategy.method == "hybrid":
            notes.append("Combine static scraping with selective dynamic rendering")
            notes.append("Identify which pages require JavaScript")
            
        elif strategy.method == "api":
            notes.append("Investigate API endpoints for direct data access")
            notes.append("Check for API documentation or swagger")
            
        elif strategy.method == "restricted":
            notes.append("Access restrictions detected - may require special handling")
            notes.append("Consider contacting site owner for permission")
        
        # Content-specific notes
        if candidate.virginia_specific:
            notes.append("Focus on Virginia-specific legal content")
            notes.append("Filter for Virginia jurisdictional relevance")
            
        if candidate.family_law_focus:
            notes.append("Rich family law content available")
            notes.append("Prioritize divorce, custody, and support materials")
            
        if candidate.has_forms:
            notes.append("Legal forms available - check for PDF downloads")
            notes.append("Organize forms by practice area and jurisdiction")
            
        # Technical notes
        if content_structure.pagination_type != "none":
            notes.append(f"Pagination detected: {content_structure.pagination_type}")
            notes.append("Implement pagination handling in scraper")
            
        if content_structure.search_functionality:
            notes.append("Search functionality available - could enhance content discovery")
            
        # Quality and frequency notes
        if len(content_structure.content_quality_indicators) > 5:
            notes.append("High-quality content indicators present")
            
        if content_structure.update_frequency == "frequent":
            notes.append("Content updates frequently - consider daily scraping")
        elif content_structure.update_frequency == "moderate":
            notes.append("Moderate update frequency - weekly scraping recommended")
        
        return notes
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Factory function
def get_website_analyzer() -> WebsiteAnalyzer:
    """Get configured website analyzer."""
    return WebsiteAnalyzer()