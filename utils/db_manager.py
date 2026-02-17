import sqlite3
import os
import shutil
from datetime import datetime, timedelta, timezone

# Database path configuration
IS_VERCEL = "VERCEL" in os.environ
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ORIGINAL_DB_PATH = os.path.join(BASE_DIR, 'database.db')

if IS_VERCEL:
    DB_PATH = '/tmp/database.db'
    # Copy the original database to /tmp if it doesn't exist there yet
    if not os.path.exists(DB_PATH) and os.path.exists(ORIGINAL_DB_PATH):
        try:
            shutil.copy2(ORIGINAL_DB_PATH, DB_PATH)
        except Exception as e:
            print(f"DB Copy Error: {e}")
else:
    DB_PATH = ORIGINAL_DB_PATH

def get_db_connection():
    """Creates and returns a sqlite3 connection. Simplified for Vercel."""
    try:
        # Ensure the directory for DB_PATH exists
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        conn = sqlite3.connect(DB_PATH, timeout=30) 
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Connection Error: {e}")
        # Fallback to in-memory if disk is really not writable
        conn = sqlite3.connect(':memory:', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Initializes the database schema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        session_id TEXT NOT NULL,
        trade_id TEXT UNIQUE NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        ai_prediction TEXT NOT NULL,
        ai_confidence REAL NOT NULL,
        signal_source TEXT NOT NULL,
        user_choice TEXT,
        actual_result TEXT,
        bet_amount REAL,
        is_archived INTEGER DEFAULT 0
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        subscription_tier TEXT DEFAULT 'free',
        is_admin INTEGER DEFAULT 0
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS correction_table (
        pattern TEXT PRIMARY KEY,
        incorrect_prediction TEXT,
        correct_result TEXT,
        occurrence_count INTEGER DEFAULT 1,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        reliability_score REAL DEFAULT 0.5
    )
    ''')
    
    conn.commit()
    conn.close()

def add_trade(trade_data):
    """Adds a new trade entry."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        timestamp = trade_data.get('timestamp')
        if not timestamp:
            ist_offset = timezone(timedelta(hours=5, minutes=30))
            timestamp = datetime.now(tz=ist_offset).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('SELECT 1 FROM trades WHERE trade_id = ?', (trade_data['trade_id'],))
        if cursor.fetchone(): return False

        cursor.execute('''
        INSERT INTO trades (user_id, session_id, trade_id, timestamp, ai_prediction, ai_confidence, signal_source, user_choice, actual_result, bet_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['user_id'], trade_data['session_id'], trade_data['trade_id'], timestamp,
            trade_data['ai_prediction'], trade_data['ai_confidence'], trade_data['signal_source'], 
            trade_data.get('user_choice'), trade_data.get('actual_result'), trade_data.get('bet_amount')
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error: {e}")
        return False
    finally:
        if conn: conn.close()

def get_recent_trades(limit=10, include_archived=False):
    conn = get_db_connection()
    try:
        query = 'SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?' if include_archived else \
                'SELECT * FROM trades WHERE is_archived = 0 ORDER BY timestamp DESC LIMIT ?'
        trades = conn.execute(query, (limit,)).fetchall()
        return [dict(row) for row in trades]
    finally:
        conn.close()

def archive_all_trades():
    conn = get_db_connection()
    try:
        conn.execute('UPDATE trades SET is_archived = 1 WHERE is_archived = 0')
        conn.commit()
    finally:
        conn.close()

def delete_trade(trade_id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM trades WHERE trade_id = ?', (trade_id,))
        conn.commit()
    finally:
        conn.close()

def clear_db():
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM trades')
        conn.commit()
    finally:
        conn.close()

def get_total_trades_count(include_archived=False):
    conn = get_db_connection()
    try:
        query = 'SELECT COUNT(*) FROM trades' if include_archived else \
                'SELECT COUNT(*) FROM trades WHERE is_archived = 0'
        row = conn.execute(query).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()

def get_session_trades(session_id):
    conn = get_db_connection()
    try:
        trades = conn.execute('SELECT * FROM trades WHERE session_id = ? ORDER BY timestamp ASC', (session_id,)).fetchall()
        return [dict(row) for row in trades]
    finally:
        conn.close()
