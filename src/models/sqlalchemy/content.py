"""Content model for storing scraped content."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class Content(BaseModel):
    """Model for content items (videos, articles, documents)."""
    
    __tablename__ = "content"
    
    # Source Relationship
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        comment="Source that provided this content"
    )
    
    # Basic Information
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Content title"
    )
    
    content_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type: video, article, document, case, statute, etc."
    )
    
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="Content URL"
    )
    
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="External ID (e.g., YouTube video ID)"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Content description or summary"
    )
    
    # Content Data
    text_content: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Extracted text content"
    )
    
    html_content: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Raw HTML content"
    )
    
    # Metadata
    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        comment="Content language code"
    )
    
    author: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="Content author or creator"
    )
    
    published_at: Mapped[Optional[datetime]] = mapped_column(
        comment="Original publication date"
    )
    
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Duration for video/audio content"
    )
    
    word_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Word count of text content"
    )
    
    # Legal Metadata
    jurisdiction: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Legal jurisdiction"
    )
    
    case_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Case number if applicable"
    )
    
    court: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="Court name if applicable"
    )
    
    legal_topic: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="Primary legal topic"
    )
    
    # Processing Status
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        comment="Status: pending, processing, completed, failed"
    )
    
    transcription_status: Mapped[str] = mapped_column(
        String(50),
        default="not_applicable",
        comment="Status: not_applicable, pending, processing, completed, failed"
    )
    
    nlp_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        comment="Status: pending, processing, completed, failed"
    )
    
    embedding_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        comment="Status: pending, processing, completed, failed"
    )
    
    # Quality Metrics
    quality_score: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Content quality score (0.0 to 1.0)"
    )
    
    credibility_score: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Content credibility score (0.0 to 1.0)"
    )
    
    # Engagement Metrics (if available)
    view_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="View/read count"
    )
    
    like_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Like/upvote count"
    )
    
    comment_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Comment count"
    )
    
    # Flags
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Whether content is publicly accessible"
    )
    
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether all processing is complete"
    )
    
    # Raw metadata from source
    raw_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Raw metadata from source API"
    )
    
    # Relationships
    source = relationship("Source", back_populates="content_items")
    transcripts = relationship(
        "Transcript",
        back_populates="content",
        cascade="all, delete-orphan"
    )
    embeddings = relationship(
        "Embedding",
        back_populates="content",
        cascade="all, delete-orphan"
    )
    entities = relationship(
        "Entity",
        back_populates="content",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<Content(title='{self.title[:50]}...', type='{self.content_type}')>"