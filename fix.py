import sqlite3
import os

def fix_database():
    """Fix database by adding missing columns and updating structure"""
    
    if not os.path.exists('freejam.db'):
        print("No database found. Run setup_database.py first.")
        return
    
    print("Fixing Free Jam database...")
    
    conn = sqlite3.connect('freejam.db')
    cursor = conn.cursor()
    
    try:
        # Check current rooms table structure
        cursor.execute("PRAGMA table_info(rooms)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current rooms columns: {columns}")
        
        # Add missing columns to rooms table
        if 'last_active' not in columns:
            print("Adding last_active column to rooms...")
            cursor.execute('ALTER TABLE rooms ADD COLUMN last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            print("✅ Added last_active column")
        else:
            print("✅ last_active column already exists")
        
        if 'active_users' not in columns:
            print("Adding active_users column to rooms...")
            cursor.execute('ALTER TABLE rooms ADD COLUMN active_users INTEGER DEFAULT 0')
            print("✅ Added active_users column")
        else:
            print("✅ active_users column already exists")
        
        if 'current_song' not in columns:
            print("Adding current_song column to rooms...")
            cursor.execute('ALTER TABLE rooms ADD COLUMN current_song TEXT DEFAULT ""')
            print("✅ Added current_song column")
        else:
            print("✅ current_song column already exists")
        
        # Check songs table structure
        cursor.execute("PRAGMA table_info(songs)")
        song_columns = [column[1] for column in cursor.fetchall()]
        print(f"Current songs columns: {song_columns}")
        
        # Add missing columns to songs table
        if 'thumbnail' not in song_columns:
            print("Adding thumbnail column to songs...")
            cursor.execute('ALTER TABLE songs ADD COLUMN thumbnail TEXT DEFAULT ""')
            print("✅ Added thumbnail column")
        else:
            print("✅ thumbnail column already exists")
        
        if 'channel_title' not in song_columns:
            print("Adding channel_title column to songs...")
            cursor.execute('ALTER TABLE songs ADD COLUMN channel_title TEXT DEFAULT ""')
            print("✅ Added channel_title column")
        else:
            print("✅ channel_title column already exists")
        
        # Update existing data
        cursor.execute('''
            UPDATE rooms 
            SET last_active = CURRENT_TIMESTAMP 
            WHERE last_active IS NULL OR last_active = ''
        ''')
        
        cursor.execute('''
            UPDATE rooms 
            SET active_users = 0 
            WHERE active_users IS NULL
        ''')
        
        cursor.execute('''
            UPDATE rooms 
            SET current_song = '' 
            WHERE current_song IS NULL
        ''')
        
        cursor.execute('''
            UPDATE songs 
            SET thumbnail = 'https://img.youtube.com/vi/' || youtube_id || '/mqdefault.jpg'
            WHERE thumbnail = '' OR thumbnail IS NULL
        ''')
        
        cursor.execute('''
            UPDATE songs 
            SET channel_title = 'Unknown Artist'
            WHERE channel_title = '' OR channel_title IS NULL
        ''')
        
        conn.commit()
        print("✅ Database fixed successfully!")
        
        # Show final structure
        cursor.execute("PRAGMA table_info(rooms)")
        final_columns = [column[1] for column in cursor.fetchall()]
        print(f"Final rooms columns: {final_columns}")
        
    except Exception as e:
        print(f"❌ Error fixing database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    fix_database()
