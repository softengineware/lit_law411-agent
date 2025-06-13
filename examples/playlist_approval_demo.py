#!/usr/bin/env python3
"""
Demo of Interactive Playlist Approval Process for YouTube Legal Content

This demonstrates how the approval system would work in an interactive environment.
Shows the playlists that would be presented for approval.
"""

import sys
from pathlib import Path
from typing import List

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.youtube import get_youtube_client, PlaylistMetadata
from src.core.config import settings


def demo_playlist_discovery_and_approval(channel_id: str):
    """Demo the playlist discovery and approval process."""
    print("🚀 DEMO: Interactive Legal Playlist Approval System")
    print("=" * 70)
    print("This demo shows what playlists would be presented for user approval.")
    print("In an interactive environment, you would approve/deny each playlist individually.")
    print(f"\nTarget channel: {channel_id}")
    
    # Check if API key is available
    if not settings.youtube_api_key or settings.youtube_api_key == "your_youtube_api_key_here":
        print("❌ YouTube API key not configured!")
        return
    
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
            return
        
        # Find legal playlists
        print(f"\n🔍 Searching for legal playlists...")
        playlists = client.get_channel_playlists(channel_id)
        
        if not playlists:
            print("   ❌ No legal playlists found in this channel")
            return
        
        print(f"   ✅ Found {len(playlists)} legal playlists")
        
        # Demo the approval process
        print(f"\n📋 APPROVAL PROCESS DEMO - {len(playlists)} Playlists Would Be Presented")
        print("=" * 70)
        print("🔥 **NO VIDEOS WILL BE PROCESSED** - This is approval demo only!")
        print("In interactive mode, you would see each playlist and choose y/n/skip/quit")
        
        for i, playlist in enumerate(playlists, 1):
            print(f"\n📚 Playlist {i}/{len(playlists)} - WOULD REQUEST APPROVAL")
            print("=" * 50)
            print(f"📚 Title: {playlist.title}")
            print(f"📹 Video Count: {playlist.video_count}")
            print(f"📅 Created: {playlist.published_at.strftime('%Y-%m-%d')}")
            print(f"🏷️  ID: {playlist.playlist_id}")
            
            if playlist.description:
                description = playlist.description[:200] + "..." if len(playlist.description) > 200 else playlist.description
                print(f"📝 Description: {description}")
            
            print(f"🔗 URL: https://www.youtube.com/playlist?list={playlist.playlist_id}")
            print(f"📊 DEMO: In interactive mode, user would choose (y/n/skip/quit)")
            
            # Show what legal keywords were found
            text = f"{playlist.title} {playlist.description}".lower()
            found_keywords = [keyword for keyword in client.legal_keywords if keyword in text]
            if found_keywords:
                print(f"🎯 Legal keywords found: {', '.join(found_keywords[:5])}")
        
        print(f"\n🎯 DEMO SUMMARY")
        print("=" * 30)
        print(f"📊 Found {len(playlists)} legal playlists that would require approval")
        print(f"📹 Total videos across all playlists: {sum(p.video_count for p in playlists)}")
        print(f"🚫 **NO DATA STORED** - This was discovery only")
        
        print(f"\n✅ APPROVAL PROCESS READY")
        print("=" * 30)
        print("To run interactive approval:")
        print("1. Use: python examples/interactive_playlist_approval.py")
        print("2. You'll be asked to approve each playlist individually")
        print("3. Only approved playlists will have videos extracted")
        print("4. You can skip or quit at any time")
        
        # Show quota usage
        print(f"\n📊 API Quota Usage:")
        print(f"   Used: {client.quota_manager.used_quota}")
        print(f"   Remaining: {client.quota_manager.daily_quota - client.quota_manager.used_quota}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Run the demo."""
    channel_id = "UCX6b17PVsYBQ0ip5gyeme-Q"  # CrashCourse
    demo_playlist_discovery_and_approval(channel_id)


if __name__ == "__main__":
    main()