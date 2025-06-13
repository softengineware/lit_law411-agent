# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

lit_law411-agent is an enterprise-grade Legal Knowledge Base Agent that automatically gathers, processes, and organizes legal knowledge from diverse sources including YouTube videos and legal websites. Built with modern microservices architecture, it creates a comprehensive, searchable knowledge base for the Law411 platform.

**IMPORTANT**: This agent is part of the LIT_MASTER-AGENT ecosystem, serving as one of four specialized sub-agents coordinated by the central lit_lawyer-agent (SUITS) system. It provides legal research and knowledge extraction capabilities to support litigation strategy and motion drafting.

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

## Agent Ecosystem Integration

This agent operates within the LIT_MASTER-AGENT ecosystem alongside three other specialized agents:

### Ecosystem Architecture
```
LIT_MASTER-AGENT (SUITS) - Central Coordinator
├── lit_audio-agent (SUITS-AUDIO) ✅ Ready - Transcription & Audio Processing
├── lit_rules-agent (LAW-INSIGHT) ✅ Ready - Legal Rules & Motion Templates  
├── lit_email-agent 🚧 Development - Email Intelligence & Correspondence
└── lit_law411-agent (THIS AGENT) ❌ Core Development Required
```

### Integration Status: **DEVELOPMENT PHASE - NOT READY FOR INTEGRATION**

**Current Capability**: Health monitoring and infrastructure only
**Required Development**: Core functionality implementation needed before integration

### Integration Requirements

#### Phase 1: Core Functionality Implementation (CRITICAL - 2-3 months)
1. **YouTube Data API Integration**
   - Video metadata extraction and audio download
   - Integration with Whisper transcription pipeline
   - Content quality validation and filtering

2. **Web Scraping Infrastructure** 
   - Scrapy spiders for legal websites and RSS feeds
   - Content extraction and legal relevance scoring
   - Rate limiting and politeness policies

3. **NLP Processing Pipeline**
   - Whisper audio transcription processing
   - spaCy legal entity recognition (cases, statutes, courts)
   - OpenAI embedding generation for semantic search

4. **Three-Database Storage Operations**
   - Complete Airtable, Supabase, and Pinecone client implementations
   - Sync operations with consistency checking
   - Data persistence for all content types

#### Phase 2: Integration-Ready Features (4-6 months)
1. **Legal Research API**
   - Semantic search across YouTube and web content
   - Entity extraction (cases, statutes, parties, courts)
   - Legal topic classification and relevance scoring

2. **LIT_MASTER-AGENT Coordination**
   - Service discovery and health reporting
   - Shared authentication (OAuth2/JWT) 
   - Event-driven updates and coordination
   - Resource management (API rate limiting)

### Integration Challenges
1. **Resource Intensive**: GPU/CPU for transcription, API costs for embeddings
2. **Rate Limiting**: YouTube Data API, OpenAI embeddings, web scraping
3. **Data Quality**: External content validation and legal accuracy verification
4. **Storage Coordination**: Three-database consistency across agent ecosystem

### Temporary Integration Strategy
Currently, LIT_MASTER-AGENT can only use basic health monitoring:
```python
# Limited current integration capability
class Law411Service:
    async def check_service_health(self) -> ServiceStatus:
        return await self.status_client.get_health()
    
    # NOTE: Core legal knowledge functions not available yet
```

### Future Full Integration (Post-Development)
```python
# Target integration after core development
class Law411Service:
    async def extract_legal_entities(self, text: str) -> List[LegalEntity]:
        # Extract cases, statutes, courts, parties, etc.
        
    async def search_legal_knowledge(self, query: str) -> List[LegalContent]:
        # Semantic search across YouTube and web content
        
    async def get_case_insights(self, case_citation: str) -> CaseAnalysis:
        # Deep analysis of legal cases and precedents
        
    async def find_supporting_content(self, legal_issue: str) -> List[SupportingEvidence]:
        # Find relevant YouTube videos and articles for legal arguments
```

## Development Priorities for LIT_MASTER-AGENT Integration

### Immediate (0-2 weeks)
- Use health check endpoints for service monitoring
- Plan integration architecture for future capabilities

### Short-term (2-8 weeks) 
- Begin core YouTube API and transcription implementation
- Implement basic storage operations

### Medium-term (2-6 months)
- Complete NLP pipeline and search functionality
- Begin integration testing with LIT_MASTER-AGENT

### Long-term (6+ months)
- Full legal knowledge extraction and research capabilities
- Production-ready integration with complete agent ecosystem

## Next Steps

**CRITICAL**: This agent requires substantial core development before integration with LIT_MASTER-AGENT ecosystem.

### Current Phase: **CORE DEVELOPMENT REQUIRED**

1. **Immediate Development Focus**
   - Implement YouTube Data API integration
   - Build web scraping infrastructure
   - Complete three-database storage operations
   - Integrate Whisper transcription pipeline

2. **Integration Preparation**
   - Service discovery and health reporting
   - Authentication coordination with other agents
   - Event-driven update mechanisms
   - Rate limiting coordination

3. **Quality Assurance**
   - Legal content validation systems
   - Performance optimization
   - Error handling and recovery
   - Integration testing

Remember: LIT_MASTER-AGENT integration timeline depends on completion of core functionality implementation!