import sqlite3
import os

def setup_database():
    """Initialize the Free Jam database (clean setup)"""
    
    # Create database connection
    conn = sqlite3.connect('freejam.db')
    cursor = conn.cursor()
    
    print("Setting up Free Jam database...")
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            is_private BOOLEAN DEFAULT FALSE,
            pin TEXT,
            creator_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES users (id)
        )
    ''')
    
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
            FOREIGN KEY (added_by) REFERENCES users (id)
        )
    ''')
    
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
    
    conn.commit()
    conn.close()
    
    print("Database setup complete!")
    print("🚀 Ready to start jamming!")
    print("No sample data - start fresh!")

if __name__ == '__main__':
    setup_database()
