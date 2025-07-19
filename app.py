import sqlite3
import os
import uuid
import json
import threading
import time
from datetime import datetime, timedelta
import requests
from urllib.parse import quote_plus
import re
from functools import wraps

# Import our music services
from services.music_downloader import music_downloader
from services.download_queue import download_queue

# Flask and SocketIO imports (assuming they are already imported in the original file)
from flask import Flask, render_template, request, jsonify, session, send_from_directory, url_for, redirect, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*")

# YouTube API Configuration
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', 'YOUR_YOUTUBE_API_KEY_HERE')
YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'
YOUTUBE_VIDEOS_URL = 'https://www.googleapis.com/youtube/v3/videos'

# Create necessary directories
os.makedirs('media', exist_ok=True)
os.makedirs('media/songs', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# Authentication decorator
def login_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
      if 'user_id' not in session:
          if request.is_json:
              return jsonify({'error': 'Authentication required'}), 401
          return redirect('/login')
      return f(*args, **kwargs)
  return decorated_function

# Database initialization
def init_db():
  conn = sqlite3.connect('freejam.db')
  cursor = conn.cursor()
  
  # Users table
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          email TEXT UNIQUE NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
  ''')
  
  # Rooms table with activity tracking
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS rooms (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          is_private BOOLEAN DEFAULT FALSE,
          pin TEXT,
          creator_id INTEGER,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          active_users INTEGER DEFAULT 0,
          current_song TEXT DEFAULT '',
          FOREIGN KEY (creator_id) REFERENCES users (id)
      )
  ''')
  
  # Songs table with download status
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS songs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          youtube_id TEXT UNIQUE NOT NULL,
          title TEXT NOT NULL,
          duration INTEGER,
          thumbnail TEXT DEFAULT '',
          channel_title TEXT DEFAULT '',
          is_downloaded BOOLEAN DEFAULT FALSE,
          download_path TEXT DEFAULT '',
          file_size INTEGER DEFAULT 0,
          added_by INTEGER,
          added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (added_by) REFERENCES users (id)
      )
  ''')
  
  # Room playlists table
  cursor.execute('''
      CREATE TABLE IF NOT EXISTS room_playlists (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          room_id TEXT,
          song_id INTEGER,
          position INTEGER,
          added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (room_id) REFERENCES rooms (id),
          FOREIGN KEY (song_id) REFERENCES songs (id)
      )
  ''')
  
  # Add missing columns if they don't exist (for existing databases)
  try:
      cursor.execute('ALTER TABLE rooms ADD COLUMN last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
  except sqlite3.OperationalError:
      pass
  
  try:
      cursor.execute('ALTER TABLE rooms ADD COLUMN active_users INTEGER DEFAULT 0')
  except sqlite3.OperationalError:
      pass
  
  try:
      cursor.execute('ALTER TABLE rooms ADD COLUMN current_song TEXT DEFAULT ""')
  except sqlite3.OperationalError:
      pass
  
  try:
      cursor.execute('ALTER TABLE songs ADD COLUMN thumbnail TEXT DEFAULT ""')
  except sqlite3.OperationalError:
      pass
  
  try:
      cursor.execute('ALTER TABLE songs ADD COLUMN channel_title TEXT DEFAULT ""')
  except sqlite3.OperationalError:
      pass
  
  try:
      cursor.execute('ALTER TABLE songs ADD COLUMN is_downloaded BOOLEAN DEFAULT FALSE')
  except sqlite3.OperationalError:
      pass
  
  try:
      cursor.execute('ALTER TABLE songs ADD COLUMN download_path TEXT DEFAULT ""')
  except sqlite3.OperationalError:
      pass
  
  try:
      cursor.execute('ALTER TABLE songs ADD COLUMN file_size INTEGER DEFAULT 0')
  except sqlite3.OperationalError:
      pass
  
  conn.commit()
  conn.close()

# Room state management
room_states = {}

class RoomState:
  def __init__(self, room_id):
      self.room_id = room_id
      self.current_song = None
      self.is_playing = False
      self.current_time = 0
      self.last_update = time.time()
      self.users = set()
      self.playlist = []

def get_room_state(room_id):
  if room_id not in room_states:
      room_states[room_id] = RoomState(room_id)
  return room_states[room_id]

def update_room_activity(room_id, user_count=None, current_song=None):
  """Update room activity in database with better error handling"""
  try:
      conn = sqlite3.connect('freejam.db')
      cursor = conn.cursor()
      
      # Check if columns exist first
      cursor.execute("PRAGMA table_info(rooms)")
      columns = [column[1] for column in cursor.fetchall()]
      
      if 'last_active' in columns and 'active_users' in columns and 'current_song' in columns:
          if user_count is not None:
              cursor.execute('''
                  UPDATE rooms 
                  SET last_active = CURRENT_TIMESTAMP, active_users = ?, current_song = ?
                  WHERE id = ?
              ''', (user_count, current_song or '', room_id))
          else:
              cursor.execute('''
                  UPDATE rooms 
                  SET last_active = CURRENT_TIMESTAMP
                  WHERE id = ?
              ''', (room_id,))
      
      conn.commit()
      conn.close()
  except Exception as e:
      print(f"Error updating room activity: {e}")

def get_live_rooms():
  """Get list of active rooms with better error handling"""
  try:
      conn = sqlite3.connect('freejam.db')
      cursor = conn.cursor()
      
      # Check if columns exist
      cursor.execute("PRAGMA table_info(rooms)")
      columns = [column[1] for column in cursor.fetchall()]
      
      if 'last_active' in columns and 'active_users' in columns:
          # Get rooms active in last 5 minutes with at least 1 user
          five_minutes_ago = datetime.now() - timedelta(minutes=5)
          
          cursor.execute('''
              SELECT r.id, r.name, r.is_private, r.active_users, r.current_song, 
                     u.name as creator_name, r.created_at
              FROM rooms r
              LEFT JOIN users u ON r.creator_id = u.id
              WHERE r.last_active > ? AND r.active_users > 0
              ORDER BY r.active_users DESC, r.last_active DESC
              LIMIT 20
          ''', (five_minutes_ago,))
      else:
          # Fallback query without activity columns
          cursor.execute('''
              SELECT r.id, r.name, r.is_private, 0, '', 
                     u.name as creator_name, r.created_at
              FROM rooms r
              LEFT JOIN users u ON r.creator_id = u.id
              ORDER BY r.created_at DESC
              LIMIT 20
          ''')
      
      rooms = []
      for row in cursor.fetchall():
          rooms.append({
              'id': row[0],
              'name': row[1],
              'is_private': bool(row[2]),
              'active_users': row[3],
              'current_song': row[4],
              'creator_name': row[5] or 'Unknown',
              'created_at': row[6]
          })
      
      conn.close()
      return rooms
  except Exception as e:
      print(f"Error getting live rooms: {e}")
      return []

def get_user_stats(user_id):
  """Get real-time user statistics"""
  try:
      conn = sqlite3.connect('freejam.db')
      cursor = conn.cursor()
      
      # Count rooms created by user
      cursor.execute('SELECT COUNT(*) FROM rooms WHERE creator_id = ?', (user_id,))
      rooms_created = cursor.fetchone()[0]
      
      # Count songs added by user
      cursor.execute('SELECT COUNT(*) FROM songs WHERE added_by = ?', (user_id,))
      songs_added = cursor.fetchone()[0]
      
      # Count downloaded songs
      cursor.execute('SELECT COUNT(*) FROM songs WHERE is_downloaded = TRUE AND added_by = ?', (user_id,))
      songs_downloaded = cursor.fetchone()[0]
      
      conn.close()
      return {
          'rooms_created': rooms_created, 
          'songs_added': songs_added,
          'songs_downloaded': songs_downloaded
      }
  except Exception as e:
      print(f"Error getting user stats: {e}")
      return {'rooms_created': 0, 'songs_added': 0, 'songs_downloaded': 0}

def parse_duration(duration_str):
  """Parse YouTube duration format PT4M13S to seconds"""
  import re
  pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
  match = re.match(pattern, duration_str)
  if not match:
      return 0
  
  hours = int(match.group(1) or 0)
  minutes = int(match.group(2) or 0)
  seconds = int(match.group(3) or 0)
  
  return hours * 3600 + minutes * 60 + seconds

def is_video_available(video_id):
  """Check if a YouTube video is available and not restricted"""
  try:
      if YOUTUBE_API_KEY == 'YOUR_YOUTUBE_API_KEY_HERE':
          return True  # Skip check if no API key
      
      # Get video details to check availability
      params = {
          'part': 'status,contentDetails',
          'id': video_id,
          'key': YOUTUBE_API_KEY
      }
      
      response = requests.get(YOUTUBE_VIDEOS_URL, params=params)
      data = response.json()
      
      if 'items' not in data or len(data['items']) == 0:
          return False
      
      video = data['items'][0]
      status = video.get('status', {})
      
      # Check if video is embeddable and not private/unlisted
      if not status.get('embeddable', True):
          return False
      
      if status.get('privacyStatus') in ['private', 'privacyStatusUnspecified']:
          return False
      
      # Check if video has content restrictions
      content_details = video.get('contentDetails', {})
      if content_details.get('regionRestriction', {}).get('blocked'):
          return False
      
      return True
      
  except Exception as e:
      print(f"Error checking video availability: {e}")
      return True  # Default to available if check fails

def search_youtube(query, max_results=8):
  """Search YouTube using the official API"""
  try:
      if YOUTUBE_API_KEY == 'YOUR_YOUTUBE_API_KEY_HERE':
          # Fallback to demo data if API key not set
          print("Warning: YouTube API key not set. Using demo data.")
          return [
              {
                  'id': f'dQw4w9WgXcQ',
                  'title': f'{query} - Demo Song {i+1}',
                  'duration': 180 + i * 30,
                  'thumbnail': f'https://img.youtube.com/vi/dQw4w9WgXcQ/mqdefault.jpg',
                  'channel_title': f'Demo Channel {i+1}'
              }
              for i in range(max_results)
          ]
      
      # Search for videos
      search_params = {
          'part': 'snippet',
          'q': query,
          'type': 'video',
          'maxResults': max_results,
          'key': YOUTUBE_API_KEY,
          'videoCategoryId': '10',  # Music category
          'order': 'relevance'
      }
      
      search_response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
      search_data = search_response.json()
      
      if 'items' not in search_data:
          print(f"YouTube API Error: {search_data}")
          return []
      
      # Get video IDs for duration lookup
      video_ids = [item['id']['videoId'] for item in search_data['items']]
      
      # Get video details including duration
      videos_params = {
          'part': 'contentDetails',
          'id': ','.join(video_ids),
          'key': YOUTUBE_API_KEY
      }
      
      videos_response = requests.get(YOUTUBE_VIDEOS_URL, params=videos_params)
      videos_data = videos_response.json()
      
      # Combine search results with duration data
      results = []
      for i, item in enumerate(search_data['items']):
          video_id = item['id']['videoId']
          snippet = item['snippet']
          
          # Find duration for this video
          duration = 0
          for video in videos_data.get('items', []):
              if video['id'] == video_id:
                  duration = parse_duration(video['contentDetails']['duration'])
                  break
          
          # Skip very short videos (likely ads or clips)
          if duration < 30:
              continue
          
          results.append({
              'id': video_id,
              'title': snippet['title'],
              'duration': duration,
              'thumbnail': snippet['thumbnails']['medium']['url'],
              'channel_title': snippet['channelTitle']
          })
      
      return results
      
  except Exception as e:
      print(f"YouTube search error: {e}")
      return []

def download_callback(youtube_id, result):
  """Callback function for when a download completes"""
  try:
      conn = sqlite3.connect('freejam.db')
      cursor = conn.cursor()
      
      if result['success']:
          # Update song as downloaded
          file_size = result.get('file_size', 0)
          
          cursor.execute('''
              UPDATE songs 
              SET is_downloaded = TRUE, download_path = ?, file_size = ?
              WHERE youtube_id = ?
          ''', (result['path'], file_size, youtube_id))
          
          print(f"Marked song {youtube_id} as downloaded")
          
          # Check if this should become the current song in any room
          cursor.execute('''
              SELECT DISTINCT rp.room_id 
              FROM room_playlists rp
              JOIN songs s ON rp.song_id = s.id
              WHERE s.youtube_id = ?
          ''', (youtube_id,))
          
          rooms_with_song = cursor.fetchall()
          
          for (room_id,) in rooms_with_song:
              room_state = get_room_state(room_id)
              
              # Update playlist to reflect download status
              for song in room_state.playlist:
                  if song['youtube_id'] == youtube_id:
                      song['is_downloaded'] = True
                      break
              
              # If no current song, make this the current song
              if not room_state.current_song:
                  # Find the song in the playlist
                  for song in room_state.playlist:
                      if song['youtube_id'] == youtube_id:
                          room_state.current_song = song
                          update_room_activity(room_id, len(room_state.users), song['title'])
                          
                          # Notify room that song is ready to play
                          socketio.emit('song_changed', {
                              'song': song,
                              'is_playing': False,
                              'current_time': 0
                          }, room=room_id)
                          break
      else:
          print(f"Download failed for {youtube_id}: {result.get('error')}")
      
      conn.commit()
      conn.close()
      
      # Notify all users about download completion
      socketio.emit('song_download_complete', {
          'youtube_id': youtube_id,
          'success': result['success'],
          'message': result.get('message', result.get('error', ''))
      })
      
  except Exception as e:
      print(f"Error in download callback: {e}")

def add_to_playlist(user_id, room_id, youtube_id, title, duration, thumbnail='', channel_title=''):
  try:
      conn = sqlite3.connect('freejam.db')
      cursor = conn.cursor()
      
      # Check if song already exists
      cursor.execute('SELECT id, is_downloaded FROM songs WHERE youtube_id = ?', (youtube_id,))
      existing_song = cursor.fetchone()
      
      if existing_song:
          song_id, is_downloaded = existing_song
      else:
          # Add new song to database (initially not downloaded)
          cursor.execute('''
              INSERT INTO songs (youtube_id, title, duration, thumbnail, channel_title, 
                               is_downloaded, added_by) 
              VALUES (?, ?, ?, ?, ?, FALSE, ?)
          ''', (youtube_id, title, duration, thumbnail, channel_title, user_id))
          
          song_id = cursor.lastrowid
          is_downloaded = False
      
      # Check if song already in room playlist
      cursor.execute('SELECT id FROM room_playlists WHERE room_id = ? AND song_id = ?', (room_id, song_id))
      if cursor.fetchone():
          conn.close()
          return {'success': False, 'message': 'Song already in playlist'}
      
      # Add to room playlist
      cursor.execute(
          'SELECT COALESCE(MAX(position), 0) + 1 FROM room_playlists WHERE room_id = ?',
          (room_id,)
      )
      position = cursor.fetchone()[0]
      
      cursor.execute(
          'INSERT INTO room_playlists (room_id, song_id, position) VALUES (?, ?, ?)',
          (room_id, song_id, position)
      )
      
      conn.commit()
      conn.close()
      
      # Create song data object
      song_data = {
          'id': song_id,
          'title': title,
          'duration': duration,
          'youtube_id': youtube_id,
          'thumbnail': thumbnail or f'https://img.youtube.com/vi/{youtube_id}/mqdefault.jpg',
          'channel_title': channel_title or 'Unknown Artist',
          'is_downloaded': is_downloaded or music_downloader.is_downloaded(youtube_id)
      }
      
      # Update room state
      room_state = get_room_state(room_id)
      room_state.playlist.append(song_data)
      
      # Start download if not already downloaded
      if not song_data['is_downloaded']:
          download_queue.add_to_queue(
              youtube_id, title, channel_title, thumbnail, download_callback
          )
          
          # Notify users that download started
          socketio.emit('song_download_started', {
              'youtube_id': youtube_id,
              'title': title,
              'message': 'Download started...'
          }, room=room_id)
      
      # Only set as current song if no current song exists AND song is downloaded
      if not room_state.current_song:
          if song_data['is_downloaded']:
              room_state.current_song = song_data
              update_room_activity(room_id, len(room_state.users), song_data['title'])
              socketio.emit('song_changed', {
                  'song': song_data,
                  'is_playing': False,
                  'current_time': 0
              }, room=room_id)
          else:
              # Wait for download to complete before making it current
              pass
      
      # Notify room users
      socketio.emit('song_added', {
          'song': song_data,
          'playlist': room_state.playlist
      }, room=room_id)
      
      if song_data['is_downloaded']:
          return {'success': True, 'message': 'Song added to playlist and ready to play!'}
      else:
          return {'success': True, 'message': 'Song added to playlist and queued for download!'}
      
  except Exception as e:
      print(f"Error in add_to_playlist: {e}")
      return {'success': False, 'message': 'Database error'}

def get_room_playlist(room_id):
  """Get current playlist for a room"""
  try:
      conn = sqlite3.connect('freejam.db')
      cursor = conn.cursor()
      
      # Check if new columns exist
      cursor.execute("PRAGMA table_info(songs)")
      columns = [column[1] for column in cursor.fetchall()]
      
      if 'is_downloaded' in columns:
          cursor.execute('''
              SELECT s.id, s.title, s.duration, s.youtube_id, s.thumbnail, s.channel_title, 
                     s.is_downloaded, rp.position
              FROM room_playlists rp
              JOIN songs s ON rp.song_id = s.id
              WHERE rp.room_id = ?
              ORDER BY rp.position
          ''', (room_id,))
      else:
          cursor.execute('''
              SELECT s.id, s.title, s.duration, s.youtube_id, s.thumbnail, s.channel_title, 
                     0, rp.position
              FROM room_playlists rp
              JOIN songs s ON rp.song_id = s.id
              WHERE rp.room_id = ?
              ORDER BY rp.position
          ''', (room_id,))
      
      playlist = []
      for row in cursor.fetchall():
          youtube_id = row[3]
          is_downloaded = bool(row[6]) or music_downloader.is_downloaded(youtube_id)
          
          playlist.append({
              'id': row[0],
              'title': row[1],
              'duration': row[2],
              'youtube_id': youtube_id,
              'thumbnail': row[4] or f'https://img.youtube.com/vi/{youtube_id}/mqdefault.jpg',
              'channel_title': row[5] or 'Unknown Artist',
              'is_downloaded': is_downloaded,
              'position': row[7]
          })
      
      conn.close()
      return playlist
  except Exception as e:
      print(f"Error getting playlist: {e}")
      return []

# Routes
@app.route('/')
@login_required
def index():
  return render_template('dashboard.html')

@app.route('/login')
def login_page():
  if 'user_id' in session:
      return redirect('/')
  return render_template('login.html')

# Audio streaming route
@app.route('/stream/<youtube_id>')
@login_required
def stream_audio(youtube_id):
  """Stream downloaded audio file"""
  try:
      song_path = music_downloader.get_song_path(youtube_id)
      if os.path.exists(song_path):
          return send_file(song_path, mimetype='audio/mpeg', as_attachment=False)
      else:
          return jsonify({'error': 'Song not found or not downloaded'}), 404
  except Exception as e:
      print(f"Error streaming audio: {e}")
      return jsonify({'error': 'Streaming error'}), 500

@app.route('/download-status/<youtube_id>')
@login_required
def download_status(youtube_id):
  """Get download status for a song"""
  status = download_queue.get_status(youtube_id)
  return jsonify(status)

@app.route('/download-queue-status')
@login_required
def download_queue_status():
  """Get current download queue status"""
  return jsonify({
      'queue_size': download_queue.get_queue_size(),
      'all_status': download_queue.get_all_status()
  })

@app.route('/signup', methods=['POST'])
def signup():
  data = request.get_json()
  name = data.get('name', '').strip()
  email = data.get('email', '').strip()
  
  if not name or not email:
      return jsonify({'error': 'Name and email are required'}), 400
  
  # Validate email format
  import re
  email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
  if not re.match(email_regex, email):
      return jsonify({'error': 'Please enter a valid email address'}), 400
  
  conn = sqlite3.connect('freejam.db')
  cursor = conn.cursor()
  
  # Check if user already exists
  cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
  existing_user = cursor.fetchone()
  
  if existing_user:
      conn.close()
      return jsonify({'error': 'An account with this email already exists. Please login instead.'}), 409
  
  # Create new user
  cursor.execute('INSERT INTO users (name, email) VALUES (?, ?)', (name, email))
  user_id = cursor.lastrowid
  
  conn.commit()
  conn.close()
  
  # Set session
  session['user_id'] = user_id
  session['user_name'] = name
  session['user_email'] = email
  
  return jsonify({'success': True, 'message': 'Account created successfully!'})

@app.route('/login', methods=['POST'])
def login():
  data = request.get_json()
  email = data.get('email', '').strip()
  
  if not email:
      return jsonify({'error': 'Email is required'}), 400
  
  conn = sqlite3.connect('freejam.db')
  cursor = conn.cursor()
  
  # Check if user exists
  cursor.execute('SELECT id, name FROM users WHERE email = ?', (email,))
  user = cursor.fetchone()
  
  if not user:
      conn.close()
      return jsonify({'error': 'No account found with this email. Please sign up first.'}), 404
  
  user_id, name = user
  
  # Update last active
  cursor.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
  conn.commit()
  conn.close()
  
  # Set session
  session['user_id'] = user_id
  session['user_name'] = name
  session['user_email'] = email
  
  return jsonify({'success': True, 'message': f'Welcome back, {name}!'})

@app.route('/check-email', methods=['POST'])
def check_email():
  """Check if email exists to determine if user should login or signup"""
  data = request.get_json()
  email = data.get('email', '').strip()
  
  if not email:
      return jsonify({'error': 'Email is required'}), 400
  
  conn = sqlite3.connect('freejam.db')
  cursor = conn.cursor()
  cursor.execute('SELECT name FROM users WHERE email = ?', (email,))
  user = cursor.fetchone()
  conn.close()
  
  if user:
      return jsonify({'exists': True, 'name': user[0]})
  else:
      return jsonify({'exists': False})

@app.route('/logout')
def logout():
  session.clear()
  return redirect('/login')

@app.route('/user-stats')
@login_required
def user_stats():
  """Get real-time user statistics"""
  stats = get_user_stats(session['user_id'])
  return jsonify(stats)

@app.route('/live-rooms')
@login_required
def live_rooms():
  """Get list of live/active rooms"""
  rooms = get_live_rooms()
  return jsonify({'rooms': rooms})

# NEW: API endpoint to get rooms created by the current user
@app.route('/api/user-rooms')
@login_required
def api_user_rooms():
  try:
      conn = sqlite3.connect('freejam.db')
      cursor = conn.cursor()
      
      cursor.execute('''
          SELECT id, name, is_private, active_users, current_song, created_at
          FROM rooms
          WHERE creator_id = ?
          ORDER BY created_at DESC
      ''', (session['user_id'],))
      
      rooms = []
      for row in cursor.fetchall():
          rooms.append({
              'id': row[0],
              'name': row[1],
              'is_private': bool(row[2]),
              'active_users': row[3],
              'current_song': row[4],
              'created_at': row[5]
          })
      
      conn.close()
      return jsonify({'rooms': rooms})
  except Exception as e:
      print(f"Error getting user's rooms: {e}")
      return jsonify({'rooms': []}), 500

# NEW: API endpoint to get downloaded songs for the current user
@app.route('/api/downloaded-songs')
@login_required
def api_downloaded_songs():
  try:
      conn = sqlite3.connect('freejam.db')
      cursor = conn.cursor()
      
      cursor.execute('''
          SELECT youtube_id, title, duration, thumbnail, channel_title, download_path
          FROM songs
          WHERE is_downloaded = TRUE AND added_by = ?
          ORDER BY added_at DESC
      ''', (session['user_id'],))
      
      songs = []
      for row in cursor.fetchall():
          songs.append({
              'youtube_id': row[0],
              'title': row[1],
              'duration': row[2],
              'thumbnail': row[3],
              'channel_title': row[4],
              'download_path': row[5]
          })
      
      conn.close()
      return jsonify({'songs': songs})
  except Exception as e:
      print(f"Error getting downloaded songs: {e}")
      return jsonify({'songs': []}), 500

@app.route('/search-rooms')
@login_required
def search_rooms():
  """Search for rooms by name"""
  query = request.args.get('q', '').strip()
  
  if not query:
      return jsonify({'rooms': []})
  
  try:
      conn = sqlite3.connect('freejam.db')
      cursor = conn.cursor()
      
      # Check if activity columns exist
      cursor.execute("PRAGMA table_info(rooms)")
      columns = [column[1] for column in cursor.fetchall()]
      
      if 'active_users' in columns and 'current_song' in columns:
          # Search rooms by name (case insensitive)
          cursor.execute('''
              SELECT r.id, r.name, r.is_private, r.active_users, r.current_song, 
                     u.name as creator_name, r.created_at
              FROM rooms r
              LEFT JOIN users u ON r.creator_id = u.id
              WHERE LOWER(r.name) LIKE LOWER(?)
              ORDER BY r.active_users DESC, r.created_at DESC
              LIMIT 10
          ''', (f'%{query}%',))
      else:
          # Fallback query
          cursor.execute('''
              SELECT r.id, r.name, r.is_private, 0, '', 
                     u.name as creator_name, r.created_at
              FROM rooms r
              LEFT JOIN users u ON r.creator_id = u.id
              WHERE LOWER(r.name) LIKE LOWER(?)
              ORDER BY r.created_at DESC
              LIMIT 10
          ''', (f'%{query}%',))
      
      rooms = []
      for row in cursor.fetchall():
          rooms.append({
              'id': row[0],
              'name': row[1],
              'is_private': bool(row[2]),
              'active_users': row[3],
              'current_song': row[4],
              'creator_name': row[5] or 'Unknown',
              'created_at': row[6]
          })
      
      conn.close()
      return jsonify({'rooms': rooms})
  except Exception as e:
      print(f"Error searching rooms: {e}")
      return jsonify({'rooms': []})

@app.route('/create-room', methods=['POST'])
@login_required
def create_room():
  data = request.get_json()
  room_name = data.get('name', '').strip()
  is_private = data.get('is_private', False)
  pin = data.get('pin', '').strip() if is_private else None
  
  if not room_name:
      return jsonify({'error': 'Room name is required'}), 400
  
  room_id = str(uuid.uuid4())[:8]
  
  conn = sqlite3.connect('freejam.db')
  cursor = conn.cursor()
  cursor.execute(
      'INSERT INTO rooms (id, name, is_private, pin, creator_id) VALUES (?, ?, ?, ?, ?)',
      (room_id, room_name, is_private, pin, session['user_id'])
  )
  conn.commit()
  conn.close()
  
  return jsonify({'room_id': room_id})

@app.route('/join-room', methods=['POST'])
@login_required
def join_room_route():
  data = request.get_json()
  room_id = data.get('room_id', '').strip()
  pin = data.get('pin', '').strip()
  
  conn = sqlite3.connect('freejam.db')
  cursor = conn.cursor()
  cursor.execute('SELECT name, is_private, pin FROM rooms WHERE id = ?', (room_id,))
  room = cursor.fetchone()
  conn.close()
  
  if not room:
      return jsonify({'error': 'Room not found'}), 404
  
  room_name, is_private, room_pin = room
  
  if is_private and pin != room_pin:
      return jsonify({'error': 'Invalid PIN'}), 403
  
  return jsonify({'success': True, 'room_name': room_name})

@app.route('/room/<room_id>')
@login_required
def room(room_id):
  conn = sqlite3.connect('freejam.db')
  cursor = conn.cursor()
  cursor.execute('SELECT name FROM rooms WHERE id = ?', (room_id,))
  room = cursor.fetchone()
  conn.close()
  
  if not room:
      return "Room not found", 404
  
  return render_template('room.html', room_id=room_id, room_name=room[0])

@app.route('/search-songs', methods=['POST'])
@login_required
def search_songs():
  data = request.get_json()
  query = data.get('query', '').strip()
  
  if not query:
      return jsonify({'error': 'Search query is required'}), 400
  
  results = search_youtube(query)
  return jsonify({'results': results})

@app.route('/add-song', methods=['POST'])
@login_required
def add_song():
  data = request.get_json()
  room_id = data.get('room_id')
  youtube_id = data.get('youtube_id')
  title = data.get('title')
  duration = data.get('duration', 0)
  thumbnail = data.get('thumbnail', '')
  channel_title = data.get('channel_title', '')
  
  result = add_to_playlist(session['user_id'], room_id, youtube_id, title, duration, thumbnail, channel_title)
  return jsonify(result)

@app.route('/room/<room_id>/playlist')
@login_required
def get_playlist(room_id):
  playlist = get_room_playlist(room_id)
  return jsonify({'playlist': playlist})

# Socket.IO events
@socketio.on('join_room')
def on_join_room(data):
  if 'user_id' not in session:
      return
      
  room_id = data['room_id']
  join_room(room_id)
  
  room_state = get_room_state(room_id)
  room_state.users.add(session.get('user_name', 'Anonymous'))
  
  # Load playlist if not already loaded
  if not room_state.playlist:
      room_state.playlist = get_room_playlist(room_id)
      if room_state.playlist and not room_state.current_song:
          # Find the first downloaded song, or just the first song if none are downloaded
          first_playable_song = next((s for s in room_state.playlist if s['is_downloaded']), None)
          if first_playable_song:
              room_state.current_song = first_playable_song
          else:
              room_state.current_song = room_state.playlist[0] # Fallback to first song even if not downloaded
  
  # Update room activity
  current_song_title = room_state.current_song['title'] if room_state.current_song else ''
  update_room_activity(room_id, len(room_state.users), current_song_title)
  
  # Send current room state to new user
  emit('room_state', {
      'current_song': room_state.current_song,
      'is_playing': room_state.is_playing,
      'current_time': room_state.current_time,
      'users': list(room_state.users),
      'playlist': room_state.playlist
  })
  
  # Notify others
  emit('user_joined', {
      'user': session.get('user_name', 'Anonymous'),
      'users': list(room_state.users)
  }, room=room_id, include_self=False)

@socketio.on('leave_room')
def on_leave_room(data):
  if 'user_id' not in session:
      return
      
  room_id = data['room_id']
  leave_room(room_id)
  
  room_state = get_room_state(room_id)
  room_state.users.discard(session.get('user_name', 'Anonymous'))
  
  # Update room activity
  current_song_title = room_state.current_song['title'] if room_state.current_song else ''
  update_room_activity(room_id, len(room_state.users), current_song_title)
  
  emit('user_left', {
      'user': session.get('user_name', 'Anonymous'),
      'users': list(room_state.users)
  }, room=room_id)

@socketio.on('play_pause')
def on_play_pause(data):
  if 'user_id' not in session:
      return
      
  room_id = data['room_id']
  is_playing = data['is_playing']
  current_time = data.get('current_time', 0)
  
  room_state = get_room_state(room_id)
  room_state.is_playing = is_playing
  room_state.current_time = current_time
  room_state.last_update = time.time()
  
  emit('sync_playback', {
      'is_playing': is_playing,
      'current_time': current_time,
      'timestamp': time.time()
  }, room=room_id, include_self=False)

@socketio.on('seek')
def on_seek(data):
  if 'user_id' not in session:
      return
      
  room_id = data['room_id']
  current_time = data['current_time']
  
  room_state = get_room_state(room_id)
  room_state.current_time = current_time
  room_state.last_update = time.time()
  
  emit('sync_seek', {
      'current_time': current_time,
      'timestamp': time.time()
  }, room=room_id, include_self=False)

@socketio.on('next_song')
def on_next_song(data):
  if 'user_id' not in session:
      return
      
  room_id = data['room_id']
  
  room_state = get_room_state(room_id)
  if room_state.playlist:
      # Find current song index
      current_index = 0
      if room_state.current_song:
          for i, song in enumerate(room_state.playlist):
              if song['youtube_id'] == room_state.current_song['youtube_id']:
                  current_index = i
                  break
      
      # Get next song
      next_index = (current_index + 1) % len(room_state.playlist)
      next_song = room_state.playlist[next_index]
      
      room_state.current_song = next_song
      room_state.current_time = 0
      room_state.is_playing = True
      room_state.last_update = time.time()
      
      # Update room activity
      update_room_activity(room_id, len(room_state.users), next_song['title'])
      
      emit('song_changed', {
          'song': next_song,
          'is_playing': True,
          'current_time': 0
      }, room=room_id)

if __name__ == '__main__':
  init_db()
  socketio.run(app, debug=True, host='0.0.0.0', port=2007)
