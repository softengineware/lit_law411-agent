"""
Tests for transcription functionality.
"""

import asyncio
import pytest
import tempfile
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from datetime import datetime

from src.processors.transcription import (
    TranscriptionService,
    YouTubeAudioDownloader,
    WhisperTranscriber,
    TranscriptionQueue,
    AudioMetadata,
    TranscriptionJob
)
from src.models.pydantic.transcript import TranscriptSegment, TranscriptResponse


class TestYouTubeAudioDownloader:
    """Test YouTube audio downloading."""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = YouTubeAudioDownloader(self.temp_dir)
    
    def test_extract_video_id_from_watch_url(self):
        """Test video ID extraction from standard YouTube URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = self.downloader._extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_from_short_url(self):
        """Test video ID extraction from short YouTube URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = self.downloader._extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_direct(self):
        """Test video ID extraction from direct ID."""
        video_id = self.downloader._extract_video_id("dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_invalid(self):
        """Test video ID extraction from invalid URL."""
        video_id = self.downloader._extract_video_id("https://example.com/invalid")
        assert video_id is None
    
    @pytest.mark.asyncio
    async def test_find_existing_audio(self):
        """Test finding existing audio files."""
        # Create mock audio file
        video_id = "test123"
        audio_path = Path(self.temp_dir) / "legal_audio" / f"{video_id}.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_text("mock audio data")
        
        found_path = await self.downloader._find_existing_audio(video_id)
        assert found_path == audio_path
    
    @pytest.mark.asyncio
    async def test_find_existing_audio_not_found(self):
        """Test finding non-existent audio files."""
        found_path = await self.downloader._find_existing_audio("nonexistent")
        assert found_path is None
    
    @pytest.mark.asyncio
    async def test_get_audio_metadata(self):
        """Test audio metadata extraction."""
        # Create mock audio file
        audio_path = Path(self.temp_dir) / "test.mp3"
        audio_path.write_text("mock audio data")
        
        metadata = await self.downloader._get_audio_metadata(
            str(audio_path), "https://example.com"
        )
        
        assert metadata.file_size_bytes > 0
        assert metadata.format == "mp3"
        assert metadata.source_url == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_download_audio_with_existing_file(self):
        """Test audio download when file already exists."""
        video_url = "https://www.youtube.com/watch?v=test123"
        video_id = "test123"
        
        # Create existing file
        audio_path = self.downloader.download_dir / f"{video_id}.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_text("existing audio data")
        
        result_path, metadata = await self.downloader.download_audio(video_url)
        
        assert Path(result_path) == audio_path
        assert metadata.source_url == video_url
    
    @pytest.mark.asyncio
    async def test_cleanup_old_files(self):
        """Test cleanup of old audio files."""
        # Create old file
        old_file = self.downloader.download_dir / "old_audio.mp3"
        old_file.parent.mkdir(parents=True, exist_ok=True)
        old_file.write_text("old audio")
        
        # Set old modification time
        import os
        old_time = (datetime.now().timestamp() - 86400 * 8)  # 8 days ago
        os.utime(old_file, (old_time, old_time))
        
        await self.downloader.cleanup_old_files(max_age_days=7)
        
        assert not old_file.exists()


class TestWhisperTranscriber:
    """Test Whisper transcription."""
    
    def setup_method(self):
        # Mock OpenAI client
        with patch('src.processors.transcription.AsyncOpenAI') as mock_openai:
            self.transcriber = WhisperTranscriber()
            self.mock_client = mock_openai.return_value
    
    @pytest.mark.asyncio
    async def test_validate_audio_file_success(self):
        """Test audio file validation for valid file."""
        # Create temporary audio file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b"mock audio data")
            audio_path = Path(f.name)
        
        try:
            await self.transcriber._validate_audio_file(audio_path)
            # Should not raise exception
        finally:
            audio_path.unlink()
    
    @pytest.mark.asyncio
    async def test_validate_audio_file_not_found(self):
        """Test audio file validation for missing file."""
        audio_path = Path("/nonexistent/file.mp3")
        
        with pytest.raises(FileNotFoundError):
            await self.transcriber._validate_audio_file(audio_path)
    
    @pytest.mark.asyncio
    async def test_validate_audio_file_unsupported_format(self):
        """Test audio file validation for unsupported format."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"not audio")
            audio_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="Unsupported audio format"):
                await self.transcriber._validate_audio_file(audio_path)
        finally:
            audio_path.unlink()
    
    def test_create_legal_prompt(self):
        """Test legal context prompt creation."""
        prompt = self.transcriber._create_legal_prompt()
        assert "legal discussion" in prompt.lower()
        assert "case names" in prompt.lower()
        assert "virginia law" in prompt.lower()
    
    def test_create_legal_prompt_with_custom(self):
        """Test legal prompt with custom context."""
        custom = "This is about divorce proceedings"
        prompt = self.transcriber._create_legal_prompt(custom)
        assert custom in prompt
        assert "legal discussion" in prompt.lower()
    
    def test_clean_legal_text(self):
        """Test legal text cleaning and formatting."""
        text = "virginia  circuit court   divorce   motion"
        cleaned = self.transcriber._clean_legal_text(text)
        assert "Virginia" in cleaned
        assert "Circuit Court" in cleaned
        assert "Divorce" in cleaned
        assert "Motion" in cleaned
    
    def test_extract_legal_entities(self):
        """Test legal entity extraction from text."""
        text = """
        This case involves Virginia Code section 20-108 and the Supreme Court
        decision in Smith v. Jones regarding custody arrangements.
        """
        entities = self.transcriber._extract_legal_entities(text)
        
        assert any("20-108" in entity for entity in entities)
        assert any("Smith v. Jones" in entity for entity in entities)
        assert any("supreme court" in entity for entity in entities)
    
    def test_calculate_average_confidence(self):
        """Test confidence score calculation."""
        segments = [
            TranscriptSegment(id=1, start_time=0, end_time=5, text="test", confidence=0.9),
            TranscriptSegment(id=2, start_time=5, end_time=10, text="test", confidence=0.8),
            TranscriptSegment(id=3, start_time=10, end_time=15, text="test", confidence=0.7),
        ]
        
        avg_confidence = self.transcriber._calculate_average_confidence(segments)
        assert avg_confidence == 0.8  # (0.9 + 0.8 + 0.7) / 3
    
    def test_calculate_average_confidence_empty(self):
        """Test confidence calculation with no segments."""
        avg_confidence = self.transcriber._calculate_average_confidence([])
        assert avg_confidence == 0.0
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self):
        """Test successful audio transcription."""
        # Create mock audio file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b"mock audio data")
            audio_path = Path(f.name)
        
        # Mock OpenAI response
        mock_response = {
            'text': 'This is about Virginia family law and divorce proceedings.',
            'language': 'en',
            'duration': 120.5,
            'segments': [
                {
                    'id': 0,
                    'start': 0.0,
                    'end': 10.0,
                    'text': 'This is about Virginia family law',
                    'confidence': 0.95
                },
                {
                    'id': 1,
                    'start': 10.0,
                    'end': 20.0,
                    'text': 'and divorce proceedings.',
                    'confidence': 0.88
                }
            ]
        }
        
        # Mock the transcription call
        mock_transcript = Mock()
        mock_transcript.model_dump.return_value = mock_response
        self.mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcript)
        
        try:
            result = await self.transcriber.transcribe_audio(str(audio_path))
            
            assert isinstance(result, TranscriptResponse)
            assert "Virginia family law" in result.text
            assert result.language == "en"
            assert result.duration == 120.5
            assert len(result.segments) == 2
            assert len(result.legal_entities) > 0
            assert result.confidence_score > 0.8
            
        finally:
            audio_path.unlink()


class TestTranscriptionQueue:
    """Test transcription job queue."""
    
    def setup_method(self):
        self.queue = TranscriptionQueue()
    
    @pytest.mark.asyncio
    async def test_add_job(self):
        """Test adding job to queue."""
        job_id = await self.queue.add_job(
            "https://youtube.com/watch?v=test",
            "/path/to/audio.mp3"
        )
        
        assert job_id in self.queue.jobs
        job = self.queue.jobs[job_id]
        assert job.source_url == "https://youtube.com/watch?v=test"
        assert job.audio_path == "/path/to/audio.mp3"
        assert job.status == "pending"
    
    @pytest.mark.asyncio
    async def test_get_job_status(self):
        """Test getting job status."""
        job_id = await self.queue.add_job("https://test.com", "/audio.mp3")
        
        job = await self.queue.get_job_status(job_id)
        assert job is not None
        assert job.job_id == job_id
        
        # Test non-existent job
        no_job = await self.queue.get_job_status("nonexistent")
        assert no_job is None
    
    @pytest.mark.asyncio
    async def test_process_job_success(self):
        """Test successful job processing."""
        job = TranscriptionJob(
            job_id="test_job",
            source_url="https://test.com",
            audio_path="/audio.mp3"
        )
        
        # Mock transcriber
        mock_transcriber = Mock()
        mock_transcript = TranscriptResponse(
            text="Test transcript",
            language="en",
            duration=60.0
        )
        mock_transcriber.transcribe_audio = AsyncMock(return_value=mock_transcript)
        
        await self.queue._process_job(job, mock_transcriber)
        
        assert job.status == "completed"
        assert job.transcript == mock_transcript
        assert job.started_at is not None
        assert job.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_handle_job_error_with_retry(self):
        """Test job error handling with retry."""
        job = TranscriptionJob(
            job_id="test_job",
            source_url="https://test.com",
            audio_path="/audio.mp3"
        )
        
        error = Exception("Transcription failed")
        await self.queue._handle_job_error(job, error)
        
        assert job.retry_count == 1
        assert job.error_message == "Transcription failed"
        assert job.status == "pending"  # Should retry
    
    @pytest.mark.asyncio
    async def test_handle_job_error_max_retries(self):
        """Test job error handling after max retries."""
        job = TranscriptionJob(
            job_id="test_job",
            source_url="https://test.com",
            audio_path="/audio.mp3",
            retry_count=3  # Already at max
        )
        
        error = Exception("Permanent failure")
        await self.queue._handle_job_error(job, error)
        
        assert job.retry_count == 4
        assert job.status == "failed"
        assert job.completed_at is not None


class TestTranscriptionService:
    """Test main transcription service."""
    
    def setup_method(self):
        with patch('src.processors.transcription.AsyncOpenAI'):
            self.service = TranscriptionService()
    
    @pytest.mark.asyncio
    async def test_transcribe_youtube_video_success(self):
        """Test complete YouTube video transcription."""
        video_url = "https://www.youtube.com/watch?v=test123"
        
        # Mock downloader
        mock_metadata = AudioMetadata(
            duration_seconds=120.0,
            file_size_bytes=1024000,
            format="mp3",
            source_url=video_url,
            title="Test Video"
        )
        self.service.downloader.download_audio = AsyncMock(
            return_value=("/path/to/audio.mp3", mock_metadata)
        )
        
        # Mock transcriber
        mock_transcript = TranscriptResponse(
            text="This is a test transcript about Virginia law.",
            language="en",
            duration=120.0
        )
        self.service.transcriber.transcribe_audio = AsyncMock(
            return_value=mock_transcript
        )
        
        result = await self.service.transcribe_youtube_video(video_url)
        
        assert isinstance(result, TranscriptResponse)
        assert result.text == "This is a test transcript about Virginia law."
        assert result.source_metadata == mock_metadata.dict()
    
    @pytest.mark.asyncio
    async def test_queue_transcription(self):
        """Test queuing video for transcription."""
        video_url = "https://www.youtube.com/watch?v=test123"
        
        # Mock downloader
        mock_metadata = AudioMetadata(
            duration_seconds=120.0,
            file_size_bytes=1024000,
            format="mp3"
        )
        self.service.downloader.download_audio = AsyncMock(
            return_value=("/path/to/audio.mp3", mock_metadata)
        )
        
        job_id = await self.service.queue_transcription(video_url)
        
        assert job_id is not None
        job = await self.service.get_transcription_status(job_id)
        assert job is not None
        assert job.source_url == video_url
        assert job.metadata == mock_metadata
    
    @pytest.mark.asyncio
    async def test_process_transcription_queue(self):
        """Test processing the transcription queue."""
        # Add a job first
        video_url = "https://www.youtube.com/watch?v=test123"
        
        mock_metadata = AudioMetadata(
            duration_seconds=120.0,
            file_size_bytes=1024000,
            format="mp3"
        )
        self.service.downloader.download_audio = AsyncMock(
            return_value=("/path/to/audio.mp3", mock_metadata)
        )
        
        # Mock transcriber
        mock_transcript = TranscriptResponse(
            text="Test transcript",
            language="en",
            duration=120.0
        )
        self.service.transcriber.transcribe_audio = AsyncMock(
            return_value=mock_transcript
        )
        
        job_id = await self.service.queue_transcription(video_url)
        
        # Process queue
        await self.service.process_transcription_queue()
        
        # Check job was processed
        job = await self.service.get_transcription_status(job_id)
        assert job.status == "completed"
        assert job.transcript == mock_transcript
    
    @pytest.mark.asyncio
    async def test_cleanup_old_audio(self):
        """Test audio cleanup."""
        self.service.downloader.cleanup_old_files = AsyncMock()
        
        await self.service.cleanup_old_audio(max_age_days=5)
        
        self.service.downloader.cleanup_old_files.assert_called_once_with(5)