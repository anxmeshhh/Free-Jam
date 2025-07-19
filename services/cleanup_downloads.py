import os
import glob
import shutil

def cleanup_download_directory():
    """Clean up the download directory from problematic files"""
    
    download_dir = 'media/songs'
    
    if not os.path.exists(download_dir):
        print("Download directory doesn't exist yet.")
        return
    
    print("🧹 Cleaning up download directory...")
    
    # Files to remove
    problematic_extensions = ['.mhtml', '.html', '.part', '.tmp', '.ytdl', '.json', '.info']
    removed_count = 0
    
    try:
        for filename in os.listdir(download_dir):
            file_path = os.path.join(download_dir, filename)
            
            # Remove problematic files
            should_remove = False
            
            for ext in problematic_extensions:
                if filename.endswith(ext):
                    should_remove = True
                    break
            
            # Remove empty files
            if os.path.isfile(file_path) and os.path.getsize(file_path) == 0:
                should_remove = True
            
            # Remove very small files (likely corrupted)
            if (os.path.isfile(file_path) and 
                os.path.getsize(file_path) < 1000 and 
                not filename.endswith('.mp3')):
                should_remove = True
            
            if should_remove:
                try:
                    os.remove(file_path)
                    print(f"✅ Removed: {filename}")
                    removed_count += 1
                except Exception as e:
                    print(f"❌ Could not remove {filename}: {e}")
        
        print(f"\n🎉 Cleanup complete! Removed {removed_count} problematic files.")
        
        # Show remaining files
        remaining_files = [f for f in os.listdir(download_dir) if os.path.isfile(os.path.join(download_dir, f))]
        if remaining_files:
            print(f"\n📁 Remaining files ({len(remaining_files)}):")
            for f in remaining_files:
                file_path = os.path.join(download_dir, f)
                size = os.path.getsize(file_path)
                print(f"  {f} ({size} bytes)")
        else:
            print("\n📁 Download directory is now empty.")
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")

if __name__ == '__main__':
    cleanup_download_directory()
