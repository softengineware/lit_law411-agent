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
            'commentThreads': 1
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


# Factory function for easy instantiation
def get_youtube_client(api_key: Optional[str] = None) -> YouTubeClient:
    """Get configured YouTube client.
    
    Args:
        api_key: Optional API key override
        
    Returns:
        Configured YouTubeClient instance
    """
    return YouTubeClient(api_key=api_key)