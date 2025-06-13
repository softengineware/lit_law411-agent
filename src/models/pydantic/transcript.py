"""
Pydantic models for transcript data.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """Individual transcript segment with timing."""
    id: int
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcript text for this segment")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    speaker: Optional[str] = Field(None, description="Speaker identification")


class TranscriptResponse(BaseModel):
    """Complete transcript response with metadata."""
    text: str = Field(..., description="Full transcript text")
    language: str = Field(default="en", description="Detected language")
    duration: float = Field(default=0.0, description="Audio duration in seconds")
    segments: List[TranscriptSegment] = Field(default_factory=list)
    legal_entities: List[str] = Field(default_factory=list, description="Extracted legal entities")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    word_count: int = Field(default=0, description="Number of words in transcript")
    processing_time_seconds: float = Field(default=0.0)
    source_metadata: Optional[Dict[str, Any]] = Field(None, description="Source audio metadata")
    created_at: datetime = Field(default_factory=datetime.now)


class TranscriptSearchResult(BaseModel):
    """Search result within transcript."""
    segment_id: int
    start_time: float
    end_time: float
    text: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    context_before: Optional[str] = None
    context_after: Optional[str] = None


class TranscriptSummary(BaseModel):
    """Summary of transcript content."""
    key_points: List[str]
    legal_topics: List[str]
    participants: List[str]
    duration_summary: str
    confidence_rating: str = Field(description="High/Medium/Low")


class TranscriptRequest(BaseModel):
    """Request for transcript creation."""
    source_url: str
    language: Optional[str] = None
    custom_prompt: Optional[str] = None
    priority: str = Field(default="normal", regex="^(low|normal|high|urgent)$")
    callback_url: Optional[str] = None


class TranscriptUpdate(BaseModel):
    """Update transcript content."""
    text: Optional[str] = None
    segments: Optional[List[TranscriptSegment]] = None
    legal_entities: Optional[List[str]] = None
    notes: Optional[str] = None