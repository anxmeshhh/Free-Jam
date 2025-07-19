import threading
import queue
import time
from .music_downloader import music_downloader

class DownloadQueue:
    def __init__(self):
        self.download_queue = queue.Queue()
        self.download_status = {}
        self.worker_thread = None
        self.running = False
        self.callbacks = {}
        self.start_worker()
    
    def start_worker(self):
        """Start the background download worker"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            print("Download worker started")
    
    def stop_worker(self):
        """Stop the background download worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join()
    
    def add_to_queue(self, youtube_id, title, artist, thumbnail_url, callback=None):
        """Add a song to the download queue"""
        if music_downloader.is_downloaded(youtube_id):
            if callback:
                callback(youtube_id, {'success': True, 'message': 'Already downloaded'})
            return
        
        # Check if already in queue
        if youtube_id in self.download_status:
            print(f"Song {youtube_id} already in download queue")
            return
        
        self.download_status[youtube_id] = {
            'status': 'queued',
            'progress': 0,
            'message': 'Queued for download'
        }
        
        # Store callback for later use
        if callback:
            self.callbacks[youtube_id] = callback
        
        self.download_queue.put({
            'youtube_id': youtube_id,
            'title': title,
            'artist': artist,
            'thumbnail_url': thumbnail_url
        })
        
        print(f"Added {youtube_id} to download queue (Title: {title})")
    
    def get_status(self, youtube_id):
        """Get download status for a song"""
        if music_downloader.is_downloaded(youtube_id):
            return {
                'status': 'completed',
                'progress': 100,
                'message': 'Download completed'
            }
        
        return self.download_status.get(youtube_id, {
            'status': 'not_started',
            'progress': 0,
            'message': 'Not in queue'
        })
    
    def get_queue_size(self):
        """Get current queue size"""
        return self.download_queue.qsize()
    
    def get_all_status(self):
        """Get status of all downloads"""
        return self.download_status.copy()
    
    def _worker(self):
        """Background worker that processes the download queue"""
        while self.running:
            try:
                # Get next item from queue (with timeout)
                try:
                    item = self.download_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                youtube_id = item['youtube_id']
                
                # Skip if already downloaded (double-check)
                if music_downloader.is_downloaded(youtube_id):
                    print(f"Skipping {youtube_id} - already downloaded")
                    self.download_queue.task_done()
                    continue
                
                # Update status to downloading
                self.download_status[youtube_id] = {
                    'status': 'downloading',
                    'progress': 50,
                    'message': 'Downloading from YouTube...'
                }
                
                print(f"Starting download: {youtube_id} - {item['title']}")
                
                # Download the song
                result = music_downloader.download_song(
                    youtube_id,
                    item['title'],
                    item['artist'],
                    item['thumbnail_url']
                )
                
                # Update status based on result
                if result['success']:
                    self.download_status[youtube_id] = {
                        'status': 'completed',
                        'progress': 100,
                        'message': 'Download completed successfully'
                    }
                    print(f"Download completed: {youtube_id}")
                else:
                    self.download_status[youtube_id] = {
                        'status': 'failed',
                        'progress': 0,
                        'message': f"Download failed: {result.get('error', 'Unknown error')}"
                    }
                    print(f"Download failed: {youtube_id} - {result.get('error')}")
                
                # Call callback if provided
                callback = self.callbacks.get(youtube_id)
                if callback:
                    try:
                        callback(youtube_id, result)
                    except Exception as e:
                        print(f"Callback error for {youtube_id}: {e}")
                    # Remove callback after use
                    del self.callbacks[youtube_id]
                
                # Mark task as done
                self.download_queue.task_done()
                
                # Small delay between downloads to prevent overwhelming the system
                time.sleep(2)
                
            except Exception as e:
                print(f"Error in download worker: {e}")
                time.sleep(5)  # Wait before retrying

# Global download queue instance
download_queue = DownloadQueue()
