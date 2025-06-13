"""Celery tasks for lit_law411-agent."""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import current_task

from src.core.logging import get_logger
from src.db.cache_manager import cache_invalidator, cache_warmer
from src.workers.celery_app import celery_app

# Import our processors and clients
from src.processors.transcription import TranscriptionService
from src.processors.nlp import LegalNLPService
from src.processors.embeddings import LegalEmbeddingService
from src.scrapers.web import WebScrapingClient
from src.scrapers.youtube import YouTubeClient
from src.db.clients.sync_manager import ThreeDatabaseSyncManager

logger = get_logger(__name__)


def run_async_task(coro):
    """Helper to run async tasks in Celery."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, name="periodic_cleanup")
def periodic_cleanup(self):
    """Periodic cleanup of expired cache entries and temp data."""
    logger.info("Starting periodic cleanup task")
    
    try:
        # Clean up expired sessions
        async def cleanup():
            expired_count = await cache_invalidator.invalidate_expired_sessions()
            return expired_count
        
        expired_count = run_async_task(cleanup())
        
        result = {
            "status": "completed",
            "expired_sessions_cleaned": expired_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Periodic cleanup completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Periodic cleanup failed", error=str(e))
        raise


@celery_app.task(bind=True, name="invalidate_user_cache")
def invalidate_user_cache(self, user_id: str):
    """Invalidate all cache data for a specific user."""
    logger.info("Invalidating user cache", user_id=user_id)
    
    try:
        async def invalidate():
            return await cache_invalidator.invalidate_user_data(user_id)
        
        cleared_count = run_async_task(invalidate())
        
        result = {
            "status": "completed",
            "user_id": user_id,
            "cleared_entries": cleared_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("User cache invalidated", result=result)
        return result
        
    except Exception as e:
        logger.error("User cache invalidation failed", user_id=user_id, error=str(e))
        raise


@celery_app.task(bind=True, name="invalidate_content_cache")
def invalidate_content_cache(self, content_id: str):
    """Invalidate all cache data for specific content."""
    logger.info("Invalidating content cache", content_id=content_id)
    
    try:
        async def invalidate():
            return await cache_invalidator.invalidate_content_data(content_id)
        
        cleared_count = run_async_task(invalidate())
        
        result = {
            "status": "completed",
            "content_id": content_id,
            "cleared_entries": cleared_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Content cache invalidated", result=result)
        return result
        
    except Exception as e:
        logger.error("Content cache invalidation failed", content_id=content_id, error=str(e))
        raise


@celery_app.task(bind=True, name="warm_cache")
def warm_cache(self, cache_type: str, ids: List[str]):
    """Warm up cache with frequently accessed data."""
    logger.info("Starting cache warming", cache_type=cache_type, count=len(ids))
    
    try:
        async def warm():
            if cache_type == "user":
                return await cache_warmer.warm_user_data(ids)
            elif cache_type == "content":
                return await cache_warmer.warm_popular_content(ids)
            else:
                raise ValueError(f"Unknown cache type: {cache_type}")
        
        warmed_count = run_async_task(warm())
        
        result = {
            "status": "completed",
            "cache_type": cache_type,
            "requested_count": len(ids),
            "warmed_count": warmed_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Cache warming completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Cache warming failed", cache_type=cache_type, error=str(e))
        raise


@celery_app.task(bind=True, name="process_content")
def process_content(self, content_data: Dict[str, Any]):
    """Process content through the pipeline."""
    content_id = content_data.get("id")
    logger.info("Processing content", content_id=content_id)
    
    try:
        # Update task progress
        self.update_state(
            state="PROGRESS",
            meta={"current": 1, "total": 4, "status": "Starting content processing"}
        )
        
        # Step 1: Validate content
        # TODO: Implement content validation
        
        self.update_state(
            state="PROGRESS", 
            meta={"current": 2, "total": 4, "status": "Content validated"}
        )
        
        # Step 2: Extract metadata
        # TODO: Implement metadata extraction
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 3, "total": 4, "status": "Metadata extracted"}
        )
        
        # Step 3: Queue for transcription if needed
        if content_data.get("type") == "video":
            # Queue transcription task
            extract_transcription.delay(content_id)
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 4, "total": 4, "status": "Processing complete"}
        )
        
        result = {
            "status": "completed",
            "content_id": content_id,
            "processing_steps": ["validation", "metadata", "transcription_queued"],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Content processing completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Content processing failed", content_id=content_id, error=str(e))
        raise


@celery_app.task(bind=True, name="extract_transcription")
def extract_transcription(self, content_id: str):
    """Extract transcription from audio/video content."""
    logger.info("Extracting transcription", content_id=content_id)
    
    try:
        self.update_state(
            state="PROGRESS",
            meta={"current": 1, "total": 3, "status": "Downloading audio"}
        )
        
        # TODO: Implement actual transcription with Whisper
        # For now, return a placeholder
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 2, "total": 3, "status": "Transcribing audio"}
        )
        
        # Simulate transcription work
        import time
        time.sleep(2)
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 3, "total": 3, "status": "Saving transcript"}
        )
        
        # Queue embedding generation
        generate_embeddings.delay(content_id, "transcript")
        
        result = {
            "status": "completed",
            "content_id": content_id,
            "transcript_length": 1500,  # Placeholder
            "language": "en",
            "confidence": 0.95,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Transcription completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Transcription failed", content_id=content_id, error=str(e))
        raise


@celery_app.task(bind=True, name="generate_embeddings")
def generate_embeddings(self, content_id: str, content_type: str):
    """Generate embeddings for content."""
    logger.info("Generating embeddings", content_id=content_id, content_type=content_type)
    
    try:
        self.update_state(
            state="PROGRESS",
            meta={"current": 1, "total": 3, "status": "Loading content"}
        )
        
        # TODO: Implement actual embedding generation
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 2, "total": 3, "status": "Generating embeddings"}
        )
        
        # Simulate embedding work
        import time
        time.sleep(1)
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 3, "total": 3, "status": "Storing embeddings"}
        )
        
        result = {
            "status": "completed",
            "content_id": content_id,
            "content_type": content_type,
            "embedding_dimensions": 1536,  # OpenAI text-embedding-3-large
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Embedding generation completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Embedding generation failed", content_id=content_id, error=str(e))
        raise


@celery_app.task(bind=True, name="scrape_content") 
def scrape_content(self, url: str, source_config: Dict[str, Any]):
    """Scrape content from a URL."""
    logger.info("Scraping content", url=url)
    
    try:
        self.update_state(
            state="PROGRESS",
            meta={"current": 1, "total": 4, "status": "Fetching URL"}
        )
        
        # TODO: Implement actual web scraping
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 2, "total": 4, "status": "Parsing content"}
        )
        
        self.update_state(
            state="PROGRESS", 
            meta={"current": 3, "total": 4, "status": "Extracting metadata"}
        )
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 4, "total": 4, "status": "Saving content"}
        )
        
        # Queue content processing
        content_data = {
            "id": "scraped_content_123",  # Placeholder
            "url": url,
            "type": "article",
            "title": "Sample Article",  # Placeholder
        }
        process_content.delay(content_data)
        
        result = {
            "status": "completed",
            "url": url,
            "content_id": content_data["id"],
            "content_length": 5000,  # Placeholder
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Content scraping completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Content scraping failed", url=url, error=str(e))
        raise


@celery_app.task(bind=True, name="sync_databases")
def sync_databases(self):
    """Synchronize data across the three-database architecture."""
    logger.info("Starting database synchronization")
    
    try:
        # TODO: Implement actual database synchronization logic
        # This would sync between Airtable, Supabase, and Pinecone
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 1, "total": 3, "status": "Syncing Airtable -> Supabase"}
        )
        
        # Simulate sync work
        import time
        time.sleep(1)
        
        self.update_state(
            state="PROGRESS", 
            meta={"current": 2, "total": 3, "status": "Syncing Supabase -> Pinecone"}
        )
        
        time.sleep(1)
        
        self.update_state(
            state="PROGRESS",
            meta={"current": 3, "total": 3, "status": "Verification complete"}
        )
        
        result = {
            "status": "completed",
            "synced_records": 150,  # Placeholder
            "errors": 0,
            "warnings": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Database synchronization completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Database synchronization failed", error=str(e))
        raise


@celery_app.task(bind=True, name="batch_process")
def batch_process(self, task_name: str, items: List[Any], batch_size: int = 10):
    """Process items in batches to avoid overwhelming the system."""
    logger.info("Starting batch processing", task=task_name, total_items=len(items), batch_size=batch_size)
    
    try:
        results = []
        total_batches = (len(items) + batch_size - 1) // batch_size
        
        for i in range(0, len(items), batch_size):
            batch_num = (i // batch_size) + 1
            batch = items[i:i + batch_size]
            
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": batch_num,
                    "total": total_batches,
                    "status": f"Processing batch {batch_num}/{total_batches}"
                }
            )
            
            # Process batch items
            batch_results = []
            for item in batch:
                try:
                    # Queue individual task
                    if task_name == "process_content":
                        task_result = process_content.delay(item)
                    elif task_name == "generate_embeddings":
                        task_result = generate_embeddings.delay(item["content_id"], item["content_type"])
                    else:
                        logger.warning("Unknown batch task", task=task_name)
                        continue
                    
                    batch_results.append({"item": item, "task_id": task_result.id})
                    
                except Exception as e:
                    logger.error("Batch item failed", item=item, error=str(e))
                    batch_results.append({"item": item, "error": str(e)})
            
            results.extend(batch_results)
            
            # Small delay between batches
            import time
            time.sleep(0.5)
        
        result = {
            "status": "completed",
            "task_name": task_name,
            "total_items": len(items),
            "batch_size": batch_size,
            "total_batches": total_batches,
            "queued_tasks": len([r for r in results if "task_id" in r]),
            "failed_items": len([r for r in results if "error" in r]),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        logger.info("Batch processing completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Batch processing failed", task=task_name, error=str(e))
        raise


# New MVP implementation tasks

@celery_app.task(bind=True, name="process_youtube_video")
def process_youtube_video(self, video_url: str, priority: str = "normal", 
                         extract_audio: bool = True, transcribe: bool = True,
                         user_id: Optional[str] = None):
    """Complete YouTube video processing pipeline."""
    logger.info("Processing YouTube video", url=video_url, user_id=user_id)
    
    try:
        self.update_state(
            state="PROGRESS",
            meta={"current": 1, "total": 6, "status": "Extracting video metadata"}
        )
        
        async def process_video():
            # Initialize services
            youtube_client = YouTubeClient()
            transcription_service = TranscriptionService()
            nlp_service = LegalNLPService()
            embedding_service = LegalEmbeddingService()
            sync_manager = ThreeDatabaseSyncManager()
            
            # Step 1: Extract video metadata
            video_details = await youtube_client.get_video_details(video_url)
            if not video_details:
                raise ValueError(f"Could not extract video details for {video_url}")
            
            self.update_state(
                state="PROGRESS",
                meta={"current": 2, "total": 6, "status": "Downloading and transcribing audio"}
            )
            
            # Step 2: Download and transcribe audio
            transcript = None
            if extract_audio and transcribe:
                transcript = await transcription_service.transcribe_youtube_video(video_url)
            
            self.update_state(
                state="PROGRESS", 
                meta={"current": 3, "total": 6, "status": "Extracting legal entities"}
            )
            
            # Step 3: Extract legal entities from transcript
            nlp_results = None
            if transcript:
                nlp_results = await nlp_service.process_legal_content(
                    transcript.text, title=video_details.get("title", ""), source_type="youtube"
                )
            
            self.update_state(
                state="PROGRESS",
                meta={"current": 4, "total": 6, "status": "Generating embeddings"}
            )
            
            # Step 4: Generate embeddings
            embedding_results = None
            if transcript:
                # Embed full transcript
                doc_embeddings = await embedding_service.embed_legal_document(
                    transcript.text, title=video_details.get("title", ""), 
                    document_type="youtube_transcript"
                )
                
                # Embed transcript segments
                if transcript.segments:
                    segment_data = [
                        {
                            "id": seg.id,
                            "text": seg.text,
                            "start_time": seg.start_time,
                            "end_time": seg.end_time,
                            "confidence": seg.confidence
                        }
                        for seg in transcript.segments
                    ]
                    segment_embeddings = await embedding_service.embed_transcript_segments(segment_data)
                    embedding_results = {
                        "document": doc_embeddings,
                        "segments": segment_embeddings
                    }
                else:
                    embedding_results = {"document": doc_embeddings}
            
            self.update_state(
                state="PROGRESS",
                meta={"current": 5, "total": 6, "status": "Storing in databases"}
            )
            
            # Step 5: Store in three-database architecture
            content_data = {
                "content_id": str(uuid.uuid4()),
                "source_type": "youtube",
                "source_url": video_url,
                "title": video_details.get("title"),
                "description": video_details.get("description"),
                "duration": video_details.get("duration"),
                "upload_date": video_details.get("upload_date"),
                "channel": video_details.get("channel_title"),
                "transcript": transcript.dict() if transcript else None,
                "nlp_results": nlp_results,
                "embeddings": embedding_results,
                "legal_relevance_score": nlp_results.get("classification", {}).get("overall_relevance", 0.0) if nlp_results else 0.0,
                "processed_at": datetime.now().isoformat(),
                "processed_by_user": user_id
            }
            
            # Sync to all databases
            sync_result = await sync_manager.sync_content(content_data)
            
            self.update_state(
                state="PROGRESS",
                meta={"current": 6, "total": 6, "status": "Processing complete"}
            )
            
            return {
                "status": "completed",
                "content_id": content_data["content_id"],
                "video_url": video_url,
                "title": video_details.get("title"),
                "transcript_length": len(transcript.text) if transcript else 0,
                "legal_entities_count": len(nlp_results.get("entities", {}).get("named_entities", [])) if nlp_results else 0,
                "sync_result": sync_result,
                "processing_time_seconds": 0,  # Will be calculated
                "timestamp": datetime.now().isoformat()
            }
        
        result = run_async_task(process_video())
        logger.info("YouTube video processing completed", result=result)
        return result
        
    except Exception as e:
        logger.error("YouTube video processing failed", video_url=video_url, error=str(e))
        self.update_state(
            state="FAILURE",
            meta={"error": str(e), "traceback": str(e)}
        )
        raise


@celery_app.task(bind=True, name="process_youtube_playlist")
def process_youtube_playlist(self, playlist_url: str, priority: str = "normal",
                           extract_audio: bool = True, transcribe: bool = True,
                           user_id: Optional[str] = None):
    """Process entire YouTube playlist."""
    logger.info("Processing YouTube playlist", url=playlist_url, user_id=user_id)
    
    try:
        async def process_playlist():
            youtube_client = YouTubeClient()
            
            # Get playlist videos
            playlist_details = await youtube_client.get_playlist_details(playlist_url)
            if not playlist_details or not playlist_details.get("videos"):
                raise ValueError(f"Could not extract playlist videos from {playlist_url}")
            
            videos = playlist_details["videos"]
            total_videos = len(videos)
            
            logger.info(f"Processing {total_videos} videos from playlist")
            
            processed_videos = []
            failed_videos = []
            
            for i, video in enumerate(videos, 1):
                try:
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": i, 
                            "total": total_videos, 
                            "status": f"Processing video {i}/{total_videos}: {video.get('title', 'Unknown')}"
                        }
                    )
                    
                    # Process individual video
                    video_task = process_youtube_video.delay(
                        video_url=video["url"],
                        priority=priority,
                        extract_audio=extract_audio,
                        transcribe=transcribe,
                        user_id=user_id
                    )
                    
                    # Wait for video processing to complete
                    video_result = video_task.get()
                    processed_videos.append({
                        "video_url": video["url"],
                        "title": video.get("title"),
                        "result": video_result
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to process video {video.get('url')}: {e}")
                    failed_videos.append({
                        "video_url": video.get("url"),
                        "title": video.get("title"),
                        "error": str(e)
                    })
            
            return {
                "status": "completed",
                "playlist_url": playlist_url,
                "playlist_title": playlist_details.get("title"),
                "total_videos": total_videos,
                "processed_count": len(processed_videos),
                "failed_count": len(failed_videos),
                "processed_videos": processed_videos,
                "failed_videos": failed_videos,
                "timestamp": datetime.now().isoformat()
            }
        
        result = run_async_task(process_playlist())
        logger.info("YouTube playlist processing completed", result=result)
        return result
        
    except Exception as e:
        logger.error("YouTube playlist processing failed", playlist_url=playlist_url, error=str(e))
        raise


@celery_app.task(bind=True, name="scrape_website")
def scrape_website(self, website_url: str, max_depth: int = 3, 
                  respect_robots: bool = True, priority: str = "normal",
                  user_id: Optional[str] = None):
    """Scrape and process legal website content."""
    logger.info("Scraping website", url=website_url, user_id=user_id)
    
    try:
        self.update_state(
            state="PROGRESS",
            meta={"current": 1, "total": 5, "status": "Initializing web scraper"}
        )
        
        async def scrape_and_process():
            # Initialize services
            nlp_service = LegalNLPService()
            embedding_service = LegalEmbeddingService()
            sync_manager = ThreeDatabaseSyncManager()
            
            self.update_state(
                state="PROGRESS",
                meta={"current": 2, "total": 5, "status": "Scraping website content"}
            )
            
            # Scrape website
            async with WebScrapingClient() as scraper:
                scraped_content = await scraper.scrape_url(website_url)
                
                if not scraped_content:
                    raise ValueError(f"No content extracted from {website_url}")
            
            self.update_state(
                state="PROGRESS",
                meta={"current": 3, "total": 5, "status": "Processing legal content"}
            )
            
            # Process with NLP
            nlp_results = await nlp_service.process_legal_content(
                scraped_content.content, 
                title=scraped_content.title or "",
                source_type="website"
            )
            
            self.update_state(
                state="PROGRESS", 
                meta={"current": 4, "total": 5, "status": "Generating embeddings"}
            )
            
            # Generate embeddings
            embedding_results = await embedding_service.embed_legal_document(
                scraped_content.content,
                title=scraped_content.title or "",
                document_type="legal_website"
            )
            
            self.update_state(
                state="PROGRESS",
                meta={"current": 5, "total": 5, "status": "Storing in databases"}
            )
            
            # Store in databases
            content_data = {
                "content_id": str(uuid.uuid4()),
                "source_type": "website",
                "source_url": website_url,
                "title": scraped_content.title,
                "content": scraped_content.content,
                "summary": scraped_content.summary,
                "author": scraped_content.author,
                "published_date": scraped_content.published_date.isoformat() if scraped_content.published_date else None,
                "domain": scraped_content.source_domain,
                "metadata": scraped_content.metadata,
                "nlp_results": nlp_results,
                "embeddings": embedding_results,
                "legal_relevance_score": scraped_content.legal_relevance_score,
                "processed_at": datetime.now().isoformat(),
                "processed_by_user": user_id
            }
            
            sync_result = await sync_manager.sync_content(content_data)
            
            return {
                "status": "completed",
                "content_id": content_data["content_id"],
                "website_url": website_url,
                "title": scraped_content.title,
                "content_length": len(scraped_content.content),
                "legal_relevance_score": scraped_content.legal_relevance_score,
                "legal_entities_count": len(nlp_results.get("entities", {}).get("named_entities", [])),
                "sync_result": sync_result,
                "timestamp": datetime.now().isoformat()
            }
        
        result = run_async_task(scrape_and_process())
        logger.info("Website scraping completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Website scraping failed", website_url=website_url, error=str(e))
        raise


@celery_app.task(bind=True, name="process_website_batch")
def process_website_batch(self, website_urls: List[str], priority: str = "normal",
                         user_id: Optional[str] = None):
    """Process multiple websites in batch."""
    logger.info("Processing website batch", count=len(website_urls), user_id=user_id)
    
    try:
        total_sites = len(website_urls)
        processed_sites = []
        failed_sites = []
        
        for i, url in enumerate(website_urls, 1):
            try:
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": i,
                        "total": total_sites,
                        "status": f"Processing site {i}/{total_sites}: {url}"
                    }
                )
                
                # Process individual website
                site_task = scrape_website.delay(
                    website_url=url,
                    priority=priority,
                    user_id=user_id
                )
                
                # Wait for completion
                site_result = site_task.get()
                processed_sites.append({
                    "url": url,
                    "result": site_result
                })
                
            except Exception as e:
                logger.error(f"Failed to process website {url}: {e}")
                failed_sites.append({
                    "url": url,
                    "error": str(e)
                })
        
        result = {
            "status": "completed",
            "total_sites": total_sites,
            "processed_count": len(processed_sites),
            "failed_count": len(failed_sites),
            "processed_sites": processed_sites,
            "failed_sites": failed_sites,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("Website batch processing completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Website batch processing failed", error=str(e))
        raise