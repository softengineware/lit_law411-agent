# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

lit_law411-agent is an enterprise-grade Legal Knowledge Base Agent that automatically gathers, processes, and organizes legal knowledge from diverse sources including YouTube videos and legal websites. Built with modern microservices architecture, it creates a comprehensive, searchable knowledge base for the Law411 platform.

## System Architecture

### High-Level Architecture
```
External Sources → Ingestion Layer → Processing Pipeline → Storage Layer → API Layer → Clients
```

### Core Components

#### 1. Ingestion Layer
- **YouTube Client**: YouTube Data API v3 with quota management
- **Web Scraper**: Scrapy-based with robots.txt compliance
- **Feed Processor**: RSS/Atom feed parser for legal blogs
- **Rate Limiter**: Token bucket algorithm for API protection

#### 2. Processing Pipeline
- **Transcription**: OpenAI Whisper for audio-to-text
- **NLP Engine**: spaCy with custom legal entity recognition
- **Embedding Generator**: Sentence transformers for semantic search
- **Task Queue**: Celery with Redis for distributed processing

#### 3. Storage Layer (Three-Database Strategy)
- **Airtable**: Visual interface layer for human-friendly browsing, filtering, and manual data management
- **PostgreSQL (Supabase)**: ACID-compliant relational database for complex queries, data integrity, and audit trails
- **Pinecone**: Vector database for AI-powered semantic search and similarity matching
- **Redis**: Caching layer and message broker for performance optimization

**Note**: See `THREE_DATABASE_STRATEGY.md` for detailed implementation requirements and synchronization protocols.

#### 4. API Layer
- **FastAPI**: REST API with OpenAPI documentation
- **GraphQL**: Flexible query endpoint
- **WebSocket**: Real-time updates

## Development Setup

### Prerequisites
```bash
# Required versions
Python 3.11+
Docker & Docker Compose
PostgreSQL 15+
Redis 7+
Elasticsearch 8.11+
```

### Quick Start
```bash
# 1. Clone and enter directory
git clone https://github.com/softengineware/lit_law411-agent.git
cd lit_law411-agent

# 2. Set up Poetry
poetry install
poetry shell

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Start services
docker-compose up -d

# 5. Run migrations
alembic upgrade head

# 6. Start development server
uvicorn src.main:app --reload

# 7. Start Celery worker (new terminal)
celery -A src.workers worker --loglevel=info
```

## Project Structure

```
lit_law411-agent/
├── src/
│   ├── api/              # FastAPI routes & endpoints
│   │   ├── v1/          # API version 1
│   │   ├── graphql/     # GraphQL schema & resolvers
│   │   └── websocket/   # WebSocket handlers
│   ├── core/            # Business logic
│   │   ├── config.py    # Configuration management
│   │   ├── security.py  # Auth & security
│   │   └── exceptions.py # Custom exceptions
│   ├── models/          # Data models
│   │   ├── sqlalchemy/  # Database models
│   │   └── pydantic/    # API schemas
│   ├── db/              # Database layer
│   │   ├── repositories/ # Data access patterns
│   │   └── clients/     # External DB clients (Supabase, Pinecone, Airtable)
│   ├── scrapers/        # Data ingestion
│   │   ├── youtube.py   # YouTube scraper
│   │   ├── web.py       # Web scraper
│   │   └── feeds.py     # RSS/Atom processor
│   ├── processors/      # Data processing
│   │   ├── transcription.py # Audio transcription
│   │   ├── nlp.py       # NLP processing
│   │   └── embeddings.py # Vector generation
│   ├── workers/         # Background tasks
│   │   ├── tasks.py     # Celery tasks
│   │   └── schedules.py # Periodic tasks
│   └── utils/           # Utilities
├── tests/               # Test suites
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   └── e2e/           # End-to-end tests
├── alembic/            # Database migrations
├── docker/             # Docker configs
├── k8s/               # Kubernetes manifests
├── scripts/           # Utility scripts
└── docs/              # Documentation
```

## Development Guidelines

### Code Standards

```python
# Use type hints
def process_content(content: str, language: str = "en") -> ProcessedContent:
    """Process raw content with NLP.
    
    Args:
        content: Raw text content
        language: Content language code
        
    Returns:
        ProcessedContent with entities and embeddings
    """
    pass

# Handle errors gracefully
try:
    result = await scraper.fetch(url)
except RateLimitError:
    await backoff_retry(scraper.fetch, url)
except ScraperError as e:
    logger.error(f"Scraping failed: {e}")
    raise
```

### Testing Requirements
- Minimum 80% code coverage
- Unit tests for all business logic
- Integration tests for API endpoints
- Mock external services in tests
- Use pytest fixtures for test data

### Git Workflow
```bash
# Feature branch workflow
git checkout -b feature/TASK-XXX-description
# Make changes
git add .
git commit -m "feat: implement YouTube metadata extraction"
git push origin feature/TASK-XXX-description
# Create PR for review
```

## Common Tasks

### Running Tests
```bash
# All tests with coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/unit/test_youtube_scraper.py -v

# Only integration tests
pytest tests/integration/ -v

# With markers
pytest -m "not slow"
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint
ruff src/ tests/

# Type checking
mypy src/

# All checks
make lint
```

### Database Operations
```bash
# Create migration
alembic revision --autogenerate -m "Add user preferences"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### API Development
```bash
# Generate OpenAPI schema
python scripts/generate_openapi.py

# Test specific endpoint
curl -X POST http://localhost:8000/api/v1/content/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"source_type": "youtube", "source_id": "VIDEO_ID"}'
```

## Task Management

When working on tasks:
1. Check `lit_law411-agent_TASKS.md` for task details
2. Update task status when starting/completing
3. Reference task ID in commits: `git commit -m "feat(TASK-016): implement YouTube API client"`
4. Update acceptance criteria checkboxes as you progress

## Architecture Decisions

### Why Multiple Databases?
- **PostgreSQL (Supabase)**: ACID compliance for critical structured data
- **Pinecone**: Optimized for vector similarity search
- **Airtable**: Visual relationship management and categorization
- **Elasticsearch**: Powerful full-text search and aggregations
- **Redis**: Fast caching and reliable message broker

### Why FastAPI?
- High performance with async support
- Automatic OpenAPI documentation
- Built-in validation with Pydantic
- Easy GraphQL integration

### Why Celery?
- Distributed task processing
- Retry mechanisms built-in
- Scheduled task support
- Monitoring capabilities

## Performance Considerations

### API Response Times
- Target: < 500ms for 95% of requests
- Use Redis caching for frequent queries
- Implement pagination for large results
- Use database indexes appropriately

### Batch Processing
```python
# Process in batches to avoid memory issues
BATCH_SIZE = 100
for i in range(0, len(items), BATCH_SIZE):
    batch = items[i:i + BATCH_SIZE]
    await process_batch(batch)
```

### Rate Limiting
```python
# Respect API limits
@rate_limit(calls=100, period=timedelta(minutes=1))
async def fetch_youtube_data(video_id: str):
    pass
```

## Security Best Practices

### API Security
- Always use JWT tokens for authentication
- Implement rate limiting per user/IP
- Validate all inputs with Pydantic
- Use parameterized queries

### Secrets Management
```python
# Never hardcode secrets
api_key = settings.YOUTUBE_API_KEY  # From environment

# Rotate keys regularly
if key_age > timedelta(days=90):
    rotate_api_key()
```

## Monitoring & Debugging

### Logging
```python
import structlog
logger = structlog.get_logger()

logger.info("Processing content", 
    content_id=content.id,
    source=content.source,
    size=len(content.text))
```

### Metrics
```python
# Track key metrics
metrics.increment("content.processed")
metrics.histogram("processing.duration", duration)
```

### Health Checks
```bash
# Check system health
curl http://localhost:8000/health

# Check readiness
curl http://localhost:8000/ready
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```bash
   # Check PostgreSQL is running
   docker-compose ps
   # Check connection string
   echo $DATABASE_URL
   ```

2. **Celery Task Failures**
   ```bash
   # Check worker logs
   docker-compose logs celery-worker
   # Monitor queue
   celery -A src.workers inspect active
   ```

3. **API Rate Limits**
   ```python
   # Check remaining quota
   response.headers["X-RateLimit-Remaining"]
   ```

## Environment Variables Required

Create a `.env` file with:
```env
# Three-Database Strategy Configuration
# Airtable (Visual Interface Layer)
AIRTABLE_API_KEY=your_airtable_key
AIRTABLE_BASE_ID=your_airtable_base_id

# Supabase PostgreSQL (Relational Data Layer)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Pinecone (Vector Search Layer)
PINECONE_API_KEY=your_pinecone_key
PINECONE_ENVIRONMENT=your_pinecone_environment
PINECONE_INDEX_NAME=lit_law411

# APIs
YOUTUBE_API_KEY=your_youtube_api_key
OPENAI_API_KEY=your_openai_key

# Cache & Queue
REDIS_URL=redis://localhost:6379

# Sync Settings
SYNC_BATCH_SIZE=10
SYNC_MAX_RETRIES=5
SYNC_RETRY_DELAY=1
CONSISTENCY_CHECK_ENABLED=true
CONSISTENCY_TOLERANCE_SECONDS=5
```

## Data Storage Strategy (Three-Database Architecture)

This project implements a standardized three-database architecture as defined in `THREE_DATABASE_STRATEGY.md`. All data operations must synchronize across these three databases:

### 1. Airtable (Visual Interface Layer)
**Purpose**: Human-friendly visual database for browsing and management
- Visual browsing of records with filters and views
- Manual categorization and tagging by legal team
- Quick edits and annotations
- Linked records for relationship visualization
- Attachment previews and rich media display

### 2. Supabase PostgreSQL (Relational Data Layer)
**Purpose**: ACID-compliant relational database for data integrity
- Complex SQL queries and joins
- Transaction support for data consistency
- Full-text search with PostgreSQL
- Audit trails and change history
- Data validation and constraints
- Reporting and analytics

### 3. Pinecone (Vector Search Layer)
**Purpose**: AI-powered semantic search and similarity matching
- Semantic search across all content
- Finding similar documents
- AI-powered document retrieval using text-embedding-3-large
- Context-aware search results
- Namespace separation for different data types

### Data Synchronization Requirements
- **Write Operations**: Parallel writes to all three databases
- **Read Operations**: Select optimal database based on query type
- **Consistency**: 5-second sync tolerance with automatic verification
- **Error Handling**: Exponential backoff retry (max 5 attempts)
- **Reconciliation**: Daily consistency checks and repair

For detailed implementation requirements, see `THREE_DATABASE_STRATEGY.md`.

## Next Steps

Based on current project phase, focus on:

1. **Phase 1: Foundation**
   - Initialize Poetry project
   - Configure Docker Compose
   - Set up GitHub Actions CI/CD
   - Create database connections

2. **Phase 2: Core Features**
   - Implement YouTube ingestion
   - Build processing pipeline
   - Set up all three databases
   - Create search functionality

3. **Phase 3: Enhancement**
   - Add advanced NLP features
   - Build admin dashboard
   - Optimize performance

4. **Phase 4: Production Ready**
   - Security hardening
   - Load testing
   - Deployment setup

Remember to update task status in `lit_law411-agent_TASKS.md` as you progress!