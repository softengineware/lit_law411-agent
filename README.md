# lit_law411-agent

**Legal Knowledge Base Agent for Law411 Platform - Part of LIT_MASTER-AGENT Ecosystem**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI](https://github.com/softengineware/lit_law411-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/softengineware/lit_law411-agent/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/softengineware/lit_law411-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/softengineware/lit_law411-agent)

> ⚠️ **DEVELOPMENT STATUS**: Core functionality implementation required before LIT_MASTER-AGENT integration

## Overview

The lit_law411-agent is an intelligent system that automatically gathers, processes, and organizes legal knowledge from diverse sources including YouTube videos and legal websites. **This agent operates as one of four specialized sub-agents within the LIT_MASTER-AGENT ecosystem**, providing legal research and knowledge extraction capabilities to support litigation strategy and motion drafting.

### Agent Ecosystem Position

```
🏛️ LIT_MASTER-AGENT (SUITS) - Central Litigation Coordinator
├── 🎵 lit_audio-agent (SUITS-AUDIO) ✅ Production Ready
├── 📜 lit_rules-agent (LAW-INSIGHT) ✅ Integration Ready
├── 📧 lit_email-agent 🚧 Storage Development Phase
└── 🔍 lit_law411-agent (THIS AGENT) ❌ Core Development Required
```

Built for the Law411 platform, it creates a comprehensive, searchable knowledge base using a standardized three-database architecture (Airtable + Supabase PostgreSQL + Pinecone) for optimal functionality, enabling strategic retrieval of legal information for practitioners, researchers, and legal professionals.

## 🚨 Integration Status with LIT_MASTER-AGENT

| Component | Status | Integration Readiness |
|-----------|--------|--------------------|
| **Infrastructure** | ✅ Complete | Ready |
| **Database Models** | ✅ Complete | Ready |
| **API Framework** | ✅ Complete | Ready |
| **Authentication** | ✅ Complete | Ready |
| **Health Monitoring** | ✅ Complete | **INTEGRATION READY** |
| **YouTube API** | ❌ Not Implemented | **CRITICAL GAP** |
| **Web Scraping** | ❌ Not Implemented | **CRITICAL GAP** |
| **NLP Pipeline** | ❌ Not Implemented | **CRITICAL GAP** |
| **Storage Operations** | ❌ Placeholder Only | **CRITICAL GAP** |
| **Search Functionality** | ❌ Not Implemented | **CRITICAL GAP** |

### Current Integration Capability
- ✅ **Health Monitoring**: LIT_MASTER-AGENT can monitor service health
- ✅ **Service Discovery**: Ready for registration with main coordinator
- ❌ **Core Functions**: Legal knowledge extraction not yet operational

### Development Required Before Integration
1. **YouTube Data API Integration** (2-4 weeks)
2. **Web Scraping Infrastructure** (2-3 weeks)  
3. **NLP Processing Pipeline** (3-4 weeks)
4. **Storage Operations Implementation** (2-3 weeks)
5. **Search Functionality** (3-4 weeks)

**Estimated Time to Integration Readiness**: 3-6 months of active development

## Key Features

- **🎥 YouTube Integration**: Extract and transcribe legal content from YouTube videos
- **🌐 Web Scraping**: Gather legal information from trusted websites with compliance
- **🔍 Semantic Search**: Advanced vector-based search for finding relevant legal content
- **📊 NLP Processing**: Extract legal entities, citations, and analyze sentiment
- **🏛️ Jurisdiction Support**: Multi-jurisdictional content organization and filtering
- **🔒 Security First**: Enterprise-grade security with encryption and audit logging
- **📈 Scalable Architecture**: Horizontally scalable design supporting millions of documents

## Architecture

The system uses a modern microservices architecture with a three-database strategy:

### Three-Database Architecture
1. **Airtable** - Visual interface layer for human-friendly browsing and management
2. **Supabase PostgreSQL** - ACID-compliant relational database for data integrity
3. **Pinecone** - Vector database for AI-powered semantic search

### Additional Components
- **FastAPI** for high-performance REST/GraphQL APIs
- **Celery + Redis** for distributed task processing and caching
- **Docker/Kubernetes** for containerization and orchestration
- **OpenAI text-embedding-3-large** for generating embeddings

See [THREE_DATABASE_STRATEGY.md](THREE_DATABASE_STRATEGY.md) for detailed implementation requirements.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- Elasticsearch 8.11+
- API Keys:
  - YouTube Data API v3
  - Supabase
  - Pinecone
  - Airtable
  - OpenAI (for Whisper transcription)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/softengineware/lit_law411-agent.git
cd lit_law411-agent
```

### 2. Set Up Environment

Create a `.env` file based on the example:

```bash
cp .env.example .env
```

Configure your API keys in `.env`:

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
CONSISTENCY_CHECK_ENABLED=true
```

### 3. Install Dependencies

Using Poetry (recommended):

```bash
poetry install
poetry shell
```

Or using pip:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Start Development Environment

```bash
# Start all services with Docker Compose
docker-compose up -d

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn src.main:app --reload --port 8000
```

### 5. Run Workers

In a separate terminal:

```bash
# Start Celery worker
celery -A src.workers worker --loglevel=info

# Start Celery beat (for scheduled tasks)
celery -A src.workers beat --loglevel=info
```

## Usage

### API Documentation

Once running, access the interactive API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- GraphQL Playground: http://localhost:8000/graphql

### Basic Operations

#### 1. Ingest YouTube Video

```bash
curl -X POST "http://localhost:8000/api/v1/content/ingest" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "youtube",
    "source_id": "VIDEO_ID"
  }'
```

#### 2. Search Legal Content

```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "contract breach remedies",
    "jurisdiction": "US",
    "limit": 10
  }'
```

#### 3. Extract Legal Entities

```bash
curl -X POST "http://localhost:8000/api/v1/entities/extract" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "In Smith v. Jones, 123 F.3d 456 (9th Cir. 2023)..."
  }'
```

## Development

### Project Structure

```
lit_law411-agent/
├── src/
│   ├── api/           # FastAPI routes and endpoints
│   ├── core/          # Core business logic
│   ├── models/        # Pydantic and SQLAlchemy models
│   ├── db/            # Database clients and repositories
│   ├── scrapers/      # YouTube and web scrapers
│   ├── processors/    # NLP and transcription services
│   └── workers/       # Celery background tasks
├── tests/             # Test suites
├── docs/              # Documentation
├── scripts/           # Utility scripts
└── docker/            # Docker configurations
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_scrapers.py

# Run tests in parallel
pytest -n auto
```

### Code Quality

The project uses several tools to maintain code quality:

```bash
# Format code with Black
black src/ tests/

# Lint with Ruff
ruff src/ tests/

# Type check with mypy
mypy src/

# Run all checks
make lint
```

### Pre-commit Hooks

Install pre-commit hooks to ensure code quality:

```bash
pre-commit install
```

## Docker Development Environment

The project includes a complete Docker setup for local development:

### Starting the Development Environment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

### Available Services

- **PostgreSQL**: Main database (port 5432)
- **Redis**: Cache and message broker (port 6379)
- **Elasticsearch**: Full-text search (port 9200)
- **Kibana**: Elasticsearch UI (port 5601) - development only
- **Flower**: Celery monitoring (port 5555) - development only
- **Application**: FastAPI server (port 8000)
- **Celery Worker**: Background task processor
- **Celery Beat**: Scheduled task runner

### Development Tips

1. **Hot Reload**: The application automatically reloads when you change code
2. **Database Access**:

   ```bash
   docker-compose exec postgres psql -U lit_law411
   ```

3. **Redis CLI**:

   ```bash
   docker-compose exec redis redis-cli
   ```

4. **View Celery Tasks**:
   - Open <http://localhost:5555> for Flower UI
5. **Elasticsearch Queries**:
   - Use Kibana at <http://localhost:5601>

### Troubleshooting Docker

If services fail to start:

```bash
# Check service status
docker-compose ps

# View detailed logs
docker-compose logs [service-name]

# Rebuild images after dependency changes
docker-compose build --no-cache

# Reset everything
docker-compose down -v
docker-compose up -d
```

## Deployment

### Production Deployment

1. Build Docker image:

   ```bash
   docker build -t lit_law411-agent:latest .
   ```

2. Deploy to Kubernetes:

   ```bash
   kubectl apply -f k8s/
   ```

3. Configure monitoring:

   ```bash
   kubectl apply -f k8s/monitoring/
   ```

See [deployment guide](docs/deployment.md) for detailed instructions.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key | Required |
| `OPENAI_API_KEY` | OpenAI API key for Whisper | Required |
| `LOG_LEVEL` | Logging level | `INFO` |
| `WORKERS` | Number of worker processes | `4` |

### API Rate Limits

Default rate limits:

- Anonymous: 10 requests/minute
- Authenticated: 100 requests/minute
- Premium: 1000 requests/minute

Configure in `config/settings.py`.

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📧 Email: <support@law411.com>
- 🐛 Issues: [GitHub Issues](https://github.com/softengineware/lit_law411-agent/issues)
- 📖 Documentation: [Full Documentation](https://docs.law411.com)

## Acknowledgments

- OpenAI for Whisper transcription
- spaCy for NLP processing
- The open-source community for amazing tools

## Roadmap

- [ ] Multi-language support (Spanish, French)
- [ ] Mobile applications
- [ ] Browser extension
- [ ] Legal document generation
- [ ] Predictive analytics

---

Built with ❤️ for the legal community by the Law411 team
