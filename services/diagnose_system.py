import subprocess
import sys
import os

def check_dependencies():
    """Check if all required dependencies are available"""
    
    print("🔍 Diagnosing Free Jam Download System...\n")
    
    # Check Python packages
    packages = ['yt-dlp', 'pydub', 'mutagen', 'requests']
    
    print("📦 Checking Python packages:")
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - MISSING")
    
    # Check FFmpeg
    print("\n🎬 Checking FFmpeg:")
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"   ✅ FFmpeg found: {version_line}")
        else:
            print(f"   ❌ FFmpeg error: {result.stderr}")
    except FileNotFoundError:
        print("   ❌ FFmpeg not found in PATH")
    except Exception as e:
        print(f"   ❌ FFmpeg check failed: {e}")
    
    # Check yt-dlp version
    print("\n📺 Checking yt-dlp:")
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"   ✅ yt-dlp version: {version}")
        else:
            print(f"   ❌ yt-dlp error: {result.stderr}")
    except FileNotFoundError:
        print("   ❌ yt-dlp not found in PATH")
    except Exception as e:
        print(f"   ❌ yt-dlp check failed: {e}")
    
    # Check directories
    print("\n📁 Checking directories:")
    dirs = ['media', 'media/songs', 'services']
    for dir_path in dirs:
        if os.path.exists(dir_path):
            print(f"   ✅ {dir_path}")
        else:
            print(f"   ❌ {dir_path} - MISSING")
            try:
                os.makedirs(dir_path, exist_ok=True)
                print(f"      ✅ Created {dir_path}")
            except Exception as e:
                print(f"      ❌ Could not create {dir_path}: {e}")
    
    # Check download directory contents
    download_dir = 'media/songs'
    if os.path.exists(download_dir):
        files = os.listdir(download_dir)
        print(f"\n📂 Download directory contents ({len(files)} files):")
        if files:
            for f in files[:10]:  # Show first 10 files
                file_path = os.path.join(download_dir, f)
                size = os.path.getsize(file_path) if os.path.isfile(file_path) else 0
                print(f"   - {f} ({size} bytes)")
            if len(files) > 10:
                print(f"   ... and {len(files) - 10} more files")
        else:
            print("   (empty)")
    
    print("\n🎯 Recommendations:")
    print("1. If FFmpeg is missing: Install from https://ffmpeg.org/")
    print("2. If packages are missing: pip install -r requirements.txt")
    print("3. If yt-dlp is old: pip install --upgrade yt-dlp")
    print("4. Run: python scripts/force_cleanup.py")

if __name__ == '__main__':
    check_dependencies()
