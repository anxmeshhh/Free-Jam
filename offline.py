import os
import subprocess
import sys

def install_dependencies():
    """Install required dependencies for offline music functionality"""
    
    print("🎵 Setting up Free Jam Offline Music System...")
    
    # Required packages
    packages = [
        'yt-dlp==2023.10.13',
        'pydub==0.25.1',
        'mutagen==1.47.0'
    ]
    
    print("📦 Installing Python packages...")
    for package in packages:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✅ Installed {package}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False
    
    # Check for FFmpeg
    print("🔧 Checking for FFmpeg...")
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg is installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  FFmpeg not found. Please install FFmpeg:")
        print("   Windows: Download from https://ffmpeg.org/download.html")
        print("   macOS: brew install ffmpeg")
        print("   Ubuntu: sudo apt install ffmpeg")
        print("   Note: FFmpeg is required for audio conversion")
    
    # Create directories
    print("📁 Creating directories...")
    directories = [
        'media/songs',
        'services'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created {directory}")
    
    # Create __init__.py files
    init_files = [
        'services/__init__.py'
    ]
    
    for init_file in init_files:
        with open(init_file, 'w') as f:
            f.write('# Free Jam Services Module\n')
        print(f"✅ Created {init_file}")
    
    print("\n🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Make sure FFmpeg is installed and in your PATH")
    print("2. Set your YouTube API key: export YOUTUBE_API_KEY=your_key_here")
    print("3. Run: python scripts/fix_database.py")
    print("4. Start the app: python app.py")
    print("\n🎵 Features:")
    print("✅ Automatic song downloading from YouTube")
    print("✅ Offline playback with high-quality MP3")
    print("✅ Metadata and thumbnail embedding")
    print("✅ Background download queue")
    print("✅ Fallback to YouTube streaming")
    print("✅ Real-time download status")
    
    return True

if __name__ == '__main__':
    install_dependencies()
