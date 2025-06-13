"""Unit tests for SQLAlchemy models."""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.sqlalchemy import Base, Content, Entity, Embedding, SearchQuery, Source, Transcript, User


# Test database URL for SQLite in memory
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def engine():
    """Create test database engine."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestBaseModel:
    """Test BaseModel functionality."""
    
    def test_source_creation(self, session):
        """Test creating a Source model."""
        source = Source(
            name="Test Legal Blog",
            source_type="website",
            url="https://example-law.com",
            description="A test legal blog",
            language="en",
            is_active=True
        )
        
        session.add(source)
        session.commit()
        
        # Test that ID was generated
        assert source.id is not None
        assert source.created_at is not None
        assert source.updated_at is not None
        
        # Test string representation
        assert "Test Legal Blog" in str(source)
        assert source.source_type == "website"


class TestUser:
    """Test User model."""
    
    def test_user_creation(self, session):
        """Test creating a User model."""
        user = User(
            email="test@example.com",
            username="testuser",
            password_hash="hashed_password",
            first_name="John",
            last_name="Doe",
            is_active=True
        )
        
        session.add(user)
        session.commit()
        
        assert user.email == "test@example.com"
        assert user.full_name == "John Doe"
        assert not user.is_premium  # default is free tier
        assert not user.is_account_locked
        
    def test_user_properties(self, session):
        """Test User model properties."""
        user = User(
            email="premium@example.com",
            password_hash="hashed",
            subscription_tier="premium"
        )
        
        assert user.is_premium
        
        # Test locked account (set to future time)
        from datetime import timedelta, timezone
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        assert user.is_account_locked


class TestSource:
    """Test Source model."""
    
    def test_source_fields(self, session):
        """Test Source model fields."""
        source = Source(
            name="YouTube Legal Channel",
            source_type="youtube_channel",
            url="https://youtube.com/channel/123",
            external_id="UC123456789",
            jurisdiction="US Federal",
            credibility_score=0.95,
            scrape_frequency_hours=12
        )
        
        session.add(source)
        session.commit()
        
        assert source.credibility_score == 0.95
        assert source.scrape_frequency_hours == 12
        assert source.jurisdiction == "US Federal"


class TestContent:
    """Test Content model."""
    
    def test_content_creation(self, session):
        """Test creating Content with Source relationship."""
        # Create source first
        source = Source(
            name="Test Source",
            source_type="website", 
            url="https://example.com"
        )
        session.add(source)
        session.commit()
        
        # Create content
        content = Content(
            source_id=source.id,
            title="Important Legal Case",
            content_type="case",
            url="https://example.com/case-123",
            external_id="case-123",
            description="A significant legal case",
            language="en",
            author="Judge Smith",
            jurisdiction="US Supreme Court",
            case_number="2023-001",
            processing_status="pending"
        )
        
        session.add(content)
        session.commit()
        
        assert content.title == "Important Legal Case"
        assert content.source_id == source.id
        assert content.case_number == "2023-001"
        assert "Important Legal Case" in str(content)


class TestTranscript:
    """Test Transcript model."""
    
    def test_transcript_creation(self, session):
        """Test creating Transcript with Content relationship."""
        # Create source and content first
        source = Source(name="Video Source", source_type="youtube", url="https://youtube.com/123")
        session.add(source)
        session.commit()
        
        content = Content(
            source_id=source.id,
            title="Legal Video",
            content_type="video",
            url="https://youtube.com/watch?v=123"
        )
        session.add(content)
        session.commit()
        
        # Create transcript
        transcript = Transcript(
            content_id=content.id,
            text="This is the full transcript of the legal video.",
            language="en",
            transcription_engine="whisper",
            confidence_score=0.92,
            word_count=10
        )
        
        session.add(transcript)
        session.commit()
        
        assert transcript.content_id == content.id
        assert transcript.confidence_score == 0.92
        assert "This is the full transcript" in str(transcript)


class TestEmbedding:
    """Test Embedding model."""
    
    def test_embedding_creation(self, session):
        """Test creating Embedding with Content relationship."""
        # Create source and content first
        source = Source(name="Article Source", source_type="website", url="https://example.com")
        session.add(source)
        session.commit()
        
        content = Content(
            source_id=source.id,
            title="Legal Article", 
            content_type="article",
            url="https://example.com/article"
        )
        session.add(content)
        session.commit()
        
        # Create embedding
        embedding = Embedding(
            content_id=content.id,
            vector=[0.1, 0.2, 0.3, 0.4, 0.5],
            embedding_model="text-embedding-3-large",
            dimension_count=5,
            source_text="Sample text for embedding",
            pinecone_id="pinecone-123"
        )
        
        session.add(embedding)
        session.commit()
        
        assert embedding.content_id == content.id
        assert len(embedding.vector) == 5
        assert embedding.dimension_count == 5
        assert "text-embedding-3-large" in str(embedding)


class TestEntity:
    """Test Entity model."""
    
    def test_entity_creation(self, session):
        """Test creating Entity with Content relationship."""
        # Create source and content first
        source = Source(name="Case Source", source_type="website", url="https://example.com")
        session.add(source)
        session.commit()
        
        content = Content(
            source_id=source.id,
            title="Legal Case Document",
            content_type="case",
            url="https://example.com/case"
        )
        session.add(content)
        session.commit()
        
        # Create entity
        entity = Entity(
            content_id=content.id,
            entity_type="CASE_CITATION",
            entity_text="Brown v. Board of Education, 347 U.S. 483 (1954)",
            normalized_text="Brown v. Board of Education",
            start_position=100,
            end_position=145,
            ner_model="spacy",
            confidence_score=0.98,
            jurisdiction="US Supreme Court",
            citation_type="case"
        )
        
        session.add(entity)
        session.commit()
        
        assert entity.entity_type == "CASE_CITATION"
        assert entity.confidence_score == 0.98
        assert "Brown v. Board" in str(entity)


class TestSearchQuery:
    """Test SearchQuery model."""
    
    def test_search_query_creation(self, session):
        """Test creating SearchQuery with optional User relationship."""
        # Test anonymous search
        query = SearchQuery(
            query_text="contract law dispute resolution",
            query_type="text",
            total_results=150,
            returned_results=20,
            search_time_ms=45.5
        )
        
        session.add(query)
        session.commit()
        
        assert query.user_id is None  # anonymous
        assert query.total_results == 150
        assert "contract law dispute" in str(query)
        
    def test_search_query_with_user(self, session):
        """Test SearchQuery with User relationship."""
        # Create user first
        user = User(
            email="searcher@example.com",
            password_hash="hashed"
        )
        session.add(user)
        session.commit()
        
        # Create search query
        query = SearchQuery(
            user_id=user.id,
            query_text="constitutional law cases",
            query_type="semantic",
            filters={"jurisdiction": "US Federal", "year": 2023},
            total_results=75,
            search_time_ms=120.3
        )
        
        session.add(query)
        session.commit()
        
        assert query.user_id == user.id
        assert query.filters["jurisdiction"] == "US Federal"