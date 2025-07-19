import os
import sys
import subprocess
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_and_install_dependencies():
    """Check and install all required dependencies"""
    print("🔧 Checking and installing dependencies...")
    
    # Required packages
    packages = [
        'yt-dlp>=2023.12.30',
        'pydub>=0.25.1',
        'mutagen>=1.47.0',
        'requests>=2.31.0'
    ]
    
    for package in packages:
        try:
            package_name = package.split('>=')[0].replace('-', '_')
            __import__(package_name)
            print(f"✅ {package} - OK")
        except ImportError:
            print(f"📦 Installing {package}...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"✅ {package} - INSTALLED")
            except Exception as e:
                print(f"❌ Failed to install {package}: {e}")
                return False
    
    return True

def update_ytdlp():
    """Update yt-dlp to latest version"""
    print("\n📺 Updating yt-dlp to latest version...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'])
        print("✅ yt-dlp updated successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to update yt-dlp: {e}")
        return False

def check_ffmpeg():
    """Check FFmpeg installation"""
    print("\n🎬 Checking FFmpeg...")
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"✅ FFmpeg found: {version}")
            return True
        else:
            print(f"❌ FFmpeg error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ FFmpeg not found!")
        print("📥 Please install FFmpeg:")
        print("   Windows: Download from https://ffmpeg.org/download.html")
        print("   macOS: brew install ffmpeg")
        print("   Linux: sudo apt install ffmpeg")
        return False
    except Exception as e:
        print(f"❌ FFmpeg check failed: {e}")
        return False

def setup_directories():
    """Create necessary directories"""
    print("\n📁 Setting up directories...")
    dirs = ['media', 'media/songs', 'services']
    
    for dir_path in dirs:
        try:
            os.makedirs(dir_path, exist_ok=True)
            print(f"✅ {dir_path}")
        except Exception as e:
            print(f"❌ Could not create {dir_path}: {e}")
            return False
    
    # Create __init__.py for services
    init_file = 'services/__init__.py'
    if not os.path.exists(init_file):
        with open(init_file, 'w') as f:
            f.write('# Free Jam Services\n')
        print(f"✅ Created {init_file}")
    
    return True

def clean_download_directory():
    """Clean the download directory"""
    print("\n🧹 Cleaning download directory...")
    download_dir = 'media/songs'
    
    if not os.path.exists(download_dir):
        print("📁 Download directory doesn't exist yet")
        return True
    
    files = os.listdir(download_dir)
    removed = 0
    
    for filename in files:
        file_path = os.path.join(download_dir, filename)
        if os.path.isfile(file_path):
            # Keep only valid MP3 files
            if filename.endswith('.mp3') and os.path.getsize(file_path) > 10000:
                continue
            else:
                try:
                    os.remove(file_path)
                    removed += 1
                    print(f"🗑️ Removed: {filename}")
                except:
                    pass
    
    print(f"✅ Cleaned {removed} files")
    return True

def test_download_system():
    """Test the download system with multiple videos"""
    print("\n🎵 Testing download system...")
    
    try:
        from services.music_downloader import music_downloader
        
        # Find a working video first
        working_video = music_downloader.find_working_video()
        
        if not working_video:
            print("❌ Could not find any working video to test with")
            return False
        
        print(f"🎯 Testing with video: {working_video}")
        
        # Test download
        result = music_downloader.download_song(
            working_video,
            "Test Song",
            "Test Artist",
            f"https://img.youtube.com/vi/{working_video}/mqdefault.jpg"
        )
        
        if result['success']:
            print("🎉 Download test SUCCESSFUL!")
            print(f"📁 File: {result['path']}")
            print(f"📊 Size: {result['file_size']} bytes")
            
            # Verify file exists and is valid
            if os.path.exists(result['path']) and os.path.getsize(result['path']) > 50000:
                print("✅ File verification passed")
                return True
            else:
                print("❌ File verification failed")
                return False
        else:
            print("❌ Download test FAILED!")
            print(f"Error: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

def main():
    """Main fix function"""
    print("🚀 FREE JAM ULTIMATE FIX SCRIPT")
    print("=" * 50)
    
    success_steps = 0
    total_steps = 6
    
    # Step 1: Dependencies
    if check_and_install_dependencies():
        success_steps += 1
    
    # Step 2: Update yt-dlp
    if update_ytdlp():
        success_steps += 1
    
    # Step 3: Check FFmpeg
    if check_ffmpeg():
        success_steps += 1
    
    # Step 4: Setup directories
    if setup_directories():
        success_steps += 1
    
    # Step 5: Clean directory
    if clean_download_directory():
        success_steps += 1
    
    # Step 6: Test system
    if test_download_system():
        success_steps += 1
    
    print("\n" + "=" * 50)
    print(f"📊 RESULTS: {success_steps}/{total_steps} steps successful")
    
    if success_steps == total_steps:
        print("🎉 ALL SYSTEMS GO! Free Jam is ready to rock!")
        print("\n🚀 Next steps:")
        print("1. Run: python app.py")
        print("2. Open: http://localhost:5000")
        print("3. Start jamming! 🎵")
    else:
        print("⚠️ Some issues remain. Check the errors above.")
        print("\n🔧 Manual steps you might need:")
        print("1. Install FFmpeg manually")
        print("2. Check your internet connection")
        print("3. Try running this script again")
    
    return success_steps == total_steps

if __name__ == '__main__':
    main()
