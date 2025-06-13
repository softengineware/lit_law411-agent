#!/usr/bin/env python3
"""
Interactive Playlist Approval for YouTube Legal Content

This script will:
1. Find all legal-related playlists in a channel
2. Ask for user approval before processing each playlist
3. Only extract videos from approved playlists
4. Provide detailed information before each decision
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.youtube import get_youtube_client, PlaylistMetadata, PlaylistItem, VideoMetadata
from src.core.config import settings


def get_user_approval(playlist: PlaylistMetadata) -> bool:
    """Ask user for approval to process a playlist.
    
    Args:
        playlist: Playlist metadata to display for approval
        
    Returns:
        True if user approves processing this playlist
    """
    print(f"\n🎯 PLAYLIST APPROVAL REQUEST")
    print("=" * 50)
    print(f"📚 Title: {playlist.title}")
    print(f"📹 Video Count: {playlist.video_count}")
    print(f"📅 Created: {playlist.published_at.strftime('%Y-%m-%d')}")
    print(f"🏷️  ID: {playlist.playlist_id}")
    
    if playlist.description:
        description = playlist.description[:200] + "..." if len(playlist.description) > 200 else playlist.description
        print(f"📝 Description: {description}")
    
    print(f"\n🔗 URL: https://www.youtube.com/playlist?list={playlist.playlist_id}")
    
    while True:
        response = input(f"\n❓ Process this playlist? (y/n/skip/quit): ").lower().strip()
        
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no', 'skip']:
            return False
        elif response in ['q', 'quit', 'exit']:
            print("👋 Exiting...")
            sys.exit(0)
        else:
            print("Please enter 'y' (yes), 'n' (no/skip), or 'q' (quit)")


def discover_legal_playlists(channel_id: str) -> Optional[List[PlaylistMetadata]]:
    """Discover legal playlists in a channel.
    
    Args:
        channel_id: YouTube channel ID
        
    Returns:
        List of legal playlists if found
    """
    print(f"🔍 Discovering Legal Playlists for Channel: {channel_id}")
    print("=" * 60)
    
    # Check if API key is available
    if not settings.youtube_api_key or settings.youtube_api_key == "your_youtube_api_key_here":
        print("❌ YouTube API key not configured!")
        print("Please set YOUTUBE_API_KEY in your .env file")
        return None
    
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
            return None
        
        # Find legal playlists
        print(f"\n🔍 Searching for legal playlists...")
        playlists = client.get_channel_playlists(channel_id)
        
        if not playlists:
            print("   ❌ No legal playlists found in this channel")
            return None
        
        print(f"   ✅ Found {len(playlists)} legal playlists")
        return playlists
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def process_approved_playlists(channel_id: str, approved_playlists: List[PlaylistMetadata], max_videos: int = 10) -> Dict[str, List[PlaylistItem]]:
    """Process only the approved playlists.
    
    Args:
        channel_id: YouTube channel ID
        approved_playlists: List of user-approved playlists
        max_videos: Maximum videos per playlist
        
    Returns:
        Dictionary of playlist titles to video lists
    """
    print(f"\n📹 Processing {len(approved_playlists)} Approved Playlists")
    print("=" * 60)
    
    client = get_youtube_client()
    all_videos = {}
    total_videos = 0
    
    for i, playlist in enumerate(approved_playlists, 1):
        print(f"\n🎬 Processing {i}/{len(approved_playlists)}: '{playlist.title}'")
        print(f"   Expected videos: {playlist.video_count}")
        
        # Get videos from playlist
        videos = client.get_playlist_videos(playlist.playlist_id, max_videos)
        
        if videos:
            all_videos[playlist.title] = videos
            total_videos += len(videos)
            print(f"   ✅ Extracted {len(videos)} videos")
            
            # Show first few videos
            print(f"   📺 Sample videos:")
            for j, video in enumerate(videos[:3], 1):
                print(f"      {j}. {video.title}")
                print(f"         Published: {video.published_at.strftime('%Y-%m-%d')}")
        else:
            print(f"   ❌ No videos found in playlist")
    
    print(f"\n📊 Processing Summary:")
    print(f"   Approved playlists: {len(approved_playlists)}")
    print(f"   Total videos extracted: {total_videos}")
    
    return all_videos


def main():
    """Run the interactive playlist approval process."""
    parser = argparse.ArgumentParser(description="Interactive YouTube Legal Playlist Approval")
    parser.add_argument("--channel", "-c", help="YouTube Channel ID", 
                       default="UCX6b17PVsYBQ0ip5gyeme-Q")  # CrashCourse as default
    parser.add_argument("--max-videos", "-m", type=int, default=10,
                       help="Maximum videos per approved playlist")
    
    args = parser.parse_args()
    
    print("🚀 Interactive Legal Playlist Approval System")
    print("=" * 70)
    print("This system will ask for your approval before processing each legal playlist.")
    print("You can approve, skip, or quit at any time.")
    print(f"\nTarget channel: {args.channel}")
    print(f"Max videos per playlist: {args.max_videos}")
    
    # Step 1: Discover legal playlists
    playlists = discover_legal_playlists(args.channel)
    
    if not playlists:
        print("\n❌ No legal playlists found. Exiting.")
        return
    
    # Step 2: Get user approval for each playlist
    print(f"\n📋 Found {len(playlists)} Legal Playlists - Requesting Approvals")
    print("=" * 60)
    
    approved_playlists = []
    
    for i, playlist in enumerate(playlists, 1):
        print(f"\n📚 Playlist {i}/{len(playlists)}")
        
        if get_user_approval(playlist):
            approved_playlists.append(playlist)
            print(f"✅ APPROVED: '{playlist.title}'")
        else:
            print(f"❌ SKIPPED: '{playlist.title}'")
    
    # Step 3: Process approved playlists
    if not approved_playlists:
        print(f"\n❌ No playlists approved for processing.")
        return
    
    print(f"\n🎯 FINAL APPROVAL SUMMARY")
    print("=" * 30)
    print(f"Approved: {len(approved_playlists)}/{len(playlists)} playlists")
    for playlist in approved_playlists:
        print(f"  ✅ {playlist.title} ({playlist.video_count} videos)")
    
    final_confirm = input(f"\n❓ Proceed with processing {len(approved_playlists)} approved playlists? (y/n): ").lower().strip()
    
    if final_confirm not in ['y', 'yes']:
        print("🚫 Processing cancelled by user.")
        return
    
    # Step 4: Extract videos from approved playlists only
    all_videos = process_approved_playlists(args.channel, approved_playlists, args.max_videos)
    
    # Step 5: Show final results
    print(f"\n🎉 PROCESSING COMPLETE!")
    print("=" * 30)
    
    total_videos = sum(len(videos) for videos in all_videos.values())
    print(f"📊 Final Results:")
    print(f"   Processed playlists: {len(all_videos)}")
    print(f"   Total videos extracted: {total_videos}")
    
    print(f"\n📚 Video Breakdown:")
    for playlist_title, videos in all_videos.items():
        print(f"   • {playlist_title}: {len(videos)} videos")
    
    if total_videos > 0:
        print(f"\n✅ Successfully extracted {total_videos} legal videos with user approval!")
        
        # Show quota usage
        client = get_youtube_client()
        print(f"\n📊 API Quota Usage:")
        print(f"   Used: {client.quota_manager.used_quota}")
        print(f"   Remaining: {client.quota_manager.daily_quota - client.quota_manager.used_quota}")
    else:
        print(f"\n📝 No videos were extracted (no playlists approved or processed).")


if __name__ == "__main__":
    main()