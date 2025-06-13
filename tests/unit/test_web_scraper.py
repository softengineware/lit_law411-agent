"""
Tests for web scraping functionality.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from bs4 import BeautifulSoup

from src.scrapers.web import (
    WebScrapingClient,
    LegalContentExtractor,
    RobotsTxtChecker,
    RSSFeedProcessor,
    ScrapedContent,
    PoliteSpider,
    LegalSiteSpider
)


class TestLegalContentExtractor:
    """Test legal content extraction."""
    
    def setup_method(self):
        self.extractor = LegalContentExtractor()
    
    def test_calculate_legal_relevance_high_score(self):
        """Test legal relevance scoring for high-relevance content."""
        content = """
        Virginia Circuit Court family law procedures for divorce and custody.
        Child support calculations under Virginia Code section 20-108.
        Motion for spousal support and property division.
        """
        score = self.extractor._calculate_legal_relevance(content)
        assert score > 0.5
    
    def test_calculate_legal_relevance_low_score(self):
        """Test legal relevance scoring for low-relevance content."""
        content = "This is a general blog post about cooking recipes and travel tips."
        score = self.extractor._calculate_legal_relevance(content)
        assert score < 0.2
    
    def test_calculate_legal_relevance_empty_content(self):
        """Test legal relevance scoring for empty content."""
        score = self.extractor._calculate_legal_relevance("")
        assert score == 0.0
    
    def test_extract_title_from_h1(self):
        """Test title extraction from H1 tag."""
        html = "<html><h1>Virginia Family Law Guide</h1></html>"
        soup = BeautifulSoup(html, 'html.parser')
        title = self.extractor._extract_title(soup)
        assert title == "Virginia Family Law Guide"
    
    def test_extract_main_content(self):
        """Test main content extraction."""
        html = """
        <html>
            <head><title>Test</title></head>
            <body>
                <nav>Navigation</nav>
                <main>
                    <p>This is the main content about Virginia law.</p>
                    <p>More legal information here.</p>
                </main>
                <footer>Footer content</footer>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        content = self.extractor._extract_main_content(soup)
        assert "main content about Virginia law" in content
        assert "Navigation" not in content
        assert "Footer content" not in content
    
    def test_extract_content_integration(self):
        """Test full content extraction integration."""
        mock_response = Mock()
        mock_response.url = "https://www.vacourts.gov/forms/family"
        mock_response.text = """
        <html>
            <head>
                <title>Virginia Family Law Forms</title>
                <meta name="description" content="Official family law forms">
            </head>
            <body>
                <h1>Family Law Forms</h1>
                <main>
                    <p>Divorce petition forms for Virginia Circuit Court.</p>
                    <p>Child custody and support calculation worksheets.</p>
                </main>
            </body>
        </html>
        """
        
        content = self.extractor.extract_content(mock_response)
        
        assert content.url == mock_response.url
        assert content.title == "Family Law Forms"
        assert "divorce petition" in content.content.lower()
        assert content.legal_relevance_score > 0.5
        assert content.source_domain == "www.vacourts.gov"


class TestRobotsTxtChecker:
    """Test robots.txt compliance checking."""
    
    def setup_method(self):
        self.checker = RobotsTxtChecker()
    
    @pytest.mark.asyncio
    async def test_can_fetch_with_robots_txt(self):
        """Test robots.txt checking with mock response."""
        robots_content = """
        User-agent: *
        Disallow: /admin/
        Allow: /forms/
        """
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=robots_content)
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # Should allow forms
            can_fetch = await self.checker.can_fetch("https://example.com/forms/divorce")
            assert can_fetch is True
            
            # Should disallow admin
            can_fetch = await self.checker.can_fetch("https://example.com/admin/dashboard")
            assert can_fetch is False
    
    @pytest.mark.asyncio
    async def test_can_fetch_no_robots_txt(self):
        """Test behavior when robots.txt doesn't exist."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_get.return_value.__aenter__.return_value = mock_response
            
            can_fetch = await self.checker.can_fetch("https://example.com/any-page")
            assert can_fetch is True  # Should allow if no robots.txt
    
    @pytest.mark.asyncio
    async def test_can_fetch_timeout(self):
        """Test timeout handling for robots.txt."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = asyncio.TimeoutError()
            
            can_fetch = await self.checker.can_fetch("https://example.com/page")
            assert can_fetch is True  # Should allow on timeout


class TestRSSFeedProcessor:
    """Test RSS feed processing."""
    
    def setup_method(self):
        self.processor = RSSFeedProcessor()
    
    @pytest.mark.asyncio
    async def test_process_feed_entry(self):
        """Test processing individual RSS feed entry."""
        mock_entry = Mock()
        mock_entry.link = "https://legal-blog.com/article-1"
        mock_entry.title = "Virginia Divorce Law Update"
        mock_entry.summary = "New changes to Virginia divorce procedures and property division."
        mock_entry.author = "Legal Expert"
        mock_entry.published_parsed = (2024, 1, 15, 10, 30, 0, 0, 0, 0)
        mock_entry.tags = [Mock(term="family-law"), Mock(term="divorce")]
        
        content = await self.processor._process_feed_entry(mock_entry, "https://legal-blog.com/feed")
        
        assert content.url == mock_entry.link
        assert content.title == mock_entry.title
        assert "divorce procedures" in content.content
        assert content.published_date == datetime(2024, 1, 15, 10, 30, 0)
        assert content.content_type == "rss_article"
        assert content.legal_relevance_score > 0.0
    
    @pytest.mark.asyncio
    async def test_process_feed_with_mock_feedparser(self):
        """Test full feed processing with mocked feedparser."""
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.entries = [
            Mock(
                link="https://legal-blog.com/article-1",
                title="Family Law Update",
                summary="Virginia custody law changes.",
                author="Lawyer",
                published_parsed=(2024, 1, 15, 10, 30, 0, 0, 0, 0),
                tags=[]
            )
        ]
        
        with patch('feedparser.parse', return_value=mock_feed):
            results = await self.processor.process_feed("https://legal-blog.com/feed")
            
            assert len(results) == 1
            assert results[0].title == "Family Law Update"
            assert results[0].legal_relevance_score > 0.0


class TestWebScrapingClient:
    """Test main web scraping client."""
    
    @pytest.mark.asyncio
    async def test_scrape_url_success(self):
        """Test successful URL scraping."""
        html_content = """
        <html>
            <head><title>Virginia Court Forms</title></head>
            <body>
                <h1>Divorce Forms</h1>
                <p>Virginia Circuit Court divorce petition forms and procedures.</p>
            </body>
        </html>
        """
        
        async with WebScrapingClient() as client:
            # Mock robots.txt check
            client.robots_checker.can_fetch = AsyncMock(return_value=True)
            
            # Mock HTTP response
            with patch.object(client.session, 'get') as mock_get:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.text = AsyncMock(return_value=html_content)
                mock_get.return_value.__aenter__.return_value = mock_response
                
                result = await client.scrape_url("https://www.vacourts.gov/forms")
                
                assert result is not None
                assert result.title == "Divorce Forms"
                assert "divorce petition" in result.content.lower()
                assert result.legal_relevance_score > 0.0
    
    @pytest.mark.asyncio
    async def test_scrape_url_robots_disallowed(self):
        """Test URL scraping when robots.txt disallows."""
        async with WebScrapingClient() as client:
            client.robots_checker.can_fetch = AsyncMock(return_value=False)
            
            result = await client.scrape_url("https://example.com/disallowed")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_scrape_multiple_urls(self):
        """Test scraping multiple URLs with concurrency."""
        urls = [
            "https://www.vacourts.gov/forms",
            "https://www.vacourts.gov/procedures",
            "https://selfhelp.vacourts.gov/guide"
        ]
        
        async with WebScrapingClient() as client:
            # Mock scrape_url to return mock content
            mock_content = ScrapedContent(
                url="https://example.com",
                content="Virginia law content",
                legal_relevance_score=0.8,
                source_domain="example.com"
            )
            
            client.scrape_url = AsyncMock(return_value=mock_content)
            
            results = await client.scrape_multiple_urls(urls, max_concurrent=2)
            
            assert len(results) == 3
            assert all(isinstance(result, ScrapedContent) for result in results)


class TestPoliteSpider:
    """Test polite spider base class."""
    
    def test_spider_settings(self):
        """Test spider polite crawling settings."""
        spider = PoliteSpider()
        
        assert spider.custom_settings['DOWNLOAD_DELAY'] == 2
        assert spider.custom_settings['ROBOTSTXT_OBEY'] is True
        assert spider.custom_settings['CONCURRENT_REQUESTS'] == 1
        assert 'LegalResearchBot' in spider.custom_settings['USER_AGENT']
    
    def test_spider_initialization(self):
        """Test spider initialization."""
        spider = PoliteSpider(max_pages=50)
        
        assert spider.max_pages == 50
        assert spider.scraped_count == 0
        assert hasattr(spider, 'content_extractor')
        assert hasattr(spider, 'robots_checker')


class TestLegalSiteSpider:
    """Test legal site spider."""
    
    def test_spider_initialization_with_params(self):
        """Test spider initialization with parameters."""
        start_urls = ["https://www.vacourts.gov"]
        allowed_domains = ["vacourts.gov"]
        
        spider = LegalSiteSpider(
            start_urls=start_urls,
            allowed_domains=allowed_domains
        )
        
        assert spider.start_urls == start_urls
        assert spider.allowed_domains == allowed_domains
        assert len(spider.legal_patterns) > 0
    
    def test_is_allowed_domain(self):
        """Test domain filtering."""
        spider = LegalSiteSpider(allowed_domains=["vacourts.gov", "example.com"])
        
        assert spider._is_allowed_domain("https://www.vacourts.gov/forms") is True
        assert spider._is_allowed_domain("https://example.com/page") is True
        assert spider._is_allowed_domain("https://badsite.com/page") is False
    
    def test_is_allowed_domain_no_restrictions(self):
        """Test domain filtering with no restrictions."""
        spider = LegalSiteSpider()  # No allowed_domains
        
        assert spider._is_allowed_domain("https://any-site.com/page") is True


class TestScrapedContent:
    """Test ScrapedContent model."""
    
    def test_scraped_content_creation(self):
        """Test creating ScrapedContent object."""
        content = ScrapedContent(
            url="https://www.vacourts.gov/forms",
            title="Family Law Forms",
            content="Virginia divorce and custody forms.",
            legal_relevance_score=0.85,
            source_domain="www.vacourts.gov"
        )
        
        assert content.url == "https://www.vacourts.gov/forms"
        assert content.title == "Family Law Forms"
        assert content.legal_relevance_score == 0.85
        assert content.content_type == "web_page"  # Default value
        assert isinstance(content.extracted_at, datetime)
    
    def test_scraped_content_with_metadata(self):
        """Test ScrapedContent with metadata."""
        metadata = {
            "word_count": 500,
            "internal_links": ["https://www.vacourts.gov/about"],
            "author": "Virginia Courts"
        }
        
        content = ScrapedContent(
            url="https://www.vacourts.gov/forms",
            content="Legal content",
            legal_relevance_score=0.7,
            source_domain="www.vacourts.gov",
            metadata=metadata
        )
        
        assert content.metadata["word_count"] == 500
        assert len(content.metadata["internal_links"]) == 1