import sqlite3
import os
from datetime import datetime, timedelta, timezone

# Database path configuration
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.db')

def get_db_connection():
    """Creates and returns a sqlite3 connection with Row factory and timeout for concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode and other optimizations for better concurrency and speed
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-2000') # 2MB cache
    return conn

def init_db():
    """Initializes the database schema and creates necessary indexes for performance."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Trades table: Stores all trading activity
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
    
    # Users table: For authentication
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        subscription_tier TEXT DEFAULT 'free',
        is_admin INTEGER DEFAULT 0
    )
    ''')
    
    # Correction Table: Stores persistent error patterns for smart memory
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
    
    # Performance Optimization: Add indexes for faster lookups and archiving
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_is_archived ON trades(is_archived)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_actual_result ON trades(actual_result)')

    conn.commit()
    conn.close()

def add_trade(trade_data):
    """Adds a new trade entry with duplicate prevention logic."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Set IST timestamp if not provided
        timestamp = trade_data.get('timestamp')
        if not timestamp:
            ist_offset = timezone(timedelta(hours=5, minutes=30))
            timestamp = datetime.now(tz=ist_offset).strftime('%Y-%m-%d %H:%M:%S')

        # Duplicate Prevention: Check if trade_id already exists
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
    except sqlite3.Error as e:
        print(f"DB Error: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def get_recent_trades(limit=10, include_archived=False):
    """Retrieves recent trades, optionally including archived ones."""
    conn = get_db_connection()
    try:
        query = 'SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?' if include_archived else \
                'SELECT * FROM trades WHERE is_archived = 0 ORDER BY timestamp DESC LIMIT ?'
        trades = conn.execute(query, (limit,)).fetchall()
        return [dict(row) for row in trades]
    finally:
        conn.close()

def archive_all_trades():
    """Marks all current active trades as archived for New Session logic."""
    conn = get_db_connection()
    try:
        conn.execute('UPDATE trades SET is_archived = 1 WHERE is_archived = 0')
        conn.commit()
    finally:
        conn.close()

def delete_trade(trade_id):
    """Deletes a specific trade by ID."""
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM trades WHERE trade_id = ?', (trade_id,))
        conn.commit()
    finally:
        conn.close()

def clear_db():
    """Permanently clears all trade history."""
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM trades')
        conn.commit()
    finally:
        conn.close()

def get_total_trades_count(include_archived=False):
    """Returns the total count of trades."""
    conn = get_db_connection()
    try:
        query = 'SELECT COUNT(*) FROM trades' if include_archived else \
                'SELECT COUNT(*) FROM trades WHERE is_archived = 0'
        row = conn.execute(query).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()

def get_session_trades(session_id):
    """Retrieves all trades for a specific session."""
    conn = get_db_connection()
    try:
        trades = conn.execute('SELECT * FROM trades WHERE session_id = ? ORDER BY timestamp ASC', (session_id,)).fetchall()
        return [dict(row) for row in trades]
    finally:
        conn.close()
