#!/usr/bin/env python3
"""
Find specific playlists in branchechols@gmail.com YouTube account

This script will search for the specified playlist names within a specific channel.
"""

import sys
from pathlib import Path
from typing import List, Optional

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.youtube import get_youtube_client, PlaylistMetadata
from src.core.config import settings


def find_channel_by_email_or_name(client, search_terms: List[str]) -> Optional[str]:
    """Try to find the channel ID by searching for channel names."""
    print("🔍 Searching for branchechols YouTube channel...")
    
    search_queries = [
        "branchechols",
        "Branch Echols", 
        "James Branchford Echols"
    ]
    
    for query in search_queries:
        try:
            print(f"   Trying search: '{query}'")
            # Search for channels (this searches public content)
            results = client.search_videos(f"channel:{query}", max_results=5)
            if results:
                for result in results:
                    print(f"   Found channel: {result.channel_title} (ID: {result.channel_id})")
                    return result.channel_id
        except Exception as e:
            print(f"   Search failed: {e}")
    
    return None


def find_playlists_by_name(client, channel_id: str, target_playlist_names: List[str]) -> List[PlaylistMetadata]:
    """Find specific playlists by name within a channel."""
    print(f"\n📚 Searching for target playlists in channel {channel_id}")
    
    # Get all playlists from the channel (not just legal ones)
    try:
        # Temporarily disable legal filtering to get ALL playlists
        original_keywords = client.legal_keywords
        client.legal_keywords = [""]  # Match everything
        
        all_playlists = client.get_channel_playlists(channel_id, max_results=200)
        
        # Restore original keywords
        client.legal_keywords = original_keywords
        
        print(f"   Found {len(all_playlists)} total playlists")
        
        # Find matching playlists
        found_playlists = []
        target_names_lower = [name.lower() for name in target_playlist_names]
        
        print(f"\n🎯 Looking for these playlists:")
        for name in target_playlist_names:
            print(f"   - {name}")
        
        print(f"\n📋 Checking all playlists:")
        for playlist in all_playlists:
            print(f"   📚 '{playlist.title}' ({playlist.video_count} videos)")
            
            # Check if playlist name matches any target
            playlist_name_lower = playlist.title.lower()
            for i, target_name in enumerate(target_names_lower):
                if target_name in playlist_name_lower or playlist_name_lower in target_name:
                    print(f"      ✅ MATCH for '{target_playlist_names[i]}'")
                    found_playlists.append(playlist)
                    break
        
        return found_playlists
        
    except Exception as e:
        print(f"❌ Error searching playlists: {e}")
        return []


def main():
    """Search for specific playlists in branchechols YouTube account."""
    
    target_playlists = [
        "Courtroom Procedures and Techniques",
        "Empowerment Lawyer", 
        "Feldstein Family Law",
        "Lassen County DCSS",
        "Law Venture",
        "Litigation",
        "Matthew Weidner",
        "RTSC"
    ]
    
    print("🚀 Finding Specific Legal Playlists in branchechols@gmail.com Account")
    print("=" * 75)
    
    # Check if API key is available
    if not settings.youtube_api_key or settings.youtube_api_key == "your_youtube_api_key_here":
        print("❌ YouTube API key not configured!")
        return
    
    try:
        client = get_youtube_client()
        print(f"✅ YouTube API connected")
        print(f"📊 Available quota: {client.quota_manager.daily_quota - client.quota_manager.used_quota}")
        
        # Method 1: Try common channel IDs that might be yours
        potential_channel_ids = [
            # You would need to provide your actual channel ID here
            # Format: "UC" followed by 22 characters
        ]
        
        print(f"\n📋 Target playlists to find:")
        for i, name in enumerate(target_playlists, 1):
            print(f"   {i}. {name}")
        
        print(f"\n🔍 NOTE: To find your personal playlists, we need your YouTube channel ID.")
        print("You can find this by:")
        print("1. Going to youtube.com")
        print("2. Click your profile picture → 'Your channel'") 
        print("3. Look at the URL: youtube.com/channel/YOUR_CHANNEL_ID")
        print("4. Or from YouTube Studio → Settings → Channel → Advanced settings")
        
        # For now, let's try to search for the playlist content publicly
        print(f"\n🔍 Attempting to find playlists through public search...")
        
        found_playlists = []
        for playlist_name in target_playlists:
            print(f"\n📚 Searching for: '{playlist_name}'")
            try:
                # Search for videos that might be in this playlist
                results = client.search_videos(f'"{playlist_name}"', max_results=3)
                if results:
                    print(f"   ✅ Found {len(results)} videos related to '{playlist_name}':")
                    for result in results:
                        print(f"      - {result.title}")
                        print(f"        Channel: {result.channel_title} (ID: {result.channel_id})")
                else:
                    print(f"   ❌ No public videos found for '{playlist_name}'")
            except Exception as e:
                print(f"   ❌ Search error: {e}")
        
        print(f"\n💡 NEXT STEPS:")
        print("To access your personal playlists, please provide your YouTube channel ID.")
        print("Once we have that, we can:")
        print("1. List all your playlists")
        print("2. Find the exact matches for your target playlists")
        print("3. Set up the interactive approval process")
        
        # Show quota usage
        print(f"\n📊 API Quota Usage:")
        print(f"   Used: {client.quota_manager.used_quota}")
        print(f"   Remaining: {client.quota_manager.daily_quota - client.quota_manager.used_quota}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()