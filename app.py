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
import backoff

# Flask and SocketIO imports
from flask import Flask, render_template, request, jsonify, session, send_from_directory, url_for, redirect, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*")

# YouTube and Piped API Configuration
# WARNING: Hardcoding API keys is a security risk and is NOT recommended for production.
YOUTUBE_API_KEY = 'AIzaSyDXDmYOabTrzpRmm_FeQXpN01vfjESP64U'
YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'
YOUTUBE_VIDEOS_URL = 'https://www.googleapis.com/youtube/v3/videos'
PIPED_API_INSTANCES = [
    'https://pipedapi.kavin.rocks',
    'https://pipedapi.adminforge.de',
    'https://pipedapi.tokhmi.xyz'
]

# Create necessary directories
os.makedirs('media', exist_ok=True)
os.makedirs('media/songs', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# --- Database Helper ---
DATABASE = 'freejam.db'

def get_db_connection():
    """Establishes and returns a new SQLite database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# --- Authentication Decorator ---
def login_required(f):
    """Decorator to ensure a user is logged in before accessing a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# --- Database Initialization ---
def init_db():
    """Initializes the database schema and adds missing columns if necessary."""
    with get_db_connection() as conn:
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

        # Songs table with stream source
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                youtube_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                duration INTEGER,
                thumbnail TEXT DEFAULT '',
                channel_title TEXT DEFAULT '',
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                stream_source TEXT DEFAULT 'youtube', -- 'youtube' or 'piped'
                piped_stream_url TEXT, -- Stores Piped API stream URL if applicable
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

        # Add missing columns if they don't exist
        def add_column_if_not_exists(table, column_name, column_type):
            try:
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column_name} {column_type}')
                conn.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    print(f"Error adding column {column_name} to {table}: {e}")

        add_column_if_not_exists('rooms', 'last_active', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        add_column_if_not_exists('rooms', 'active_users', 'INTEGER DEFAULT 0')
        add_column_if_not_exists('rooms', 'current_song', 'TEXT DEFAULT ""')
        add_column_if_not_exists('songs', 'stream_source', 'TEXT DEFAULT "youtube"')
        add_column_if_not_exists('songs', 'piped_stream_url', 'TEXT')
        
        conn.commit()

# --- Room State Management (In-memory) ---
room_states = {}

class RoomState:
    """Represents the real-time state of a music room."""
    def __init__(self, room_id):
        self.room_id = room_id
        self.current_song = None
        self.is_playing = False
        self.current_time = 0
        self.last_sync_timestamp = time.time()
        self.active_users = {}
        self.playlist = []

    def get_user_names(self):
        """Returns a list of user names currently active in the room."""
        return [user_info['user_name'] for user_info in self.active_users.values()]

def get_room_state(room_id):
    """Retrieves or creates an in-memory RoomState object for a given room ID."""
    if room_id not in room_states:
        room_states[room_id] = RoomState(room_id)
    return room_states[room_id]

# Background task for cleaning up inactive users
def cleanup_inactive_users():
    """Periodically removes inactive users from rooms."""
    while True:
        time.sleep(30)
        for room_id, room_state in list(room_states.items()):
            users_to_remove = []
            for sid, user_info in list(room_state.active_users.items()):
                if time.time() - user_info['last_heartbeat'] > 60:
                    users_to_remove.append((sid, user_info['user_name']))
            
            for sid, user_name in users_to_remove:
                del room_state.active_users[sid]
                print(f"User {user_name} (SID: {sid}) removed from room {room_id} due to inactivity.")
                socketio.emit('user_left', {
                    'user': user_name,
                    'users': room_state.get_user_names()
                }, room=room_id)
            
            current_song_title = room_state.current_song['title'] if room_state.current_song else ''
            update_room_activity(room_id, len(room_state.active_users), current_song_title)

# Start the background cleanup task
socketio.start_background_task(cleanup_inactive_users)

# --- Database Operations ---
def update_room_activity(room_id, user_count=None, current_song=None):
    """Updates room activity in the database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
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
    except Exception as e:
        print(f"Error updating room activity for {room_id}: {e}")

def get_live_rooms():
    """Retrieves a list of currently active rooms from the database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
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
            rooms_data = []
            for row in cursor.fetchall():
                rooms_data.append({
                    'id': row['id'],
                    'name': row['name'],
                    'is_private': bool(row['is_private']),
                    'active_users': row['active_users'],
                    'current_song': row['current_song'],
                    'creator_name': row['creator_name'] or 'Unknown',
                    'created_at': row['created_at']
                })
            return rooms_data
    except Exception as e:
        print(f"Error getting live rooms: {e}")
        return []

def get_user_stats(user_id):
    """Retrieves real-time statistics for a given user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM rooms WHERE creator_id = ?', (user_id,))
            rooms_created = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM songs WHERE added_by = ?', (user_id,))
            songs_added = cursor.fetchone()[0]
            return {
                'rooms_created': rooms_created, 
                'songs_added': songs_added,
                'songs_downloaded': 0
            }
    except Exception as e:
        print(f"Error getting user stats for user {user_id}: {e}")
        return {'rooms_created': 0, 'songs_added': 0, 'songs_downloaded': 0}

def parse_duration(duration_str):
    """Parses YouTube duration format (e.g., PT4M13S) into total seconds."""
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

def is_video_available(video_id):
    """Checks if a YouTube video is available using the YouTube Data API."""
    try:
        params = {
            'part': 'status,contentDetails',
            'id': video_id,
            'key': YOUTUBE_API_KEY
        }
        response = requests.get(YOUTUBE_VIDEOS_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'items' not in data or not data['items']:
            print(f"Video {video_id}: Not found or no items in response.")
            return False, "Video not found."
        
        video = data['items'][0]
        status = video.get('status', {})
        
        if not status.get('embeddable', True):
            print(f"Video {video_id}: Not embeddable. Privacy Status: {status.get('privacyStatus')}")
            return False, "Video cannot be embedded."
        
        if status.get('privacyStatus') in ['private', 'privacyStatusUnspecified']:
            print(f"Video {video_id}: Privacy status is {status.get('privacyStatus')}.")
            return False, f"Video is private or unavailable."
        
        content_details = video.get('contentDetails', {})
        if content_details.get('regionRestriction', {}).get('blocked'):
            print(f"Video {video_id}: Region restricted.")
            return False, "Video is blocked in your region."
        
        if content_details.get('contentRating') and content_details['contentRating'] != {}:
            print(f"Video {video_id}: Content rated/age restricted.")
            return False, "Video is age-restricted or has content ratings."
        
        if video.get('snippet', {}).get('liveBroadcastContent') in ['live', 'upcoming']:
            print(f"Video {video_id}: Is a live stream or upcoming event.")
            return False, "Video is a live stream or upcoming event."
            
        return True, "Video is available."
        
    except requests.exceptions.RequestException as e:
        print(f"YouTube API request error for video {video_id}: {e}")
        return False, f"API request failed: {e}"
    except Exception as e:
        print(f"Error checking video availability for {video_id}: {e}")
        return False, f"An unexpected error occurred: {e}"

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3)
def get_piped_stream(youtube_id, instance_index=0):
    """Retrieves audio stream URL from Piped API for a given YouTube video ID."""
    try:
        if instance_index >= len(PIPED_API_INSTANCES):
            return None, "No more Piped instances to try."
        
        piped_api = PIPED_API_INSTANCES[instance_index]
        response = requests.get(f'{piped_api}/streams/{youtube_id}', timeout=5)
        response.raise_for_status()
        data = response.json()
        
        audio_streams = data.get('audioStreams', [])
        if not audio_streams:
            return None, "No audio streams available from Piped API."
        
        preferred_stream = None
        for stream in audio_streams:
            if stream.get('mimeType', '').startswith('audio/'):
                preferred_stream = stream
                break
        
        if not preferred_stream:
            return None, "No suitable audio stream found."
        
        return preferred_stream.get('url'), None
    except requests.exceptions.RequestException as e:
        print(f"Piped API request error for video {youtube_id} on {PIPED_API_INSTANCES[instance_index]}: {e}")
        # Try the next instance
        return get_piped_stream(youtube_id, instance_index + 1)
    except Exception as e:
        print(f"Unexpected error retrieving Piped stream for {youtube_id} on {PIPED_API_INSTANCES[instance_index]}: {e}")
        return None, f"An unexpected error occurred: {e}"

def search_youtube(query, max_results=8):
    """Searches YouTube for videos using the YouTube Data API."""
    try:
        search_params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'maxResults': max_results,
            'key': YOUTUBE_API_KEY,
            'videoCategoryId': '10',
            'order': 'relevance'
        }
        search_response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        if 'items' not in search_data:
            print(f"YouTube API Search Error: {search_data.get('error', 'No items in search response')}")
            return []
        
        video_ids = [item['id']['videoId'] for item in search_data['items'] if 'videoId' in item['id']]
        if not video_ids:
            return []

        videos_params = {
            'part': 'contentDetails,status,snippet',
            'id': ','.join(video_ids),
            'key': YOUTUBE_API_KEY
        }
        videos_response = requests.get(YOUTUBE_VIDEOS_URL, params=videos_params)
        videos_response.raise_for_status()
        videos_data = videos_response.json()
        
        video_details_map = {item['id']: item for item in videos_data.get('items', [])}
        results = []
        for item in search_data['items']:
            video_id = item['id']['videoId']
            snippet = item['snippet']
            duration = 0
            full_video_info = video_details_map.get(video_id)

            if full_video_info:
                duration = parse_duration(full_video_info.get('contentDetails', {}).get('duration', 'PT0S'))
            
            if duration < 30:
                continue
            
            is_available, availability_message = is_video_available(video_id)
            stream_source = 'youtube' if is_available else 'piped'
            piped_stream_url = None
            if not is_available:
                piped_stream_url, error = get_piped_stream(video_id)
                if not piped_stream_url:
                    print(f"Skipping search result {video_id} due to: {availability_message} and Piped failure: {error}")
                    continue

            results.append({
                'id': video_id,
                'title': snippet['title'],
                'duration': duration,
                'thumbnail': snippet['thumbnails']['medium']['url'],
                'channel_title': snippet['channelTitle'],
                'stream_source': stream_source,
                'piped_stream_url': piped_stream_url
            })
        
        return results
        
    except requests.exceptions.RequestException as e:
        print(f"YouTube search API request error: {e}")
        return search_piped(query, max_results)
    except Exception as e:
        print(f"YouTube search error: {e}")
        return search_piped(query, max_results)

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=3)
def search_piped(query, max_results=8, instance_index=0):
    """Searches videos using the Piped API as a fallback."""
    try:
        if instance_index >= len(PIPED_API_INSTANCES):
            return []
        
        piped_api = PIPED_API_INSTANCES[instance_index]
        search_params = {
            'q': query,
            'filter': 'videos'
        }
        response = requests.get(f'{piped_api}/search', params=search_params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get('items', [])[:max_results]:
            if item.get('type') != 'stream':
                continue
            video_id = item.get('url', '').split('watch?v=')[-1]
            duration = item.get('duration', 0)
            if duration < 30:
                continue
            stream_url, error = get_piped_stream(video_id)
            if not stream_url:
                print(f"Skipping Piped search result {video_id} due to: {error}")
                continue
            results.append({
                'id': video_id,
                'title': item.get('title', 'Unknown Title'),
                'duration': duration,
                'thumbnail': item.get('thumbnail', ''),
                'channel_title': item.get('uploaderName', 'Unknown Artist'),
                'stream_source': 'piped',
                'piped_stream_url': stream_url
            })
        return results
    except requests.exceptions.RequestException as e:
        print(f"Piped search API request error on {PIPED_API_INSTANCES[instance_index]}: {e}")
        return search_piped(query, max_results, instance_index + 1)
    except Exception as e:
        print(f"Piped search error on {PIPED_API_INSTANCES[instance_index]}: {e}")
        return []

def add_to_playlist(user_id, room_id, youtube_id, title, duration, thumbnail='', channel_title='', stream_source='youtube', piped_stream_url=None):
    """Adds a song to the database and a room's playlist."""
    try:
        if stream_source == 'youtube':
            is_available, availability_message = is_video_available(youtube_id)
            if not is_available:
                stream_source = 'piped'
                piped_stream_url, error = get_piped_stream(youtube_id)
                if not piped_stream_url:
                    return {'success': False, 'message': f'Video not available: {availability_message}, Piped failed: {error}'}
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM songs WHERE youtube_id = ?', (youtube_id,))
            existing_song = cursor.fetchone()
            
            song_id = None
            if existing_song:
                song_id = existing_song['id']
                cursor.execute('''
                    UPDATE songs 
                    SET stream_source = ?, piped_stream_url = ?
                    WHERE id = ?
                ''', (stream_source, piped_stream_url, song_id))
            else:
                cursor.execute('''
                    INSERT INTO songs (youtube_id, title, duration, thumbnail, channel_title, added_by, stream_source, piped_stream_url) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (youtube_id, title, duration, thumbnail, channel_title, user_id, stream_source, piped_stream_url))
                song_id = cursor.lastrowid
            
            cursor.execute('SELECT id FROM room_playlists WHERE room_id = ? AND song_id = ?', (room_id, song_id))
            if cursor.fetchone():
                return {'success': False, 'message': 'Song already in playlist'}
            
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
        
        song_data = {
            'id': song_id,
            'title': title,
            'duration': duration,
            'youtube_id': youtube_id,
            'thumbnail': thumbnail or f'https://img.youtube.com/vi/{youtube_id}/mqdefault.jpg',
            'channel_title': channel_title or 'Unknown Artist',
            'stream_source': stream_source,
            'piped_stream_url': piped_stream_url
        }
        
        room_state = get_room_state(room_id)
        room_state.playlist.append(song_data)
        
        if not room_state.current_song:
            room_state.current_song = song_data
            room_state.current_time = 0
            room_state.is_playing = False
            room_state.last_sync_timestamp = time.time()
            update_room_activity(room_id, len(room_state.active_users), song_data['title'])
            socketio.emit('song_changed', {
                'song': song_data,
                'is_playing': False,
                'current_time': 0,
                'timestamp': room_state.last_sync_timestamp
            }, room=room_id)
        
        socketio.emit('song_added', {
            'song': song_data,
            'playlist': room_state.playlist
        }, room=room_id)
        
        return {'success': True, 'message': 'Song added to playlist!'}
        
    except Exception as e:
        print(f"Error in add_to_playlist: {e}")
        return {'success': False, 'message': 'Database error'}

def get_room_playlist(room_id):
    """Retrieves the current playlist for a given room from the database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.id, s.title, s.duration, s.youtube_id, s.thumbnail, s.channel_title, 
                       rp.position, s.stream_source, s.piped_stream_url
                FROM room_playlists rp
                JOIN songs s ON rp.song_id = s.id
                WHERE rp.room_id = ?
                ORDER BY rp.position
            ''', (room_id,))
            
            playlist = []
            for row in cursor.fetchall():
                youtube_id = row['youtube_id']
                playlist.append({
                    'id': row['id'],
                    'title': row['title'],
                    'duration': row['duration'],
                    'youtube_id': youtube_id,
                    'thumbnail': row['thumbnail'] or f'https://img.youtube.com/vi/{youtube_id}/mqdefault.jpg',
                    'channel_title': row['channel_title'] or 'Unknown Artist',
                    'stream_source': row['stream_source'],
                    'piped_stream_url': row['piped_stream_url'],
                    'playback_failed': False
                })
            return playlist
    except Exception as e:
        print(f"Error getting playlist for room {room_id}: {e}")
        return []

# --- Flask Routes ---
@app.route('/')
@login_required
def index():
    return render_template('dashboard.html')

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect('/')
    return render_template('login.html')

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    
    if not name or not email:
        return jsonify({'error': 'Name and email are required'}), 400
    
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        return jsonify({'error': 'Please enter a valid email address'}), 400

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({'error': 'An account with this email already exists. Please login instead.'}), 409

        cursor.execute('INSERT INTO users (name, email) VALUES (?, ?)', (name, email))
        user_id = cursor.lastrowid
        conn.commit()

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

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'error': 'No account found with this email. Please sign up first.'}), 404

        user_id, name = user['id'], user['name']
        cursor.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
        conn.commit()

    session['user_id'] = user_id
    session['user_name'] = name
    session['user_email'] = email

    return jsonify({'success': True, 'message': f'Welcome back, {name}!'})

@app.route('/check-email', methods=['POST'])
def check_email():
    data = request.get_json()
    email = data.get('email', '').strip()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()

    if user:
        return jsonify({'exists': True, 'name': user['name']})
    else:
        return jsonify({'exists': False})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/user-stats')
@login_required
def user_stats():
    stats = get_user_stats(session['user_id'])
    return jsonify(stats)

@app.route('/live-rooms')
@login_required
def live_rooms():
    rooms_data = get_live_rooms()
    return jsonify({'rooms': rooms_data})

@app.route('/api/user-rooms')
@login_required
def api_user_rooms():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, is_private, active_users, current_song, created_at
                FROM rooms
                WHERE creator_id = ?
                ORDER BY created_at DESC
            ''', (session['user_id'],))
            
            rooms_data = []
            for row in cursor.fetchall():
                rooms_data.append({
                    'id': row['id'],
                    'name': row['name'],
                    'is_private': bool(row['is_private']),
                    'active_users': row['active_users'],
                    'current_song': row['current_song'],
                    'created_at': row['created_at']
                })
            return jsonify({'rooms': rooms_data})
    except Exception as e:
        print(f"Error getting user's rooms: {e}")
        return jsonify({'rooms': []}), 500

@app.route('/api/downloaded-songs')
@login_required
def api_downloaded_songs():
    return jsonify({'songs': []})

@app.route('/search-rooms')
@login_required
def search_rooms():
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'rooms': []})

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.id, r.name, r.is_private, r.active_users, r.current_song, 
                       u.name as creator_name, r.created_at
                FROM rooms r
                LEFT JOIN users u ON r.creator_id = u.id
                WHERE LOWER(r.name) LIKE LOWER(?)
                ORDER BY r.active_users DESC, r.created_at DESC
                LIMIT 10
            ''', (f'%{query}%',))
            
            rooms_data = []
            for row in cursor.fetchall():
                rooms_data.append({
                    'id': row['id'],
                    'name': row['name'],
                    'is_private': bool(row['is_private']),
                    'active_users': row['active_users'],
                    'current_song': row['current_song'],
                    'creator_name': row['creator_name'] or 'Unknown',
                    'created_at': row['created_at']
                })
            return jsonify({'rooms': rooms_data})
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

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO rooms (id, name, is_private, pin, creator_id) VALUES (?, ?, ?, ?, ?)',
            (room_id, room_name, is_private, pin, session['user_id'])
        )
        conn.commit()

    return jsonify({'room_id': room_id})

@app.route('/join-room', methods=['POST'])
@login_required
def join_room_route():
    data = request.get_json()
    room_id = data.get('room_id', '').strip()
    pin = data.get('pin', '').strip()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT name, is_private, pin FROM rooms WHERE id = ?', (room_id,))
        room = cursor.fetchone()

    if not room:
        return jsonify({'error': 'Room not found'}), 404

    room_name, is_private, room_pin = room['name'], bool(room['is_private']), room['pin']

    if is_private and pin != room_pin:
        return jsonify({'error': 'Invalid PIN'}), 403

    return jsonify({'success': True, 'room_name': room_name})

@app.route('/room/<room_id>')
@login_required
def room(room_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM rooms WHERE id = ?', (room_id,))
        room_data = cursor.fetchone()

    if not room_data:
        return "Room not found", 404

    return render_template('room.html', room_id=room_id, room_name=room_data['name'])

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
    stream_source = data.get('stream_source', 'youtube')
    piped_stream_url = data.get('piped_stream_url', None)

    result = add_to_playlist(session['user_id'], room_id, youtube_id, title, duration, thumbnail, channel_title, stream_source, piped_stream_url)
    return jsonify(result)

@app.route('/room/<room_id>/playlist')
@login_required
def get_playlist_route(room_id):
    playlist = get_room_playlist(room_id)
    return jsonify({'playlist': playlist})

@app.route('/api/fallback-stream', methods=['POST'])

@login_required
def fallback_stream():
    """Handles requests for fallback streams when YouTube playback fails (e.g., Code 150)."""
    data = request.get_json()
    youtube_id = data.get('youtube_id')
    room_id = data.get('room_id')
    
    if not youtube_id or not room_id:
        return jsonify({'error': 'YouTube ID and room ID are required'}), 400

    # Try fetching Piped stream with retries and multiple instances
    stream_url, error = get_piped_stream(youtube_id)
    if not stream_url:
        return jsonify({'error': f'Failed to get Piped stream: {error}'}), 500

    # Update song in database
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE songs 
                SET stream_source = 'piped', piped_stream_url = ?
                WHERE youtube_id = ?
            ''', (stream_url, youtube_id))
            cursor.execute('SELECT * FROM songs WHERE youtube_id = ?', (youtube_id,))
            song = cursor.fetchone()
            if not song:
                return jsonify({'error': 'Song not found in database'}), 404
            conn.commit()
        
        # Update room state and playlist
        room_state = get_room_state(room_id)
        song_data = {
            'id': song['id'],
            'title': song['title'],
            'duration': song['duration'],
            'youtube_id': song['youtube_id'],
            'thumbnail': song['thumbnail'] or f'https://img.youtube.com/vi/{song["youtube_id"]}/mqdefault.jpg',
            'channel_title': song['channel_title'] or 'Unknown Artist',
            'stream_source': 'piped',
            'piped_stream_url': stream_url
        }
        
        # Update playlist
        for i, item in enumerate(room_state.playlist):
            if item['youtube_id'] == youtube_id:
                room_state.playlist[i] = song_data
                break
        
        # Update current song if it matches
        if room_state.current_song and room_state.current_song['youtube_id'] == youtube_id:
            room_state.current_song = song_data
            socketio.emit('song_changed', {
                'song': song_data,
                'is_playing': room_state.is_playing,
                'current_time': room_state.current_time,
                'timestamp': room_state.last_sync_timestamp
            }, room=room_id)
        
        socketio.emit('song_updated', {
            'song': song_data,
            'playlist': room_state.playlist
        }, room=room_id)
        
        return jsonify({'success': True, 'stream_url': stream_url})
    except Exception as e:
        print(f"Error updating stream for {youtube_id}: {e}")
        return jsonify({'error': 'Database error'}), 500

# --- Socket.IO Events ---
@socketio.on('join_room')
def on_join_room(data):
    if 'user_id' not in session:
        return
        
    room_id = data['room_id']
    join_room(room_id)

    room_state = get_room_state(room_id)
    user_name = session.get('user_name', 'Anonymous')
    
    room_state.active_users[request.sid] = {'user_name': user_name, 'last_heartbeat': time.time()}

    if not room_state.playlist:
        room_state.playlist = get_room_playlist(room_id)
        if room_state.playlist and not room_state.current_song:
            room_state.current_song = room_state.playlist[0]
            room_state.current_time = 0
            room_state.is_playing = False
            room_state.last_sync_timestamp = time.time()

    current_song_title = room_state.current_song['title'] if room_state.current_song else ''
    update_room_activity(room_id, len(room_state.active_users), current_song_title)

    emit('room_state', {
        'current_song': room_state.current_song,
        'is_playing': room_state.is_playing,
        'current_time': room_state.current_time,
        'timestamp': room_state.last_sync_timestamp,
        'users': room_state.get_user_names(),
        'playlist': room_state.playlist
    })

    emit('user_joined', {
        'user': user_name,
        'users': room_state.get_user_names()
    }, room=room_id, include_self=False)

@socketio.on('leave_room')
def on_leave_room(data):
    if 'user_id' not in session:
        return
        
    room_id = data['room_id']
    leave_room(room_id)

    room_state = get_room_state(room_id)
    user_name = session.get('user_name', 'Anonymous')
    
    if request.sid in room_state.active_users:
        del room_state.active_users[request.sid]

    current_song_title = room_state.current_song['title'] if room_state.current_song else ''
    update_room_activity(room_id, len(room_state.active_users), current_song_title)

    emit('user_left', {
        'user': user_name,
        'users': room_state.get_user_names()
    }, room=room_id)

@socketio.on('disconnect')
def on_disconnect():
    for room_id, room_state in list(room_states.items()):
        if request.sid in room_state.active_users:
            user_name = room_state.active_users[request.sid]['user_name']
            del room_state.active_users[request.sid]
            print(f"User {user_name} (SID: {request.sid}) disconnected from room {room_id}.")
            current_song_title = room_state.current_song['title'] if room_state.current_song else ''
            update_room_activity(room_id, len(room_state.active_users), current_song_title)
            socketio.emit('user_left', {
                'user': user_name,
                'users': room_state.get_user_names()
            }, room=room_id)

@socketio.on('heartbeat')
def on_heartbeat(data):
    room_id = data.get('room_id')
    if room_id and room_id in room_states and request.sid in room_states[room_id].active_users:
        room_states[room_id].active_users[request.sid]['last_heartbeat'] = time.time()

@socketio.on('play_pause')
def on_play_pause(data):
    if 'user_id' not in session:
        return
        
    room_id = data['room_id']
    is_playing = data['is_playing']
    client_current_time = data.get('current_time', 0)

    room_state = get_room_state(room_id)
    room_state.is_playing = is_playing
    room_state.current_time = client_current_time
    room_state.last_sync_timestamp = time.time()

    emit('sync_playback', {
        'is_playing': is_playing,
        'current_time': room_state.current_time,
        'timestamp': room_state.last_sync_timestamp
    }, room=room_id, include_self=False)

@socketio.on('seek')
def on_seek(data):
    if 'user_id' not in session:
        return
        
    room_id = data['room_id']
    client_current_time = data['current_time']

    room_state = get_room_state(room_id)
    room_state.current_time = client_current_time
    room_state.last_sync_timestamp = time.time()

    emit('sync_seek', {
        'current_time': room_state.current_time,
        'timestamp': room_state.last_sync_timestamp
    }, room=room_id, include_self=False)

@socketio.on('next_song')
def on_next_song(data):
    if 'user_id' not in session:
        return
        
    room_id = data['room_id']

    room_state = get_room_state(room_id)
    if room_state.playlist:
        current_index = 0
        if room_state.current_song:
            for i, song in enumerate(room_state.playlist):
                if song['youtube_id'] == room_state.current_song['youtube_id']:
                    current_index = i
                    break
        
        next_index = (current_index + 1) % len(room_state.playlist)
        next_song = room_state.playlist[next_index]
        
        room_state.current_song = next_song
        room_state.current_time = 0
        room_state.is_playing = True
        room_state.last_sync_timestamp = time.time()

        update_room_activity(room_id, len(room_state.active_users), next_song['title'])
        
        emit('song_changed', {
            'song': next_song,
            'is_playing': True,
            'current_time': 0,
            'timestamp': room_state.last_sync_timestamp
        }, room=room_id)

@socketio.on('playback_error')
def on_playback_error(data):
    """Handles playback errors reported by clients, initiating fallback to Piped API."""
    room_id = data.get('room_id')
    youtube_id = data.get('youtube_id')
    error_code = data.get('error_code')

    if not room_id or not youtube_id:
        return

    if error_code in [101, 150]:  # YouTube playback restriction
        stream_url, error = get_piped_stream(youtube_id)
        if not stream_url:
            print(f"Failed to get Piped stream for {youtube_id}: {error}")
            socketio.emit('error_notification', {
                'message': f'Failed to play video {youtube_id}: {error}'
            }, room=room_id)
            return

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE songs 
                    SET stream_source = 'piped', piped_stream_url = ?
                    WHERE youtube_id = ?
                ''', (stream_url, youtube_id))
                cursor.execute('SELECT * FROM songs WHERE youtube_id = ?', (youtube_id,))
                song = cursor.fetchone()
                if not song:
                    return
                conn.commit()
            
            room_state = get_room_state(room_id)
            song_data = {
                'id': song['id'],
                'title': song['title'],
                'duration': song['duration'],
                'youtube_id': song['youtube_id'],
                'thumbnail': song['thumbnail'] or f'https://img.youtube.com/vi/{song["youtube_id"]}/mqdefault.jpg',
                'channel_title': song['channel_title'] or 'Unknown Artist',
                'stream_source': 'piped',
                'piped_stream_url': stream_url
            }
            
            for i, item in enumerate(room_state.playlist):
                if item['youtube_id'] == youtube_id:
                    room_state.playlist[i] = song_data
                    break
            
            if room_state.current_song and room_state.current_song['youtube_id'] == youtube_id:
                room_state.current_song = song_data
                socketio.emit('song_changed', {
                    'song': song_data,
                    'is_playing': room_state.is_playing,
                    'current_time': room_state.current_time,
                    'timestamp': room_state.last_sync_timestamp
                }, room=room_id)
            
            socketio.emit('song_updated', {
                'song': song_data,
                'playlist': room_state.playlist
            }, room=room_id)
        except Exception as e:
            print(f"Error handling playback error for {youtube_id}: {e}")
            socketio.emit('error_notification', {
                'message': f'Failed to update stream for video {youtube_id}: Database error'
            }, room=room_id)



if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True, host='0.0.0.0', port=2007)