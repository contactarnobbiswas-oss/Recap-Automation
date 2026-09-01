import sqlite3
import os
import hashlib
import time
from datetime import datetime, date
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recap_studio.db")
SESSIONS: Dict[str, Dict[str, Any]] = {}  # In-memory session store: token -> user dict

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    """Hashes a password securely using PBKDF2-HMAC-SHA256."""
    salt = "recap_studio_salt_2026"
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()


def init_db():
    """Initializes SQLite database tables and seeds default admin account."""
    conn = get_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'editor',
        gemini_api_key TEXT DEFAULT '',
        daily_limit INTEGER NOT NULL DEFAULT 5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Activity Logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usage_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        video_title TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    conn.commit()

    # Seed default Admin account if not exists
    cursor.execute("SELECT id FROM users WHERE username = 'admin';")
    admin = cursor.fetchone()
    if not admin:
        admin_pass_hash = hash_password("admin123")
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, daily_limit) VALUES ('admin', ?, 'admin', 999999);",
            (admin_pass_hash,)
        )
        conn.commit()
        print("[DB Engine] Created default admin account (username: admin, password: admin123)")

    conn.close()


def authenticate_user(username: str, password_raw: str) -> Optional[Dict[str, Any]]:
    """Authenticates username & password, returns user dict if valid."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?;", (username.strip(),))
    user = cursor.fetchone()
    conn.close()

    if user:
        input_hash = hash_password(password_raw)
        if input_hash == user["password_hash"]:
            return dict(user)
    return None


def create_user(username: str, password_raw: str, role: str = "editor", daily_limit: int = 5) -> Dict[str, Any]:
    """Creates a new editor user account."""
    conn = get_connection()
    cursor = conn.cursor()
    pass_hash = hash_password(password_raw)
    
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, daily_limit) VALUES (?, ?, ?, ?);",
            (username.strip(), pass_hash, role, daily_limit)
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM users WHERE id = ?;", (new_id,))
        new_user = dict(cursor.fetchone())
        conn.close()
        return new_user
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"Username '{username}' already exists.")


def update_user_api_key(user_id: int, api_key: str):
    """Updates user's saved Gemini API key."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET gemini_api_key = ? WHERE id = ?;", (api_key.strip(), user_id))
    conn.commit()
    conn.close()


def update_user_limit(user_id: int, new_limit: int):
    """Updates an editor's daily limit."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET daily_limit = ? WHERE id = ?;", (new_limit, user_id))
    conn.commit()
    conn.close()


def get_user_today_usage_count(user_id: int) -> int:
    """Returns number of generations performed by user today (since 00:00 midnight)."""
    conn = get_connection()
    cursor = conn.cursor()
    today_str = date.today().isoformat()
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM usage_logs WHERE user_id = ? AND date(created_at) = ?;",
        (user_id, today_str)
    )
    res = cursor.fetchone()
    conn.close()
    return res["cnt"] if res else 0


def log_activity(user_id: int, username: str, action: str, video_title: str = ""):
    """Logs user action in activity log."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO usage_logs (user_id, username, action, video_title) VALUES (?, ?, ?, ?);",
        (user_id, username, action, video_title)
    )
    conn.commit()
    conn.close()


def get_all_users_with_stats() -> List[Dict[str, Any]]:
    """Returns list of all users with today's usage count (for Admin Panel)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, daily_limit, created_at, gemini_api_key FROM users ORDER BY role DESC, username ASC;")
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()

    today_str = date.today().isoformat()
    for u in users:
        u["used_today"] = get_user_today_usage_count(u["id"])
        # Mask API key for security
        key = u.get("gemini_api_key", "")
        u["has_api_key"] = bool(key)
        u["masked_api_key"] = (key[:4] + "••••••••" + key[-4:]) if len(key) >= 8 else ("••••" if key else "")
        del u["gemini_api_key"]

    return users


def get_recent_activity_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns recent activity logs for Admin Dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, action, video_title, created_at FROM usage_logs ORDER BY created_at DESC LIMIT ?;",
        (limit,)
    )
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return logs


def create_session(user_dict: Dict[str, Any]) -> str:
    """Creates a session token for logged in user."""
    token = f"sess_{user_dict['id']}_{int(time.time())}_{hashlib.md5(user_dict['username'].encode()).hexdigest()[:8]}"
    SESSIONS[token] = user_dict
    return token


def get_session_user(token: str) -> Optional[Dict[str, Any]]:
    """Returns current logged-in user dict from session token."""
    if not token:
        return None
    user = SESSIONS.get(token)
    if user:
        # Refresh current user data from DB
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?;", (user["id"],))
        db_user = cursor.fetchone()
        conn.close()
        if db_user:
            updated = dict(db_user)
            SESSIONS[token] = updated
            return updated
    return user
