import json
import sqlite3

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS cards(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
  hanzi TEXT NOT NULL,
  pinyin TEXT NOT NULL,
  meaning TEXT NOT NULL DEFAULT '',
  example TEXT NOT NULL DEFAULT '',
  image_file_id TEXT NOT NULL DEFAULT '',
  audio_path TEXT NOT NULL DEFAULT '',
  audio_file_id TEXT NOT NULL DEFAULT '',
  voice_file_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  due_date TEXT NOT NULL,
  interval REAL NOT NULL DEFAULT 0,
  ease REAL NOT NULL DEFAULT 2.5,
  repetitions INTEGER NOT NULL DEFAULT 0,
  lapses INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due_date);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS daily_log(
  day TEXT PRIMARY KEY,
  reviews INTEGER NOT NULL DEFAULT 0,
  new_introduced INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS dict_entries(
  simplified TEXT NOT NULL,
  traditional TEXT NOT NULL,
  pinyin TEXT NOT NULL,
  meaning TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dict_simp ON dict_entries(simplified);
CREATE INDEX IF NOT EXISTS idx_dict_trad ON dict_entries(traditional);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sentences(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hanzi TEXT NOT NULL,
  norm TEXT NOT NULL UNIQUE,
  words_json TEXT NOT NULL DEFAULT '',
  pinyin TEXT NOT NULL DEFAULT '',
  meaning TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'gemini',
  card_id INTEGER,
  audio_path TEXT NOT NULL DEFAULT '',
  audio_file_id TEXT NOT NULL DEFAULT '',
  times_used INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS distractors(
  card_id INTEGER NOT NULL,
  level TEXT NOT NULL,
  options_json TEXT NOT NULL,
  PRIMARY KEY(card_id, level)
);
CREATE TABLE IF NOT EXISTS practice_log(
  day TEXT NOT NULL,
  mode TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  correct INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(day, mode)
);
"""


def connect(db_path=None):
    path = db_path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO decks(id, name) VALUES(1, 'Mặc định')")
    for k, v in config.DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))
    conn.commit()
    return conn


def get_setting(conn, key):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else config.DEFAULT_SETTINGS.get(key, "")


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
    conn.commit()


def kv_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def kv_set(conn, key, value):
    conn.execute(
        "INSERT INTO kv(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
    conn.commit()


def kv_del(conn, key):
    conn.execute("DELETE FROM kv WHERE key=?", (key,))
    conn.commit()


def clear_pending(conn, action):
    """Xóa pending_input nếu nó thuộc về `action` (không đụng của luồng khác)."""
    pending = kv_get(conn, "pending_input")
    if pending and pending.get("action") == action:
        kv_del(conn, "pending_input")
