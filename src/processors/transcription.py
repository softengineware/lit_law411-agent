"""
Audio transcription processing using OpenAI Whisper.

This module provides comprehensive audio transcription capabilities
for legal content, including YouTube videos and audio files.
"""

import asyncio
import logging
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple
from urllib.parse import urlparse

import aiofiles
import aiohttp
import yt_dlp
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from ..core.config import settings
from ..core.logging import get_logger
from ..models.pydantic.transcript import TranscriptSegment, TranscriptResponse
from ..utils.performance_decorators import monitor_performance

logger = get_logger(__name__)


class AudioMetadata(BaseModel):
    """Metadata for audio files."""
    duration_seconds: float
    file_size_bytes: int
    format: str
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bitrate: Optional[int] = None
    source_url: Optional[str] = None
    title: Optional[str] = None
    uploader: Optional[str] = None
    upload_date: Optional[str] = None


class TranscriptionJob(BaseModel):
    """Transcription job tracking."""
    job_id: str
    source_url: str
    audio_path: str
    status: str = "pending"  # pending, processing, completed, failed
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Optional[AudioMetadata] = None
    transcript: Optional[TranscriptResponse] = None


class YouTubeAudioDownloader:
    """Download audio from YouTube videos using yt-dlp."""
    
    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = Path(download_dir or tempfile.gettempdir()) / "legal_audio"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # yt-dlp configuration for audio extraction
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.download_dir / '%(id)s.%(ext)s'),
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '192K',
            'noplaylist': True,
            'writeinfojson': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': True,
        }
    
    @monitor_performance
    async def download_audio(self, video_url: str) -> Tuple[str, AudioMetadata]:
        """Download audio from YouTube video."""
        try:
            # Extract video ID
            video_id = self._extract_video_id(video_url)
            if not video_id:
                raise ValueError(f"Could not extract video ID from URL: {video_url}")
            
            logger.info(f"Starting audio download for video: {video_id}")
            
            # Check if already downloaded
            existing_file = await self._find_existing_audio(video_id)
            if existing_file:
                logger.info(f"Using existing audio file: {existing_file}")
                metadata = await self._get_audio_metadata(existing_file, video_url)
                return str(existing_file), metadata
            
            # Download using yt-dlp in thread pool
            loop = asyncio.get_event_loop()
            audio_path, info = await loop.run_in_executor(
                None, self._download_sync, video_url
            )
            
            # Create metadata
            metadata = AudioMetadata(
                duration_seconds=info.get('duration', 0),
                file_size_bytes=os.path.getsize(audio_path),
                format='mp3',
                source_url=video_url,
                title=info.get('title'),
                uploader=info.get('uploader'),
                upload_date=info.get('upload_date')
            )
            
            logger.info(f"Audio download completed: {audio_path}")
            return audio_path, metadata
            
        except Exception as e:
            logger.error(f"Error downloading audio from {video_url}: {e}")
            raise
    
    def _download_sync(self, video_url: str) -> Tuple[str, Dict[str, Any]]:
        """Synchronous download using yt-dlp."""
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            # Extract info first
            info = ydl.extract_info(video_url, download=False)
            video_id = info['id']
            
            # Download audio
            ydl.download([video_url])
            
            # Find downloaded file
            for ext in ['mp3', 'm4a', 'webm']:
                audio_path = self.download_dir / f"{video_id}.{ext}"
                if audio_path.exists():
                    return str(audio_path), info
            
            raise RuntimeError(f"Downloaded audio file not found for {video_id}")
    
    def _extract_video_id(self, video_url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        try:
            if 'youtube.com/watch?v=' in video_url:
                return video_url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in video_url:
                return video_url.split('youtu.be/')[1].split('?')[0]
            elif len(video_url) == 11:  # Direct video ID
                return video_url
            return None
        except (IndexError, AttributeError):
            return None
    
    async def _find_existing_audio(self, video_id: str) -> Optional[Path]:
        """Find existing downloaded audio file."""
        for ext in ['mp3', 'm4a', 'webm']:
            audio_path = self.download_dir / f"{video_id}.{ext}"
            if audio_path.exists():
                return audio_path
        return None
    
    async def _get_audio_metadata(self, audio_path: str, source_url: str) -> AudioMetadata:
        """Get metadata for existing audio file."""
        file_path = Path(audio_path)
        file_size = file_path.stat().st_size
        
        # Try to read info from JSON file
        info_path = file_path.with_suffix('.info.json')
        info = {}
        if info_path.exists():
            import json
            async with aiofiles.open(info_path, 'r') as f:
                content = await f.read()
                info = json.loads(content)
        
        return AudioMetadata(
            duration_seconds=info.get('duration', 0),
            file_size_bytes=file_size,
            format=file_path.suffix[1:],  # Remove dot
            source_url=source_url,
            title=info.get('title'),
            uploader=info.get('uploader'),
            upload_date=info.get('upload_date')
        )
    
    async def cleanup_old_files(self, max_age_days: int = 7):
        """Remove old downloaded audio files."""
        try:
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            
            for file_path in self.download_dir.iterdir():
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_time:
                        file_path.unlink()
                        logger.info(f"Cleaned up old audio file: {file_path}")
                        
        except Exception as e:
            logger.error(f"Error during audio cleanup: {e}")


class WhisperTranscriber:
    """OpenAI Whisper-based transcription service."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.max_file_size_mb = 25  # OpenAI Whisper limit
        self.supported_formats = {'.mp3', '.m4a', '.wav', '.webm', '.mp4'}
    
    @monitor_performance
    async def transcribe_audio(self, audio_path: str, 
                             language: Optional[str] = None,
                             prompt: Optional[str] = None) -> TranscriptResponse:
        """Transcribe audio file using OpenAI Whisper."""
        try:
            audio_file_path = Path(audio_path)
            
            # Validate file
            await self._validate_audio_file(audio_file_path)
            
            logger.info(f"Starting transcription for: {audio_file_path.name}")
            
            # Prepare legal context prompt
            legal_prompt = self._create_legal_prompt(prompt)
            
            # Transcribe with timestamps
            transcript_response = await self._transcribe_with_whisper(
                audio_file_path, language, legal_prompt
            )
            
            # Process and enhance transcript
            enhanced_transcript = await self._enhance_legal_transcript(transcript_response)
            
            logger.info(f"Transcription completed for: {audio_file_path.name}")
            return enhanced_transcript
            
        except Exception as e:
            logger.error(f"Error transcribing {audio_path}: {e}")
            raise
    
    async def _validate_audio_file(self, audio_path: Path):
        """Validate audio file for transcription."""
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        if audio_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Unsupported audio format: {audio_path.suffix}")
        
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            raise ValueError(f"Audio file too large: {file_size_mb:.1f}MB (max: {self.max_file_size_mb}MB)")
    
    def _create_legal_prompt(self, custom_prompt: Optional[str] = None) -> str:
        """Create legal context prompt for better transcription."""
        base_prompt = """This is a legal discussion that may include:
- Case names and citations
- Legal terminology and statutes
- Court procedures and motions
- Family law terms (divorce, custody, support)
- Virginia law references
- Lawyer and client conversations"""
        
        if custom_prompt:
            return f"{base_prompt}\n\nAdditional context: {custom_prompt}"
        
        return base_prompt
    
    async def _transcribe_with_whisper(self, audio_path: Path, 
                                     language: Optional[str],
                                     prompt: str) -> Dict[str, Any]:
        """Call OpenAI Whisper API for transcription."""
        try:
            async with aiofiles.open(audio_path, 'rb') as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    language=language,
                    prompt=prompt[:224] if prompt else None,  # OpenAI prompt limit
                    timestamp_granularities=["segment"]
                )
                
                return transcript.model_dump()
                
        except Exception as e:
            logger.error(f"OpenAI Whisper API error: {e}")
            raise
    
    async def _enhance_legal_transcript(self, raw_transcript: Dict[str, Any]) -> TranscriptResponse:
        """Enhance transcript with legal-specific processing."""
        # Extract segments with timestamps
        segments = []
        for segment in raw_transcript.get('segments', []):
            transcript_segment = TranscriptSegment(
                id=segment.get('id', 0),
                start_time=segment.get('start', 0.0),
                end_time=segment.get('end', 0.0),
                text=segment.get('text', '').strip(),
                confidence=segment.get('confidence', 0.0)
            )
            segments.append(transcript_segment)
        
        # Clean and process full text
        full_text = raw_transcript.get('text', '')
        processed_text = self._clean_legal_text(full_text)
        
        # Extract legal entities and terms
        legal_entities = self._extract_legal_entities(processed_text)
        
        return TranscriptResponse(
            text=processed_text,
            language=raw_transcript.get('language', 'en'),
            duration=raw_transcript.get('duration', 0.0),
            segments=segments,
            legal_entities=legal_entities,
            confidence_score=self._calculate_average_confidence(segments),
            word_count=len(processed_text.split()),
            processing_time_seconds=0.0  # Will be set by decorator
        )
    
    def _clean_legal_text(self, text: str) -> str:
        """Clean and format legal transcript text."""
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Capitalize legal terms properly
        legal_terms = [
            'virginia', 'circuit court', 'supreme court', 'family court',
            'divorce', 'custody', 'child support', 'alimony', 'motion',
            'petition', 'hearing', 'trial', 'judge', 'attorney', 'counsel'
        ]
        
        for term in legal_terms:
            # Simple capitalization (could be enhanced with NLP)
            text = text.replace(f' {term} ', f' {term.title()} ')
            text = text.replace(f' {term}.', f' {term.title()}.')
            text = text.replace(f' {term},', f' {term.title()},')
        
        return text
    
    def _extract_legal_entities(self, text: str) -> List[str]:
        """Extract legal entities from transcript text."""
        entities = []
        text_lower = text.lower()
        
        # Virginia Code references
        import re
        va_code_pattern = r'virginia code (?:section )?(\d+[.-]\d+(?:[.-]\d+)*)'
        entities.extend(re.findall(va_code_pattern, text_lower))
        
        # Case citations (simplified)
        case_pattern = r'([A-Z][a-z]+ v\.? [A-Z][a-z]+)'
        entities.extend(re.findall(case_pattern, text))
        
        # Court names
        court_pattern = r'(circuit court|supreme court|district court|family court)'
        entities.extend(re.findall(court_pattern, text_lower))
        
        return list(set(entities))  # Remove duplicates
    
    def _calculate_average_confidence(self, segments: List[TranscriptSegment]) -> float:
        """Calculate average confidence score across segments."""
        if not segments:
            return 0.0
        
        confidences = [seg.confidence for seg in segments if seg.confidence > 0]
        return sum(confidences) / len(confidences) if confidences else 0.0


class TranscriptionQueue:
    """Manage transcription jobs with queue and retry logic."""
    
    def __init__(self):
        self.jobs: Dict[str, TranscriptionJob] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.max_retries = 3
        self.processing = False
    
    async def add_job(self, source_url: str, audio_path: str) -> str:
        """Add transcription job to queue."""
        job_id = f"job_{int(time.time())}_{len(self.jobs)}"
        
        job = TranscriptionJob(
            job_id=job_id,
            source_url=source_url,
            audio_path=audio_path
        )
        
        self.jobs[job_id] = job
        await self.queue.put(job_id)
        
        logger.info(f"Added transcription job: {job_id}")
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[TranscriptionJob]:
        """Get job status and results."""
        return self.jobs.get(job_id)
    
    async def process_queue(self, transcriber: WhisperTranscriber):
        """Process transcription queue."""
        if self.processing:
            return
        
        self.processing = True
        logger.info("Starting transcription queue processing")
        
        try:
            while not self.queue.empty():
                job_id = await self.queue.get()
                job = self.jobs.get(job_id)
                
                if not job:
                    continue
                
                try:
                    await self._process_job(job, transcriber)
                except Exception as e:
                    await self._handle_job_error(job, e)
                
        finally:
            self.processing = False
            logger.info("Transcription queue processing completed")
    
    async def _process_job(self, job: TranscriptionJob, transcriber: WhisperTranscriber):
        """Process individual transcription job."""
        try:
            job.status = "processing"
            job.started_at = datetime.now()
            
            logger.info(f"Processing transcription job: {job.job_id}")
            
            # Transcribe audio
            transcript = await transcriber.transcribe_audio(job.audio_path)
            
            # Update job with results
            job.transcript = transcript
            job.status = "completed"
            job.completed_at = datetime.now()
            
            logger.info(f"Transcription job completed: {job.job_id}")
            
        except Exception as e:
            raise e
    
    async def _handle_job_error(self, job: TranscriptionJob, error: Exception):
        """Handle job processing error with retry logic."""
        job.retry_count += 1
        job.error_message = str(error)
        
        if job.retry_count <= self.max_retries:
            job.status = "pending"
            await self.queue.put(job.job_id)
            logger.warning(f"Retrying job {job.job_id} (attempt {job.retry_count})")
        else:
            job.status = "failed"
            job.completed_at = datetime.now()
            logger.error(f"Job {job.job_id} failed after {self.max_retries} retries: {error}")


class TranscriptionService:
    """Main transcription service combining all components."""
    
    def __init__(self, download_dir: Optional[str] = None):
        self.downloader = YouTubeAudioDownloader(download_dir)
        self.transcriber = WhisperTranscriber()
        self.queue = TranscriptionQueue()
    
    @monitor_performance
    async def transcribe_youtube_video(self, video_url: str, 
                                     language: Optional[str] = None) -> TranscriptResponse:
        """Complete transcription workflow for YouTube video."""
        try:
            logger.info(f"Starting transcription workflow for: {video_url}")
            
            # Download audio
            audio_path, metadata = await self.downloader.download_audio(video_url)
            
            # Transcribe audio
            transcript = await self.transcriber.transcribe_audio(
                audio_path, language
            )
            
            # Add metadata to transcript
            transcript.source_metadata = metadata.dict()
            
            logger.info(f"Transcription workflow completed for: {video_url}")
            return transcript
            
        except Exception as e:
            logger.error(f"Error in transcription workflow for {video_url}: {e}")
            raise
    
    async def queue_transcription(self, video_url: str) -> str:
        """Queue video for batch transcription."""
        try:
            # Download audio first
            audio_path, metadata = await self.downloader.download_audio(video_url)
            
            # Add to queue
            job_id = await self.queue.add_job(video_url, audio_path)
            
            # Store metadata in job
            job = await self.queue.get_job_status(job_id)
            if job:
                job.metadata = metadata
            
            return job_id
            
        except Exception as e:
            logger.error(f"Error queuing transcription for {video_url}: {e}")
            raise
    
    async def process_transcription_queue(self):
        """Process all queued transcriptions."""
        await self.queue.process_queue(self.transcriber)
    
    async def get_transcription_status(self, job_id: str) -> Optional[TranscriptionJob]:
        """Get status of queued transcription."""
        return await self.queue.get_job_status(job_id)
    
    async def cleanup_old_audio(self, max_age_days: int = 7):
        """Clean up old downloaded audio files."""
        await self.downloader.cleanup_old_files(max_age_days)


# Export main components
__all__ = [
    'TranscriptionService',
    'YouTubeAudioDownloader',
    'WhisperTranscriber',
    'TranscriptionQueue',
    'AudioMetadata',
    'TranscriptionJob'
]