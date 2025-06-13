#!/usr/bin/env python3
"""
YouTube API Integration Demo

This script demonstrates the YouTube API integration for legal content extraction.
It shows how to:
1. Search for legal-related videos
2. Extract video metadata
3. Download audio for transcription
4. Check quota usage

To run this demo:
1. Set YOUTUBE_API_KEY in your .env file
2. Run: python examples/youtube_demo.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.youtube import get_youtube_client, YouTubeClient
from src.core.config import settings


def demo_video_search():
    """Demonstrate video search functionality."""
    print("🔍 YouTube Legal Content Search Demo")
    print("=" * 50)
    
    # Check if API key is available
    if not settings.youtube_api_key or settings.youtube_api_key == "your_youtube_api_key_here":
        print("❌ YouTube API key not configured!")
        print("Please set YOUTUBE_API_KEY in your .env file")
        return
    
    try:
        # Initialize YouTube client
        client = get_youtube_client()
        print(f"✅ YouTube client initialized")
        print(f"📊 Available quota: {client.quota_manager.daily_quota - client.quota_manager.used_quota}")
        
        # Search for legal content
        print("\n🔍 Searching for legal videos...")
        search_terms = [
            "constitutional law lecture",
            "supreme court case analysis",
            "contract law basics",
            "corporate law explained"
        ]
        
        all_results = []
        for term in search_terms:
            print(f"\n   Searching: '{term}'")
            results = client.search_videos(term, max_results=5)
            all_results.extend(results)
            print(f"   Found: {len(results)} relevant videos")
        
        print(f"\n📝 Total videos found: {len(all_results)}")
        
        # Display top results
        if all_results:
            print("\n🏆 Top Legal Videos Found:")
            print("-" * 50)
            
            for i, video in enumerate(all_results[:10], 1):
                print(f"{i}. {video.title}")
                print(f"   Channel: {video.channel_title}")
                print(f"   Published: {video.published_at.strftime('%Y-%m-%d')}")
                print(f"   Video ID: {video.video_id}")
                print()
        
        # Get detailed info for first video
        if all_results:
            first_video = all_results[0]
            print(f"🔍 Getting detailed info for: {first_video.title}")
            
            details = client.get_video_details(first_video.video_id)
            if details:
                print(f"   Duration: {details.duration}")
                print(f"   Views: {details.view_count:,}" if details.view_count else "   Views: N/A")
                print(f"   Likes: {details.like_count:,}" if details.like_count else "   Likes: N/A")
                print(f"   Captions: {'Yes' if details.captions_available else 'No'}")
                print(f"   Tags: {', '.join(details.tags[:5])}" if details.tags else "   Tags: None")
        
        # Show quota usage
        print(f"\n📊 Quota used: {client.quota_manager.used_quota}/{client.quota_manager.daily_quota}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_channel_analysis():
    """Demonstrate channel analysis."""
    print("\n📺 Channel Analysis Demo")
    print("=" * 50)
    
    # Well-known legal education channels
    legal_channels = {
        "CrashCourse": "UCX6b17PVsYBQ0ip5gyeme-Q",  # CrashCourse (has legal content)
        "LexFridman": "UCSHZKyawb77ixDdsGog4iWA",   # Lex Fridman (interviews legal experts)
    }
    
    try:
        client = get_youtube_client()
        
        for channel_name, channel_id in legal_channels.items():
            print(f"\n🔍 Analyzing channel: {channel_name}")
            
            channel_details = client.get_channel_details(channel_id)
            if channel_details:
                print(f"   Title: {channel_details.title}")
                print(f"   Subscribers: {channel_details.subscriber_count:,}" if channel_details.subscriber_count else "   Subscribers: Hidden")
                print(f"   Videos: {channel_details.video_count:,}" if channel_details.video_count else "   Videos: N/A")
                print(f"   Total Views: {channel_details.view_count:,}" if channel_details.view_count else "   Total Views: N/A")
                print(f"   Created: {channel_details.published_at.strftime('%Y-%m-%d')}")
            else:
                print(f"   ❌ Could not get details for {channel_name}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_audio_download():
    """Demonstrate audio download (without actually downloading)."""
    print("\n🎵 Audio Download Demo")
    print("=" * 50)
    
    # This is a demonstration - in real usage you'd want to be careful about downloading
    # copyrighted content. For this demo, we'll just show the process.
    
    print("📋 Audio download process:")
    print("1. Video ID extracted from search results")
    print("2. yt-dlp downloads best quality audio")
    print("3. Audio converted to WAV format")
    print("4. File path returned for transcription")
    print("\n⚠️  Note: Actual download skipped in demo to respect API limits")
    
    # In real usage:
    # client = get_youtube_client()
    # audio_path = client.download_audio("VIDEO_ID", "/tmp/youtube_audio")
    # if audio_path:
    #     print(f"Audio downloaded: {audio_path}")


def main():
    """Run the complete YouTube integration demo."""
    print("🚀 Legal Knowledge Base Agent - YouTube Integration Demo")
    print("=" * 60)
    
    # Check environment
    print(f"Environment: {settings.environment}")
    print(f"Debug mode: {settings.debug}")
    
    # Run demos
    demo_video_search()
    demo_channel_analysis()
    demo_audio_download()
    
    print("\n✅ Demo completed!")
    print("\nNext steps:")
    print("1. Set up transcription pipeline (Whisper)")
    print("2. Implement NLP processing for legal entities")
    print("3. Store results in three-database architecture")
    print("4. Create API endpoints for legal research")


if __name__ == "__main__":
    main()