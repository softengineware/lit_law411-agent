"""Transcript model for audio/video transcriptions."""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class Transcript(BaseModel):
    """Model for audio/video transcriptions."""
    
    __tablename__ = "transcripts"
    
    # Content Relationship
    content_id: Mapped[str] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False,
        comment="Content this transcript belongs to"
    )
    
    # Transcript Data
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full transcript text"
    )
    
    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        comment="Transcript language code"
    )
    
    # Processing Information
    transcription_engine: Mapped[str] = mapped_column(
        String(50),
        default="whisper",
        comment="Engine used: whisper, speech_recognition, etc."
    )
    
    model_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="Model version used for transcription"
    )
    
    # Quality Metrics
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Overall confidence score (0.0 to 1.0)"
    )
    
    word_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        comment="Word count of transcript"
    )
    
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Time taken to generate transcript"
    )
    
    # Detailed segments with timestamps
    segments: Mapped[Optional[list]] = mapped_column(
        JSON,
        comment="Detailed segments with timestamps and confidence scores"
    )
    
    # Raw output from transcription engine
    raw_output: Mapped[Optional[dict]] = mapped_column(
        JSON,
        comment="Raw output from transcription engine"
    )
    
    # Relationships
    content = relationship("Content", back_populates="transcripts")
    
    def __repr__(self) -> str:
        """String representation."""
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"<Transcript(content_id='{self.content_id}', preview='{preview}')>"