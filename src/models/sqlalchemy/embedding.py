"""Embedding model for vector representations."""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class Embedding(BaseModel):
    """Model for vector embeddings of content."""
    
    __tablename__ = "embeddings"
    
    # Content Relationship
    content_id: Mapped[str] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False,
        comment="Content this embedding represents"
    )
    
    # Embedding Data
    vector: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
        comment="Vector embedding"
    )
    
    # Embedding Metadata
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Model used: text-embedding-3-large, sentence-transformers, etc."
    )
    
    model_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="Model version"
    )
    
    dimension_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of dimensions in vector"
    )
    
    # Source Information
    source_text: Mapped[Optional[str]] = mapped_column(
        Text,
        comment="Text that was embedded (for debugging)"
    )
    
    chunk_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Index if content was chunked"
    )
    
    chunk_overlap: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Overlap with previous chunk in characters"
    )
    
    # Processing Information
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Time taken to generate embedding"
    )
    
    # External Storage
    pinecone_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="ID in Pinecone vector database"
    )
    
    # Relationships
    content = relationship("Content", back_populates="embeddings")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Embedding(content_id='{self.content_id}', "
            f"model='{self.embedding_model}', dims={self.dimension_count})>"
        )