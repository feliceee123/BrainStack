import os, sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv('DATABASE_PATH', str(BASE / 'data' / 'brainstack.db')))
SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', verified INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL, category TEXT NOT NULL, description TEXT DEFAULT '', license TEXT NOT NULL, download_url TEXT NOT NULL, UNIQUE(title,author));
CREATE TABLE IF NOT EXISTS favorites(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,book_id));
CREATE TABLE IF NOT EXISTS downloads(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, guest_id TEXT, book_id INTEGER NOT NULL REFERENCES books(id), created_at TEXT DEFAULT CURRENT_TIMESTAMP, CHECK ((user_id IS NOT NULL AND guest_id IS NULL) OR (user_id IS NULL AND guest_id IS NOT NULL)));
CREATE TABLE IF NOT EXISTS email_codes(email TEXT PRIMARY KEY, name TEXT NOT NULL, password_hash TEXT NOT NULL, code_hash TEXT NOT NULL, expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS ai_conversations(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, guest_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ai_messages(id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
'''
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB_PATH, timeout=30); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA busy_timeout=30000'); return c

def init_db():
    import json
    c=connect()
    try:
        c.executescript(SCHEMA)
        p=BASE/'data'/'books.json'
        if p.exists():
            rows=json.loads(p.read_text(encoding='utf-8'))
            c.executemany('INSERT OR IGNORE INTO books(title,author,category,description,license,download_url) VALUES(?,?,?,?,?,?)',[(b['title'],b['author'],b['category'],b.get('description',''),b.get('license','Public domain; verify source terms'),b['download_url']) for b in rows])
        c.commit()
    finally:c.close()
