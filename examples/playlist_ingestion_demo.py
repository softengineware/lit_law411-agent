#!/usr/bin/env python3
"""
YouTube Playlist Ingestion Demo

This script demonstrates how to:
1. Find all legal-related playlists in a YouTube channel
2. Extract all videos from those playlists
3. Get detailed metadata for all videos
4. Filter and organize legal content

To run this demo:
1. Set YOUTUBE_API_KEY in your .env file
2. Run: python examples/playlist_ingestion_demo.py

You can also specify a channel ID:
python examples/playlist_ingestion_demo.py --channel UC_CHANNEL_ID
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.youtube import get_youtube_client, PlaylistMetadata, PlaylistItem, VideoMetadata
from src.core.config import settings


def demo_legal_playlist_discovery(channel_id: str):
    """Demonstrate finding legal playlists in a channel."""
    print(f"🔍 Legal Playlist Discovery for Channel: {channel_id}")
    print("=" * 60)
    
    # Check if API key is available
    if not settings.youtube_api_key or settings.youtube_api_key == "your_youtube_api_key_here":
        print("❌ YouTube API key not configured!")
        print("Please set YOUTUBE_API_KEY in your .env file")
        return None, None
    
    try:
        # Initialize YouTube client
        client = get_youtube_client()
        print(f"✅ YouTube client initialized")
        print(f"📊 Available quota: {client.quota_manager.daily_quota - client.quota_manager.used_quota}")
        
        # Get channel details first
        print(f"\n📺 Getting channel information...")
        channel_details = client.get_channel_details(channel_id)
        
        if channel_details:
            print(f"   Channel: {channel_details.title}")
            print(f"   Subscribers: {channel_details.subscriber_count:,}" if channel_details.subscriber_count else "   Subscribers: Hidden")
            print(f"   Total Videos: {channel_details.video_count:,}" if channel_details.video_count else "   Total Videos: N/A")
        else:
            print(f"   ❌ Could not get channel details for {channel_id}")
            return None, None
        
        # Find legal playlists
        print(f"\n🔍 Searching for legal playlists...")
        playlists = client.get_channel_playlists(channel_id)
        
        if not playlists:
            print("   ❌ No legal playlists found in this channel")
            return None, client
        
        print(f"   ✅ Found {len(playlists)} legal playlists")
        print("\n📚 Legal Playlists Found:")
        print("-" * 50)
        
        for i, playlist in enumerate(playlists, 1):
            print(f"{i}. {playlist.title}")
            print(f"   Videos: {playlist.video_count}")
            print(f"   Created: {playlist.published_at.strftime('%Y-%m-%d')}")
            print(f"   ID: {playlist.playlist_id}")
            if playlist.description:
                description = playlist.description[:100] + "..." if len(playlist.description) > 100 else playlist.description
                print(f"   Description: {description}")
            print()
        
        return playlists, client
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None


def demo_playlist_video_extraction(client, playlists: List[PlaylistMetadata], max_videos_per_playlist: int = 10):
    """Demonstrate extracting videos from legal playlists."""
    print(f"📹 Video Extraction from Legal Playlists")
    print("=" * 60)
    
    if not playlists:
        print("No playlists to process")
        return []
    
    all_video_ids = []
    playlist_videos = {}
    
    for playlist in playlists:
        print(f"\n🎬 Processing: '{playlist.title}'")
        print(f"   Expected videos: {playlist.video_count}")
        
        # Get videos from playlist
        videos = client.get_playlist_videos(playlist.playlist_id, max_videos_per_playlist)
        
        if videos:
            playlist_videos[playlist.title] = videos
            video_ids = [video.video_id for video in videos]
            all_video_ids.extend(video_ids)
            
            print(f"   ✅ Extracted {len(videos)} videos")
            
            # Show first few videos
            print(f"   📺 Sample videos:")
            for i, video in enumerate(videos[:3], 1):
                print(f"      {i}. {video.title}")
                print(f"         Published: {video.published_at.strftime('%Y-%m-%d')}")
                print(f"         Video ID: {video.video_id}")
        else:
            print(f"   ❌ No videos found in playlist")
    
    print(f"\n📊 Extraction Summary:")
    print(f"   Total playlists processed: {len(playlists)}")
    print(f"   Total videos extracted: {len(all_video_ids)}")
    print(f"   Unique videos: {len(set(all_video_ids))}")
    
    return list(set(all_video_ids))  # Remove duplicates


def demo_bulk_video_details(client, video_ids: List[str], max_videos: int = 20):
    """Demonstrate bulk video metadata extraction."""
    print(f"\n🔍 Bulk Video Metadata Extraction")
    print("=" * 60)
    
    if not video_ids:
        print("No video IDs to process")
        return []
    
    # Limit to max_videos for demo
    video_ids = video_ids[:max_videos]
    
    print(f"📋 Getting detailed metadata for {len(video_ids)} videos...")
    
    # Get detailed metadata
    videos = client.bulk_get_video_details(video_ids)
    
    if videos:
        print(f"✅ Successfully retrieved metadata for {len(videos)} videos")
        
        # Analyze the videos
        total_views = sum(v.view_count for v in videos if v.view_count)
        total_likes = sum(v.like_count for v in videos if v.like_count)
        
        print(f"\n📈 Content Analysis:")
        print(f"   Total views: {total_views:,}")
        print(f"   Total likes: {total_likes:,}")
        print(f"   Average views per video: {total_views // len(videos):,}" if videos else 0)
        
        # Show top videos by views
        videos_by_views = sorted(videos, key=lambda x: x.view_count or 0, reverse=True)
        
        print(f"\n🏆 Top Videos by Views:")
        print("-" * 50)
        for i, video in enumerate(videos_by_views[:5], 1):
            print(f"{i}. {video.title}")
            print(f"   Views: {video.view_count:,}" if video.view_count else "   Views: N/A")
            print(f"   Likes: {video.like_count:,}" if video.like_count else "   Likes: N/A")
            print(f"   Duration: {video.duration}")
            print(f"   Published: {video.published_at.strftime('%Y-%m-%d')}")
            print()
        
        # Show legal relevance analysis
        legal_keywords_found = {}
        for video in videos:
            text = f"{video.title} {video.description}".lower()
            for keyword in client.legal_keywords:
                if keyword in text:
                    legal_keywords_found[keyword] = legal_keywords_found.get(keyword, 0) + 1
        
        if legal_keywords_found:
            print(f"🏛️ Legal Keywords Analysis:")
            print("-" * 30)
            sorted_keywords = sorted(legal_keywords_found.items(), key=lambda x: x[1], reverse=True)
            for keyword, count in sorted_keywords[:10]:
                print(f"   {keyword}: {count} videos")
        
        return videos
    else:
        print("❌ Failed to retrieve video metadata")
        return []


def demo_channel_legal_content_summary(client, channel_id: str):
    """Demonstrate comprehensive legal content analysis for a channel."""
    print(f"\n📊 Comprehensive Legal Content Analysis")
    print("=" * 60)
    
    # Get all legal videos from channel
    all_videos = client.get_legal_videos_from_channel(channel_id, max_videos_per_playlist=5)  # Limit for demo
    
    if not all_videos:
        print("No legal content found in channel")
        return
    
    total_videos = sum(len(videos) for videos in all_videos.values())
    
    print(f"📋 Channel Legal Content Summary:")
    print(f"   Legal playlists: {len(all_videos)}")
    print(f"   Total legal videos: {total_videos}")
    
    print(f"\n📚 Playlist Breakdown:")
    for playlist_title, videos in all_videos.items():
        print(f"   • {playlist_title}: {len(videos)} videos")
    
    # Get detailed metadata for a sample
    sample_video_ids = []
    for videos in all_videos.values():
        sample_video_ids.extend([v.video_id for v in videos[:2]])  # 2 from each playlist
    
    if sample_video_ids:
        print(f"\n🔍 Sample Video Analysis (first 2 from each playlist):")
        sample_videos = client.bulk_get_video_details(sample_video_ids[:10])  # Limit for demo
        
        if sample_videos:
            avg_views = sum(v.view_count for v in sample_videos if v.view_count) / len(sample_videos)
            print(f"   Average views: {avg_views:,.0f}")
            
            recent_videos = [v for v in sample_videos if v.published_at.year >= 2023]
            print(f"   Recent videos (2023+): {len(recent_videos)}")


def main():
    """Run the playlist ingestion demo."""
    parser = argparse.ArgumentParser(description="YouTube Legal Playlist Ingestion Demo")
    parser.add_argument("--channel", "-c", help="YouTube Channel ID", 
                       default="UCX6b17PVsYBQ0ip5gyeme-Q")  # CrashCourse as default
    parser.add_argument("--max-videos", "-m", type=int, default=10,
                       help="Maximum videos per playlist to process")
    
    args = parser.parse_args()
    
    print("🚀 Legal Knowledge Base Agent - Playlist Ingestion Demo")
    print("=" * 70)
    
    # Check environment
    print(f"Environment: {settings.environment}")
    print(f"Debug mode: {settings.debug}")
    print(f"Target channel: {args.channel}")
    print(f"Max videos per playlist: {args.max_videos}")
    
    # Step 1: Discover legal playlists
    playlists, client = demo_legal_playlist_discovery(args.channel)
    
    if not playlists or not client:
        print("\n❌ Cannot proceed without legal playlists")
        return
    
    # Step 2: Extract videos from playlists
    video_ids = demo_playlist_video_extraction(client, playlists, args.max_videos)
    
    # Step 3: Get detailed video metadata
    if video_ids:
        videos = demo_bulk_video_details(client, video_ids, max_videos=20)
    
    # Step 4: Channel summary analysis
    demo_channel_legal_content_summary(client, args.channel)
    
    # Show final quota usage
    print(f"\n📊 API Quota Usage:")
    print(f"   Used: {client.quota_manager.used_quota}")
    print(f"   Remaining: {client.quota_manager.daily_quota - client.quota_manager.used_quota}")
    
    print("\n✅ Playlist ingestion demo completed!")
    print("\nNext steps:")
    print("1. Store video metadata in database")
    print("2. Download audio for transcription")
    print("3. Extract legal entities from descriptions")
    print("4. Create searchable legal knowledge base")


if __name__ == "__main__":
    main()