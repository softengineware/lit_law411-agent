"""Source model for tracking content sources."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class Source(BaseModel):
    """Model for content sources (YouTube channels, websites, etc.)."""
    
    __tablename__ = "sources"
    
    # Basic Information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Source name or title"
    )
    
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type: youtube_channel, website, rss_feed, etc."
    )
    
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        unique=True,
        comment="Source URL or identifier"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Source description"
    )
    
    # Metadata
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="External ID (e.g., YouTube channel ID)"
    )
    
    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        comment="Primary language code"
    )
    
    country: Mapped[Optional[str]] = mapped_column(
        String(2),
        comment="Country code (ISO 3166-1 alpha-2)"
    )
    
    jurisdiction: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Legal jurisdiction (e.g., 'US Federal', 'CA Supreme Court')"
    )
    
    # Status and Quality
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Whether source is actively monitored"
    )
    
    credibility_score: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Credibility score (0.0 to 1.0)"
    )
    
    # Scraping Configuration
    scrape_frequency_hours: Mapped[int] = mapped_column(
        Integer,
        default=24,
        comment="How often to check for new content (hours)"
    )
    
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(
        comment="Last successful scrape timestamp"
    )
    
    scrape_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Consecutive scrape error count"
    )
    
    # Statistics
    total_content_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Total content items from this source"
    )
    
    # Relationships
    content_items = relationship(
        "Content",
        back_populates="source",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<Source(name='{self.name}', type='{self.source_type}')>"