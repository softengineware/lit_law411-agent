"""Tests for YouTube API client."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Mock settings before importing
with patch('src.core.config.Settings') as mock_settings_class:
    mock_settings = Mock()
    mock_settings.youtube_api_key = "test_api_key"
    mock_settings_class.return_value = mock_settings
    
    from src.scrapers.youtube import (
        YouTubeClient, 
        YouTubeQuotaManager, 
        VideoMetadata, 
        SearchResult,
        get_youtube_client
    )


@pytest.fixture
def mock_youtube_service():
    """Mock YouTube API service."""
    return Mock()


@pytest.fixture
def youtube_client(mock_youtube_service):
    """Create YouTube client with mocked service."""
    with patch('src.scrapers.youtube.build') as mock_build:
        mock_build.return_value = mock_youtube_service
        client = YouTubeClient(api_key="test_api_key")
        return client


class TestYouTubeQuotaManager:
    """Test quota management functionality."""
    
    def test_quota_manager_init(self):
        """Test quota manager initialization."""
        manager = YouTubeQuotaManager(daily_quota=1000)
        assert manager.daily_quota == 1000
        assert manager.used_quota == 0
        assert 'search' in manager.operation_costs
        assert manager.operation_costs['search'] == 100
    
    def test_check_quota_within_limit(self):
        """Test quota check when within limit."""
        manager = YouTubeQuotaManager(daily_quota=1000)
        assert manager.check_quota('search', 1) is True
        assert manager.check_quota('videos', 10) is True
    
    def test_check_quota_exceeds_limit(self):
        """Test quota check when exceeding limit."""
        manager = YouTubeQuotaManager(daily_quota=50)
        assert manager.check_quota('search', 1) is False  # search costs 100 units
    
    def test_use_quota(self):
        """Test quota usage tracking."""
        manager = YouTubeQuotaManager(daily_quota=1000)
        manager.use_quota('search', 1)
        assert manager.used_quota == 100
        
        manager.use_quota('videos', 5)
        assert manager.used_quota == 105


class TestYouTubeClient:
    """Test YouTube client functionality."""
    
    def test_client_initialization(self, youtube_client):
        """Test client initialization."""
        assert youtube_client.api_key == "test_api_key"
        assert isinstance(youtube_client.quota_manager, YouTubeQuotaManager)
        assert len(youtube_client.legal_keywords) > 0
    
    def test_client_initialization_no_api_key(self):
        """Test client initialization without API key."""
        with patch('src.scrapers.youtube.settings') as mock_settings:
            mock_settings.youtube_api_key = None
            with patch('src.scrapers.youtube.build'):
                with pytest.raises(ValueError, match="YouTube API key is required"):
                    YouTubeClient()
    
    def test_extract_video_id_standard_url(self, youtube_client):
        """Test video ID extraction from standard YouTube URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = youtube_client.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_short_url(self, youtube_client):
        """Test video ID extraction from short YouTube URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = youtube_client.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_embed_url(self, youtube_client):
        """Test video ID extraction from embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        video_id = youtube_client.extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_just_id(self, youtube_client):
        """Test video ID extraction from just the ID."""
        video_id = youtube_client.extract_video_id("dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_video_id_invalid(self, youtube_client):
        """Test video ID extraction from invalid URL."""
        video_id = youtube_client.extract_video_id("not_a_youtube_url")
        assert video_id is None
    
    def test_is_legal_content_positive(self, youtube_client):
        """Test legal content detection - positive case."""
        title = "Constitutional Law Lecture - Supreme Court Cases"
        description = "This video covers important constitutional law principles..."
        
        assert youtube_client._is_legal_content(title, description) is True
    
    def test_is_legal_content_negative(self, youtube_client):
        """Test legal content detection - negative case."""
        title = "Cooking Tutorial - How to Make Pasta"
        description = "Learn to cook delicious pasta at home..."
        
        assert youtube_client._is_legal_content(title, description) is False
    
    def test_get_video_details_success(self, youtube_client, mock_youtube_service):
        """Test successful video details retrieval."""
        # Mock API response
        mock_response = {
            'items': [{
                'snippet': {
                    'title': 'Contract Law Basics',
                    'description': 'Introduction to contract law principles',
                    'channelTitle': 'Law School',
                    'channelId': 'UC123456789',
                    'publishedAt': '2023-01-01T00:00:00Z',
                    'tags': ['law', 'contracts'],
                    'categoryId': '27',
                    'defaultLanguage': 'en',
                    'thumbnails': {
                        'high': {'url': 'http://example.com/thumb.jpg'}
                    }
                },
                'statistics': {
                    'viewCount': '1000',
                    'likeCount': '50',
                    'commentCount': '10'
                },
                'contentDetails': {
                    'duration': 'PT10M30S'
                }
            }]
        }
        
        # Mock the API call
        mock_request = Mock()
        mock_request.execute.return_value = mock_response
        mock_youtube_service.videos.return_value.list.return_value = mock_request
        
        # Mock captions check
        with patch.object(youtube_client, '_check_captions_available', return_value=True):
            result = youtube_client.get_video_details("test_video_id")
        
        assert isinstance(result, VideoMetadata)
        assert result.title == "Contract Law Basics"
        assert result.channel_title == "Law School"
        assert result.view_count == 1000
        assert result.captions_available is True
    
    def test_get_video_details_not_found(self, youtube_client, mock_youtube_service):
        """Test video details retrieval when video not found."""
        # Mock empty response
        mock_response = {'items': []}
        
        mock_request = Mock()
        mock_request.execute.return_value = mock_response
        mock_youtube_service.videos.return_value.list.return_value = mock_request
        
        result = youtube_client.get_video_details("nonexistent_video")
        assert result is None
    
    def test_get_video_details_quota_exceeded(self, youtube_client):
        """Test video details retrieval when quota exceeded."""
        # Mock quota manager to return False
        youtube_client.quota_manager.check_quota = Mock(return_value=False)
        
        result = youtube_client.get_video_details("test_video_id")
        assert result is None
    
    def test_search_videos_success(self, youtube_client, mock_youtube_service):
        """Test successful video search."""
        # Mock search response
        mock_response = {
            'items': [{
                'id': {'videoId': 'abc123'},
                'snippet': {
                    'title': 'Employment Law Basics',
                    'description': 'Learn about employment law fundamentals',
                    'channelTitle': 'Legal Education',
                    'channelId': 'UC987654321',
                    'publishedAt': '2023-01-01T00:00:00Z',
                    'thumbnails': {
                        'high': {'url': 'http://example.com/thumb.jpg'}
                    }
                }
            }],
            'nextPageToken': None
        }
        
        mock_request = Mock()
        mock_request.execute.return_value = mock_response
        mock_youtube_service.search.return_value.list.return_value = mock_request
        
        results = youtube_client.search_videos("employment law", max_results=10)
        
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "Employment Law Basics"
        assert results[0].video_id == "abc123"
    
    def test_search_videos_quota_exceeded(self, youtube_client):
        """Test video search when quota exceeded."""
        youtube_client.quota_manager.check_quota = Mock(return_value=False)
        
        results = youtube_client.search_videos("law", max_results=10)
        assert results == []


class TestFactoryFunction:
    """Test factory function."""
    
    @patch('src.scrapers.youtube.YouTubeClient')
    def test_get_youtube_client(self, mock_client_class):
        """Test factory function."""
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance
        
        client = get_youtube_client("test_key")
        
        mock_client_class.assert_called_once_with(api_key="test_key")
        assert client == mock_instance
    
    @patch('src.scrapers.youtube.YouTubeClient')
    def test_get_youtube_client_no_key(self, mock_client_class):
        """Test factory function without API key."""
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance
        
        client = get_youtube_client()
        
        mock_client_class.assert_called_once_with(api_key=None)
        assert client == mock_instance