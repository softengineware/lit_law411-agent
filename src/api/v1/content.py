"""Content ingestion and management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
import structlog

from src.core.auth import get_current_active_user
from src.models.pydantic.content import ContentCreate, ContentResponse
from src.models.pydantic.auth import User
from src.workers.tasks import (
    process_youtube_video,
    process_youtube_playlist,
    scrape_website,
    process_website_batch
)

logger = structlog.get_logger()

router = APIRouter(prefix="/content", tags=["content"])


class YouTubeIngestRequest(BaseModel):
    """Request model for YouTube content ingestion."""
    url: HttpUrl
    priority: str = "normal"  # low, normal, high
    extract_audio: bool = True
    transcribe: bool = True


class WebsiteIngestRequest(BaseModel):
    """Request model for website content ingestion."""
    url: HttpUrl
    priority: str = "normal"
    max_depth: int = 3
    respect_robots: bool = True


class BatchIngestRequest(BaseModel):
    """Request model for batch content ingestion."""
    urls: List[HttpUrl]
    content_type: str  # "youtube" or "website"
    priority: str = "normal"


class IngestResponse(BaseModel):
    """Response model for content ingestion."""
    job_id: str
    message: str
    status: str = "queued"
    estimated_time: Optional[str] = None


@router.post("/ingest/youtube", response_model=IngestResponse)
async def ingest_youtube_content(
    request: YouTubeIngestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """
    Ingest content from a YouTube video or playlist.
    
    This endpoint will:
    1. Extract video metadata
    2. Download audio (if requested)
    3. Transcribe audio (if requested)
    4. Extract legal entities
    5. Store in all three databases (Airtable, Supabase, Pinecone)
    """
    try:
        logger.info("YouTube ingestion requested", 
                   url=str(request.url), 
                   user_id=current_user.id)
        
        # Determine if it's a video or playlist
        url_str = str(request.url)
        if "playlist" in url_str or "list=" in url_str:
            task = process_youtube_playlist.delay(
                playlist_url=url_str,
                priority=request.priority,
                extract_audio=request.extract_audio,
                transcribe=request.transcribe,
                user_id=current_user.id
            )
            estimated_time = "10-30 minutes per video"
        else:
            task = process_youtube_video.delay(
                video_url=url_str,
                priority=request.priority,
                extract_audio=request.extract_audio,
                transcribe=request.transcribe,
                user_id=current_user.id
            )
            estimated_time = "5-15 minutes"
        
        return IngestResponse(
            job_id=task.id,
            message="YouTube content ingestion queued successfully",
            estimated_time=estimated_time
        )
        
    except Exception as e:
        logger.error("YouTube ingestion failed", error=str(e), url=str(request.url))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue YouTube ingestion: {str(e)}"
        )


@router.post("/ingest/website", response_model=IngestResponse)
async def ingest_website_content(
    request: WebsiteIngestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """
    Ingest content from a legal website.
    
    This endpoint will:
    1. Crawl the website respectfully
    2. Extract legal content (forms, procedures, statutes)
    3. Process and clean the content
    4. Extract legal entities
    5. Store in all three databases
    """
    try:
        logger.info("Website ingestion requested", 
                   url=str(request.url), 
                   user_id=current_user.id)
        
        task = scrape_website.delay(
            website_url=str(request.url),
            max_depth=request.max_depth,
            respect_robots=request.respect_robots,
            priority=request.priority,
            user_id=current_user.id
        )
        
        return IngestResponse(
            job_id=task.id,
            message="Website content ingestion queued successfully",
            estimated_time="2-10 minutes depending on site size"
        )
        
    except Exception as e:
        logger.error("Website ingestion failed", error=str(e), url=str(request.url))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue website ingestion: {str(e)}"
        )


@router.post("/ingest/batch", response_model=IngestResponse)
async def ingest_batch_content(
    request: BatchIngestRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """
    Ingest multiple pieces of content in batch.
    
    Useful for processing all identified Virginia legal websites
    or multiple YouTube playlists at once.
    """
    try:
        logger.info("Batch ingestion requested", 
                   count=len(request.urls),
                   content_type=request.content_type,
                   user_id=current_user.id)
        
        if request.content_type == "website":
            task = process_website_batch.delay(
                website_urls=[str(url) for url in request.urls],
                priority=request.priority,
                user_id=current_user.id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch YouTube processing not yet implemented"
            )
        
        return IngestResponse(
            job_id=task.id,
            message=f"Batch ingestion of {len(request.urls)} {request.content_type} URLs queued",
            estimated_time=f"{len(request.urls) * 5}-{len(request.urls) * 15} minutes"
        )
        
    except Exception as e:
        logger.error("Batch ingestion failed", error=str(e), count=len(request.urls))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue batch ingestion: {str(e)}"
        )


@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get the status of a content ingestion job."""
    try:
        # Import here to avoid circular imports
        from src.workers.tasks import celery_app
        
        task = celery_app.AsyncResult(job_id)
        
        if task.state == "PENDING":
            response = {
                "job_id": job_id,
                "status": "pending",
                "message": "Job is waiting to be processed"
            }
        elif task.state == "PROGRESS":
            response = {
                "job_id": job_id,
                "status": "in_progress",
                "message": task.info.get('message', 'Processing'),
                "progress": task.info.get('progress', 0)
            }
        elif task.state == "SUCCESS":
            response = {
                "job_id": job_id,
                "status": "completed",
                "message": "Job completed successfully",
                "result": task.info
            }
        else:  # FAILURE
            response = {
                "job_id": job_id,
                "status": "failed",
                "message": str(task.info),
                "error": True
            }
        
        return response
        
    except Exception as e:
        logger.error("Failed to get job status", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job status: {str(e)}"
        )


@router.post("/process-all-virginia-sites")
async def process_all_virginia_legal_sites(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """
    Convenience endpoint to process all identified Virginia legal websites.
    
    This will trigger the complete MVP data extraction process.
    """
    try:
        # List of all identified Virginia legal websites
        virginia_sites = [
            "https://www.vacourts.gov",
            "https://selfhelp.vacourts.gov", 
            "https://law.lis.virginia.gov",
            "https://www.fairfaxcounty.gov/circuit",
            "https://www.chesterfield.gov/government/departments-services/circuit-court",
            "https://www.henrico.us/services/circuit-court",
            "https://www.loudoun.gov/government/offices-departments/circuit-court",
            "https://www.pwcgov.org/government/dept/courts/pages/circuit-court.aspx",
            "https://www.vbgov.com/government/departments/circuit-court",
            "https://www.norfolk.gov/government/city-departments/circuit-court-clerk",
            "https://www.rva.gov/circuit-court-clerk",
            "https://www.alexandriava.gov/government/city-departments/circuit-court-clerk",
            "https://www.arlingtonva.us/government/departments/circuit-court-clerk",
            "https://www.newport-news.org/government/departments/circuit-court-clerk",
            "https://www.hampton.gov/government/departments/circuit-court-clerk",
            "https://www.portsmouthva.gov/government/departments/circuit-court-clerk",
            "https://www.suffolkva.us/government/departments/circuit-court-clerk",
            "https://www.chesapeake.va.us/government/departments/circuit-court-clerk",
            "https://www.danville-va.gov/government/departments/circuit-court-clerk",
            "https://www.lynchburgva.gov/circuit-court-clerk"
        ]
        
        logger.info("Processing all Virginia legal sites", 
                   site_count=len(virginia_sites),
                   user_id=current_user.id)
        
        task = process_website_batch.delay(
            website_urls=virginia_sites,
            priority="high",
            user_id=current_user.id
        )
        
        return IngestResponse(
            job_id=task.id,
            message=f"Processing all {len(virginia_sites)} Virginia legal websites",
            estimated_time="2-4 hours for complete processing"
        )
        
    except Exception as e:
        logger.error("Failed to process Virginia sites", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process Virginia legal sites: {str(e)}"
        )


@router.post("/process-youtube-playlists")
async def process_approved_youtube_playlists(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    """
    Convenience endpoint to process all approved YouTube playlists.
    
    This processes the 8 approved playlists from branchechols@gmail.com.
    """
    try:
        # Would need actual playlist URLs - placeholder for now
        approved_playlists = [
            # These would be the actual playlist URLs from the user's account
            # "https://www.youtube.com/playlist?list=...", 
        ]
        
        if not approved_playlists:
            return {
                "message": "No approved playlists configured. Please add playlist URLs to process.",
                "status": "no_content"
            }
        
        logger.info("Processing approved YouTube playlists", 
                   playlist_count=len(approved_playlists),
                   user_id=current_user.id)
        
        # Process each playlist individually
        job_ids = []
        for playlist_url in approved_playlists:
            task = process_youtube_playlist.delay(
                playlist_url=playlist_url,
                priority="high",
                extract_audio=True,
                transcribe=True,
                user_id=current_user.id
            )
            job_ids.append(task.id)
        
        return {
            "message": f"Processing {len(approved_playlists)} YouTube playlists",
            "job_ids": job_ids,
            "estimated_time": "1-3 hours depending on playlist sizes"
        }
        
    except Exception as e:
        logger.error("Failed to process YouTube playlists", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process YouTube playlists: {str(e)}"
        )