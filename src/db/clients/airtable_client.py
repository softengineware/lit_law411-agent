"""Airtable client implementation for visual interface layer."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from pyairtable import Api, Base, Table
from pyairtable.formulas import match

from src.core.config import settings
from src.core.logging import logger
from src.db.clients.base_client import BaseDatabaseClient, SyncResult


class AirtableClient(BaseDatabaseClient):
    """Airtable database client for visual interface layer.
    
    This client handles:
    - Visual browsing of records with filters and views
    - Manual categorization and tagging
    - Linked records for relationship visualization
    - Attachment previews and rich media display
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Airtable client.
        
        Args:
            config: Optional configuration override
        """
        if config is None:
            config = {
                "api_key": settings.AIRTABLE_API_KEY,
                "base_id": settings.AIRTABLE_BASE_ID,
            }
        super().__init__(config)
        
        self.api = None
        self.base = None
        self._tables = {}
    
    async def connect(self) -> None:
        """Establish connection to Airtable."""
        try:
            self.api = Api(self.config["api_key"])
            self.base = Base(self.api, self.config["base_id"])
            logger.info("Connected to Airtable", base_id=self.config["base_id"])
        except Exception as e:
            logger.error("Failed to connect to Airtable", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close connection to Airtable."""
        # Airtable uses REST API, no persistent connection to close
        self.api = None
        self.base = None
        self._tables.clear()
        logger.info("Disconnected from Airtable")
    
    def _get_table(self, table_name: str) -> Table:
        """Get or create a table reference.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table object
        """
        if table_name not in self._tables:
            self._tables[table_name] = self.base.table(table_name)
        return self._tables[table_name]
    
    def _prepare_for_airtable(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert record to Airtable format with human-readable field names.
        
        Args:
            record: Record in standard format
            
        Returns:
            Record in Airtable format
        """
        # Map standard fields to human-readable Airtable fields
        airtable_record = {
            "Record ID": record.get("id"),
            "Record Type": record.get("record_type"),
            "Created At": record.get("created_at"),
            "Updated At": record.get("updated_at"),
            "Synced At": record.get("synced_at"),
            "Source System": record.get("source_system"),
            "Source ID": record.get("source_id"),
            "Sync Version": record.get("sync_version"),
            "Created By": record.get("created_by"),
            "Updated By": record.get("updated_by"),
            "Agent Version": record.get("agent_version"),
        }
        
        # Add record-type specific fields
        if record.get("record_type") == "youtube_video":
            airtable_record.update({
                "Video Title": record.get("title"),
                "Channel Name": record.get("channel_name"),
                "Video URL": record.get("url"),
                "Duration": record.get("duration"),
                "View Count": record.get("view_count"),
                "Published Date": record.get("published_at"),
                "Description": record.get("description"),
                "Tags": ", ".join(record.get("tags", [])),
                "Thumbnail": [{"url": record.get("thumbnail_url")}] if record.get("thumbnail_url") else None,
                "Legal Categories": record.get("legal_categories", []),
                "Transcript Available": record.get("has_transcript", False),
            })
        elif record.get("record_type") == "legal_website":
            airtable_record.update({
                "Website Name": record.get("name"),
                "Website URL": record.get("url"),
                "Content Type": record.get("content_type"),
                "Legal Topics": record.get("legal_topics", []),
                "Jurisdiction": record.get("jurisdiction"),
                "Last Scraped": record.get("last_scraped"),
                "Quality Score": record.get("quality_score"),
                "Authority Level": record.get("authority_level"),
            })
        elif record.get("record_type") == "transcript":
            airtable_record.update({
                "Content": record.get("content"),
                "Source Type": record.get("source_type"),
                "Source URL": record.get("source_url"),
                "Language": record.get("language"),
                "Duration Seconds": record.get("duration_seconds"),
                "Word Count": len(record.get("content", "").split()),
                "Confidence Score": record.get("confidence_score"),
                "Legal Entities": record.get("legal_entities", []),
            })
        
        # Add any additional metadata
        if "metadata" in record:
            airtable_record["Metadata"] = str(record["metadata"])
        
        # Remove None values (Airtable doesn't like them)
        return {k: v for k, v in airtable_record.items() if v is not None}
    
    async def upsert(self, record: Dict[str, Any]) -> SyncResult:
        """Insert or update a record in Airtable.
        
        Args:
            record: Record data to upsert
            
        Returns:
            SyncResult indicating success or failure
        """
        try:
            table_name = self._get_table_name(record.get("record_type", "default"))
            table = self._get_table(table_name)
            
            airtable_data = self._prepare_for_airtable(record)
            
            # Check if record exists
            existing = None
            if record.get("airtable_id"):
                try:
                    existing = table.get(record["airtable_id"])
                except:
                    pass
            
            if not existing and record.get("id"):
                # Search by Record ID
                formula = match({"Record ID": record["id"]})
                results = table.all(formula=formula)
                if results:
                    existing = results[0]
            
            if existing:
                # Update existing record
                updated = table.update(existing["id"], airtable_data)
                return SyncResult(
                    success=True,
                    database="Airtable",
                    record_id=updated["id"],
                )
            else:
                # Create new record
                created = table.create(airtable_data)
                return SyncResult(
                    success=True,
                    database="Airtable",
                    record_id=created["id"],
                )
                
        except Exception as e:
            logger.error("Airtable upsert failed", error=str(e), record_id=record.get("id"))
            return SyncResult(
                success=False,
                database="Airtable",
                error=str(e),
            )
    
    async def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a record from Airtable.
        
        Args:
            record_id: Airtable record ID
            
        Returns:
            Record data if found, None otherwise
        """
        try:
            # Try all tables
            for table_name in ["youtube_videos", "legal_websites", "transcripts", "default"]:
                table = self._get_table(table_name)
                try:
                    record = table.get(record_id)
                    if record:
                        return self._from_airtable_format(record)
                except:
                    continue
            return None
        except Exception as e:
            logger.error("Airtable get failed", error=str(e), record_id=record_id)
            return None
    
    async def query(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Query records from Airtable.
        
        Args:
            filters: Query filters
            limit: Maximum number of records to return
            
        Returns:
            List of matching records
        """
        try:
            table_name = self._get_table_name(filters.get("record_type", "default"))
            table = self._get_table(table_name)
            
            # Build Airtable formula from filters
            formula_parts = []
            for key, value in filters.items():
                if key != "record_type":
                    airtable_key = self._to_airtable_field_name(key)
                    formula_parts.append(f"{{{airtable_key}}} = '{value}'")
            
            formula = None
            if formula_parts:
                formula = "AND(" + ", ".join(formula_parts) + ")"
            
            records = table.all(formula=formula, max_records=limit)
            return [self._from_airtable_format(r) for r in records]
            
        except Exception as e:
            logger.error("Airtable query failed", error=str(e), filters=filters)
            return []
    
    async def delete(self, record_id: str) -> SyncResult:
        """Delete a record from Airtable.
        
        Args:
            record_id: Airtable record ID
            
        Returns:
            SyncResult indicating success or failure
        """
        try:
            # Try all tables
            for table_name in ["youtube_videos", "legal_websites", "transcripts", "default"]:
                table = self._get_table(table_name)
                try:
                    table.delete(record_id)
                    return SyncResult(
                        success=True,
                        database="Airtable",
                        record_id=record_id,
                    )
                except:
                    continue
                    
            return SyncResult(
                success=False,
                database="Airtable",
                error="Record not found",
            )
            
        except Exception as e:
            logger.error("Airtable delete failed", error=str(e), record_id=record_id)
            return SyncResult(
                success=False,
                database="Airtable",
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
        
        # Process each table's records in batches of 10 (Airtable limit)
        for table_name, table_records in records_by_table.items():
            table = self._get_table(table_name)
            
            for i in range(0, len(table_records), 10):
                batch = table_records[i:i + 10]
                batch_data = [self._prepare_for_airtable(r) for r in batch]
                
                try:
                    # Airtable batch create
                    created = table.batch_create(batch_data)
                    for record in created:
                        results.append(SyncResult(
                            success=True,
                            database="Airtable",
                            record_id=record["id"],
                        ))
                except Exception as e:
                    logger.error("Airtable batch upsert failed", error=str(e))
                    for _ in batch:
                        results.append(SyncResult(
                            success=False,
                            database="Airtable",
                            error=str(e),
                        ))
        
        return results
    
    def _get_table_name(self, record_type: str) -> str:
        """Get Airtable table name for a record type.
        
        Args:
            record_type: Type of record
            
        Returns:
            Table name
        """
        table_mapping = {
            "youtube_video": "YouTube Videos",
            "legal_website": "Legal Websites",
            "transcript": "Transcripts",
            "legal_entity": "Legal Entities",
            "search_query": "Search Queries",
        }
        return table_mapping.get(record_type, "Records")
    
    def _to_airtable_field_name(self, field: str) -> str:
        """Convert snake_case field to Airtable human-readable format.
        
        Args:
            field: Field name in snake_case
            
        Returns:
            Human-readable field name
        """
        return field.replace("_", " ").title()
    
    def _from_airtable_format(self, airtable_record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Airtable record back to standard format.
        
        Args:
            airtable_record: Record from Airtable
            
        Returns:
            Record in standard format
        """
        fields = airtable_record.get("fields", {})
        
        # Map back to standard fields
        standard_record = {
            "airtable_id": airtable_record.get("id"),
            "id": fields.get("Record ID"),
            "record_type": fields.get("Record Type"),
            "created_at": fields.get("Created At"),
            "updated_at": fields.get("Updated At"),
            "synced_at": fields.get("Synced At"),
            "source_system": fields.get("Source System"),
            "source_id": fields.get("Source ID"),
            "sync_version": fields.get("Sync Version"),
            "created_by": fields.get("Created By"),
            "updated_by": fields.get("Updated By"),
            "agent_version": fields.get("Agent Version"),
        }
        
        # Add all other fields
        for key, value in fields.items():
            snake_key = key.lower().replace(" ", "_")
            if snake_key not in standard_record:
                standard_record[snake_key] = value
        
        return standard_record