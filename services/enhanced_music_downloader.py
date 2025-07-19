import os
import sys
from .universal_downloader import universal_downloader

class EnhancedMusicDownloader:
    """Enhanced music downloader that uses the universal downloader as backend"""
    
    def __init__(self, download_dir='media/songs'):
        self.download_dir = download_dir
        self.universal = universal_downloader
    
    def download_song(self, youtube_id, title=None, artist=None, thumbnail_url=None):
        """Download song using universal downloader with Free Jam compatibility"""
        try:
            # Use universal downloader
            result = self.universal.download_video(youtube_id, title=title)
            
            if result['success']:
                # Add metadata if provided
                if title or artist or thumbnail_url:
                    self._add_metadata(result['path'], title, artist, thumbnail_url)
                
                return {
                    'success': True,
                    'path': result['path'],
                    'file_size': result['file_size'],
                    'message': f"Downloaded successfully using {result['method']}"
                }
            else:
                return {
                    'success': False,
                    'error': result['error']
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Enhanced downloader error: {str(e)}"
            }
    
    def is_downloaded(self, youtube_id):
        """Check if song is downloaded"""
        return self.universal.is_downloaded(youtube_id)
    
    def get_song_path(self, youtube_id):
        """Get path to downloaded song"""
        return self.universal.get_song_path(youtube_id)
    
    def get_song_info(self, youtube_id):
        """Get video information"""
        return self.universal.get_video_info(youtube_id)
    
    def _add_metadata(self, mp3_path, title, artist, thumbnail_url):
        """Add metadata to MP3 file"""
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
            import requests
            
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

# Global instance for Free Jam compatibility
enhanced_music_downloader = EnhancedMusicDownloader()
