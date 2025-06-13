# Three-Database Strategy for Multi-Agent System

## Overview

This document defines the standardized three-database architecture used across all agents in the litigation support ecosystem. Each agent MUST implement this exact pattern to ensure data consistency and interoperability.

## The Three Databases

### 1. Airtable - Visual Interface Layer
**Purpose**: Human-friendly visual database for browsing, filtering, and manual data management

**Use Cases**:
- Visual browsing of records with filters and views
- Manual categorization and tagging by legal team
- Quick edits and annotations
- Linked records for relationship visualization
- Attachment previews and rich media display

**Implementation Requirements**:
- Use pyairtable client library
- Implement auto-field creation for schema flexibility
- Batch operations for performance (max 10 records per request)
- Maintain linked record relationships
- Use Airtable formulas for computed fields

### 2. Supabase PostgreSQL - Relational Data Layer
**Purpose**: ACID-compliant relational database for complex queries, data integrity, and audit trails

**Use Cases**:
- Complex SQL queries and joins
- Transaction support for data consistency
- Full-text search with PostgreSQL
- Audit trails and change history
- Data validation and constraints
- Reporting and analytics

**Implementation Requirements**:
- Use supabase-py client library
- Implement proper indexes for query performance
- Use database triggers for audit logging
- Maintain referential integrity
- Support for JSON columns for flexible metadata

### 3. Pinecone - Vector Search Layer
**Purpose**: AI-powered semantic search and similarity matching

**Use Cases**:
- Semantic search across all content
- Finding similar documents
- AI-powered document retrieval
- Context-aware search results
- Multi-modal embeddings (text, potentially images)

**Implementation Requirements**:
- Use pinecone-client library
- OpenAI text-embedding-3-large for embeddings
- Store rich metadata with each vector
- Implement namespace separation for different data types
- Hybrid search combining metadata filters with vector similarity

## Data Synchronization Protocol

### Write Operations - Parallel Sync Pattern
```python
async def sync_to_all_databases(record: Dict[str, Any]) -> SyncResult:
    """
    All agents MUST use this pattern for writing data.
    Writes happen in parallel to all three databases.
    """
    # Prepare data for each database
    airtable_data = prepare_for_airtable(record)
    supabase_data = prepare_for_supabase(record)
    pinecone_data = prepare_for_pinecone(record)
    
    # Parallel writes
    results = await asyncio.gather(
        airtable_client.upsert(airtable_data),
        supabase_client.upsert(supabase_data),
        pinecone_client.upsert(pinecone_data),
        return_exceptions=True
    )
    
    # Verify consistency
    sync_result = verify_sync_consistency(results)
    if not sync_result.is_consistent:
        await handle_sync_failure(sync_result)
    
    return sync_result
```

### Read Operations - Database Selection
```python
def select_read_database(query_type: QueryType) -> DatabaseClient:
    """
    Choose the optimal database based on query type.
    """
    if query_type == QueryType.VISUAL_BROWSE:
        return airtable_client  # Best for UI operations
    elif query_type == QueryType.COMPLEX_QUERY:
        return supabase_client  # Best for SQL joins
    elif query_type == QueryType.SEMANTIC_SEARCH:
        return pinecone_client  # Best for AI search
    else:
        return supabase_client  # Default to most reliable
```

## Standard Data Models

### Base Record Schema
Every record across all agents MUST include these fields:

```python
@dataclass
class BaseRecord:
    # Identity
    id: str  # UUID format
    record_type: str  # email, document, hearing, etc.
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    synced_at: datetime
    
    # Tracking
    source_system: str  # Which agent created this
    source_id: str  # Original ID from source
    
    # Sync metadata
    airtable_id: Optional[str]
    supabase_id: Optional[str]
    pinecone_id: Optional[str]
    sync_version: int
    
    # Audit
    created_by: str
    updated_by: str
    agent_version: str
```

### Database-Specific Schemas

#### Airtable Schema Conventions
```python
# Field naming: Use human-readable names with spaces
{
    "Email Subject": "Re: Motion to Dismiss",
    "From Address": "opposing@counsel.com",
    "Received Date": "2024-01-15T10:30:00Z",
    "Has Attachments": True,
    "Related Hearing": ["rec123ABC"],  # Linked record
    "Status": {
        "label": "Processed",
        "color": "green"
    }
}
```

#### Supabase Schema Conventions
```sql
-- Use snake_case for all identifiers
CREATE TABLE base_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    source_system VARCHAR(100) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    airtable_id VARCHAR(50),
    pinecone_id VARCHAR(100),
    sync_version INTEGER DEFAULT 1,
    created_by VARCHAR(255) NOT NULL,
    updated_by VARCHAR(255) NOT NULL,
    agent_version VARCHAR(50) NOT NULL,
    metadata JSONB DEFAULT '{}',
    
    -- Indexes
    INDEX idx_record_type (record_type),
    INDEX idx_source (source_system, source_id),
    INDEX idx_sync (synced_at, sync_version),
    UNIQUE INDEX idx_unique_source (source_system, source_id)
);

-- Audit trigger
CREATE TRIGGER update_updated_at
    BEFORE UPDATE ON base_records
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

#### Pinecone Metadata Schema
```python
{
    "id": "email_123e4567-e89b-12d3-a456-426614174000",
    "values": [0.023, -0.445, 0.122, ...],  # 1536-dim embedding
    "metadata": {
        # Required fields
        "record_type": "email",
        "content_hash": "sha256:abcd1234...",
        "created_at": "2024-01-15T10:30:00Z",
        "source_system": "email_agent",
        
        # Searchable fields
        "title": "Re: Motion to Dismiss",
        "author": "opposing@counsel.com",
        "date": "2024-01-15",
        "tags": ["motion", "dismiss", "hearing"],
        
        # Reference fields
        "airtable_id": "recABC123",
        "supabase_id": "123e4567-e89b-12d3-a456-426614174000",
        
        # Content preview
        "text_preview": "First 200 chars of content...",
        "word_count": 1523,
        "language": "en"
    }
}
```

## Consistency Rules

### 1. ID Management
- Use UUIDs as primary identifiers
- Store cross-references to all database IDs
- Never rely on auto-increment IDs

### 2. Timestamp Handling
- Always use UTC timestamps
- Store as ISO 8601 strings in Airtable
- Use TIMESTAMPTZ in PostgreSQL
- Include as metadata in Pinecone

### 3. Data Type Mapping
| Data Type | Airtable | Supabase | Pinecone Metadata |
|-----------|----------|----------|-------------------|
| Text | Single/Long Text | VARCHAR/TEXT | string |
| Number | Number | INTEGER/DECIMAL | number |
| Boolean | Checkbox | BOOLEAN | boolean |
| Date | Date | TIMESTAMPTZ | string (ISO 8601) |
| Array | Linked Records | ARRAY/JSONB | array |
| JSON | Long Text | JSONB | object |

### 4. Sync Verification
```python
async def verify_sync_consistency(
    record_id: str,
    tolerance_seconds: int = 5
) -> ConsistencyReport:
    """
    Verify record exists and matches across all databases.
    """
    # Fetch from all databases
    records = await asyncio.gather(
        fetch_from_airtable(record_id),
        fetch_from_supabase(record_id),
        fetch_from_pinecone(record_id)
    )
    
    # Check existence
    if not all(records):
        return ConsistencyReport(
            is_consistent=False,
            missing_from=identify_missing_databases(records)
        )
    
    # Check update timestamps
    timestamps = [r.updated_at for r in records]
    max_diff = max(timestamps) - min(timestamps)
    
    if max_diff.total_seconds() > tolerance_seconds:
        return ConsistencyReport(
            is_consistent=False,
            timestamp_mismatch=True,
            max_difference=max_diff
        )
    
    return ConsistencyReport(is_consistent=True)
```

## Error Handling

### Partial Sync Failures
```python
class SyncFailureHandler:
    """
    Standard handler for sync failures across agents.
    """
    
    async def handle_partial_sync(
        self,
        record: BaseRecord,
        results: List[Union[Success, Exception]]
    ):
        failed_dbs = self.identify_failed_databases(results)
        
        # Log failure
        await self.log_sync_failure(record, failed_dbs)
        
        # Add to retry queue
        await self.queue_for_retry(record, failed_dbs)
        
        # Alert if critical
        if self.is_critical_failure(failed_dbs):
            await self.send_alert(record, failed_dbs)
```

### Retry Strategy
- Exponential backoff: 1s, 2s, 4s, 8s, 16s
- Max retries: 5
- Dead letter queue after max retries
- Daily reconciliation job for failed syncs

## Configuration Template

All agents must use this configuration structure:

```python
# config/database.py
from pydantic import BaseSettings

class DatabaseConfig(BaseSettings):
    # Airtable
    AIRTABLE_API_KEY: str
    AIRTABLE_BASE_ID: str
    AIRTABLE_TIMEOUT: int = 30
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_TIMEOUT: int = 30
    
    # Pinecone
    PINECONE_API_KEY: str
    PINECONE_ENVIRONMENT: str
    PINECONE_INDEX_NAME: str
    PINECONE_TIMEOUT: int = 30
    
    # Sync settings
    SYNC_BATCH_SIZE: int = 10
    SYNC_MAX_RETRIES: int = 5
    SYNC_RETRY_DELAY: int = 1
    
    # Consistency checks
    CONSISTENCY_CHECK_ENABLED: bool = True
    CONSISTENCY_TOLERANCE_SECONDS: int = 5
    
    class Config:
        env_file = ".env"
```

## Integration Requirements

### For New Agents

1. **Import Base Classes**
```python
from shared.database import (
    ThreeDatabaseClient,
    BaseRecord,
    SyncResult,
    ConsistencyReport
)
```

2. **Initialize Clients**
```python
class YourAgent:
    def __init__(self):
        self.db = ThreeDatabaseClient(
            config=DatabaseConfig(),
            agent_name="your_agent_name"
        )
```

3. **Use Standard Methods**
```python
# Write to all databases
result = await self.db.sync_record(record)

# Read with optimal database selection
data = await self.db.read_optimal(
    query=query,
    query_type=QueryType.SEMANTIC_SEARCH
)

# Verify consistency
report = await self.db.verify_consistency(record_id)
```

## Monitoring & Metrics

All agents must expose these metrics:

1. **Sync Metrics**
   - `sync_success_total` - Counter of successful syncs
   - `sync_failure_total` - Counter by database
   - `sync_duration_seconds` - Histogram by database
   - `sync_lag_seconds` - Gauge of sync delay

2. **Consistency Metrics**
   - `consistency_check_total` - Counter
   - `consistency_failure_total` - Counter
   - `records_out_of_sync` - Gauge

3. **Database Health**
   - `database_up` - Gauge (0/1) by database
   - `database_latency_seconds` - Histogram by operation

## Best Practices

1. **Always Write to All Three**
   - Never skip a database unless it's down
   - Use parallel writes for performance
   - Implement proper retry logic

2. **Choose the Right Database for Reads**
   - Airtable: Visual operations, user edits
   - Supabase: Complex queries, reports
   - Pinecone: Semantic search, similarity

3. **Handle Eventual Consistency**
   - Design for 5-second sync tolerance
   - Implement read-after-write consistency where critical
   - Use Supabase as source of truth for conflicts

4. **Monitor Everything**
   - Set up alerts for sync failures
   - Dashboard for consistency metrics
   - Daily reconciliation reports

## Migration Guide

For existing single-database agents:

1. **Phase 1**: Add database clients
2. **Phase 2**: Implement parallel writes
3. **Phase 3**: Migrate historical data
4. **Phase 4**: Switch reads to optimal database
5. **Phase 5**: Decommission old system

## Support

For questions or issues with the three-database strategy:
- Review this document first
- Check the shared database library docs
- Contact the architecture team

Remember: Consistency and reliability are more important than performance. When in doubt, verify across all three databases.