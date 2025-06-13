"""Pinecone client implementation for vector search layer."""

import asyncio
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pinecone
from pinecone import Index, Vector
import openai
import numpy as np

from src.core.config import settings
from src.core.logging import logger
from src.db.clients.base_client import BaseDatabaseClient, SyncResult


class PineconeClient(BaseDatabaseClient):
    """Pinecone vector database client for AI-powered search.
    
    This client handles:
    - Semantic search across all content
    - Finding similar documents
    - AI-powered document retrieval
    - Context-aware search results
    - Multi-modal embeddings (text, potentially images)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Pinecone client.
        
        Args:
            config: Optional configuration override
        """
        if config is None:
            config = {
                "api_key": settings.PINECONE_API_KEY,
                "environment": settings.PINECONE_ENVIRONMENT,
                "index_name": settings.PINECONE_INDEX_NAME,
                "openai_api_key": settings.OPENAI_API_KEY,
            }
        super().__init__(config)
        
        self.index: Optional[Index] = None
        self.openai_client = None
        self._embedding_model = "text-embedding-3-large"
        self._embedding_dimensions = 1536  # For text-embedding-3-large
    
    async def connect(self) -> None:
        """Establish connection to Pinecone."""
        try:
            # Initialize Pinecone
            pinecone.init(
                api_key=self.config["api_key"],
                environment=self.config["environment"]
            )
            
            # Check if index exists, create if not
            index_name = self.config["index_name"]
            if index_name not in pinecone.list_indexes():
                logger.info(f"Creating Pinecone index: {index_name}")
                pinecone.create_index(
                    name=index_name,
                    dimension=self._embedding_dimensions,
                    metric="cosine",
                    metadata_config={
                        "indexed": [
                            "record_type",
                            "source_system",
                            "created_at",
                            "legal_categories",
                            "jurisdiction",
                        ]
                    }
                )
            
            # Connect to index
            self.index = pinecone.Index(index_name)
            
            # Initialize OpenAI client for embeddings
            openai.api_key = self.config["openai_api_key"]
            self.openai_client = openai
            
            # Get index stats
            stats = self.index.describe_index_stats()
            logger.info(
                "Connected to Pinecone",
                index=index_name,
                vectors=stats.total_vector_count,
                dimensions=stats.dimension
            )
            
        except Exception as e:
            logger.error("Failed to connect to Pinecone", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close connection to Pinecone."""
        self.index = None
        self.openai_client = None
        logger.info("Disconnected from Pinecone")
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            response = await asyncio.to_thread(
                self.openai_client.Embedding.create,
                input=text,
                model=self._embedding_model
            )
            return response["data"][0]["embedding"]
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            raise
    
    def _generate_vector_id(self, record: Dict[str, Any]) -> str:
        """Generate a unique vector ID for a record.
        
        Args:
            record: Record data
            
        Returns:
            Vector ID
        """
        # Use record ID if available, otherwise generate from content
        if record.get("id"):
            return f"{record['record_type']}_{record['id']}"
        else:
            # Generate deterministic ID from content
            content = str(record)
            return f"{record['record_type']}_{hashlib.md5(content.encode()).hexdigest()}"
    
    def _prepare_metadata(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare metadata for Pinecone storage.
        
        Args:
            record: Record data
            
        Returns:
            Metadata dictionary
        """
        # Core metadata fields
        metadata = {
            "record_id": record.get("id"),
            "record_type": record.get("record_type"),
            "source_system": record.get("source_system", "lit_law411_agent"),
            "source_id": record.get("source_id"),
            "created_at": record.get("created_at", datetime.utcnow().isoformat()),
            "updated_at": record.get("updated_at", datetime.utcnow().isoformat()),
            "airtable_id": record.get("airtable_id"),
            "supabase_id": record.get("supabase_id"),
        }
        
        # Add searchable text content
        content_parts = []
        
        if record.get("record_type") == "youtube_video":
            metadata.update({
                "title": record.get("title", ""),
                "channel_name": record.get("channel_name", ""),
                "video_id": record.get("video_id"),
                "url": record.get("url"),
                "published_at": record.get("published_at"),
                "legal_categories": record.get("legal_categories", []),
                "has_transcript": record.get("has_transcript", False),
            })
            content_parts.extend([
                record.get("title", ""),
                record.get("description", ""),
                " ".join(record.get("tags", [])),
            ])
            
        elif record.get("record_type") == "legal_website":
            metadata.update({
                "name": record.get("name", ""),
                "url": record.get("url"),
                "legal_topics": record.get("legal_topics", []),
                "jurisdiction": record.get("jurisdiction"),
                "authority_level": record.get("authority_level"),
                "quality_score": record.get("quality_score", 0.0),
            })
            content_parts.extend([
                record.get("name", ""),
                record.get("content", ""),
                " ".join(record.get("legal_topics", [])),
            ])
            
        elif record.get("record_type") == "transcript":
            metadata.update({
                "source_type": record.get("source_type"),
                "source_url": record.get("source_url"),
                "language": record.get("language", "en"),
                "duration_seconds": record.get("duration_seconds"),
                "legal_entities": record.get("legal_entities", []),
            })
            content_parts.append(record.get("content", ""))
            
        elif record.get("record_type") == "legal_entity":
            metadata.update({
                "entity_type": record.get("entity_type"),
                "entity_text": record.get("entity_text"),
                "normalized_text": record.get("normalized_text"),
                "confidence_score": record.get("confidence_score", 0.0),
            })
            content_parts.extend([
                record.get("entity_text", ""),
                record.get("context", ""),
            ])
        
        # Combine content for embedding
        metadata["content"] = " ".join(filter(None, content_parts))[:5000]  # Limit length
        
        # Remove None values and ensure all values are JSON-serializable
        clean_metadata = {}
        for key, value in metadata.items():
            if value is not None:
                if isinstance(value, (list, dict)):
                    clean_metadata[key] = value
                else:
                    clean_metadata[key] = str(value)
        
        return clean_metadata
    
    async def upsert(self, record: Dict[str, Any]) -> SyncResult:
        """Insert or update a record in Pinecone.
        
        Args:
            record: Record data to upsert
            
        Returns:
            SyncResult indicating success or failure
        """
        try:
            if not self.index:
                await self.connect()
            
            # Prepare metadata
            metadata = self._prepare_metadata(record)
            
            # Generate embedding from content
            content = metadata.get("content", "")
            if not content:
                return SyncResult(
                    success=False,
                    database="Pinecone",
                    error="No content to embed",
                )
            
            embedding = await self._generate_embedding(content)
            
            # Generate vector ID
            vector_id = self._generate_vector_id(record)
            
            # Upsert to Pinecone
            self.index.upsert(
                vectors=[(vector_id, embedding, metadata)],
                namespace=record.get("namespace", "default")
            )
            
            return SyncResult(
                success=True,
                database="Pinecone",
                record_id=vector_id,
            )
            
        except Exception as e:
            logger.error("Pinecone upsert failed", error=str(e), record_id=record.get("id"))
            return SyncResult(
                success=False,
                database="Pinecone",
                error=str(e),
            )
    
    async def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a record from Pinecone by ID.
        
        Args:
            record_id: Vector ID
            
        Returns:
            Record data if found, None otherwise
        """
        try:
            if not self.index:
                await self.connect()
            
            # Fetch vector by ID
            result = self.index.fetch(
                ids=[record_id],
                namespace="default"
            )
            
            if record_id in result["vectors"]:
                vector_data = result["vectors"][record_id]
                return self._from_pinecone_format(record_id, vector_data)
            
            return None
            
        except Exception as e:
            logger.error("Pinecone get failed", error=str(e), record_id=record_id)
            return None
    
    async def query(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Query records from Pinecone using vector similarity or metadata filters.
        
        Args:
            filters: Query filters (can include 'query_text' for semantic search)
            limit: Maximum number of records to return
            
        Returns:
            List of matching records
        """
        try:
            if not self.index:
                await self.connect()
            
            # Check if this is a semantic search
            if "query_text" in filters:
                # Generate embedding for query
                query_embedding = await self._generate_embedding(filters["query_text"])
                
                # Build metadata filter
                metadata_filter = {}
                for key, value in filters.items():
                    if key != "query_text":
                        metadata_filter[key] = value
                
                # Query by vector similarity
                result = self.index.query(
                    vector=query_embedding,
                    top_k=limit,
                    include_metadata=True,
                    filter=metadata_filter if metadata_filter else None,
                    namespace=filters.get("namespace", "default")
                )
                
                return [
                    self._from_pinecone_match(match)
                    for match in result["matches"]
                ]
            else:
                # Metadata-only query (less efficient in Pinecone)
                # For better performance, use Supabase for non-semantic queries
                logger.warning("Metadata-only query in Pinecone is inefficient")
                return []
                
        except Exception as e:
            logger.error("Pinecone query failed", error=str(e), filters=filters)
            return []
    
    async def delete(self, record_id: str) -> SyncResult:
        """Delete a record from Pinecone.
        
        Args:
            record_id: Vector ID
            
        Returns:
            SyncResult indicating success or failure
        """
        try:
            if not self.index:
                await self.connect()
            
            # Delete by ID
            self.index.delete(
                ids=[record_id],
                namespace="default"
            )
            
            return SyncResult(
                success=True,
                database="Pinecone",
                record_id=record_id,
            )
            
        except Exception as e:
            logger.error("Pinecone delete failed", error=str(e), record_id=record_id)
            return SyncResult(
                success=False,
                database="Pinecone",
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
        vectors_to_upsert = []
        record_map = {}
        
        try:
            if not self.index:
                await self.connect()
            
            # Prepare all vectors
            for record in records:
                try:
                    metadata = self._prepare_metadata(record)
                    content = metadata.get("content", "")
                    
                    if not content:
                        results.append(SyncResult(
                            success=False,
                            database="Pinecone",
                            error="No content to embed",
                        ))
                        continue
                    
                    # Generate embedding
                    embedding = await self._generate_embedding(content)
                    vector_id = self._generate_vector_id(record)
                    
                    vectors_to_upsert.append((vector_id, embedding, metadata))
                    record_map[vector_id] = record
                    
                except Exception as e:
                    results.append(SyncResult(
                        success=False,
                        database="Pinecone",
                        error=str(e),
                    ))
            
            # Batch upsert (Pinecone supports up to 100 vectors per request)
            for i in range(0, len(vectors_to_upsert), 100):
                batch = vectors_to_upsert[i:i + 100]
                self.index.upsert(
                    vectors=batch,
                    namespace="default"
                )
                
                # Add success results for this batch
                for vector_id, _, _ in batch:
                    results.append(SyncResult(
                        success=True,
                        database="Pinecone",
                        record_id=vector_id,
                    ))
            
        except Exception as e:
            logger.error("Pinecone batch upsert failed", error=str(e))
            # Add failure results for remaining records
            remaining = len(records) - len(results)
            for _ in range(remaining):
                results.append(SyncResult(
                    success=False,
                    database="Pinecone",
                    error=str(e),
                ))
        
        return results
    
    async def search_similar(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        score_threshold: float = 0.7
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Search for similar documents using semantic search.
        
        Args:
            query_text: Text to search for
            filters: Optional metadata filters
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            
        Returns:
            List of (record, score) tuples
        """
        try:
            if not self.index:
                await self.connect()
            
            # Generate query embedding
            query_embedding = await self._generate_embedding(query_text)
            
            # Query Pinecone
            result = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filters,
                namespace="default"
            )
            
            # Filter by score threshold and format results
            similar_records = []
            for match in result["matches"]:
                if match["score"] >= score_threshold:
                    record = self._from_pinecone_match(match)
                    similar_records.append((record, match["score"]))
            
            return similar_records
            
        except Exception as e:
            logger.error("Similarity search failed", error=str(e), query=query_text)
            return []
    
    def _from_pinecone_format(self, vector_id: str, vector_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Pinecone vector data to standard format.
        
        Args:
            vector_id: Vector ID
            vector_data: Vector data from Pinecone
            
        Returns:
            Record in standard format
        """
        metadata = vector_data.get("metadata", {})
        
        # Reconstruct record from metadata
        record = {
            "pinecone_id": vector_id,
            "id": metadata.get("record_id"),
            "record_type": metadata.get("record_type"),
            "source_system": metadata.get("source_system"),
            "source_id": metadata.get("source_id"),
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
            "airtable_id": metadata.get("airtable_id"),
            "supabase_id": metadata.get("supabase_id"),
        }
        
        # Add all other metadata fields
        for key, value in metadata.items():
            if key not in record:
                record[key] = value
        
        return record
    
    def _from_pinecone_match(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Pinecone match result to standard format.
        
        Args:
            match: Match result from Pinecone query
            
        Returns:
            Record in standard format
        """
        record = self._from_pinecone_format(match["id"], {"metadata": match.get("metadata", {})})
        record["similarity_score"] = match.get("score", 0.0)
        return record