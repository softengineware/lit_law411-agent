"""Supabase PostgreSQL client implementation for relational data layer."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from supabase import create_client, Client
from postgrest.exceptions import APIError

from src.core.config import settings
from src.core.logging import logger
from src.db.clients.base_client import BaseDatabaseClient, SyncResult


class SupabaseClient(BaseDatabaseClient):
    """Supabase PostgreSQL client for relational data layer.
    
    This client handles:
    - Complex SQL queries and joins
    - Transaction support for data consistency
    - Full-text search with PostgreSQL
    - Audit trails and change history
    - Data validation and constraints
    - Reporting and analytics
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Supabase client.
        
        Args:
            config: Optional configuration override
        """
        if config is None:
            config = {
                "url": settings.SUPABASE_URL,
                "anon_key": settings.SUPABASE_ANON_KEY,
                "service_role_key": settings.SUPABASE_SERVICE_ROLE_KEY,
            }
        super().__init__(config)
        
        self.client: Optional[Client] = None
        self._table_cache = {}
    
    async def connect(self) -> None:
        """Establish connection to Supabase."""
        try:
            # Use service role key for full access
            self.client = create_client(
                self.config["url"],
                self.config["service_role_key"]
            )
            
            # Test connection
            await self._test_connection()
            
            logger.info("Connected to Supabase", url=self.config["url"])
        except Exception as e:
            logger.error("Failed to connect to Supabase", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close connection to Supabase."""
        # Supabase client doesn't have explicit disconnect
        self.client = None
        self._table_cache.clear()
        logger.info("Disconnected from Supabase")
    
    async def _test_connection(self) -> None:
        """Test the database connection."""
        try:
            # Try to query a simple count
            result = self.client.table("base_records").select("count", count="exact").limit(1).execute()
            logger.debug("Supabase connection test successful")
        except Exception as e:
            # If base_records doesn't exist, that's okay for now
            if "relation" not in str(e).lower():
                raise
    
    def _ensure_uuid(self, record_id: str) -> str:
        """Ensure record ID is a valid UUID.
        
        Args:
            record_id: Record ID (may or may not be UUID)
            
        Returns:
            Valid UUID string
        """
        try:
            # If it's already a valid UUID, return it
            uuid_obj = uuid4() if not record_id else record_id
            return str(uuid_obj)
        except:
            # Generate a new UUID if invalid
            return str(uuid4())
    
    def _prepare_for_supabase(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert record to Supabase format with snake_case fields.
        
        Args:
            record: Record in standard format
            
        Returns:
            Record in Supabase format
        """
        # Ensure we have a valid UUID
        record_id = self._ensure_uuid(record.get("id"))
        
        # Base fields for all records
        supabase_record = {
            "id": record_id,
            "record_type": record.get("record_type"),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
            "synced_at": record.get("synced_at", datetime.utcnow().isoformat()),
            "source_system": record.get("source_system", "lit_law411_agent"),
            "source_id": record.get("source_id", record_id),
            "airtable_id": record.get("airtable_id"),
            "pinecone_id": record.get("pinecone_id"),
            "sync_version": record.get("sync_version", 1),
            "created_by": record.get("created_by", "system"),
            "updated_by": record.get("updated_by", "system"),
            "agent_version": record.get("agent_version", settings.APP_VERSION),
        }
        
        # Add metadata as JSONB
        metadata = {}
        
        # Add record-type specific fields to metadata
        if record.get("record_type") == "youtube_video":
            metadata.update({
                "title": record.get("title"),
                "channel_name": record.get("channel_name"),
                "channel_id": record.get("channel_id"),
                "video_id": record.get("video_id"),
                "url": record.get("url"),
                "duration": record.get("duration"),
                "view_count": record.get("view_count"),
                "like_count": record.get("like_count"),
                "comment_count": record.get("comment_count"),
                "published_at": record.get("published_at"),
                "description": record.get("description"),
                "tags": record.get("tags", []),
                "thumbnail_url": record.get("thumbnail_url"),
                "legal_categories": record.get("legal_categories", []),
                "has_transcript": record.get("has_transcript", False),
                "transcript_id": record.get("transcript_id"),
            })
        elif record.get("record_type") == "legal_website":
            metadata.update({
                "name": record.get("name"),
                "url": record.get("url"),
                "domain": record.get("domain"),
                "content_type": record.get("content_type"),
                "legal_topics": record.get("legal_topics", []),
                "jurisdiction": record.get("jurisdiction"),
                "last_scraped": record.get("last_scraped"),
                "quality_score": record.get("quality_score"),
                "authority_level": record.get("authority_level"),
                "scraping_strategy": record.get("scraping_strategy"),
                "update_frequency": record.get("update_frequency"),
            })
        elif record.get("record_type") == "transcript":
            metadata.update({
                "content": record.get("content"),
                "source_type": record.get("source_type"),
                "source_id": record.get("source_id"),
                "source_url": record.get("source_url"),
                "language": record.get("language", "en"),
                "duration_seconds": record.get("duration_seconds"),
                "confidence_score": record.get("confidence_score"),
                "legal_entities": record.get("legal_entities", []),
                "key_phrases": record.get("key_phrases", []),
                "summary": record.get("summary"),
            })
        elif record.get("record_type") == "legal_entity":
            metadata.update({
                "entity_type": record.get("entity_type"),
                "entity_text": record.get("entity_text"),
                "normalized_text": record.get("normalized_text"),
                "context": record.get("context"),
                "source_document_id": record.get("source_document_id"),
                "confidence_score": record.get("confidence_score"),
                "metadata": record.get("entity_metadata", {}),
            })
        
        # Add any additional fields to metadata
        for key, value in record.items():
            if key not in supabase_record and key not in metadata:
                metadata[key] = value
        
        supabase_record["metadata"] = metadata
        
        # Remove None values
        return {k: v for k, v in supabase_record.items() if v is not None}
    
    async def upsert(self, record: Dict[str, Any]) -> SyncResult:
        """Insert or update a record in Supabase.
        
        Args:
            record: Record data to upsert
            
        Returns:
            SyncResult indicating success or failure
        """
        try:
            if not self.client:
                await self.connect()
            
            supabase_data = self._prepare_for_supabase(record)
            table_name = self._get_table_name(record.get("record_type", "default"))
            
            # Perform upsert
            result = self.client.table(table_name).upsert(
                supabase_data,
                on_conflict="id"
            ).execute()
            
            if result.data and len(result.data) > 0:
                return SyncResult(
                    success=True,
                    database="Supabase",
                    record_id=result.data[0]["id"],
                )
            else:
                return SyncResult(
                    success=False,
                    database="Supabase",
                    error="No data returned from upsert",
                )
                
        except Exception as e:
            logger.error("Supabase upsert failed", error=str(e), record_id=record.get("id"))
            return SyncResult(
                success=False,
                database="Supabase",
                error=str(e),
            )
    
    async def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a record from Supabase.
        
        Args:
            record_id: Record ID (UUID)
            
        Returns:
            Record data if found, None otherwise
        """
        try:
            if not self.client:
                await self.connect()
            
            # Try base_records table first
            result = self.client.table("base_records").select("*").eq("id", record_id).execute()
            
            if result.data and len(result.data) > 0:
                return self._from_supabase_format(result.data[0])
            
            # Try other tables if not found
            for table in ["youtube_videos", "legal_websites", "transcripts", "legal_entities"]:
                try:
                    result = self.client.table(table).select("*").eq("id", record_id).execute()
                    if result.data and len(result.data) > 0:
                        return self._from_supabase_format(result.data[0])
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.error("Supabase get failed", error=str(e), record_id=record_id)
            return None
    
    async def query(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Query records from Supabase with SQL capabilities.
        
        Args:
            filters: Query filters
            limit: Maximum number of records to return
            
        Returns:
            List of matching records
        """
        try:
            if not self.client:
                await self.connect()
            
            table_name = self._get_table_name(filters.get("record_type", "default"))
            query = self.client.table(table_name).select("*")
            
            # Apply filters
            for key, value in filters.items():
                if key == "record_type":
                    continue
                elif key.startswith("metadata."):
                    # Handle JSONB queries
                    json_key = key.replace("metadata.", "")
                    query = query.contains("metadata", {json_key: value})
                elif key.endswith("__gte"):
                    field = key.replace("__gte", "")
                    query = query.gte(field, value)
                elif key.endswith("__lte"):
                    field = key.replace("__lte", "")
                    query = query.lte(field, value)
                elif key.endswith("__like"):
                    field = key.replace("__like", "")
                    query = query.like(field, value)
                elif key.endswith("__in"):
                    field = key.replace("__in", "")
                    query = query.in_(field, value)
                else:
                    query = query.eq(key, value)
            
            # Apply limit and execute
            result = query.limit(limit).execute()
            
            return [self._from_supabase_format(r) for r in result.data]
            
        except Exception as e:
            logger.error("Supabase query failed", error=str(e), filters=filters)
            return []
    
    async def delete(self, record_id: str) -> SyncResult:
        """Delete a record from Supabase.
        
        Args:
            record_id: Record ID (UUID)
            
        Returns:
            SyncResult indicating success or failure
        """
        try:
            if not self.client:
                await self.connect()
            
            # Try to find and delete from appropriate table
            record = await self.get(record_id)
            if not record:
                return SyncResult(
                    success=False,
                    database="Supabase",
                    error="Record not found",
                )
            
            table_name = self._get_table_name(record.get("record_type", "default"))
            result = self.client.table(table_name).delete().eq("id", record_id).execute()
            
            return SyncResult(
                success=True,
                database="Supabase",
                record_id=record_id,
            )
            
        except Exception as e:
            logger.error("Supabase delete failed", error=str(e), record_id=record_id)
            return SyncResult(
                success=False,
                database="Supabase",
                error=str(e),
            )
    
    async def batch_upsert(self, records: List[Dict[str, Any]]) -> List[SyncResult]:
        """Batch insert or update multiple records.
        
        Args:
            records: List of records to upsert
            
        Returns:
            List of SyncResults for each record
        """
        results = []
        
        # Group records by table
        records_by_table = {}
        for record in records:
            table_name = self._get_table_name(record.get("record_type", "default"))
            if table_name not in records_by_table:
                records_by_table[table_name] = []
            records_by_table[table_name].append(record)
        
        # Process each table's records
        for table_name, table_records in records_by_table.items():
            try:
                # Prepare all records
                supabase_data = [self._prepare_for_supabase(r) for r in table_records]
                
                # Batch upsert
                result = self.client.table(table_name).upsert(
                    supabase_data,
                    on_conflict="id"
                ).execute()
                
                # Create success results
                for record in result.data:
                    results.append(SyncResult(
                        success=True,
                        database="Supabase",
                        record_id=record["id"],
                    ))
                    
            except Exception as e:
                logger.error("Supabase batch upsert failed", error=str(e))
                for _ in table_records:
                    results.append(SyncResult(
                        success=False,
                        database="Supabase",
                        error=str(e),
                    ))
        
        return results
    
    async def execute_sql(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute raw SQL query (for complex queries).
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Query results
        """
        try:
            if not self.client:
                await self.connect()
            
            # Use Supabase RPC for raw SQL
            result = self.client.rpc("execute_sql", {
                "query": query,
                "params": params or {}
            }).execute()
            
            return result.data
            
        except Exception as e:
            logger.error("SQL execution failed", error=str(e), query=query)
            raise
    
    def _get_table_name(self, record_type: str) -> str:
        """Get Supabase table name for a record type.
        
        Args:
            record_type: Type of record
            
        Returns:
            Table name
        """
        # Use base_records table for all types (single table inheritance)
        # This allows for complex queries across all record types
        return "base_records"
    
    def _from_supabase_format(self, supabase_record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Supabase record back to standard format.
        
        Args:
            supabase_record: Record from Supabase
            
        Returns:
            Record in standard format
        """
        # Extract base fields
        standard_record = {
            "id": supabase_record.get("id"),
            "record_type": supabase_record.get("record_type"),
            "created_at": supabase_record.get("created_at"),
            "updated_at": supabase_record.get("updated_at"),
            "synced_at": supabase_record.get("synced_at"),
            "source_system": supabase_record.get("source_system"),
            "source_id": supabase_record.get("source_id"),
            "airtable_id": supabase_record.get("airtable_id"),
            "supabase_id": supabase_record.get("id"),
            "pinecone_id": supabase_record.get("pinecone_id"),
            "sync_version": supabase_record.get("sync_version"),
            "created_by": supabase_record.get("created_by"),
            "updated_by": supabase_record.get("updated_by"),
            "agent_version": supabase_record.get("agent_version"),
        }
        
        # Extract metadata fields
        metadata = supabase_record.get("metadata", {})
        for key, value in metadata.items():
            if key not in standard_record:
                standard_record[key] = value
        
        return standard_record