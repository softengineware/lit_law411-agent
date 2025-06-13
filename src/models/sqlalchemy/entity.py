"""Entity model for legal entity recognition results."""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class Entity(BaseModel):
    """Model for extracted legal entities."""
    
    __tablename__ = "entities"
    
    # Content Relationship
    content_id: Mapped[str] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"),
        nullable=False,
        comment="Content this entity was extracted from"
    )
    
    # Entity Information
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type: CASE_CITATION, STATUTE, REGULATION, COURT, JUDGE, PARTY, etc."
    )
    
    entity_text: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Raw text of the entity"
    )
    
    normalized_text: Mapped[Optional[str]] = mapped_column(
        String(500),
        comment="Normalized/standardized version of entity text"
    )
    
    # Position in Content
    start_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Character position where entity starts"
    )
    
    end_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Character position where entity ends"
    )
    
    # Context
    context_before: Mapped[Optional[str]] = mapped_column(
        String(200),
        comment="Text before the entity for context"
    )
    
    context_after: Mapped[Optional[str]] = mapped_column(
        String(200),
        comment="Text after the entity for context"
    )
    
    # NER Model Information
    ner_model: Mapped[str] = mapped_column(
        String(100),
        default="spacy",
        comment="NER model used: spacy, transformers, etc."
    )
    
    model_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="Model version"
    )
    
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Confidence score (0.0 to 1.0)"
    )
    
    # Legal-specific Information
    jurisdiction: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Jurisdiction if applicable"
    )
    
    citation_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="For citations: case, statute, regulation, etc."
    )
    
    court_level: Mapped[Optional[str]] = mapped_column(
        String(50),
        comment="For courts: federal, state, supreme, appellate, trial"
    )
    
    # External References
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        comment="External ID if entity can be linked to database"
    )
    
    # Structured Data
    structured_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Structured representation of entity data"
    )
    
    # Raw NER Output
    raw_ner_output: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Raw output from NER model"
    )
    
    # Relationships
    content = relationship("Content", back_populates="entities")
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Entity(type='{self.entity_type}', "
            f"text='{self.entity_text[:30]}...', "
            f"confidence={self.confidence_score})>"
        )