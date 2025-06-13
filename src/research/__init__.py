"""
Legal Website Research Module

This module provides comprehensive research and analysis capabilities
for discovering and evaluating legal websites for content scraping.

Key Components:
- LegalWebsiteResearcher: Discovers valuable legal websites
- WebsiteAnalyzer: Analyzes scraping strategies and content value
- Focus on Virginia Circuit Court family law practice
- Universal legal principles and educational content
"""

from .legal_website_researcher import (
    LegalWebsiteResearcher,
    LegalWebsiteCandidate,
    get_legal_website_researcher
)

from .website_analyzer import (
    WebsiteAnalyzer,
    WebsiteAnalysis,
    ScrapingStrategy,
    ContentStructure,
    get_website_analyzer
)

__all__ = [
    'LegalWebsiteResearcher',
    'LegalWebsiteCandidate', 
    'WebsiteAnalyzer',
    'WebsiteAnalysis',
    'ScrapingStrategy',
    'ContentStructure',
    'get_legal_website_researcher',
    'get_website_analyzer'
]