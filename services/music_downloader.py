import os
import yt_dlp
import requests
from pydub import AudioSegment
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
import hashlib
import json
import time
import glob
import shutil
import random
from urllib.parse import urlparse

class MusicDownloader:
    def __init__(self, download_dir='media/songs'):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        
        # User agents to rotate through
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
    
    def get_song_path(self, youtube_id):
        """Get the file path for a downloaded song"""
        return os.path.join(self.download_dir, f"{youtube_id}.mp3")
    
    def is_downloaded(self, youtube_id):
        """Check if song is already downloaded"""
        return os.path.exists(self.get_song_path(youtube_id))
    
    def cleanup_all_files(self):
        """Clean up ALL non-MP3 files"""
        try:
            if not os.path.exists(self.download_dir):
                return
                
            for filename in os.listdir(self.download_dir):
                file_path = os.path.join(self.download_dir, filename)
                
                if os.path.isfile(file_path):
                    # Keep only valid MP3 files
                    if filename.endswith('.mp3') and os.path.getsize(file_path) > 10000:
                        continue
                    else:
                        try:
                            os.remove(file_path)
                            print(f"Cleaned up: {filename}")
                        except:
                            pass
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def check_video_availability(self, youtube_id):
        """Check if a video is available before attempting download"""
        try:
            opts = {
                'quiet': True,
                'no_warnings': True,
                'simulate': True,  # Don't download, just check
                'user_agent': random.choice(self.user_agents),
                'referer': 'https://www.youtube.com/',
                'geo_bypass': True,
                'nocheckcertificate': True,
            }
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={youtube_id}", download=False)
                
                if not info:
                    return False, "Video info not available"
                
                # Check for common unavailability indicators
                title = info.get('title', '')
                if 'unavailable' in title.lower() or 'private' in title.lower():
                    return False, f"Video unavailable: {title}"
                
                # Check if we have actual video formats (not just images)
                formats = info.get('formats', [])
                has_video_audio = False
                
                for fmt in formats:
                    if (fmt.get('acodec') != 'none' or 
                        (fmt.get('vcodec') != 'none' and fmt.get('ext') not in ['mhtml', 'webp', 'jpg'])):
                        has_video_audio = True
                        break
                
                if not has_video_audio:
                    return False, "Only images available - video content blocked"
                
                return True, f"Video available: {title}"
                
        except Exception as e:
            error_msg = str(e).lower()
            if 'private' in error_msg or 'unavailable' in error_msg or 'removed' in error_msg:
                return False, f"Video unavailable: {str(e)}"
            return False, f"Check failed: {str(e)}"
    
    def get_working_test_videos(self):
        """Get a list of videos that should definitely work"""
        # These are extremely popular, stable videos that rarely get removed
        return [
            {
                'id': 'dQw4w9WgXcQ',
                'title': 'Rick Astley - Never Gonna Give You Up',
                'reason': 'Most stable video on YouTube'
            },
            {
                'id': 'kJQP7kiw5Fk', 
                'title': 'Luis Fonsi - Despacito ft. Daddy Yankee',
                'reason': 'Most viewed video on YouTube'
            },
            {
                'id': '9bZkp7q19f0',
                'title': 'PSY - Gangnam Style',
                'reason': 'Historic viral video'
            },
            {
                'id': 'fJ9rUzIMcZQ',
                'title': 'Queen - Bohemian Rhapsody',
                'reason': 'Classic rock, official channel'
            },
            {
                'id': 'JGwWNGJdvx8',
                'title': 'Ed Sheeran - Shape of You',
                'reason': 'Popular recent song'
            }
        ]
    
    def find_working_video(self):
        """Find a video that actually works for testing"""
        test_videos = self.get_working_test_videos()
        
        print("🔍 Finding a working video for testing...")
        
        for video in test_videos:
            print(f"Testing: {video['id']} - {video['title']}")
            available, message = self.check_video_availability(video['id'])
            
            if available:
                print(f"✅ Found working video: {video['id']}")
                print(f"   Title: {video['title']}")
                print(f"   Reason: {video['reason']}")
                return video['id']
            else:
                print(f"❌ Not available: {message}")
            
            time.sleep(1)  # Small delay between checks
        
        print("❌ No working videos found")
        return None
    
    def download_song(self, youtube_id, title=None, artist=None, thumbnail_url=None):
        """Download a song with availability checking"""
        try:
            song_path = self.get_song_path(youtube_id)
            
            # Skip if already downloaded
            if self.is_downloaded(youtube_id):
                return {
                    'success': True,
                    'path': song_path,
                    'message': 'Song already downloaded',
                    'file_size': os.path.getsize(song_path)
                }
            
            print(f"Starting download: {youtube_id}")
            
            # Check availability first
            available, availability_message = self.check_video_availability(youtube_id)
            if not available:
                return {
                    'success': False,
                    'error': f'Video not available: {availability_message}'
                }
            
            print(f"✅ Video is available: {availability_message}")
            
            # Clean up first
            self.cleanup_all_files()
            
            # Simple, reliable download configurations
            download_configs = [
                # Strategy 1: Best audio only
                {
                    'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio',
                    'outtmpl': os.path.join(self.download_dir, '%(id)s.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'user_agent': random.choice(self.user_agents),
                    'referer': 'https://www.youtube.com/',
                    'quiet': True,
                    'no_warnings': True,
                },
                # Strategy 2: Any audio
                {
                    'format': 'bestaudio/best[height<=480]',
                    'outtmpl': os.path.join(self.download_dir, '%(id)s.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '128',
                    }],
                    'user_agent': random.choice(self.user_agents),
                    'referer': 'https://www.youtube.com/',
                    'quiet': True,
                    'no_warnings': True,
                },
                # Strategy 3: Minimal config
                {
                    'outtmpl': os.path.join(self.download_dir, '%(id)s.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '128',
                    }],
                    'quiet': False,  # Show output for debugging
                    'no_warnings': False,
                }
            ]
            
            downloaded_file = None
            last_error = None
            
            for i, config in enumerate(download_configs):
                try:
                    print(f"\n🔄 Trying download strategy {i+1}/{len(download_configs)}...")
                    
                    # Clean up before each attempt
                    self.cleanup_all_files()
                    
                    with yt_dlp.YoutubeDL(config) as ydl:
                        url = f"https://www.youtube.com/watch?v={youtube_id}"
                        ydl.download([url])
                    
                    # Look for downloaded file
                    downloaded_file = self._find_downloaded_file(youtube_id)
                    if downloaded_file:
                        print(f"✅ Strategy {i+1} successful: {downloaded_file}")
                        break
                    else:
                        print(f"❌ Strategy {i+1}: No file found after download")
                        
                except Exception as e:
                    last_error = str(e)
                    print(f"❌ Strategy {i+1} failed: {e}")
                    self.cleanup_all_files()
                    continue
            
            if not downloaded_file:
                return {
                    'success': False,
                    'error': f'All download strategies failed. Last error: {last_error}'
                }
            
            # Convert to MP3 if needed
            final_path = self._ensure_mp3_format(downloaded_file, song_path)
            
            if not final_path or not os.path.exists(final_path):
                return {
                    'success': False,
                    'error': 'Failed to create final MP3 file'
                }
            
            file_size = os.path.getsize(final_path)
            if file_size < 50000:  # Less than 50KB is suspicious
                os.remove(final_path)
                return {
                    'success': False,
                    'error': 'Downloaded file is too small to be valid audio'
                }
            
            # Add metadata
            try:
                self.add_metadata(final_path, title, artist, thumbnail_url)
            except Exception as e:
                print(f"Metadata error (non-critical): {e}")
            
            print(f"✅ Successfully downloaded: {final_path} ({file_size} bytes)")
            
            return {
                'success': True,
                'path': final_path,
                'message': 'Song downloaded successfully',
                'file_size': file_size
            }
            
        except Exception as e:
            print(f"❌ Critical error downloading {youtube_id}: {e}")
            self.cleanup_all_files()
            return {
                'success': False,
                'error': str(e)
            }
    
    def _find_downloaded_file(self, youtube_id):
        """Find downloaded file with any extension"""
        if not os.path.exists(self.download_dir):
            return None
            
        # Look for files starting with the YouTube ID (exclude problematic files)
        for filename in os.listdir(self.download_dir):
            if (filename.startswith(youtube_id) and 
                not filename.endswith(('.part', '.tmp', '.mhtml', '.html', '.webp', '.jpg'))):
                file_path = os.path.join(self.download_dir, filename)
                if os.path.isfile(file_path) and os.path.getsize(file_path) > 1000:
                    return file_path
        
        return None
    
    def _ensure_mp3_format(self, input_file, target_path):
        """Convert any audio file to MP3"""
        try:
            # If it's already MP3 and in the right place
            if input_file == target_path and input_file.endswith('.mp3'):
                return target_path
            
            # If it's MP3 but wrong location
            if input_file.endswith('.mp3'):
                shutil.move(input_file, target_path)
                return target_path
            
            print(f"🔄 Converting {os.path.basename(input_file)} to MP3...")
            
            # Try pydub first
            try:
                audio = AudioSegment.from_file(input_file)
                audio.export(target_path, format="mp3", bitrate="192k")
                
                if os.path.exists(target_path) and os.path.getsize(target_path) > 10000:
                    os.remove(input_file)
                    return target_path
            except Exception as e:
                print(f"Pydub failed: {e}")
            
            # Try ffmpeg directly
            try:
                import subprocess
                cmd = [
                    'ffmpeg', '-i', input_file,
                    '-acodec', 'libmp3lame', '-b:a', '192k',
                    '-ar', '44100', '-ac', '2',
                    '-y', target_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0 and os.path.exists(target_path) and os.path.getsize(target_path) > 10000:
                    os.remove(input_file)
                    return target_path
            except Exception as e:
                print(f"FFmpeg failed: {e}")
            
            # Last resort: rename if it's an audio format
            if any(input_file.endswith(ext) for ext in ['.m4a', '.aac', '.ogg', '.webm', '.mp4']):
                try:
                    shutil.move(input_file, target_path)
                    return target_path
                except Exception as e:
                    print(f"Move failed: {e}")
            
            return None
            
        except Exception as e:
            print(f"Conversion error: {e}")
            return None
    
    def add_metadata(self, mp3_path, title, artist, thumbnail_url=None):
        """Add metadata to MP3 file"""
        try:
            audio_file = MP3(mp3_path, ID3=ID3)
            
            try:
                audio_file.add_tags()
            except:
                pass
            
            if title:
                audio_file.tags.add(TIT2(encoding=3, text=title))
            if artist:
                audio_file.tags.add(TPE1(encoding=3, text=artist))
            
            audio_file.tags.add(TALB(encoding=3, text="Free Jam"))
            
            if thumbnail_url:
                try:
                    response = requests.get(thumbnail_url, timeout=10)
                    if response.status_code == 200:
                        audio_file.tags.add(
                            APIC(
                                encoding=3,
                                mime='image/jpeg',
                                type=3,
                                desc='Cover',
                                data=response.content
                            )
                        )
                except:
                    pass
            
            audio_file.save()
            
        except Exception as e:
            print(f"Metadata error: {e}")
    
    def get_song_duration(self, youtube_id):
        """Get duration of downloaded song"""
        try:
            song_path = self.get_song_path(youtube_id)
            if os.path.exists(song_path):
                audio = MP3(song_path)
                return int(audio.info.length)
            return 0
        except:
            return 0
    
    def delete_song(self, youtube_id):
        """Delete a downloaded song"""
        try:
            song_path = self.get_song_path(youtube_id)
            if os.path.exists(song_path):
                os.remove(song_path)
                return True
            return False
        except:
            return False

# Global downloader instance
music_downloader = MusicDownloader()
