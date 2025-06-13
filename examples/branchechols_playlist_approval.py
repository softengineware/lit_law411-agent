#!/usr/bin/env python3
"""
Interactive Playlist Approval for branchechols@gmail.com YouTube Account

This script will find and process specific legal playlists from your personal YouTube account.
Target playlists:
- Courtroom Procedures and Techniques
- Empowerment Lawyer  
- Feldstein Family Law
- Lassen County DCSS
- Law Venture
- Litigation
- Matthew Weidner
- RTSC
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.youtube import get_youtube_client, PlaylistMetadata, PlaylistItem
from src.core.config import settings


def get_user_approval(playlist: PlaylistMetadata, target_name: str) -> bool:
    """Ask user for approval to process a playlist.
    
    Args:
        playlist: Playlist metadata to display for approval
        target_name: The target playlist name this matches
        
    Returns:
        True if user approves processing this playlist
    """
    print(f"\n🎯 PLAYLIST APPROVAL REQUEST")
    print("=" * 50)
    print(f"🎯 Target: {target_name}")
    print(f"📚 Found: {playlist.title}")
    print(f"📹 Video Count: {playlist.video_count}")
    print(f"📅 Created: {playlist.published_at.strftime('%Y-%m-%d')}")
    print(f"🏷️  ID: {playlist.playlist_id}")
    
    if playlist.description:
        description = playlist.description[:200] + "..." if len(playlist.description) > 200 else playlist.description
        print(f"📝 Description: {description}")
    
    print(f"\n🔗 URL: https://www.youtube.com/playlist?list={playlist.playlist_id}")
    
    while True:
        response = input(f"\n❓ Process '{target_name}' playlist? (y/n/skip/quit): ").lower().strip()
        
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no', 'skip']:
            return False
        elif response in ['q', 'quit', 'exit']:
            print("👋 Exiting...")
            sys.exit(0)
        else:
            print("Please enter 'y' (yes), 'n' (no/skip), or 'q' (quit)")


def find_target_playlists(channel_id: str, target_names: List[str]) -> List[tuple]:
    """Find specific target playlists in your channel.
    
    Args:
        channel_id: Your YouTube channel ID
        target_names: List of target playlist names to find
        
    Returns:
        List of (playlist, target_name) tuples for found matches
    """
    print(f"🔍 Searching for Target Playlists in Your Channel")
    print("=" * 60)
    
    # Check if API key is available
    if not settings.youtube_api_key or settings.youtube_api_key == "your_youtube_api_key_here":
        print("❌ YouTube API key not configured!")
        return []
    
    try:
        client = get_youtube_client()
        print(f"✅ YouTube client initialized")
        print(f"📊 Available quota: {client.quota_manager.daily_quota - client.quota_manager.used_quota}")
        
        # Get channel details first
        print(f"\n📺 Getting your channel information...")
        channel_details = client.get_channel_details(channel_id)
        
        if channel_details:
            print(f"   Channel: {channel_details.title}")
            print(f"   Total Videos: {channel_details.video_count:,}" if channel_details.video_count else "   Total Videos: N/A")
        else:
            print(f"   ❌ Could not access channel {channel_id}")
            print("   Please verify the channel ID is correct and accessible")
            return []
        
        # Get ALL playlists (temporarily disable legal filtering)
        print(f"\n🔍 Getting ALL playlists from your channel...")
        original_keywords = client.legal_keywords
        client.legal_keywords = ["a"]  # Match most playlists
        
        all_playlists = client.get_channel_playlists(channel_id, max_results=200)
        
        # Restore original keywords
        client.legal_keywords = original_keywords
        
        if not all_playlists:
            print("   ❌ No playlists found in your channel")
            return []
        
        print(f"   ✅ Found {len(all_playlists)} total playlists")
        
        # Find target matches
        found_matches = []
        target_names_lower = [name.lower() for name in target_names]
        
        print(f"\n🎯 Looking for target playlists:")
        for target in target_names:
            print(f"   - {target}")
        
        print(f"\n📋 Checking all playlists for matches:")
        for playlist in all_playlists:
            playlist_name_lower = playlist.title.lower()
            matched = False
            
            for i, target_name_lower in enumerate(target_names_lower):
                # Check for partial matches in both directions
                if (target_name_lower in playlist_name_lower or 
                    playlist_name_lower in target_name_lower or
                    any(word in playlist_name_lower for word in target_name_lower.split() if len(word) > 3)):
                    
                    print(f"   ✅ MATCH: '{playlist.title}' → '{target_names[i]}' ({playlist.video_count} videos)")
                    found_matches.append((playlist, target_names[i]))
                    matched = True
                    break
            
            if not matched:
                print(f"   📚 '{playlist.title}' ({playlist.video_count} videos)")
        
        print(f"\n📊 Search Results:")
        print(f"   Total playlists found: {len(all_playlists)}")
        print(f"   Target matches: {len(found_matches)}")
        
        return found_matches
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def process_approved_playlists(found_matches: List[tuple], max_videos: int = 10) -> Dict[str, List[PlaylistItem]]:
    """Process user-approved playlists and extract videos.
    
    Args:
        found_matches: List of (playlist, target_name) tuples
        max_videos: Maximum videos per playlist
        
    Returns:
        Dictionary of playlist titles to video lists
    """
    print(f"\n📹 Processing Approved Playlists")
    print("=" * 50)
    
    client = get_youtube_client()
    all_videos = {}
    total_videos = 0
    
    for i, (playlist, target_name) in enumerate(found_matches, 1):
        print(f"\n🎬 Processing {i}/{len(found_matches)}: '{playlist.title}'")
        print(f"   Target: '{target_name}'")
        print(f"   Expected videos: {playlist.video_count}")
        
        # Get videos from playlist
        videos = client.get_playlist_videos(playlist.playlist_id, max_videos)
        
        if videos:
            # Use target name as key for consistency
            all_videos[target_name] = videos
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
    print(f"   Processed playlists: {len(found_matches)}")
    print(f"   Total videos extracted: {total_videos}")
    
    return all_videos


def main():
    """Run the interactive approval process for your specific playlists."""
    
    # Your channel ID and target playlists
    CHANNEL_ID = "UCPp_BxrpuTIJNTfO02zn3FQ"
    TARGET_PLAYLISTS = [
        "Courtroom Procedures and Techniques",
        "Empowerment Lawyer", 
        "Feldstein Family Law",
        "Lassen County DCSS",
        "Law Venture",
        "Litigation",
        "Matthew Weidner",
        "RTSC"
    ]
    
    print("🚀 branchechols@gmail.com Legal Playlist Approval System")
    print("=" * 70)
    print("This system will find and process your specific legal playlists.")
    print("You'll approve each playlist individually before any videos are extracted.")
    print(f"\nYour channel: {CHANNEL_ID}")
    print(f"Target playlists: {len(TARGET_PLAYLISTS)}")
    
    # Step 1: Find target playlists in your channel
    found_matches = find_target_playlists(CHANNEL_ID, TARGET_PLAYLISTS)
    
    if not found_matches:
        print("\n❌ No target playlists found. Please check:")
        print("1. Channel ID is correct")
        print("2. Playlists exist in your account") 
        print("3. API quota is available")
        return
    
    # Step 2: Get user approval for each found playlist
    print(f"\n📋 Found {len(found_matches)} Target Playlists - Requesting Approvals")
    print("=" * 70)
    
    approved_matches = []
    
    for i, (playlist, target_name) in enumerate(found_matches, 1):
        print(f"\n📚 Playlist {i}/{len(found_matches)}")
        
        if get_user_approval(playlist, target_name):
            approved_matches.append((playlist, target_name))
            print(f"✅ APPROVED: '{target_name}' → '{playlist.title}'")
        else:
            print(f"❌ SKIPPED: '{target_name}' → '{playlist.title}'")
    
    # Step 3: Final confirmation
    if not approved_matches:
        print(f"\n❌ No playlists approved for processing.")
        return
    
    print(f"\n🎯 FINAL APPROVAL SUMMARY")
    print("=" * 40)
    print(f"Approved: {len(approved_matches)}/{len(found_matches)} playlists")
    total_videos = sum(playlist.video_count for playlist, _ in approved_matches)
    
    for playlist, target_name in approved_matches:
        print(f"  ✅ {target_name}")
        print(f"     → '{playlist.title}' ({playlist.video_count} videos)")
    
    print(f"\nTotal videos to extract: {total_videos}")
    
    final_confirm = input(f"\n❓ Proceed with processing {len(approved_matches)} approved playlists? (y/n): ").lower().strip()
    
    if final_confirm not in ['y', 'yes']:
        print("🚫 Processing cancelled by user.")
        return
    
    # Step 4: Extract videos from approved playlists only
    max_videos = int(input("📹 Max videos per playlist (10): ") or "10")
    
    all_videos = process_approved_playlists(approved_matches, max_videos)
    
    # Step 5: Show final results
    print(f"\n🎉 PROCESSING COMPLETE!")
    print("=" * 40)
    
    total_extracted = sum(len(videos) for videos in all_videos.values())
    print(f"📊 Final Results:")
    print(f"   Processed playlists: {len(all_videos)}")
    print(f"   Total videos extracted: {total_extracted}")
    
    print(f"\n📚 Video Breakdown:")
    for target_name, videos in all_videos.items():
        print(f"   • {target_name}: {len(videos)} videos")
    
    if total_extracted > 0:
        print(f"\n✅ Successfully extracted {total_extracted} legal videos with your approval!")
        
        # Show quota usage
        client = get_youtube_client()
        print(f"\n📊 API Quota Usage:")
        print(f"   Used: {client.quota_manager.used_quota}")
        print(f"   Remaining: {client.quota_manager.daily_quota - client.quota_manager.used_quota}")
        
        print(f"\n🔄 Next Steps:")
        print("1. Store video metadata in databases (Airtable, Supabase, Pinecone)")
        print("2. Download audio for transcription") 
        print("3. Extract legal entities with NLP")
        print("4. Create searchable legal knowledge base")
    else:
        print(f"\n📝 No videos were extracted.")


if __name__ == "__main__":
    main()