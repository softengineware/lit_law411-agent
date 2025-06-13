"""Base database client interface for three-database architecture."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar
from uuid import UUID

T = TypeVar("T")


@dataclass
class SyncResult:
    """Result of a database sync operation."""
    
    success: bool
    database: str
    record_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class BaseRecord:
    """Base record schema that all records must include."""
    
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
    airtable_id: Optional[str] = None
    supabase_id: Optional[str] = None
    pinecone_id: Optional[str] = None
    sync_version: int = 1
    
    # Audit
    created_by: str
    updated_by: str
    agent_version: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {
            "id": self.id,
            "record_type": self.record_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "synced_at": self.synced_at.isoformat(),
            "source_system": self.source_system,
            "source_id": self.source_id,
            "airtable_id": self.airtable_id,
            "supabase_id": self.supabase_id,
            "pinecone_id": self.pinecone_id,
            "sync_version": self.sync_version,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "agent_version": self.agent_version,
        }


class BaseDatabaseClient(ABC):
    """Abstract base class for database clients."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the database client.
        
        Args:
            config: Configuration dictionary with connection details
        """
        self.config = config
        self.database_name = self.__class__.__name__.replace("Client", "")
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the database."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the database."""
        pass
    
    @abstractmethod
    async def upsert(self, record: Dict[str, Any]) -> SyncResult:
        """Insert or update a record.
        
        Args:
            record: Record data to upsert
            
        Returns:
            SyncResult indicating success or failure
        """
        pass
    
    @abstractmethod
    async def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a record by ID.
        
        Args:
            record_id: ID of the record to retrieve
            
        Returns:
            Record data if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def query(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Query records with filters.
        
        Args:
            filters: Query filters
            limit: Maximum number of records to return
            
        Returns:
            List of matching records
        """
        pass
    
    @abstractmethod
    async def delete(self, record_id: str) -> SyncResult:
        """Delete a record.
        
        Args:
            record_id: ID of the record to delete
            
        Returns:
            SyncResult indicating success or failure
        """
        pass
    
    @abstractmethod
    async def batch_upsert(self, records: List[Dict[str, Any]]) -> List[SyncResult]:
        """Batch insert or update multiple records.
        
        Args:
            records: List of records to upsert
            
        Returns:
            List of SyncResults for each record
        """
        pass
    
    async def health_check(self) -> bool:
        """Check if the database connection is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            await self.connect()
            await self.disconnect()
            return True
        except Exception:
            return False
    
    def prepare_record(self, record: BaseRecord) -> Dict[str, Any]:
        """Prepare a record for database-specific storage.
        
        Args:
            record: BaseRecord to prepare
            
        Returns:
            Dictionary ready for database storage
        """
        # Default implementation - can be overridden by subclasses
        return record.to_dict()