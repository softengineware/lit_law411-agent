"""
Web scraping client for legal websites and RSS feeds.

This module provides a comprehensive web scraping infrastructure using Scrapy
with robots.txt compliance, user-agent rotation, and content extraction
specifically tailored for legal websites.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
import scrapy
from scrapy import signals
from scrapy.crawler import CrawlerProcess, CrawlerRunner
from scrapy.http import Response
from scrapy.selector import Selector
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy.exceptions import IgnoreRequest, CloseSpider
from scrapy.downloadermiddlewares.robotstxt import RobotsTxtMiddleware
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
import feedparser

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class ScrapedContent(BaseModel):
    """Model for scraped web content."""
    url: str
    title: Optional[str] = None
    content: str
    summary: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    content_type: str = "web_page"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    extracted_at: datetime = Field(default_factory=datetime.now)
    legal_relevance_score: float = 0.0
    source_domain: str


class LegalContentExtractor:
    """Extract and analyze legal content from web pages."""
    
    LEGAL_KEYWORDS = {
        'virginia_law': [
            'virginia code', 'va code', 'circuit court', 'virginia supreme court',
            'family law', 'divorce', 'custody', 'child support', 'alimony',
            'spousal support', 'property division', 'protective order'
        ],
        'legal_procedures': [
            'motion', 'petition', 'complaint', 'pleading', 'discovery',
            'subpoena', 'deposition', 'trial', 'hearing', 'verdict',
            'judgment', 'appeal', 'writ', 'summons'
        ],
        'court_documents': [
            'form', 'template', 'filing', 'docket', 'case law',
            'statute', 'regulation', 'rule', 'order', 'decree'
        ]
    }
    
    def __init__(self):
        self.legal_terms = set()
        for category in self.LEGAL_KEYWORDS.values():
            self.legal_terms.update(term.lower() for term in category)
    
    def extract_content(self, response: Response) -> ScrapedContent:
        """Extract structured content from web page."""
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Extract title
        title = self._extract_title(soup)
        
        # Extract main content
        content = self._extract_main_content(soup)
        
        # Extract metadata
        metadata = self._extract_metadata(soup, response)
        
        # Calculate legal relevance score
        legal_score = self._calculate_legal_relevance(content)
        
        return ScrapedContent(
            url=response.url,
            title=title,
            content=content,
            metadata=metadata,
            legal_relevance_score=legal_score,
            source_domain=urlparse(response.url).netloc
        )
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract page title."""
        # Try various title selectors
        title_selectors = [
            'h1', 'title', '.page-title', '.article-title', 
            '.entry-title', '.post-title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                return element.get_text().strip()
        
        return None
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main text content."""
        # Try to find main content areas
        content_selectors = [
            'main', 'article', '.content', '.post-content',
            '.entry-content', '.article-content', 'body'
        ]
        
        content_text = ""
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                content_text = element.get_text(separator=' ', strip=True)
                if len(content_text) > 100:  # Minimum content length
                    break
        
        if not content_text:
            # Fallback to body text
            content_text = soup.get_text(separator=' ', strip=True)
        
        return content_text
    
    def _extract_metadata(self, soup: BeautifulSoup, response: Response) -> Dict[str, Any]:
        """Extract page metadata."""
        metadata = {}
        
        # Meta tags
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name') or tag.get('property')
            content = tag.get('content')
            if name and content:
                metadata[name] = content
        
        # Links and references
        links = [a.get('href') for a in soup.find_all('a', href=True)]
        metadata['internal_links'] = [
            link for link in links 
            if link and urlparse(link).netloc == urlparse(response.url).netloc
        ]
        
        # Word count
        content_text = soup.get_text()
        metadata['word_count'] = len(content_text.split())
        
        return metadata
    
    def _calculate_legal_relevance(self, content: str) -> float:
        """Calculate legal relevance score (0.0 to 1.0)."""
        if not content:
            return 0.0
        
        content_lower = content.lower()
        
        # Count legal term matches
        matches = 0
        total_terms = len(self.legal_terms)
        
        for term in self.legal_terms:
            if term in content_lower:
                matches += 1
        
        # Base score from term frequency
        base_score = min(matches / total_terms * 2, 0.8)  # Max 0.8 from terms
        
        # Bonus for Virginia-specific content
        virginia_terms = ['virginia', 'va court', 'circuit court', 'virginia code']
        virginia_matches = sum(1 for term in virginia_terms if term in content_lower)
        virginia_bonus = min(virginia_matches * 0.05, 0.2)  # Max 0.2 bonus
        
        return min(base_score + virginia_bonus, 1.0)


class RobotsTxtChecker:
    """Check robots.txt compliance before scraping."""
    
    def __init__(self):
        self.robots_cache: Dict[str, RobotFileParser] = {}
        self.cache_expiry: Dict[str, datetime] = {}
    
    async def can_fetch(self, url: str, user_agent: str = '*') -> bool:
        """Check if URL can be fetched according to robots.txt."""
        try:
            domain = urlparse(url).netloc
            
            # Check cache
            if domain in self.robots_cache:
                if datetime.now() < self.cache_expiry[domain]:
                    rp = self.robots_cache[domain]
                    return rp.can_fetch(user_agent, url)
            
            # Fetch robots.txt
            robots_url = f"https://{domain}/robots.txt"
            
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(robots_url, timeout=10) as response:
                        if response.status == 200:
                            robots_content = await response.text()
                            
                            rp = RobotFileParser()
                            rp.set_url(robots_url)
                            rp.read_text(robots_content)
                            
                            # Cache for 24 hours
                            self.robots_cache[domain] = rp
                            self.cache_expiry[domain] = datetime.now() + timedelta(hours=24)
                            
                            return rp.can_fetch(user_agent, url)
                        else:
                            # If robots.txt not found, assume allowed
                            return True
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout fetching robots.txt for {domain}")
                    return True
                
        except Exception as e:
            logger.error(f"Error checking robots.txt for {url}: {e}")
            return True  # Allow by default if check fails


class PoliteSpider(scrapy.Spider):
    """Base spider with polite crawling behavior."""
    
    name = 'polite_spider'
    
    # Polite crawling settings
    custom_settings = {
        'DOWNLOAD_DELAY': 2,  # 2 seconds between requests
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'DOWNLOAD_TIMEOUT': 30,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],
        'CONCURRENT_REQUESTS': 1,  # One request at a time
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'ROBOTSTXT_OBEY': True,
        'USER_AGENT': 'LegalResearchBot/1.0 (+https://law411.com)',
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware': 100,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        }
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_extractor = LegalContentExtractor()
        self.robots_checker = RobotsTxtChecker()
        self.scraped_count = 0
        self.max_pages = kwargs.get('max_pages', 100)
    
    def parse(self, response):
        """Default parse method."""
        try:
            content = self.content_extractor.extract_content(response)
            
            # Only yield if content has some legal relevance
            if content.legal_relevance_score > 0.1:
                self.scraped_count += 1
                logger.info(f"Scraped legal content from {response.url} "
                           f"(score: {content.legal_relevance_score:.2f})")
                yield content.dict()
            
            # Stop if we've reached max pages
            if self.scraped_count >= self.max_pages:
                raise CloseSpider(f"Reached maximum pages limit: {self.max_pages}")
                
        except Exception as e:
            logger.error(f"Error parsing {response.url}: {e}")


class LegalSiteSpider(PoliteSpider):
    """Spider for legal websites with intelligent content discovery."""
    
    name = 'legal_site_spider'
    
    def __init__(self, start_urls=None, allowed_domains=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = start_urls or []
        self.allowed_domains = allowed_domains or []
        
        # Legal content patterns for link extraction
        self.legal_patterns = [
            r'/forms?/',
            r'/procedure',
            r'/rules?/',
            r'/statute',
            r'/code/',
            r'/law/',
            r'/legal/',
            r'/court/',
            r'/family/',
            r'/divorce/',
            r'/custody/',
        ]
    
    def parse(self, response):
        """Parse page and follow legal-related links."""
        # Extract content from current page
        yield from super().parse(response)
        
        # Follow legal-related links
        for pattern in self.legal_patterns:
            links = response.css(f'a[href*="{pattern}"]::attr(href)').getall()
            for link in links:
                full_url = urljoin(response.url, link)
                if self._is_allowed_domain(full_url):
                    yield response.follow(link, self.parse)
    
    def _is_allowed_domain(self, url: str) -> bool:
        """Check if URL is in allowed domains."""
        if not self.allowed_domains:
            return True
        
        domain = urlparse(url).netloc
        return any(allowed in domain for allowed in self.allowed_domains)


class RSSFeedProcessor:
    """Process RSS/Atom feeds for legal content."""
    
    def __init__(self):
        self.content_extractor = LegalContentExtractor()
    
    async def process_feed(self, feed_url: str) -> List[ScrapedContent]:
        """Process RSS feed and extract legal content."""
        try:
            # Parse feed
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:
                logger.warning(f"Feed parsing issues for {feed_url}: {feed.bozo_exception}")
            
            results = []
            
            for entry in feed.entries:
                try:
                    content = await self._process_feed_entry(entry, feed_url)
                    if content and content.legal_relevance_score > 0.1:
                        results.append(content)
                except Exception as e:
                    logger.error(f"Error processing feed entry: {e}")
            
            logger.info(f"Processed {len(results)} legal articles from {feed_url}")
            return results
            
        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}")
            return []
    
    async def _process_feed_entry(self, entry, feed_url: str) -> Optional[ScrapedContent]:
        """Process individual feed entry."""
        # Extract content
        content_text = ""
        if hasattr(entry, 'content'):
            content_text = entry.content[0].value
        elif hasattr(entry, 'summary'):
            content_text = entry.summary
        elif hasattr(entry, 'description'):
            content_text = entry.description
        
        # Clean HTML
        if content_text:
            soup = BeautifulSoup(content_text, 'html.parser')
            content_text = soup.get_text(separator=' ', strip=True)
        
        # Extract date
        published_date = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_date = datetime(*entry.published_parsed[:6])
        
        # Calculate legal relevance
        legal_score = self.content_extractor._calculate_legal_relevance(content_text)
        
        return ScrapedContent(
            url=entry.link,
            title=entry.get('title', ''),
            content=content_text,
            published_date=published_date,
            content_type="rss_article",
            legal_relevance_score=legal_score,
            source_domain=urlparse(feed_url).netloc,
            metadata={
                'feed_url': feed_url,
                'author': entry.get('author', ''),
                'tags': [tag.term for tag in entry.get('tags', [])]
            }
        )


class WebScrapingClient:
    """Main web scraping client with comprehensive functionality."""
    
    def __init__(self):
        self.content_extractor = LegalContentExtractor()
        self.robots_checker = RobotsTxtChecker()
        self.rss_processor = RSSFeedProcessor()
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'LegalResearchBot/1.0 (+https://law411.com)'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def scrape_url(self, url: str) -> Optional[ScrapedContent]:
        """Scrape single URL with robots.txt compliance."""
        try:
            # Check robots.txt
            if not await self.robots_checker.can_fetch(url):
                logger.warning(f"Robots.txt disallows scraping {url}")
                return None
            
            # Add delay for politeness
            await asyncio.sleep(1)
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Create mock Scrapy response for content extraction
                    mock_response = type('MockResponse', (), {
                        'url': url,
                        'text': html,
                        'status': response.status
                    })()
                    
                    content = self.content_extractor.extract_content(mock_response)
                    logger.info(f"Scraped {url} (legal score: {content.legal_relevance_score:.2f})")
                    return content
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    async def scrape_multiple_urls(self, urls: List[str], 
                                 max_concurrent: int = 3) -> List[ScrapedContent]:
        """Scrape multiple URLs with concurrency control."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url):
            async with semaphore:
                return await self.scrape_url(url)
        
        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        valid_results = [
            result for result in results 
            if isinstance(result, ScrapedContent)
        ]
        
        logger.info(f"Successfully scraped {len(valid_results)} out of {len(urls)} URLs")
        return valid_results
    
    def run_spider(self, spider_class, **spider_kwargs) -> List[Dict]:
        """Run Scrapy spider and return results."""
        results = []
        
        def collect_items(item, response, spider):
            results.append(item)
        
        # Configure Scrapy
        process = CrawlerProcess({
            'LOG_LEVEL': 'WARNING',  # Reduce Scrapy logging
            'FEEDS': {},  # Disable file output
        })
        
        crawler = process.create_crawler(spider_class)
        crawler.signals.connect(collect_items, signal=signals.item_scraped)
        
        process.crawl(crawler, **spider_kwargs)
        process.start()
        
        return results
    
    async def process_rss_feed(self, feed_url: str) -> List[ScrapedContent]:
        """Process RSS feed for legal content."""
        return await self.rss_processor.process_feed(feed_url)
    
    async def discover_legal_content(self, domain: str, 
                                   max_pages: int = 50) -> List[ScrapedContent]:
        """Discover legal content on a domain using intelligent crawling."""
        start_urls = [
            f"https://{domain}",
            f"https://{domain}/forms",
            f"https://{domain}/procedures",
            f"https://{domain}/rules",
            f"https://{domain}/self-help",
        ]
        
        # Filter valid URLs
        valid_urls = []
        for url in start_urls:
            try:
                if await self.robots_checker.can_fetch(url):
                    valid_urls.append(url)
            except Exception:
                pass
        
        if not valid_urls:
            logger.warning(f"No accessible URLs found for domain {domain}")
            return []
        
        # Run spider
        try:
            spider_results = self.run_spider(
                LegalSiteSpider,
                start_urls=valid_urls,
                allowed_domains=[domain],
                max_pages=max_pages
            )
            
            # Convert to ScrapedContent objects
            results = []
            for item in spider_results:
                try:
                    content = ScrapedContent(**item)
                    results.append(content)
                except Exception as e:
                    logger.error(f"Error creating ScrapedContent: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error running spider for {domain}: {e}")
            return []


# Export main components
__all__ = [
    'WebScrapingClient',
    'LegalSiteSpider', 
    'PoliteSpider',
    'RSSFeedProcessor',
    'LegalContentExtractor',
    'ScrapedContent'
]