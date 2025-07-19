import os
import shutil
import glob

def force_cleanup_downloads():
    """Aggressively clean up the download directory"""
    
    download_dir = 'media/songs'
    
    if not os.path.exists(download_dir):
        print("Download directory doesn't exist.")
        return
    
    print("🧹 Force cleaning download directory...")
    
    # Get all files
    all_files = os.listdir(download_dir)
    print(f"Found {len(all_files)} files")
    
    # Keep only valid MP3 files
    kept_files = []
    removed_files = []
    
    for filename in all_files:
        file_path = os.path.join(download_dir, filename)
        
        if not os.path.isfile(file_path):
            continue
        
        # Keep only MP3 files that are reasonably sized
        if filename.endswith('.mp3') and os.path.getsize(file_path) > 10000:
            kept_files.append(filename)
            print(f"✅ Keeping: {filename} ({os.path.getsize(file_path)} bytes)")
        else:
            try:
                os.remove(file_path)
                removed_files.append(filename)
                print(f"🗑️ Removed: {filename}")
            except Exception as e:
                print(f"❌ Could not remove {filename}: {e}")
    
    print(f"\n📊 Summary:")
    print(f"   Kept: {len(kept_files)} files")
    print(f"   Removed: {len(removed_files)} files")
    
    if removed_files:
        print(f"\n🗑️ Removed files:")
        for f in removed_files:
            print(f"   - {f}")
    
    if kept_files:
        print(f"\n✅ Kept files:")
        for f in kept_files:
            print(f"   - {f}")
    else:
        print("\n📁 Download directory is now clean (no valid MP3 files found)")

def test_single_download():
    """Test downloading a single, known-good video"""
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from services.music_downloader import music_downloader
    
    print("\n🎵 Testing single download...")
    
    # Use a very short, simple video for testing
    test_id = "jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video, very short
    
    print(f"Testing with video ID: {test_id}")
    
    # Clean up first
    music_downloader.cleanup_problematic_files()
    music_downloader._cleanup_partial_downloads(test_id)
    
    # Try download
    result = music_downloader.download_song(test_id, "Test Video", "Test Channel")
    
    if result['success']:
        print("🎉 Test download successful!")
        print(f"File: {result['path']}")
        print(f"Size: {result.get('file_size', 'Unknown')} bytes")
    else:
        print("❌ Test download failed!")
        print(f"Error: {result['error']}")
        
        # Show what files are in the directory
        download_dir = 'media/songs'
        if os.path.exists(download_dir):
            files = os.listdir(download_dir)
            print(f"Files in download directory: {files}")
    
    return result['success']

if __name__ == '__main__':
    force_cleanup_downloads()
    
    # Ask if user wants to test
    test_choice = input("\n🧪 Would you like to test a download? (y/n): ").lower().strip()
    if test_choice == 'y':
        success = test_single_download()
        if success:
            print("\n✅ Download system is working!")
        else:
            print("\n❌ Download system needs more troubleshooting.")
            print("\n🔧 Try these steps:")
            print("1. Check FFmpeg: ffmpeg -version")
            print("2. Update yt-dlp: pip install --upgrade yt-dlp")
            print("3. Check internet connection")
            print("4. Try a different video ID")
