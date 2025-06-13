"""Tests for YouTube playlist functionality."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Mock settings before importing
with patch('src.core.config.Settings') as mock_settings_class:
    mock_settings = Mock()
    mock_settings.youtube_api_key = "test_api_key"
    mock_settings_class.return_value = mock_settings
    
    from src.scrapers.youtube import (
        YouTubeClient, 
        PlaylistMetadata, 
        PlaylistItem,
        VideoMetadata
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


class TestPlaylistOperations:
    """Test playlist-related operations."""
    
    def test_get_channel_playlists_success(self, youtube_client, mock_youtube_service):
        """Test successful playlist retrieval."""
        # Mock playlists response
        mock_response = {
            'items': [{
                'id': 'PLrAXtmrdJttlsP9kd_8TlnhTPL2JQJeKR',
                'snippet': {
                    'title': 'Constitutional Law Lectures',
                    'description': 'Series on constitutional law and civil rights',
                    'channelTitle': 'Law School',
                    'channelId': 'UC123456789',
                    'publishedAt': '2023-01-01T00:00:00Z',
                    'thumbnails': {
                        'high': {'url': 'http://example.com/thumb.jpg'}
                    }
                },
                'contentDetails': {
                    'itemCount': 25
                }
            }],
            'nextPageToken': None
        }
        
        # Mock the API call
        mock_request = Mock()
        mock_request.execute.return_value = mock_response
        mock_youtube_service.playlists.return_value.list.return_value = mock_request
        
        result = youtube_client.get_channel_playlists("UC123456789")
        
        assert len(result) == 1
        assert isinstance(result[0], PlaylistMetadata)
        assert result[0].title == "Constitutional Law Lectures"
        assert result[0].video_count == 25
        assert "constitutional" in result[0].description.lower()
    
    def test_get_channel_playlists_no_legal_content(self, youtube_client, mock_youtube_service):
        """Test playlist retrieval with no legal content."""
        # Mock playlists response with non-legal content
        mock_response = {
            'items': [{
                'id': 'PLrAXtmrdJttlsP9kd_8TlnhTPL2JQJeKR',
                'snippet': {
                    'title': 'Cooking Tutorials',
                    'description': 'Learn to cook delicious meals',
                    'channelTitle': 'Cooking Channel',
                    'channelId': 'UC123456789',
                    'publishedAt': '2023-01-01T00:00:00Z'
                },
                'contentDetails': {
                    'itemCount': 10
                }
            }],
            'nextPageToken': None
        }
        
        mock_request = Mock()
        mock_request.execute.return_value = mock_response
        mock_youtube_service.playlists.return_value.list.return_value = mock_request
        
        result = youtube_client.get_channel_playlists("UC123456789")
        
        # Should return empty list since no legal content
        assert len(result) == 0
    
    def test_get_playlist_videos_success(self, youtube_client, mock_youtube_service):
        """Test successful video retrieval from playlist."""
        mock_response = {
            'items': [{
                'snippet': {
                    'title': 'Introduction to Contract Law',
                    'description': 'Basic principles of contract law',
                    'channelTitle': 'Law School',
                    'channelId': 'UC123456789',
                    'publishedAt': '2023-01-01T00:00:00Z',
                    'position': 0,
                    'resourceId': {
                        'videoId': 'abc123def456'
                    },
                    'thumbnails': {
                        'high': {'url': 'http://example.com/thumb.jpg'}
                    }
                }
            }],
            'nextPageToken': None
        }
        
        mock_request = Mock()
        mock_request.execute.return_value = mock_response
        mock_youtube_service.playlistItems.return_value.list.return_value = mock_request
        
        result = youtube_client.get_playlist_videos("PLrAXtmrdJttlsP9kd_8TlnhTPL2JQJeKR")
        
        assert len(result) == 1
        assert isinstance(result[0], PlaylistItem)
        assert result[0].video_id == "abc123def456"
        assert result[0].title == "Introduction to Contract Law"
        assert result[0].position == 0
    
    def test_get_playlist_videos_skip_deleted(self, youtube_client, mock_youtube_service):
        """Test that deleted/private videos are skipped."""
        mock_response = {
            'items': [
                {
                    'snippet': {
                        'title': 'Deleted video',
                        'description': '',
                        'channelTitle': '',
                        'channelId': '',
                        'publishedAt': '2023-01-01T00:00:00Z',
                        'position': 0,
                        'resourceId': {
                            'videoId': 'deleted123'
                        }
                    }
                },
                {
                    'snippet': {
                        'title': 'Valid Contract Law Video',
                        'description': 'Valid legal content',
                        'channelTitle': 'Law School',
                        'channelId': 'UC123456789',
                        'publishedAt': '2023-01-01T00:00:00Z',
                        'position': 1,
                        'resourceId': {
                            'videoId': 'valid123'
                        }
                    }
                }
            ],
            'nextPageToken': None
        }
        
        mock_request = Mock()
        mock_request.execute.return_value = mock_response
        mock_youtube_service.playlistItems.return_value.list.return_value = mock_request
        
        result = youtube_client.get_playlist_videos("PLrAXtmrdJttlsP9kd_8TlnhTPL2JQJeKR")
        
        # Should only return the valid video, skipping deleted one
        assert len(result) == 1
        assert result[0].video_id == "valid123"
    
    def test_bulk_get_video_details(self, youtube_client, mock_youtube_service):
        """Test bulk video details retrieval."""
        mock_response = {
            'items': [{
                'id': 'abc123',
                'snippet': {
                    'title': 'Employment Law Basics',
                    'description': 'Understanding employment law fundamentals',
                    'channelTitle': 'Law School',
                    'channelId': 'UC123456789',
                    'publishedAt': '2023-01-01T00:00:00Z',
                    'tags': ['law', 'employment'],
                    'categoryId': '27'
                },
                'statistics': {
                    'viewCount': '5000',
                    'likeCount': '150'
                },
                'contentDetails': {
                    'duration': 'PT15M30S'
                }
            }]
        }
        
        mock_request = Mock()
        mock_request.execute.return_value = mock_response
        mock_youtube_service.videos.return_value.list.return_value = mock_request
        
        result = youtube_client.bulk_get_video_details(['abc123', 'def456'])
        
        assert len(result) == 1
        assert isinstance(result[0], VideoMetadata)
        assert result[0].video_id == "abc123"
        assert result[0].view_count == 5000
        assert result[0].duration == "PT15M30S"
    
    def test_get_legal_videos_from_channel(self, youtube_client, mock_youtube_service):
        """Test comprehensive legal video extraction from channel."""
        # Mock playlists response
        playlists_response = {
            'items': [{
                'id': 'PL_legal_123',
                'snippet': {
                    'title': 'Constitutional Law',
                    'description': 'Constitutional law lectures',
                    'channelTitle': 'Law School',
                    'channelId': 'UC123456789',
                    'publishedAt': '2023-01-01T00:00:00Z'
                },
                'contentDetails': {
                    'itemCount': 2
                }
            }],
            'nextPageToken': None
        }
        
        # Mock playlist items response
        playlist_items_response = {
            'items': [{
                'snippet': {
                    'title': 'Constitutional Law Video 1',
                    'description': 'First constitutional law video',
                    'channelTitle': 'Law School',
                    'channelId': 'UC123456789',
                    'publishedAt': '2023-01-01T00:00:00Z',
                    'position': 0,
                    'resourceId': {
                        'videoId': 'const_law_1'
                    }
                }
            }],
            'nextPageToken': None
        }
        
        # Setup mocks
        mock_playlists_request = Mock()
        mock_playlists_request.execute.return_value = playlists_response
        mock_youtube_service.playlists.return_value.list.return_value = mock_playlists_request
        
        mock_items_request = Mock()
        mock_items_request.execute.return_value = playlist_items_response
        mock_youtube_service.playlistItems.return_value.list.return_value = mock_items_request
        
        result = youtube_client.get_legal_videos_from_channel("UC123456789")
        
        assert len(result) == 1
        assert "Constitutional Law" in result
        assert len(result["Constitutional Law"]) == 1
        assert result["Constitutional Law"][0].video_id == "const_law_1"
    
    def test_quota_management_for_playlists(self, youtube_client):
        """Test quota management for playlist operations."""
        # Set quota to a low value
        youtube_client.quota_manager.daily_quota = 50
        youtube_client.quota_manager.used_quota = 45
        
        # Should fail quota check for playlists (costs 1 unit, but close to limit)
        result = youtube_client.get_channel_playlists("UC123456789", max_results=100)
        assert result == []
        
        # Should fail quota check for playlist items
        result = youtube_client.get_playlist_videos("PL123456789", max_results=100) 
        assert result == []