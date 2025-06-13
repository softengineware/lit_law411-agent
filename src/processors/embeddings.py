"""
Embedding generation for semantic search using OpenAI text-embedding-3-large.

This module provides comprehensive embedding generation capabilities
for legal content to enable semantic search across the knowledge base.
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from openai import AsyncOpenAI
import structlog

from ..core.config import settings
from ..core.logging import get_logger
from ..utils.performance_decorators import monitor_performance

logger = get_logger(__name__)


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    embedding: List[float]
    text: str
    model: str
    token_count: int
    processing_time: float
    content_hash: str
    created_at: datetime


@dataclass
class BatchEmbeddingResult:
    """Result of batch embedding generation."""
    embeddings: List[EmbeddingResult]
    total_tokens: int
    total_processing_time: float
    success_count: int
    error_count: int
    errors: List[str]


class EmbeddingGenerator:
    """Generate embeddings using OpenAI text-embedding-3-large."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-large"
        self.max_tokens = 8191  # Max tokens for text-embedding-3-large
        self.max_batch_size = 100  # OpenAI batch limit
        self.embedding_dimension = 3072  # text-embedding-3-large dimension
        
        # Rate limiting
        self.requests_per_minute = 5000  # OpenAI limit
        self.tokens_per_minute = 10000000  # OpenAI limit
        self.request_timestamps = []
        self.token_usage = []
    
    @monitor_performance
    async def generate_embedding(self, text: str, content_id: Optional[str] = None) -> EmbeddingResult:
        """Generate embedding for a single text."""
        try:
            # Validate and prepare text
            processed_text = self._prepare_text(text)
            
            # Check rate limits
            await self._check_rate_limits(estimated_tokens=len(processed_text.split()))
            
            logger.info(f"Generating embedding for text (length: {len(processed_text)})")
            
            start_time = time.time()
            
            # Generate embedding
            response = await self.client.embeddings.create(
                model=self.model,
                input=processed_text,
                encoding_format="float"
            )
            
            processing_time = time.time() - start_time
            
            # Extract results
            embedding_data = response.data[0]
            embedding = embedding_data.embedding
            
            # Create content hash for deduplication
            content_hash = self._create_content_hash(processed_text)
            
            # Track usage
            self._track_usage(response.usage.total_tokens, processing_time)
            
            result = EmbeddingResult(
                embedding=embedding,
                text=processed_text,
                model=self.model,
                token_count=response.usage.total_tokens,
                processing_time=processing_time,
                content_hash=content_hash,
                created_at=datetime.now()
            )
            
            logger.info(f"Embedding generated successfully (tokens: {response.usage.total_tokens})")
            return result
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    @monitor_performance
    async def generate_batch_embeddings(self, texts: List[str], 
                                      content_ids: Optional[List[str]] = None) -> BatchEmbeddingResult:
        """Generate embeddings for multiple texts in batch."""
        try:
            logger.info(f"Generating batch embeddings for {len(texts)} texts")
            
            # Split into batches if needed
            batches = self._split_into_batches(texts)
            
            all_embeddings = []
            total_tokens = 0
            total_time = 0
            errors = []
            
            for batch_idx, batch_texts in enumerate(batches):
                try:
                    logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch_texts)} texts)")
                    
                    # Process batch
                    batch_results = await self._process_batch(batch_texts)
                    
                    all_embeddings.extend(batch_results.embeddings)
                    total_tokens += batch_results.total_tokens
                    total_time += batch_results.total_processing_time
                    errors.extend(batch_results.errors)
                    
                    # Add delay between batches to respect rate limits
                    if batch_idx < len(batches) - 1:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    error_msg = f"Error processing batch {batch_idx + 1}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            result = BatchEmbeddingResult(
                embeddings=all_embeddings,
                total_tokens=total_tokens,
                total_processing_time=total_time,
                success_count=len(all_embeddings),
                error_count=len(errors),
                errors=errors
            )
            
            logger.info(f"Batch embedding completed: {result.success_count} success, {result.error_count} errors")
            return result
            
        except Exception as e:
            logger.error(f"Error in batch embedding generation: {e}")
            raise
    
    async def _process_batch(self, texts: List[str]) -> BatchEmbeddingResult:
        """Process a single batch of texts."""
        # Prepare texts
        processed_texts = [self._prepare_text(text) for text in texts]
        
        # Estimate tokens
        estimated_tokens = sum(len(text.split()) for text in processed_texts)
        
        # Check rate limits
        await self._check_rate_limits(estimated_tokens)
        
        start_time = time.time()
        
        try:
            # Generate embeddings
            response = await self.client.embeddings.create(
                model=self.model,
                input=processed_texts,
                encoding_format="float"
            )
            
            processing_time = time.time() - start_time
            
            # Create results
            embeddings = []
            for i, embedding_data in enumerate(response.data):
                content_hash = self._create_content_hash(processed_texts[i])
                
                result = EmbeddingResult(
                    embedding=embedding_data.embedding,
                    text=processed_texts[i],
                    model=self.model,
                    token_count=response.usage.total_tokens // len(processed_texts),  # Approximate
                    processing_time=processing_time / len(processed_texts),  # Approximate
                    content_hash=content_hash,
                    created_at=datetime.now()
                )
                embeddings.append(result)
            
            # Track usage
            self._track_usage(response.usage.total_tokens, processing_time)
            
            return BatchEmbeddingResult(
                embeddings=embeddings,
                total_tokens=response.usage.total_tokens,
                total_processing_time=processing_time,
                success_count=len(embeddings),
                error_count=0,
                errors=[]
            )
            
        except Exception as e:
            return BatchEmbeddingResult(
                embeddings=[],
                total_tokens=0,
                total_processing_time=0,
                success_count=0,
                error_count=len(texts),
                errors=[str(e)]
            )
    
    def _prepare_text(self, text: str) -> str:
        """Prepare text for embedding generation."""
        # Clean and normalize text
        text = text.strip()
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Truncate if too long (keeping some buffer for tokenization)
        max_chars = self.max_tokens * 4  # Rough estimation
        if len(text) > max_chars:
            text = text[:max_chars]
            logger.warning(f"Text truncated to {max_chars} characters")
        
        return text
    
    def _split_into_batches(self, texts: List[str]) -> List[List[str]]:
        """Split texts into batches respecting OpenAI limits."""
        batches = []
        current_batch = []
        current_tokens = 0
        
        for text in texts:
            # Estimate tokens for this text
            estimated_tokens = len(text.split())
            
            # Check if adding this text would exceed limits
            if (len(current_batch) >= self.max_batch_size or 
                current_tokens + estimated_tokens > self.max_tokens):
                
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
            
            current_batch.append(text)
            current_tokens += estimated_tokens
        
        # Add final batch
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _create_content_hash(self, text: str) -> str:
        """Create hash of content for deduplication."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    async def _check_rate_limits(self, estimated_tokens: int):
        """Check and enforce rate limits."""
        current_time = time.time()
        
        # Remove old timestamps (older than 1 minute)
        self.request_timestamps = [ts for ts in self.request_timestamps 
                                 if current_time - ts < 60]
        self.token_usage = [(ts, tokens) for ts, tokens in self.token_usage 
                           if current_time - ts < 60]
        
        # Check request rate limit
        if len(self.request_timestamps) >= self.requests_per_minute:
            sleep_time = 60 - (current_time - self.request_timestamps[0])
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping for {sleep_time:.1f} seconds")
                await asyncio.sleep(sleep_time)
        
        # Check token rate limit
        total_tokens_last_minute = sum(tokens for _, tokens in self.token_usage)
        if total_tokens_last_minute + estimated_tokens > self.tokens_per_minute:
            sleep_time = 60 - (current_time - self.token_usage[0][0])
            if sleep_time > 0:
                logger.info(f"Token rate limit reached, sleeping for {sleep_time:.1f} seconds")
                await asyncio.sleep(sleep_time)
    
    def _track_usage(self, tokens: int, processing_time: float):
        """Track API usage for rate limiting."""
        current_time = time.time()
        self.request_timestamps.append(current_time)
        self.token_usage.append((current_time, tokens))


class SemanticChunker:
    """Chunk large documents into semantically coherent pieces."""
    
    def __init__(self, max_chunk_size: int = 500, overlap_size: int = 50):
        self.max_chunk_size = max_chunk_size  # words
        self.overlap_size = overlap_size  # words
    
    def chunk_text(self, text: str, preserve_structure: bool = True) -> List[str]:
        """Chunk text into smaller pieces for embedding."""
        if preserve_structure:
            return self._chunk_by_structure(text)
        else:
            return self._chunk_by_words(text)
    
    def _chunk_by_structure(self, text: str) -> List[str]:
        """Chunk text preserving logical structure (paragraphs, sections)."""
        chunks = []
        
        # Split by double newlines (paragraphs)
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        current_word_count = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            para_word_count = len(paragraph.split())
            
            # If this paragraph alone exceeds max size, split it
            if para_word_count > self.max_chunk_size:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Split large paragraph
                chunks.extend(self._chunk_by_words(paragraph))
                
                current_chunk = ""
                current_word_count = 0
            
            # If adding this paragraph would exceed max size, start new chunk
            elif current_word_count + para_word_count > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                current_chunk = paragraph
                current_word_count = para_word_count
            
            # Add paragraph to current chunk
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
                current_word_count += para_word_count
        
        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _chunk_by_words(self, text: str) -> List[str]:
        """Chunk text by word count with overlap."""
        words = text.split()
        chunks = []
        
        start = 0
        while start < len(words):
            end = min(start + self.max_chunk_size, len(words))
            chunk_words = words[start:end]
            chunks.append(' '.join(chunk_words))
            
            # Move start forward, accounting for overlap
            if end == len(words):
                break
            start = end - self.overlap_size
        
        return chunks


class LegalEmbeddingService:
    """Main service for legal content embedding generation."""
    
    def __init__(self):
        self.generator = EmbeddingGenerator()
        self.chunker = SemanticChunker()
        self.embedding_cache = {}  # Simple in-memory cache
    
    @monitor_performance
    async def embed_legal_document(self, text: str, title: str = "", 
                                 document_type: str = "general",
                                 chunk_if_large: bool = True) -> Dict[str, Any]:
        """Embed a legal document, handling chunking if needed."""
        try:
            logger.info(f"Embedding legal document: {title} (type: {document_type})")
            
            # Prepare document metadata
            metadata = {
                'title': title,
                'document_type': document_type,
                'original_length': len(text),
                'word_count': len(text.split()),
                'created_at': datetime.now().isoformat()
            }
            
            # Check if document needs chunking
            word_count = len(text.split())
            if chunk_if_large and word_count > 400:  # Leave buffer for max tokens
                return await self._embed_chunked_document(text, metadata)
            else:
                return await self._embed_single_document(text, metadata)
                
        except Exception as e:
            logger.error(f"Error embedding legal document: {e}")
            raise
    
    async def _embed_single_document(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Embed a single document without chunking."""
        # Check cache
        content_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        if content_hash in self.embedding_cache:
            logger.info("Using cached embedding")
            return self.embedding_cache[content_hash]
        
        # Generate embedding
        result = await self.generator.generate_embedding(text)
        
        # Prepare response
        response = {
            'embeddings': [self._embedding_result_to_dict(result)],
            'chunks': [{'text': text, 'chunk_index': 0, 'word_count': len(text.split())}],
            'metadata': metadata,
            'total_chunks': 1,
            'total_tokens': result.token_count,
            'processing_time': result.processing_time
        }
        
        # Cache result
        self.embedding_cache[content_hash] = response
        
        return response
    
    async def _embed_chunked_document(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Embed a document with chunking."""
        # Chunk the document
        chunks = self.chunker.chunk_text(text, preserve_structure=True)
        
        logger.info(f"Document chunked into {len(chunks)} pieces")
        
        # Generate embeddings for all chunks
        batch_result = await self.generator.generate_batch_embeddings(chunks)
        
        # Prepare chunk information
        chunk_info = []
        for i, chunk in enumerate(chunks):
            chunk_info.append({
                'text': chunk,
                'chunk_index': i,
                'word_count': len(chunk.split()),
                'start_position': self._find_chunk_position(text, chunk)
            })
        
        # Update metadata
        metadata.update({
            'total_chunks': len(chunks),
            'chunking_method': 'semantic_structure',
            'average_chunk_size': sum(len(c.split()) for c in chunks) / len(chunks)
        })
        
        return {
            'embeddings': [self._embedding_result_to_dict(emb) for emb in batch_result.embeddings],
            'chunks': chunk_info,
            'metadata': metadata,
            'total_chunks': len(chunks),
            'total_tokens': batch_result.total_tokens,
            'processing_time': batch_result.total_processing_time,
            'errors': batch_result.errors
        }
    
    @monitor_performance
    async def embed_transcript_segments(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Embed transcript segments with timestamp information."""
        try:
            logger.info(f"Embedding {len(segments)} transcript segments")
            
            # Prepare texts for embedding
            texts = []
            segment_metadata = []
            
            for segment in segments:
                text = segment.get('text', '')
                if text.strip():
                    texts.append(text)
                    segment_metadata.append({
                        'segment_id': segment.get('id'),
                        'start_time': segment.get('start_time'),
                        'end_time': segment.get('end_time'),
                        'confidence': segment.get('confidence'),
                        'word_count': len(text.split())
                    })
            
            if not texts:
                raise ValueError("No valid text found in transcript segments")
            
            # Generate embeddings
            batch_result = await self.generator.generate_batch_embeddings(texts)
            
            return {
                'embeddings': [self._embedding_result_to_dict(emb) for emb in batch_result.embeddings],
                'segments': segment_metadata,
                'total_segments': len(texts),
                'total_tokens': batch_result.total_tokens,
                'processing_time': batch_result.total_processing_time,
                'errors': batch_result.errors
            }
            
        except Exception as e:
            logger.error(f"Error embedding transcript segments: {e}")
            raise
    
    @monitor_performance
    async def embed_legal_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Embed legal entities for entity-based search."""
        try:
            logger.info(f"Embedding {len(entities)} legal entities")
            
            # Prepare entity texts
            texts = []
            entity_metadata = []
            
            for entity in entities:
                # Create rich text representation of entity
                entity_text = self._create_entity_text(entity)
                texts.append(entity_text)
                entity_metadata.append({
                    'entity_type': entity.get('entity_type'),
                    'original_text': entity.get('text'),
                    'context': entity.get('context'),
                    'confidence': entity.get('confidence')
                })
            
            # Generate embeddings
            batch_result = await self.generator.generate_batch_embeddings(texts)
            
            return {
                'embeddings': [self._embedding_result_to_dict(emb) for emb in batch_result.embeddings],
                'entities': entity_metadata,
                'total_entities': len(texts),
                'total_tokens': batch_result.total_tokens,
                'processing_time': batch_result.total_processing_time,
                'errors': batch_result.errors
            }
            
        except Exception as e:
            logger.error(f"Error embedding legal entities: {e}")
            raise
    
    def _create_entity_text(self, entity: Dict[str, Any]) -> str:
        """Create rich text representation for entity embedding."""
        entity_type = entity.get('entity_type', '')
        text = entity.get('text', '')
        context = entity.get('context', '')
        
        # Create descriptive text for better embeddings
        if entity_type == 'VIRGINIA_CODE':
            return f"Virginia Code statute {text} legal provision {context}"
        elif entity_type == 'CASE_CITATION':
            return f"Legal case {text} court decision {context}"
        elif entity_type == 'COURT':
            return f"Court {text} judicial authority {context}"
        elif entity_type == 'FAMILY_LAW':
            return f"Family law concept {text} legal term {context}"
        else:
            return f"{entity_type} {text} {context}"
    
    def _find_chunk_position(self, full_text: str, chunk: str) -> int:
        """Find the starting position of a chunk in the full text."""
        try:
            return full_text.index(chunk)
        except ValueError:
            # If exact match not found, try to find similar content
            chunk_words = chunk.split()[:5]  # First 5 words
            search_text = ' '.join(chunk_words)
            try:
                return full_text.index(search_text)
            except ValueError:
                return 0
    
    def _embedding_result_to_dict(self, result: EmbeddingResult) -> Dict[str, Any]:
        """Convert EmbeddingResult to dictionary."""
        return {
            'embedding': result.embedding,
            'text_length': len(result.text),
            'model': result.model,
            'token_count': result.token_count,
            'processing_time': result.processing_time,
            'content_hash': result.content_hash,
            'created_at': result.created_at.isoformat()
        }


# Export main components
__all__ = [
    'LegalEmbeddingService',
    'EmbeddingGenerator',
    'SemanticChunker',
    'EmbeddingResult',
    'BatchEmbeddingResult'
]