"""YouTube Data API v3 client for legal content extraction.

This module provides functionality to:
- Search for legal-related videos
- Extract video metadata and descriptions
- Get video captions/transcripts
- Manage API quotas and rate limits
- Download audio for transcription
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse
import re

import httpx
import yt_dlp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VideoMetadata:
    """YouTube video metadata."""
    video_id: str
    title: str
    description: str
    channel_title: str
    channel_id: str
    published_at: datetime
    duration: Optional[str]
    view_count: Optional[int]
    like_count: Optional[int]
    comment_count: Optional[int]
    tags: List[str]
    category_id: str
    default_language: Optional[str]
    thumbnail_url: Optional[str]
    captions_available: bool = False


@dataclass
class ChannelMetadata:
    """YouTube channel metadata."""
    channel_id: str
    title: str
    description: str
    subscriber_count: Optional[int]
    video_count: Optional[int]
    view_count: Optional[int]
    published_at: datetime
    keywords: List[str]
    country: Optional[str]


@dataclass
class SearchResult:
    """YouTube search result."""
    video_id: str
    title: str
    description: str
    channel_title: str
    channel_id: str
    published_at: datetime
    thumbnail_url: str
    duration: Optional[str] = None


@dataclass
class PlaylistMetadata:
    """YouTube playlist metadata."""
    playlist_id: str
    title: str
    description: str
    channel_title: str
    channel_id: str
    published_at: datetime
    video_count: int
    thumbnail_url: Optional[str]
    privacy_status: str = "public"


@dataclass
class PlaylistItem:
    """YouTube playlist item."""
    video_id: str
    title: str
    description: str
    channel_title: str
    channel_id: str
    published_at: datetime
    position: int
    thumbnail_url: Optional[str]
    playlist_id: str


class YouTubeQuotaManager:
    """Manages YouTube API quota usage."""
    
    def __init__(self, daily_quota: int = 10000):
        """Initialize quota manager.
        
        Args:
            daily_quota: Daily API quota limit
        """
        self.daily_quota = daily_quota
        self.used_quota = 0
        self.reset_time = datetime.now() + timedelta(days=1)
        
        # API operation costs (quota units)
        self.operation_costs = {
            'search': 100,
            'videos': 1,
            'channels': 1,
            'captions': 200,
            'commentThreads': 1,
            'playlists': 1,
            'playlistItems': 1
        }
    
    def check_quota(self, operation: str, count: int = 1) -> bool:
        """Check if operation is within quota.
        
        Args:
            operation: API operation name
            count: Number of operations
            
        Returns:
            True if within quota
        """
        if datetime.now() >= self.reset_time:
            self.reset_quota()
        
        cost = self.operation_costs.get(operation, 1) * count
        return (self.used_quota + cost) <= self.daily_quota
    
    def use_quota(self, operation: str, count: int = 1) -> None:
        """Record quota usage.
        
        Args:
            operation: API operation name
            count: Number of operations
        """
        cost = self.operation_costs.get(operation, 1) * count
        self.used_quota += cost
        logger.info(f"Used {cost} quota units for {operation}. Total: {self.used_quota}/{self.daily_quota}")
    
    def reset_quota(self) -> None:
        """Reset daily quota."""
        self.used_quota = 0
        self.reset_time = datetime.now() + timedelta(days=1)
        logger.info("YouTube API quota reset")


class YouTubeClient:
    """YouTube Data API v3 client with rate limiting and quota management."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize YouTube client.
        
        Args:
            api_key: YouTube Data API v3 key
        """
        self.api_key = api_key or settings.youtube_api_key
        if not self.api_key:
            raise ValueError("YouTube API key is required")
        
        # Build YouTube API service
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
        self.quota_manager = YouTubeQuotaManager()
        
        # Legal content keywords for filtering
        self.legal_keywords = [
            "law", "legal", "court", "attorney", "lawyer", "judge", "case",
            "lawsuit", "litigation", "trial", "hearing", "deposition",
            "contract", "statute", "regulation", "constitutional", "supreme court",
            "federal court", "district court", "appeals court", "criminal law",
            "civil law", "corporate law", "intellectual property", "patent",
            "trademark", "copyright", "employment law", "family law",
            "immigration law", "tax law", "real estate law", "personal injury"
        ]
    
    def _execute_request(self, request):
        """Execute YouTube API request with error handling.
        
        Args:
            request: Google API client request object
            
        Returns:
            API response data
            
        Raises:
            HttpError: On API errors
        """
        try:
            return request.execute()
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            raise
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL.
        
        Args:
            url: YouTube URL
            
        Returns:
            Video ID if found
        """
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def get_video_details(self, video_id: str) -> Optional[VideoMetadata]:
        """Get detailed video information.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Video metadata if found
        """
        if not self.quota_manager.check_quota('videos'):
            logger.warning("YouTube API quota exceeded")
            return None
        
        try:
            request = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=video_id
            )
            
            data = self._execute_request(request)
            self.quota_manager.use_quota('videos')
            
            if not data.get('items'):
                logger.warning(f"Video not found: {video_id}")
                return None
            
            item = data['items'][0]
            snippet = item['snippet']
            statistics = item.get('statistics', {})
            
            # Check if captions are available
            captions_available = self._check_captions_available(video_id)
            
            return VideoMetadata(
                video_id=video_id,
                title=snippet['title'],
                description=snippet['description'],
                channel_title=snippet['channelTitle'],
                channel_id=snippet['channelId'],
                published_at=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                duration=item['contentDetails'].get('duration'),
                view_count=int(statistics.get('viewCount', 0)) if statistics.get('viewCount') else None,
                like_count=int(statistics.get('likeCount', 0)) if statistics.get('likeCount') else None,
                comment_count=int(statistics.get('commentCount', 0)) if statistics.get('commentCount') else None,
                tags=snippet.get('tags', []),
                category_id=snippet.get('categoryId', ''),
                default_language=snippet.get('defaultLanguage'),
                thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url'),
                captions_available=captions_available
            )
            
        except Exception as e:
            logger.error(f"Error getting video details for {video_id}: {e}")
            return None
    
    def _check_captions_available(self, video_id: str) -> bool:
        """Check if captions are available for video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            True if captions available
        """
        try:
            request = self.youtube.captions().list(
                part='snippet',
                videoId=video_id
            )
            
            data = self._execute_request(request)
            return len(data.get('items', [])) > 0
            
        except Exception as e:
            logger.debug(f"Could not check captions for {video_id}: {e}")
            return False
    
    def search_videos(
        self,
        query: str,
        max_results: int = 50,
        published_after: Optional[datetime] = None,
        channel_id: Optional[str] = None,
        order: str = 'relevance'
    ) -> List[SearchResult]:
        """Search for videos with legal content focus.
        
        Args:
            query: Search query
            max_results: Maximum results to return
            published_after: Only videos after this date
            channel_id: Search within specific channel
            order: Sort order (relevance, date, rating, viewCount)
            
        Returns:
            List of search results
        """
        if not self.quota_manager.check_quota('search', max_results // 50 + 1):
            logger.warning("YouTube API quota exceeded")
            return []
        
        results = []
        page_token = None
        
        try:
            while len(results) < max_results:
                # Build request parameters
                request_params = {
                    'part': 'snippet',
                    'q': query,
                    'type': 'video',
                    'maxResults': min(50, max_results - len(results)),
                    'order': order
                }
                
                if published_after:
                    request_params['publishedAfter'] = published_after.isoformat()
                
                if channel_id:
                    request_params['channelId'] = channel_id
                
                if page_token:
                    request_params['pageToken'] = page_token
                
                request = self.youtube.search().list(**request_params)
                data = self._execute_request(request)
                self.quota_manager.use_quota('search')
                
                for item in data.get('items', []):
                    snippet = item['snippet']
                    
                    # Filter for legal relevance
                    if self._is_legal_content(snippet['title'], snippet['description']):
                        results.append(SearchResult(
                            video_id=item['id']['videoId'],
                            title=snippet['title'],
                            description=snippet['description'],
                            channel_title=snippet['channelTitle'],
                            channel_id=snippet['channelId'],
                            published_at=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                            thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', '')
                        ))
                
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            
            logger.info(f"Found {len(results)} legal videos for query: {query}")
            return results[:max_results]
            
        except Exception as e:
            logger.error(f"Error searching videos: {e}")
            return results
    
    def _is_legal_content(self, title: str, description: str) -> bool:
        """Check if content is legal-related.
        
        Args:
            title: Video title
            description: Video description
            
        Returns:
            True if appears to be legal content
        """
        text = f"{title} {description}".lower()
        
        # Check for legal keywords
        for keyword in self.legal_keywords:
            if keyword in text:
                return True
        
        return False
    
    def get_channel_details(self, channel_id: str) -> Optional[ChannelMetadata]:
        """Get channel information.
        
        Args:
            channel_id: YouTube channel ID
            
        Returns:
            Channel metadata if found
        """
        if not self.quota_manager.check_quota('channels'):
            logger.warning("YouTube API quota exceeded")
            return None
        
        try:
            request = self.youtube.channels().list(
                part='snippet,statistics',
                id=channel_id
            )
            
            data = self._execute_request(request)
            self.quota_manager.use_quota('channels')
            
            if not data.get('items'):
                logger.warning(f"Channel not found: {channel_id}")
                return None
            
            item = data['items'][0]
            snippet = item['snippet']
            statistics = item.get('statistics', {})
            
            return ChannelMetadata(
                channel_id=channel_id,
                title=snippet['title'],
                description=snippet['description'],
                subscriber_count=int(statistics.get('subscriberCount', 0)) if statistics.get('subscriberCount') else None,
                video_count=int(statistics.get('videoCount', 0)) if statistics.get('videoCount') else None,
                view_count=int(statistics.get('viewCount', 0)) if statistics.get('viewCount') else None,
                published_at=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                keywords=snippet.get('keywords', []),
                country=snippet.get('country')
            )
            
        except Exception as e:
            logger.error(f"Error getting channel details for {channel_id}: {e}")
            return None
    
    def download_audio(self, video_id: str, output_dir: str = "/tmp") -> Optional[str]:
        """Download audio from YouTube video for transcription.
        
        Args:
            video_id: YouTube video ID
            output_dir: Directory to save audio file
            
        Returns:
            Path to downloaded audio file
        """
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
                'extractaudio': True,
                'audioformat': 'wav',
                'audio-quality': 0,  # Best quality
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # yt-dlp might change the extension
                if not filename.endswith('.wav'):
                    filename = filename.rsplit('.', 1)[0] + '.wav'
                
                logger.info(f"Downloaded audio for video {video_id}: {filename}")
                return filename
                
        except Exception as e:
            logger.error(f"Error downloading audio for {video_id}: {e}")
            return None
    
    def get_channel_playlists(self, channel_id: str, max_results: int = 50) -> List[PlaylistMetadata]:
        """Get all playlists for a channel, filtered for legal content.
        
        Args:
            channel_id: YouTube channel ID
            max_results: Maximum playlists to return
            
        Returns:
            List of legal-related playlists
        """
        if not self.quota_manager.check_quota('playlists', max_results // 50 + 1):
            logger.warning("YouTube API quota exceeded")
            return []
        
        playlists = []
        page_token = None
        
        try:
            while len(playlists) < max_results:
                request_params = {
                    'part': 'snippet,contentDetails',
                    'channelId': channel_id,
                    'maxResults': min(50, max_results - len(playlists))
                }
                
                if page_token:
                    request_params['pageToken'] = page_token
                
                request = self.youtube.playlists().list(**request_params)
                data = self._execute_request(request)
                self.quota_manager.use_quota('playlists')
                
                for item in data.get('items', []):
                    snippet = item['snippet']
                    content_details = item['contentDetails']
                    
                    # Filter for legal content
                    if self._is_legal_content(snippet['title'], snippet['description']):
                        playlists.append(PlaylistMetadata(
                            playlist_id=item['id'],
                            title=snippet['title'],
                            description=snippet['description'],
                            channel_title=snippet['channelTitle'],
                            channel_id=snippet['channelId'],
                            published_at=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                            video_count=content_details['itemCount'],
                            thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url'),
                            privacy_status=snippet.get('privacyStatus', 'public')
                        ))
                
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            
            logger.info(f"Found {len(playlists)} legal playlists for channel {channel_id}")
            return playlists[:max_results]
            
        except Exception as e:
            logger.error(f"Error getting playlists for channel {channel_id}: {e}")
            return playlists
    
    def get_playlist_videos(self, playlist_id: str, max_results: int = None) -> List[PlaylistItem]:
        """Get all videos from a playlist.
        
        Args:
            playlist_id: YouTube playlist ID
            max_results: Maximum videos to return (None for all)
            
        Returns:
            List of videos in the playlist
        """
        if max_results and not self.quota_manager.check_quota('playlistItems', max_results // 50 + 1):
            logger.warning("YouTube API quota exceeded")
            return []
        
        videos = []
        page_token = None
        
        try:
            while True:
                request_params = {
                    'part': 'snippet',
                    'playlistId': playlist_id,
                    'maxResults': 50
                }
                
                if max_results:
                    request_params['maxResults'] = min(50, max_results - len(videos))
                
                if page_token:
                    request_params['pageToken'] = page_token
                
                request = self.youtube.playlistItems().list(**request_params)
                data = self._execute_request(request)
                self.quota_manager.use_quota('playlistItems')
                
                for item in data.get('items', []):
                    snippet = item['snippet']
                    
                    # Skip deleted/private videos
                    if snippet['title'] == 'Deleted video' or snippet['title'] == 'Private video':
                        continue
                    
                    videos.append(PlaylistItem(
                        video_id=snippet['resourceId']['videoId'],
                        title=snippet['title'],
                        description=snippet['description'],
                        channel_title=snippet['channelTitle'],
                        channel_id=snippet['channelId'],
                        published_at=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                        position=snippet['position'],
                        thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url'),
                        playlist_id=playlist_id
                    ))
                
                page_token = data.get('nextPageToken')
                if not page_token or (max_results and len(videos) >= max_results):
                    break
            
            logger.info(f"Found {len(videos)} videos in playlist {playlist_id}")
            return videos[:max_results] if max_results else videos
            
        except Exception as e:
            logger.error(f"Error getting videos from playlist {playlist_id}: {e}")
            return videos
    
    def get_legal_videos_from_channel(self, channel_id: str, max_videos_per_playlist: int = None) -> Dict[str, List[PlaylistItem]]:
        """Get all legal videos from all legal playlists in a channel.
        
        Args:
            channel_id: YouTube channel ID
            max_videos_per_playlist: Max videos per playlist (None for all)
            
        Returns:
            Dictionary mapping playlist titles to lists of videos
        """
        logger.info(f"Starting legal content ingestion for channel {channel_id}")
        
        # Get all legal playlists
        playlists = self.get_channel_playlists(channel_id)
        
        if not playlists:
            logger.warning(f"No legal playlists found for channel {channel_id}")
            return {}
        
        # Get videos from each legal playlist
        all_videos = {}
        total_videos = 0
        
        for playlist in playlists:
            logger.info(f"Processing playlist: '{playlist.title}' ({playlist.video_count} videos)")
            
            videos = self.get_playlist_videos(playlist.playlist_id, max_videos_per_playlist)
            
            if videos:
                all_videos[playlist.title] = videos
                total_videos += len(videos)
                logger.info(f"Added {len(videos)} videos from '{playlist.title}'")
            else:
                logger.warning(f"No videos found in playlist '{playlist.title}'")
        
        logger.info(f"Legal content ingestion complete: {total_videos} videos from {len(playlists)} playlists")
        return all_videos
    
    def bulk_get_video_details(self, video_ids: List[str], batch_size: int = 50) -> List[VideoMetadata]:
        """Get details for multiple videos efficiently.
        
        Args:
            video_ids: List of YouTube video IDs
            batch_size: Number of videos to request per API call (max 50)
            
        Returns:
            List of video metadata objects
        """
        if not self.quota_manager.check_quota('videos', len(video_ids) // batch_size + 1):
            logger.warning("YouTube API quota exceeded")
            return []
        
        all_videos = []
        
        # Process videos in batches
        for i in range(0, len(video_ids), batch_size):
            batch_ids = video_ids[i:i + batch_size]
            
            try:
                request = self.youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(batch_ids)
                )
                
                data = self._execute_request(request)
                self.quota_manager.use_quota('videos')
                
                for item in data.get('items', []):
                    snippet = item['snippet']
                    statistics = item.get('statistics', {})
                    
                    # Check if captions are available (this would require additional API calls)
                    # For bulk operations, we'll skip this to save quota
                    captions_available = False
                    
                    video_metadata = VideoMetadata(
                        video_id=item['id'],
                        title=snippet['title'],
                        description=snippet['description'],
                        channel_title=snippet['channelTitle'],
                        channel_id=snippet['channelId'],
                        published_at=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                        duration=item['contentDetails'].get('duration'),
                        view_count=int(statistics.get('viewCount', 0)) if statistics.get('viewCount') else None,
                        like_count=int(statistics.get('likeCount', 0)) if statistics.get('likeCount') else None,
                        comment_count=int(statistics.get('commentCount', 0)) if statistics.get('commentCount') else None,
                        tags=snippet.get('tags', []),
                        category_id=snippet.get('categoryId', ''),
                        default_language=snippet.get('defaultLanguage'),
                        thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url'),
                        captions_available=captions_available
                    )
                    
                    all_videos.append(video_metadata)
                
                logger.info(f"Processed batch {i//batch_size + 1}: {len(data.get('items', []))} videos")
                
            except Exception as e:
                logger.error(f"Error processing video batch {i//batch_size + 1}: {e}")
                continue
        
        logger.info(f"Bulk video details complete: {len(all_videos)} videos processed")
        return all_videos


# Factory function for easy instantiation
def get_youtube_client(api_key: Optional[str] = None) -> YouTubeClient:
    """Get configured YouTube client.
    
    Args:
        api_key: Optional API key override
        
    Returns:
        Configured YouTubeClient instance
    """
    return YouTubeClient(api_key=api_key)