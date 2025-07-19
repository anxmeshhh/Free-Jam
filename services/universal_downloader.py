import os
import requests
import yt_dlp
import time
import random
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import subprocess
from pydub import AudioSegment

class UniversalYouTubeDownloader:
    def __init__(self, download_dir='media/songs'):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        
        # User agents for web scraping
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        # Y2mate.com endpoints
        self.y2mate_endpoints = [
            'https://v2.www-y2mate.com/',
            'https://www.y2mate.com/',
            'https://y2mate.is/',
            'https://y2mate.guru/',
        ]
    
    def get_song_path(self, youtube_id):
        """Get the file path for a downloaded song"""
        return os.path.join(self.download_dir, f"{youtube_id}.mp3")
    
    def is_downloaded(self, youtube_id):
        """Check if song is already downloaded"""
        return os.path.exists(self.get_song_path(youtube_id))
    
    def download_video(self, youtube_url_or_id, title=None, quality='best'):
        """
        Universal download method that tries multiple strategies
        """
        # Extract video ID if full URL provided
        youtube_id = self._extract_video_id(youtube_url_or_id)
        if not youtube_id:
            return {'success': False, 'error': 'Invalid YouTube URL or ID'}
        
        youtube_url = f"https://www.youtube.com/watch?v={youtube_id}"
        
        # Check if already downloaded
        if self.is_downloaded(youtube_id):
            return {
                'success': True,
                'path': self.get_song_path(youtube_id),
                'method': 'already_downloaded',
                'file_size': os.path.getsize(self.get_song_path(youtube_id))
            }
        
        print(f"🎵 Starting universal download for: {youtube_id}")
        
        # Strategy 1: Direct yt-dlp (fastest)
        result = self._download_with_ytdlp(youtube_url, youtube_id, title, quality)
        if result['success']:
            return result
        
        print("❌ yt-dlp failed, trying web scrapers...")
        
        # Strategy 2: Y2mate.com scraping
        result = self._download_with_y2mate(youtube_url, youtube_id, title)
        if result['success']:
            return result
        
        # Strategy 3: Alternative scrapers
        result = self._download_with_alternative_scrapers(youtube_url, youtube_id, title)
        if result['success']:
            return result
        
        # Strategy 4: Selenium-based scraping (last resort)
        result = self._download_with_selenium(youtube_url, youtube_id, title)
        if result['success']:
            return result
        
        return {
            'success': False,
            'error': 'All download methods failed',
            'tried_methods': ['yt-dlp', 'y2mate', 'alternative_scrapers', 'selenium']
        }
    
    def _extract_video_id(self, url_or_id):
        """Extract YouTube video ID from URL or return ID if already provided"""
        if len(url_or_id) == 11 and url_or_id.isalnum():
            return url_or_id
        
        # Extract from various YouTube URL formats
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        
        return None
    
    def _download_with_ytdlp(self, youtube_url, youtube_id, title, quality):
        """Download using yt-dlp with multiple configurations"""
        print("🔄 Trying yt-dlp download...")
        
        configs = [
            # High quality audio
            {
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio',
                'outtmpl': os.path.join(self.download_dir, '%(id)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            },
            # Medium quality
            {
                'format': 'bestaudio/best[height<=720]',
                'outtmpl': os.path.join(self.download_dir, '%(id)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            },
            # Any available format
            {
                'outtmpl': os.path.join(self.download_dir, '%(id)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',
                }],
            }
        ]
        
        for i, config in enumerate(configs):
            try:
                config.update({
                    'user_agent': random.choice(self.user_agents),
                    'referer': 'https://www.youtube.com/',
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                })
                
                with yt_dlp.YoutubeDL(config) as ydl:
                    ydl.download([youtube_url])
                
                # Check if file was created
                output_path = self.get_song_path(youtube_id)
                if os.path.exists(output_path):
                    return {
                        'success': True,
                        'path': output_path,
                        'method': f'yt-dlp_config_{i+1}',
                        'file_size': os.path.getsize(output_path)
                    }
                
            except Exception as e:
                print(f"yt-dlp config {i+1} failed: {e}")
                continue
        
        return {'success': False, 'error': 'All yt-dlp configurations failed'}
    
    def _download_with_y2mate(self, youtube_url, youtube_id, title):
        """Download using Y2mate.com scraping"""
        print("🔄 Trying Y2mate.com download...")
        
        for endpoint in self.y2mate_endpoints:
            try:
                result = self._scrape_y2mate(endpoint, youtube_url, youtube_id, title)
                if result['success']:
                    return result
            except Exception as e:
                print(f"Y2mate endpoint {endpoint} failed: {e}")
                continue
        
        return {'success': False, 'error': 'All Y2mate endpoints failed'}
    
    def _scrape_y2mate(self, base_url, youtube_url, youtube_id, title):
        """Scrape Y2mate.com for download links"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Referer': base_url,
            'Origin': base_url.rstrip('/'),
        })
        
        try:
            # Step 1: Get the main page
            response = session.get(base_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Step 2: Submit the YouTube URL
            # Look for the form or AJAX endpoint
            form = soup.find('form') or soup.find('div', {'id': 'main'})
            
            # Try different Y2mate API patterns
            api_endpoints = [
                urljoin(base_url, 'mates/analyze/ajax'),
                urljoin(base_url, 'mates/en/analyze/ajax'),
                urljoin(base_url, 'ajax'),
                urljoin(base_url, 'analyze'),
            ]
            
            for api_endpoint in api_endpoints:
                try:
                    # Submit URL for analysis
                    analyze_data = {
                        'url': youtube_url,
                        'q_auto': '1',
                        'ajax': '1'
                    }
                    
                    analyze_response = session.post(
                        api_endpoint,
                        data=analyze_data,
                        timeout=15,
                        headers={
                            'X-Requested-With': 'XMLHttpRequest',
                            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        }
                    )
                    
                    if analyze_response.status_code == 200:
                        analyze_result = analyze_response.json()
                        
                        if analyze_result.get('status') == 'ok':
                            # Extract download links
                            download_url = self._extract_y2mate_download_link(
                                analyze_result, session, base_url, youtube_id
                            )
                            
                            if download_url:
                                # Download the file
                                return self._download_file_from_url(
                                    download_url, youtube_id, session, 'y2mate'
                                )
                
                except Exception as e:
                    print(f"Y2mate API {api_endpoint} failed: {e}")
                    continue
            
            return {'success': False, 'error': 'Could not extract download link from Y2mate'}
            
        except Exception as e:
            return {'success': False, 'error': f'Y2mate scraping failed: {e}'}
    
    def _extract_y2mate_download_link(self, analyze_result, session, base_url, youtube_id):
        """Extract actual download link from Y2mate response"""
        try:
            # Parse the HTML response for download buttons
            html_content = analyze_result.get('result', '')
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for MP3 download buttons
            mp3_buttons = soup.find_all('td', string=re.compile(r'mp3|MP3'))
            
            for button_row in mp3_buttons:
                parent_row = button_row.find_parent('tr')
                if parent_row:
                    download_btn = parent_row.find('button', {'class': 'btn'}) or parent_row.find('a', {'class': 'btn'})
                    
                    if download_btn:
                        # Get the data attributes for the download request
                        data_ftype = download_btn.get('data-ftype', 'mp3')
                        data_fquality = download_btn.get('data-fquality', '128')
                        
                        # Make the download request
                        convert_data = {
                            'type': 'youtube',
                            'ftype': data_ftype,
                            'fquality': data_fquality,
                            'token': analyze_result.get('token', ''),
                            'timeExpire': analyze_result.get('timeExpires', ''),
                            'client': 'y2mate'
                        }
                        
                        convert_endpoint = urljoin(base_url, 'mates/convert')
                        convert_response = session.post(
                            convert_endpoint,
                            data=convert_data,
                            timeout=30,
                            headers={'X-Requested-With': 'XMLHttpRequest'}
                        )
                        
                        if convert_response.status_code == 200:
                            convert_result = convert_response.json()
                            
                            if convert_result.get('status') == 'ok':
                                # Extract download URL from result
                                result_html = convert_result.get('result', '')
                                result_soup = BeautifulSoup(result_html, 'html.parser')
                                
                                download_link = result_soup.find('a', {'href': True})
                                if download_link:
                                    return download_link['href']
            
            return None
            
        except Exception as e:
            print(f"Error extracting Y2mate download link: {e}")
            return None
    
    def _download_with_alternative_scrapers(self, youtube_url, youtube_id, title):
        """Try alternative scraping services"""
        print("🔄 Trying alternative scrapers...")
        
        alternative_services = [
            {
                'name': 'SaveFrom.net',
                'url': 'https://en.savefrom.net/',
                'method': self._scrape_savefrom
            },
            {
                'name': 'KeepVid',
                'url': 'https://keepvid.ch/',
                'method': self._scrape_keepvid
            },
            {
                'name': 'YouTubeMP3',
                'url': 'https://youtubemp3.ch/',
                'method': self._scrape_youtubemp3
            }
        ]
        
        for service in alternative_services:
            try:
                print(f"Trying {service['name']}...")
                result = service['method'](service['url'], youtube_url, youtube_id, title)
                if result['success']:
                    return result
            except Exception as e:
                print(f"{service['name']} failed: {e}")
                continue
        
        return {'success': False, 'error': 'All alternative scrapers failed'}
    
    def _scrape_savefrom(self, base_url, youtube_url, youtube_id, title):
        """Scrape SaveFrom.net"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Referer': base_url,
        })
        
        try:
            # SaveFrom.net API
            api_url = 'https://worker.sf-tools.com/savefrom'
            
            response = session.post(api_url, data={
                'sf_url': youtube_url,
                'sf_submit': '',
                'new': '2'
            }, timeout=15)
            
            if response.status_code == 200:
                # Parse response for download links
                data = response.json()
                
                for item in data.get('url_info', []):
                    if item.get('type') == 'audio' or 'mp3' in item.get('ext', '').lower():
                        download_url = item.get('url')
                        if download_url:
                            return self._download_file_from_url(
                                download_url, youtube_id, session, 'savefrom'
                            )
            
            return {'success': False, 'error': 'No suitable format found on SaveFrom'}
            
        except Exception as e:
            return {'success': False, 'error': f'SaveFrom scraping failed: {e}'}
    
    def _scrape_keepvid(self, base_url, youtube_url, youtube_id, title):
        """Scrape KeepVid"""
        # Similar implementation for KeepVid
        return {'success': False, 'error': 'KeepVid scraper not implemented yet'}
    
    def _scrape_youtubemp3(self, base_url, youtube_url, youtube_id, title):
        """Scrape YouTubeMP3"""
        # Similar implementation for YouTubeMP3
        return {'success': False, 'error': 'YouTubeMP3 scraper not implemented yet'}
    
    def _download_with_selenium(self, youtube_url, youtube_id, title):
        """Last resort: Use Selenium for JavaScript-heavy sites"""
        print("🔄 Trying Selenium-based download (last resort)...")
        
        try:
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument(f'--user-agent={random.choice(self.user_agents)}')
            
            # Try to create driver
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                # Navigate to Y2mate
                driver.get('https://v2.www-y2mate.com/')
                
                # Find URL input and submit
                url_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="text"]'))
                )
                
                url_input.clear()
                url_input.send_keys(youtube_url)
                
                # Click submit button
                submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
                submit_btn.click()
                
                # Wait for results and find MP3 download link
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.btn'))
                )
                
                # Look for MP3 download buttons
                mp3_buttons = driver.find_elements(By.XPATH, "//td[contains(text(), 'mp3')]/following-sibling::td//button")
                
                if mp3_buttons:
                    mp3_buttons[0].click()
                    
                    # Wait for download link
                    download_link = WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="download"]'))
                    )
                    
                    download_url = download_link.get_attribute('href')
                    
                    if download_url:
                        # Download using requests
                        session = requests.Session()
                        return self._download_file_from_url(
                            download_url, youtube_id, session, 'selenium'
                        )
                
                return {'success': False, 'error': 'No download link found with Selenium'}
                
            finally:
                driver.quit()
                
        except Exception as e:
            return {'success': False, 'error': f'Selenium download failed: {e}'}
    
    def _download_file_from_url(self, download_url, youtube_id, session, method):
        """Download file from direct URL"""
        try:
            print(f"📥 Downloading from {method}: {download_url}")
            
            response = session.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Determine file extension from headers or URL
            content_type = response.headers.get('content-type', '')
            if 'audio/mpeg' in content_type or download_url.endswith('.mp3'):
                file_ext = '.mp3'
            elif 'audio/mp4' in content_type or download_url.endswith('.m4a'):
                file_ext = '.m4a'
            else:
                file_ext = '.mp3'  # Default
            
            temp_path = os.path.join(self.download_dir, f"{youtube_id}_temp{file_ext}")
            final_path = self.get_song_path(youtube_id)
            
            # Download file
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Convert to MP3 if needed
            if file_ext != '.mp3':
                self._convert_to_mp3(temp_path, final_path)
                os.remove(temp_path)
            else:
                os.rename(temp_path, final_path)
            
            file_size = os.path.getsize(final_path)
            
            if file_size < 50000:  # Less than 50KB is suspicious
                os.remove(final_path)
                return {'success': False, 'error': 'Downloaded file too small'}
            
            return {
                'success': True,
                'path': final_path,
                'method': method,
                'file_size': file_size
            }
            
        except Exception as e:
            return {'success': False, 'error': f'File download failed: {e}'}
    
    def _convert_to_mp3(self, input_path, output_path):
        """Convert audio file to MP3"""
        try:
            # Try pydub first
            audio = AudioSegment.from_file(input_path)
            audio.export(output_path, format="mp3", bitrate="192k")
        except:
            # Fallback to ffmpeg
            subprocess.run([
                'ffmpeg', '-i', input_path,
                '-acodec', 'libmp3lame', '-b:a', '192k',
                '-y', output_path
            ], check=True, capture_output=True)
    
    def get_video_info(self, youtube_url_or_id):
        """Get video information"""
        youtube_id = self._extract_video_id(youtube_url_or_id)
        if not youtube_id:
            return None
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={youtube_id}",
                    download=False
                )
                
                return {
                    'id': youtube_id,
                    'title': info.get('title', 'Unknown'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'view_count': info.get('view_count', 0),
                }
        except:
            return {
                'id': youtube_id,
                'title': 'Unknown Video',
                'uploader': 'Unknown',
                'duration': 0,
                'thumbnail': f'https://img.youtube.com/vi/{youtube_id}/mqdefault.jpg',
                'view_count': 0,
            }

# Global instance
universal_downloader = UniversalYouTubeDownloader()
