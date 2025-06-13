"""SearchQuery model for tracking user searches."""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class SearchQuery(BaseModel):
    """Model for tracking user search queries."""
    
    __tablename__ = "search_queries"
    
    # User Relationship (optional - can track anonymous searches)
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        comment="User who performed the search (null for anonymous)"
    )
    
    # Query Information
    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Original search query text"
    )
    
    query_type: Mapped[str] = mapped_column(
        String(50),
        default="text",
        comment="Type: text, semantic, hybrid, citation, etc."
    )
    
    # Search Parameters
    filters: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Applied filters (jurisdiction, date range, content type, etc.)"
    )
    
    sort_by: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="Sort order: relevance, date, credibility, etc."
    )
    
    limit_count: Mapped[int] = mapped_column(
        Integer,
        default=20,
        comment="Number of results requested"
    )
    
    offset_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Pagination offset"
    )
    
    # Search Results
    total_results: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Total number of results found"
    )
    
    returned_results: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of results returned to user"
    )
    
    # Performance Metrics
    search_time_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Time taken to execute search in milliseconds"
    )
    
    embedding_time_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Time taken to generate query embedding"
    )
    
    # Search Engine Information
    search_engines_used: Mapped[Optional[list]] = mapped_column(
        JSONB,
        comment="Which search engines were used: elasticsearch, pinecone, etc."
    )
    
    # User Context
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="User session ID"
    )
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 support
        comment="User IP address"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="User agent string"
    )
    
    # Search Quality
    clicked_results: Mapped[Optional[list]] = mapped_column(
        JSONB,
        comment="Which results were clicked by user"
    )
    
    user_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="User rating of search results (1-5)"
    )
    
    user_feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="User feedback on search results"
    )
    
    # Raw Data
    raw_results: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Raw search results for analysis"
    )
    
    # Relationships
    user = relationship("User", back_populates="search_queries")
    
    def __repr__(self) -> str:
        """String representation."""
        query_preview = self.query_text[:50] + "..." if len(self.query_text) > 50 else self.query_text
        return (
            f"<SearchQuery(query='{query_preview}', "
            f"results={self.total_results}, "
            f"time={self.search_time_ms}ms)>"
        )