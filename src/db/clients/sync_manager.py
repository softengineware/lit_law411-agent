"""Synchronization manager for three-database architecture."""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from src.core.config import settings
from src.core.logging import logger
from src.db.clients.airtable_client import AirtableClient
from src.db.clients.base_client import BaseRecord, SyncResult
from src.db.clients.pinecone_client import PineconeClient
from src.db.clients.supabase_client import SupabaseClient


class QueryType(Enum):
    """Types of database queries for optimal database selection."""
    
    VISUAL_BROWSE = "visual_browse"  # Use Airtable
    COMPLEX_QUERY = "complex_query"  # Use Supabase
    SEMANTIC_SEARCH = "semantic_search"  # Use Pinecone
    FULL_SYNC = "full_sync"  # Use all databases


class ConsistencyResult:
    """Result of consistency check across databases."""
    
    def __init__(self):
        self.is_consistent = True
        self.missing_in_airtable: Set[str] = set()
        self.missing_in_supabase: Set[str] = set()
        self.missing_in_pinecone: Set[str] = set()
        self.version_mismatches: List[Dict[str, Any]] = []
        self.timestamp = datetime.utcnow()
    
    def add_missing(self, database: str, record_id: str):
        """Add a missing record to the appropriate set."""
        if database == "airtable":
            self.missing_in_airtable.add(record_id)
        elif database == "supabase":
            self.missing_in_supabase.add(record_id)
        elif database == "pinecone":
            self.missing_in_pinecone.add(record_id)
        self.is_consistent = False
    
    def add_version_mismatch(self, record_id: str, versions: Dict[str, int]):
        """Add a version mismatch."""
        self.version_mismatches.append({
            "record_id": record_id,
            "versions": versions
        })
        self.is_consistent = False


class ThreeDatabaseSyncManager:
    """Manager for synchronizing data across three databases."""
    
    def __init__(self):
        """Initialize the sync manager with three database clients."""
        self.airtable = AirtableClient()
        self.supabase = SupabaseClient()
        self.pinecone = PineconeClient()
        
        # Sync configuration
        self.batch_size = settings.SYNC_BATCH_SIZE
        self.max_retries = settings.SYNC_MAX_RETRIES
        self.retry_delay = settings.SYNC_RETRY_DELAY
        self.consistency_check_enabled = settings.CONSISTENCY_CHECK_ENABLED
        self.consistency_tolerance_seconds = settings.CONSISTENCY_TOLERANCE_SECONDS
    
    async def connect_all(self) -> None:
        """Connect to all three databases."""
        await asyncio.gather(
            self.airtable.connect(),
            self.supabase.connect(),
            self.pinecone.connect()
        )
        logger.info("Connected to all three databases")
    
    async def disconnect_all(self) -> None:
        """Disconnect from all three databases."""
        await asyncio.gather(
            self.airtable.disconnect(),
            self.supabase.disconnect(),
            self.pinecone.disconnect()
        )
        logger.info("Disconnected from all three databases")
    
    async def sync_to_all_databases(self, record: Dict[str, Any]) -> Dict[str, SyncResult]:
        """Sync a record to all three databases in parallel.
        
        Args:
            record: Record to sync
            
        Returns:
            Dictionary of database name to SyncResult
        """
        # Ensure we have base record fields
        if "id" not in record:
            record["id"] = str(uuid4())
        if "synced_at" not in record:
            record["synced_at"] = datetime.utcnow().isoformat()
        if "sync_version" in record:
            record["sync_version"] += 1
        else:
            record["sync_version"] = 1
        
        # Parallel writes to all databases
        results = await asyncio.gather(
            self.airtable.upsert(record),
            self.supabase.upsert(record),
            self.pinecone.upsert(record),
            return_exceptions=True
        )
        
        # Map results
        sync_results = {
            "airtable": results[0] if not isinstance(results[0], Exception) else SyncResult(
                success=False, database="Airtable", error=str(results[0])
            ),
            "supabase": results[1] if not isinstance(results[1], Exception) else SyncResult(
                success=False, database="Supabase", error=str(results[1])
            ),
            "pinecone": results[2] if not isinstance(results[2], Exception) else SyncResult(
                success=False, database="Pinecone", error=str(results[2])
            ),
        }
        
        # Update record with database IDs
        if sync_results["airtable"].success:
            record["airtable_id"] = sync_results["airtable"].record_id
        if sync_results["supabase"].success:
            record["supabase_id"] = sync_results["supabase"].record_id
        if sync_results["pinecone"].success:
            record["pinecone_id"] = sync_results["pinecone"].record_id
        
        # Check consistency if enabled
        if self.consistency_check_enabled:
            await self._verify_sync_consistency(record, sync_results)
        
        return sync_results
    
    async def batch_sync_to_all_databases(
        self,
        records: List[Dict[str, Any]]
    ) -> Dict[str, List[SyncResult]]:
        """Sync multiple records to all databases in batches.
        
        Args:
            records: List of records to sync
            
        Returns:
            Dictionary of database name to list of SyncResults
        """
        all_results = {
            "airtable": [],
            "supabase": [],
            "pinecone": [],
        }
        
        # Process in batches
        for i in range(0, len(records), self.batch_size):
            batch = records[i:i + self.batch_size]
            
            # Prepare batch records
            for record in batch:
                if "id" not in record:
                    record["id"] = str(uuid4())
                if "synced_at" not in record:
                    record["synced_at"] = datetime.utcnow().isoformat()
                if "sync_version" in record:
                    record["sync_version"] += 1
                else:
                    record["sync_version"] = 1
            
            # Batch sync to all databases
            results = await asyncio.gather(
                self.airtable.batch_upsert(batch),
                self.supabase.batch_upsert(batch),
                self.pinecone.batch_upsert(batch),
                return_exceptions=True
            )
            
            # Handle results
            for db_idx, db_name in enumerate(["airtable", "supabase", "pinecone"]):
                if isinstance(results[db_idx], Exception):
                    # All records in batch failed
                    for _ in batch:
                        all_results[db_name].append(SyncResult(
                            success=False,
                            database=db_name.title(),
                            error=str(results[db_idx])
                        ))
                else:
                    all_results[db_name].extend(results[db_idx])
        
        return all_results
    
    def select_read_database(self, query_type: QueryType) -> Any:
        """Select the optimal database for a query type.
        
        Args:
            query_type: Type of query
            
        Returns:
            Database client
        """
        if query_type == QueryType.VISUAL_BROWSE:
            return self.airtable
        elif query_type == QueryType.COMPLEX_QUERY:
            return self.supabase
        elif query_type == QueryType.SEMANTIC_SEARCH:
            return self.pinecone
        else:
            return self.supabase  # Default to most reliable
    
    async def query_with_fallback(
        self,
        filters: Dict[str, Any],
        query_type: QueryType = QueryType.COMPLEX_QUERY,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query with automatic fallback to other databases if primary fails.
        
        Args:
            filters: Query filters
            query_type: Type of query
            limit: Maximum results
            
        Returns:
            List of matching records
        """
        # Determine primary and fallback databases
        primary_db = self.select_read_database(query_type)
        fallback_order = []
        
        if primary_db == self.airtable:
            fallback_order = [self.supabase, self.pinecone]
        elif primary_db == self.supabase:
            fallback_order = [self.airtable, self.pinecone]
        else:  # Pinecone
            fallback_order = [self.supabase, self.airtable]
        
        # Try primary database
        try:
            results = await primary_db.query(filters, limit)
            if results:
                return results
        except Exception as e:
            logger.warning(f"Primary database query failed: {e}")
        
        # Try fallback databases
        for db in fallback_order:
            try:
                results = await db.query(filters, limit)
                if results:
                    logger.info(f"Query succeeded with fallback database: {db.database_name}")
                    return results
            except Exception as e:
                logger.warning(f"Fallback database query failed: {e}")
        
        return []
    
    async def check_consistency(
        self,
        record_ids: Optional[List[str]] = None,
        record_type: Optional[str] = None
    ) -> ConsistencyResult:
        """Check consistency across all three databases.
        
        Args:
            record_ids: Specific record IDs to check (if None, checks all)
            record_type: Filter by record type
            
        Returns:
            ConsistencyResult with details
        """
        result = ConsistencyResult()
        
        # Get records from each database
        if record_ids:
            # Check specific records
            for record_id in record_ids:
                records = await asyncio.gather(
                    self.airtable.get(record_id),
                    self.supabase.get(record_id),
                    self.pinecone.get(record_id),
                    return_exceptions=True
                )
                
                # Check existence
                airtable_record = records[0] if not isinstance(records[0], Exception) else None
                supabase_record = records[1] if not isinstance(records[1], Exception) else None
                pinecone_record = records[2] if not isinstance(records[2], Exception) else None
                
                # Track missing records
                if not airtable_record:
                    result.add_missing("airtable", record_id)
                if not supabase_record:
                    result.add_missing("supabase", record_id)
                if not pinecone_record:
                    result.add_missing("pinecone", record_id)
                
                # Check version consistency
                versions = {}
                if airtable_record:
                    versions["airtable"] = airtable_record.get("sync_version", 0)
                if supabase_record:
                    versions["supabase"] = supabase_record.get("sync_version", 0)
                if pinecone_record:
                    versions["pinecone"] = pinecone_record.get("sync_version", 0)
                
                if len(set(versions.values())) > 1:
                    result.add_version_mismatch(record_id, versions)
        
        else:
            # Check all records (expensive operation)
            filters = {"record_type": record_type} if record_type else {}
            
            records_by_db = await asyncio.gather(
                self.supabase.query(filters, limit=10000),  # Primary source of truth
                self.airtable.query(filters, limit=10000),
                self.pinecone.query(filters, limit=10000),
                return_exceptions=True
            )
            
            # Build ID sets
            supabase_ids = {r["id"] for r in records_by_db[0]} if not isinstance(records_by_db[0], Exception) else set()
            airtable_ids = {r["id"] for r in records_by_db[1]} if not isinstance(records_by_db[1], Exception) else set()
            pinecone_ids = {r["id"] for r in records_by_db[2]} if not isinstance(records_by_db[2], Exception) else set()
            
            # Find missing records
            all_ids = supabase_ids | airtable_ids | pinecone_ids
            
            for record_id in all_ids:
                if record_id not in airtable_ids:
                    result.add_missing("airtable", record_id)
                if record_id not in supabase_ids:
                    result.add_missing("supabase", record_id)
                if record_id not in pinecone_ids:
                    result.add_missing("pinecone", record_id)
        
        return result
    
    async def reconcile_databases(
        self,
        consistency_result: ConsistencyResult,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Reconcile inconsistencies across databases.
        
        Args:
            consistency_result: Result from consistency check
            dry_run: If True, only report what would be done
            
        Returns:
            Reconciliation report
        """
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "actions": [],
            "errors": []
        }
        
        # Use Supabase as source of truth
        for record_id in consistency_result.missing_in_airtable | consistency_result.missing_in_pinecone:
            try:
                # Get record from Supabase
                record = await self.supabase.get(record_id)
                if record:
                    action = {
                        "type": "sync_missing",
                        "record_id": record_id,
                        "missing_in": []
                    }
                    
                    if record_id in consistency_result.missing_in_airtable:
                        action["missing_in"].append("airtable")
                    if record_id in consistency_result.missing_in_pinecone:
                        action["missing_in"].append("pinecone")
                    
                    if not dry_run:
                        # Sync to missing databases
                        sync_results = await self.sync_to_all_databases(record)
                        action["results"] = {
                            db: result.success
                            for db, result in sync_results.items()
                        }
                    
                    report["actions"].append(action)
                    
            except Exception as e:
                report["errors"].append({
                    "record_id": record_id,
                    "error": str(e)
                })
        
        # Handle version mismatches
        for mismatch in consistency_result.version_mismatches:
            try:
                # Get the latest version (highest sync_version)
                record_id = mismatch["record_id"]
                latest_version = max(mismatch["versions"].values())
                source_db = [db for db, v in mismatch["versions"].items() if v == latest_version][0]
                
                action = {
                    "type": "resolve_version_mismatch",
                    "record_id": record_id,
                    "source_database": source_db,
                    "versions": mismatch["versions"]
                }
                
                if not dry_run:
                    # Get record from source database
                    if source_db == "airtable":
                        record = await self.airtable.get(record_id)
                    elif source_db == "supabase":
                        record = await self.supabase.get(record_id)
                    else:
                        record = await self.pinecone.get(record_id)
                    
                    if record:
                        # Sync to all databases
                        sync_results = await self.sync_to_all_databases(record)
                        action["results"] = {
                            db: result.success
                            for db, result in sync_results.items()
                        }
                
                report["actions"].append(action)
                
            except Exception as e:
                report["errors"].append({
                    "record_id": record_id,
                    "error": str(e)
                })
        
        return report
    
    async def _verify_sync_consistency(
        self,
        record: Dict[str, Any],
        sync_results: Dict[str, SyncResult]
    ) -> None:
        """Verify that a sync operation was consistent.
        
        Args:
            record: Record that was synced
            sync_results: Results from sync operation
        """
        # Check if all syncs succeeded
        all_success = all(result.success for result in sync_results.values())
        
        if not all_success:
            # Log failure and attempt retry with exponential backoff
            failed_dbs = [db for db, result in sync_results.items() if not result.success]
            logger.error(
                "Sync consistency failure",
                record_id=record.get("id"),
                failed_databases=failed_dbs
            )
            
            # Retry failed databases
            for attempt in range(self.max_retries):
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
                
                retry_tasks = []
                if "airtable" in failed_dbs and not sync_results["airtable"].success:
                    retry_tasks.append(self.airtable.upsert(record))
                if "supabase" in failed_dbs and not sync_results["supabase"].success:
                    retry_tasks.append(self.supabase.upsert(record))
                if "pinecone" in failed_dbs and not sync_results["pinecone"].success:
                    retry_tasks.append(self.pinecone.upsert(record))
                
                if retry_tasks:
                    retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
                    
                    # Check if retries succeeded
                    all_retry_success = all(
                        not isinstance(r, Exception) and r.success
                        for r in retry_results
                    )
                    
                    if all_retry_success:
                        logger.info(
                            "Sync consistency restored after retry",
                            record_id=record.get("id"),
                            attempt=attempt + 1
                        )
                        break
            else:
                # All retries failed
                logger.critical(
                    "Sync consistency could not be restored",
                    record_id=record.get("id"),
                    failed_databases=failed_dbs
                )
                
                # Store failure for manual intervention
                await self._store_sync_failure(record, sync_results)
    
    async def _store_sync_failure(
        self,
        record: Dict[str, Any],
        sync_results: Dict[str, SyncResult]
    ) -> None:
        """Store sync failure for manual intervention.
        
        Args:
            record: Record that failed to sync
            sync_results: Sync results showing failures
        """
        failure_record = {
            "id": str(uuid4()),
            "record_type": "sync_failure",
            "failed_record_id": record.get("id"),
            "failed_record_type": record.get("record_type"),
            "failure_timestamp": datetime.utcnow().isoformat(),
            "sync_results": {
                db: {
                    "success": result.success,
                    "error": result.error,
                    "record_id": result.record_id
                }
                for db, result in sync_results.items()
            },
            "original_record": record,
            "source_system": "sync_manager",
            "created_by": "system",
            "updated_by": "system",
            "agent_version": settings.APP_VERSION,
        }
        
        try:
            # Try to store in Supabase (most reliable)
            await self.supabase.upsert(failure_record)
            logger.info("Sync failure recorded", record_id=record.get("id"))
        except Exception as e:
            logger.critical(
                "Failed to record sync failure",
                record_id=record.get("id"),
                error=str(e)
            )
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all three databases.
        
        Returns:
            Dictionary of database health status
        """
        health_checks = await asyncio.gather(
            self.airtable.health_check(),
            self.supabase.health_check(),
            self.pinecone.health_check(),
            return_exceptions=True
        )
        
        return {
            "airtable": health_checks[0] if not isinstance(health_checks[0], Exception) else False,
            "supabase": health_checks[1] if not isinstance(health_checks[1], Exception) else False,
            "pinecone": health_checks[2] if not isinstance(health_checks[2], Exception) else False,
        }