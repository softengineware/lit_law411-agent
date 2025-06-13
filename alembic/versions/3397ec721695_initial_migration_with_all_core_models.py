"""Initial migration with all core models

Revision ID: 3397ec721695
Revises: 
Create Date: 2025-06-13 01:41:53.708520

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3397ec721695'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create sources table
    op.create_table(
        'sources',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False, comment='Unique identifier'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last update timestamp'),
        sa.Column('name', sa.String(length=255), nullable=False, comment='Source name or title'),
        sa.Column('source_type', sa.String(length=50), nullable=False, comment='Type: youtube_channel, website, rss_feed, etc.'),
        sa.Column('url', sa.String(length=2048), nullable=False, comment='Source URL or identifier'),
        sa.Column('description', sa.Text(), nullable=True, comment='Source description'),
        sa.Column('external_id', sa.String(length=255), nullable=True, comment='External ID (e.g., YouTube channel ID)'),
        sa.Column('language', sa.String(length=10), nullable=False, default='en', comment='Primary language code'),
        sa.Column('country', sa.String(length=2), nullable=True, comment='Country code (ISO 3166-1 alpha-2)'),
        sa.Column('jurisdiction', sa.String(length=100), nullable=True, comment='Legal jurisdiction (e.g., \'US Federal\', \'CA Supreme Court\')'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='Whether source is actively monitored'),
        sa.Column('credibility_score', sa.Float(), nullable=True, comment='Credibility score (0.0 to 1.0)'),
        sa.Column('scrape_frequency_hours', sa.Integer(), nullable=False, default=24, comment='How often to check for new content (hours)'),
        sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True, comment='Last successful scrape timestamp'),
        sa.Column('scrape_errors', sa.Integer(), nullable=False, default=0, comment='Consecutive scrape error count'),
        sa.Column('total_content_count', sa.Integer(), nullable=False, default=0, comment='Total content items from this source'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url')
    )

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False, comment='Unique identifier'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last update timestamp'),
        sa.Column('email', sa.String(length=255), nullable=False, comment='User email address'),
        sa.Column('username', sa.String(length=50), nullable=True, comment='Unique username'),
        sa.Column('password_hash', sa.String(length=255), nullable=False, comment='Hashed password'),
        sa.Column('first_name', sa.String(length=100), nullable=True, comment='First name'),
        sa.Column('last_name', sa.String(length=100), nullable=True, comment='Last name'),
        sa.Column('organization', sa.String(length=255), nullable=True, comment='Organization or law firm'),
        sa.Column('job_title', sa.String(length=100), nullable=True, comment='Job title'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True, comment='Account is active'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False, comment='Email is verified'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, default=False, comment='Has admin privileges'),
        sa.Column('role', sa.String(length=50), nullable=False, default='user', comment='User role: user, premium, admin, superuser'),
        sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Additional permissions'),
        sa.Column('subscription_tier', sa.String(length=50), nullable=False, default='free', comment='Subscription tier: free, basic, premium, enterprise'),
        sa.Column('subscription_expires_at', sa.DateTime(timezone=True), nullable=True, comment='Subscription expiration date'),
        sa.Column('api_calls_today', sa.Integer(), nullable=False, default=0, comment='API calls made today'),
        sa.Column('api_calls_month', sa.Integer(), nullable=False, default=0, comment='API calls made this month'),
        sa.Column('total_api_calls', sa.Integer(), nullable=False, default=0, comment='Total API calls made'),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, default=0, comment='Failed login attempts'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True, comment='Account locked until this time'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True, comment='Last successful login'),
        sa.Column('last_login_ip', sa.String(length=45), nullable=True, comment='IP address of last login'),
        sa.Column('email_verification_token', sa.String(length=255), nullable=True, comment='Email verification token'),
        sa.Column('email_verification_expires_at', sa.DateTime(timezone=True), nullable=True, comment='Email verification token expiration'),
        sa.Column('password_reset_token', sa.String(length=255), nullable=True, comment='Password reset token'),
        sa.Column('password_reset_expires_at', sa.DateTime(timezone=True), nullable=True, comment='Password reset token expiration'),
        sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='User preferences and settings'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )

    # Create content table
    op.create_table(
        'content',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False, comment='Unique identifier'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last update timestamp'),
        sa.Column('source_id', postgresql.UUID(as_uuid=False), nullable=False, comment='Source that provided this content'),
        sa.Column('title', sa.String(length=500), nullable=False, comment='Content title'),
        sa.Column('content_type', sa.String(length=50), nullable=False, comment='Type: video, article, document, case, statute, etc.'),
        sa.Column('url', sa.String(length=2048), nullable=False, comment='Content URL'),
        sa.Column('external_id', sa.String(length=255), nullable=True, comment='External ID (e.g., YouTube video ID)'),
        sa.Column('description', sa.Text(), nullable=True, comment='Content description or summary'),
        sa.Column('text_content', sa.Text(), nullable=True, comment='Extracted text content'),
        sa.Column('html_content', sa.Text(), nullable=True, comment='Raw HTML content'),
        sa.Column('language', sa.String(length=10), nullable=False, default='en', comment='Content language code'),
        sa.Column('author', sa.String(length=255), nullable=True, comment='Content author or creator'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True, comment='Original publication date'),
        sa.Column('duration_seconds', sa.Integer(), nullable=True, comment='Duration for video/audio content'),
        sa.Column('word_count', sa.Integer(), nullable=True, comment='Word count of text content'),
        sa.Column('jurisdiction', sa.String(length=100), nullable=True, comment='Legal jurisdiction'),
        sa.Column('case_number', sa.String(length=100), nullable=True, comment='Case number if applicable'),
        sa.Column('court', sa.String(length=255), nullable=True, comment='Court name if applicable'),
        sa.Column('legal_topic', sa.String(length=255), nullable=True, comment='Primary legal topic'),
        sa.Column('processing_status', sa.String(length=50), nullable=False, default='pending', comment='Status: pending, processing, completed, failed'),
        sa.Column('transcription_status', sa.String(length=50), nullable=False, default='not_applicable', comment='Status: not_applicable, pending, processing, completed, failed'),
        sa.Column('nlp_status', sa.String(length=50), nullable=False, default='pending', comment='Status: pending, processing, completed, failed'),
        sa.Column('embedding_status', sa.String(length=50), nullable=False, default='pending', comment='Status: pending, processing, completed, failed'),
        sa.Column('quality_score', sa.Float(), nullable=True, comment='Content quality score (0.0 to 1.0)'),
        sa.Column('credibility_score', sa.Float(), nullable=True, comment='Content credibility score (0.0 to 1.0)'),
        sa.Column('view_count', sa.Integer(), nullable=True, comment='View/read count'),
        sa.Column('like_count', sa.Integer(), nullable=True, comment='Like/upvote count'),
        sa.Column('comment_count', sa.Integer(), nullable=True, comment='Comment count'),
        sa.Column('is_public', sa.Boolean(), nullable=False, default=True, comment='Whether content is publicly accessible'),
        sa.Column('is_processed', sa.Boolean(), nullable=False, default=False, comment='Whether all processing is complete'),
        sa.Column('raw_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Raw metadata from source API'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create search_queries table
    op.create_table(
        'search_queries',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False, comment='Unique identifier'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last update timestamp'),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=True, comment='User who performed the search (null for anonymous)'),
        sa.Column('query_text', sa.Text(), nullable=False, comment='Original search query text'),
        sa.Column('query_type', sa.String(length=50), nullable=False, default='text', comment='Type: text, semantic, hybrid, citation, etc.'),
        sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Applied filters (jurisdiction, date range, content type, etc.)'),
        sa.Column('sort_by', sa.String(length=50), nullable=True, comment='Sort order: relevance, date, credibility, etc.'),
        sa.Column('limit_count', sa.Integer(), nullable=False, default=20, comment='Number of results requested'),
        sa.Column('offset_count', sa.Integer(), nullable=False, default=0, comment='Pagination offset'),
        sa.Column('total_results', sa.Integer(), nullable=True, comment='Total number of results found'),
        sa.Column('returned_results', sa.Integer(), nullable=False, default=0, comment='Number of results returned to user'),
        sa.Column('search_time_ms', sa.Float(), nullable=True, comment='Time taken to execute search in milliseconds'),
        sa.Column('embedding_time_ms', sa.Float(), nullable=True, comment='Time taken to generate query embedding'),
        sa.Column('search_engines_used', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Which search engines were used: elasticsearch, pinecone, etc.'),
        sa.Column('session_id', sa.String(length=255), nullable=True, comment='User session ID'),
        sa.Column('ip_address', sa.String(length=45), nullable=True, comment='User IP address'),
        sa.Column('user_agent', sa.Text(), nullable=True, comment='User agent string'),
        sa.Column('clicked_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Which results were clicked by user'),
        sa.Column('user_rating', sa.Integer(), nullable=True, comment='User rating of search results (1-5)'),
        sa.Column('user_feedback', sa.Text(), nullable=True, comment='User feedback on search results'),
        sa.Column('raw_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Raw search results for analysis'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create transcripts table
    op.create_table(
        'transcripts',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False, comment='Unique identifier'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last update timestamp'),
        sa.Column('content_id', postgresql.UUID(as_uuid=False), nullable=False, comment='Content this transcript belongs to'),
        sa.Column('text', sa.Text(), nullable=False, comment='Full transcript text'),
        sa.Column('language', sa.String(length=10), nullable=False, default='en', comment='Transcript language code'),
        sa.Column('transcription_engine', sa.String(length=50), nullable=False, default='whisper', comment='Engine used: whisper, speech_recognition, etc.'),
        sa.Column('model_version', sa.String(length=50), nullable=True, comment='Model version used for transcription'),
        sa.Column('confidence_score', sa.Float(), nullable=True, comment='Overall confidence score (0.0 to 1.0)'),
        sa.Column('word_count', sa.Integer(), nullable=True, comment='Word count of transcript'),
        sa.Column('processing_time_seconds', sa.Float(), nullable=True, comment='Time taken to generate transcript'),
        sa.Column('segments', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Detailed segments with timestamps and confidence scores'),
        sa.Column('raw_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Raw output from transcription engine'),
        sa.ForeignKeyConstraint(['content_id'], ['content.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create embeddings table
    op.create_table(
        'embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False, comment='Unique identifier'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last update timestamp'),
        sa.Column('content_id', postgresql.UUID(as_uuid=False), nullable=False, comment='Content this embedding represents'),
        sa.Column('vector', postgresql.ARRAY(sa.Float()), nullable=False, comment='Vector embedding'),
        sa.Column('embedding_model', sa.String(length=100), nullable=False, comment='Model used: text-embedding-3-large, sentence-transformers, etc.'),
        sa.Column('model_version', sa.String(length=50), nullable=True, comment='Model version'),
        sa.Column('dimension_count', sa.Integer(), nullable=False, comment='Number of dimensions in vector'),
        sa.Column('source_text', sa.Text(), nullable=True, comment='Text that was embedded (for debugging)'),
        sa.Column('chunk_index', sa.Integer(), nullable=True, comment='Index if content was chunked'),
        sa.Column('chunk_overlap', sa.Integer(), nullable=True, comment='Overlap with previous chunk in characters'),
        sa.Column('processing_time_seconds', sa.Float(), nullable=True, comment='Time taken to generate embedding'),
        sa.Column('pinecone_id', sa.String(length=255), nullable=True, comment='ID in Pinecone vector database'),
        sa.ForeignKeyConstraint(['content_id'], ['content.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create entities table
    op.create_table(
        'entities',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False, comment='Unique identifier'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Last update timestamp'),
        sa.Column('content_id', postgresql.UUID(as_uuid=False), nullable=False, comment='Content this entity was extracted from'),
        sa.Column('entity_type', sa.String(length=50), nullable=False, comment='Type: CASE_CITATION, STATUTE, REGULATION, COURT, JUDGE, PARTY, etc.'),
        sa.Column('entity_text', sa.String(length=500), nullable=False, comment='Raw text of the entity'),
        sa.Column('normalized_text', sa.String(length=500), nullable=True, comment='Normalized/standardized version of entity text'),
        sa.Column('start_position', sa.Integer(), nullable=False, comment='Character position where entity starts'),
        sa.Column('end_position', sa.Integer(), nullable=False, comment='Character position where entity ends'),
        sa.Column('context_before', sa.String(length=200), nullable=True, comment='Text before the entity for context'),
        sa.Column('context_after', sa.String(length=200), nullable=True, comment='Text after the entity for context'),
        sa.Column('ner_model', sa.String(length=100), nullable=False, default='spacy', comment='NER model used: spacy, transformers, etc.'),
        sa.Column('model_version', sa.String(length=50), nullable=True, comment='Model version'),
        sa.Column('confidence_score', sa.Float(), nullable=True, comment='Confidence score (0.0 to 1.0)'),
        sa.Column('jurisdiction', sa.String(length=100), nullable=True, comment='Jurisdiction if applicable'),
        sa.Column('citation_type', sa.String(length=50), nullable=True, comment='For citations: case, statute, regulation, etc.'),
        sa.Column('court_level', sa.String(length=50), nullable=True, comment='For courts: federal, state, supreme, appellate, trial'),
        sa.Column('external_id', sa.String(length=255), nullable=True, comment='External ID if entity can be linked to database'),
        sa.Column('structured_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Structured representation of entity data'),
        sa.Column('raw_ner_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Raw output from NER model'),
        sa.ForeignKeyConstraint(['content_id'], ['content.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse dependency order
    op.drop_table('entities')
    op.drop_table('embeddings')
    op.drop_table('transcripts')
    op.drop_table('search_queries')
    op.drop_table('content')
    op.drop_table('users')
    op.drop_table('sources')
