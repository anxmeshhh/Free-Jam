import subprocess
import sys
import os

def install_dependencies():
    """Install all required dependencies for universal downloader"""
    print("🚀 INSTALLING UNIVERSAL DOWNLOADER DEPENDENCIES")
    print("=" * 60)
    
    # Required packages
    packages = [
        'yt-dlp>=2023.12.30',
        'requests>=2.31.0',
        'beautifulsoup4>=4.12.0',
        'selenium>=4.15.0',
        'pydub>=0.25.1',
        'mutagen>=1.47.0',
    ]
    
    print("📦 Installing Python packages...")
    for package in packages:
        try:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✅ {package} installed")
        except Exception as e:
            print(f"❌ Failed to install {package}: {e}")
    
    print("\n🌐 Checking ChromeDriver for Selenium...")
    try:
        # Try to install chromedriver-autoinstaller
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'chromedriver-autoinstaller'])
        
        # Auto-install ChromeDriver
        import chromedriver_autoinstaller
        chromedriver_autoinstaller.install()
        print("✅ ChromeDriver installed automatically")
    except Exception as e:
        print("⚠️ ChromeDriver auto-install failed")
        print("📝 Manual installation required:")
        print("   1. Download ChromeDriver from https://chromedriver.chromium.org/")
        print("   2. Add to PATH or place in project directory")
    
    print("\n🎬 Checking FFmpeg...")
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg is available")
    except:
        print("⚠️ FFmpeg not found")
        print("📝 Install FFmpeg:")
        print("   Windows: Download from https://ffmpeg.org/")
        print("   macOS: brew install ffmpeg")
        print("   Linux: sudo apt install ffmpeg")
    
    print("\n🎉 Installation complete!")
    print("🧪 Run: python scripts/test_universal_downloader.py")

if __name__ == '__main__':
    install_dependencies()
