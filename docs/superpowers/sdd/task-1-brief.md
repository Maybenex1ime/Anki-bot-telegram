### Task 1: Scaffold + config + db

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `app/__init__.py`, `app/config.py`, `app/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `config.DATA_DIR/DB_PATH/MEDIA_DIR/TZ/BOT_TOKEN/OWNER_ID/CEDICT_URL/DEFAULT_SETTINGS`, `config.today() -> datetime.date`, `config.today_iso() -> str`; `db.connect(db_path=None) -> sqlite3.Connection`, `db.get_setting(conn,key) -> str`, `db.set_setting(conn,key,value)`, `db.kv_get(conn,key,default=None)`, `db.kv_set(conn,key,value)`, `db.kv_del(conn,key)`

- [ ] **Step 1: Tạo file cấu hình dự án**

`requirements.txt`:
```
python-telegram-bot[job-queue]==21.*
pypinyin>=0.53
edge-tts>=6.1
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8
pytest-asyncio>=0.23
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
data/
.env
```

`app/__init__.py`: file rỗng.

- [ ] **Step 2: Viết test cho db (fail trước)**

`tests/test_db.py`:
```python
from app import db


def test_connect_creates_schema_and_defaults(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"decks", "cards", "settings", "daily_log", "dict_entries", "kv"} <= tables
    assert conn.execute("SELECT name FROM decks WHERE id=1").fetchone()["name"] == "Mặc định"
    assert db.get_setting(conn, "new_per_day") == "20"


def test_settings_roundtrip(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.set_setting(conn, "new_per_day", "5")
    assert db.get_setting(conn, "new_per_day") == "5"


def test_kv_roundtrip(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    assert db.kv_get(conn, "x") is None
    db.kv_set(conn, "x", {"a": [1, 2]})
    assert db.kv_get(conn, "x") == {"a": [1, 2]}
    db.kv_del(conn, "x")
    assert db.kv_get(conn, "x", "gone") == "gone"
```

- [ ] **Step 3: Chạy test, xác nhận FAIL**

Run: `python -m pytest tests/test_db.py -v` — Expected: FAIL (ImportError/AttributeError).

- [ ] **Step 4: Viết `app/config.py` và `app/db.py`**

`app/config.py`:
```python
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DB_PATH = DATA_DIR / "reminder.db"
MEDIA_DIR = DATA_DIR / "media"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
CEDICT_URL = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
DEFAULT_SETTINGS = {
    "reminder_times": "07:30,12:30,20:00",
    "evening_nudge": "21:30",
    "new_per_day": "20",
    "tts_voice": "zh-CN-XiaoxiaoNeural",
}


def today():
    return datetime.now(TZ).date()


def today_iso():
    return today().isoformat()
```

`app/db.py`:
```python
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
```

- [ ] **Step 5: Chạy test, xác nhận PASS** — `python -m pytest tests/test_db.py -v`

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: scaffold, config, sqlite schema + kv/settings helpers"`

---

