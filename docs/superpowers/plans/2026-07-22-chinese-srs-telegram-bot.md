# Chinese SRS Telegram Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Model policy (user requirement):** dispatch implementation subagents with **model Opus** (`model: "opus"`). Planning/review stays on the session model.

**Goal:** Telegram bot cá nhân học tiếng Trung kiểu Anki: gõ chữ Hán → thẻ tự tra (pinyin + nghĩa Anh + audio), ôn SM-2 ngay trong chat, nhắc theo giờ, chạy trên Fly.io.

**Architecture:** Một tiến trình Python async duy nhất: `python-telegram-bot` long-polling + JobQueue scheduler + SQLite (kèm bảng từ điển CC-CEDICT) trên volume. Trạng thái phiên ôn/nhập liệu lưu trong bảng `kv` của SQLite nên sống sót qua restart.

**Tech Stack:** Python 3.12, python-telegram-bot v21 (async, job-queue extra), SQLite (stdlib `sqlite3`), pypinyin, edge-tts, pytest.

**Spec:** `docs/superpowers/specs/2026-07-22-chinese-srs-telegram-bot-design.md`

## Global Constraints

- Python 3.12; toàn bộ chuỗi hiển thị cho người dùng bằng **tiếng Việt**.
- Bot phục vụ đúng 1 người: mọi handler lọc theo `OWNER_ID` (env var). Callback handler phải tự kiểm tra vì filter chỉ áp cho message handler.
- Múi giờ cố định `Asia/Ho_Chi_Minh` (zoneinfo), "ngày" = ngày theo múi giờ này, lưu dạng chuỗi ISO `YYYY-MM-DD`.
- Mọi đường dẫn dữ liệu đi qua `app/config.py` (`DATA_DIR` env var, mặc định `./data`); không hardcode đường dẫn ở nơi khác.
- Không bao giờ chặn việc tạo thẻ vì tra cứu/TTS thất bại (spec §8).
- SM-2 thuần (spec §4): min ease 1.3; AGAIN → interval 1, due hôm nay (lặp lại trong phiên); mặc định 20 thẻ mới/ngày.
- Commit sau mỗi task; test chạy bằng `python -m pytest tests/ -v` từ thư mục gốc repo.
- Secrets (`BOT_TOKEN`, `OWNER_ID`) chỉ qua env var — không commit vào repo.

## File Structure

```
app/
  __init__.py
  config.py        # env, paths, hằng số, today()
  db.py            # schema, connect(), settings + kv helpers
  srs.py           # SM-2 thuần (không I/O)
  lookup.py        # pypinyin + CC-CEDICT (tải, parse, tra)
  tts.py           # edge-tts wrapper
  csv_import.py    # parser CSV thuần
  stats.py         # daily_log, streak, thống kê
  cards.py         # CRUD thẻ, pipeline tạo thẻ, queue ôn, apply_rating
  bot/
    __init__.py
    auth.py        # owner filter + decorator cho callback
    main.py        # Application, đăng ký handler, post_init
    misc.py        # /start, /thongke, /backup
    textrouter.py  # điều phối text/photo theo pending_input trong kv
    create_flow.py # gõ chữ Hán → preview → lưu
    review_flow.py # /on, front/answer, chấm điểm, audio
    voice_flow.py  # 🎤 thu âm & so sánh
    reminders.py   # job nhắc theo giờ + nhắc cuối ngày
    decks_flow.py  # /bo
    manage_flow.py # /tim, xem/sửa/xóa thẻ
    csv_flow.py    # nhận file .csv, chọn bộ, nhập
    settings_flow.py # /settings
tests/
  test_db.py test_srs.py test_lookup.py test_tts.py
  test_csv_import.py test_stats.py test_cards.py
requirements.txt requirements-dev.txt Dockerfile fly.toml .gitignore
```

---

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

### Task 2: SM-2 (`app/srs.py`)

**Files:** Create `app/srs.py`; Test `tests/test_srs.py`

**Interfaces:**
- Produces: hằng `srs.AGAIN=1, HARD=2, GOOD=3, EASY=4`; `@dataclass SrsState(interval: float=0.0, ease: float=2.5, repetitions: int=0, lapses: int=0)`; `srs.review(state: SrsState, rating: int, today: date) -> tuple[SrsState, date]` (trả state MỚI, không sửa state cũ; date = due mới).

- [ ] **Step 1: Viết test (fail trước)**

`tests/test_srs.py`:
```python
from datetime import date, timedelta

import pytest

from app.srs import AGAIN, EASY, GOOD, HARD, SrsState, review

TODAY = date(2026, 7, 22)


def test_new_card_good_gives_1_day():
    s, due = review(SrsState(), GOOD, TODAY)
    assert (s.interval, s.repetitions) == (1.0, 1)
    assert due == TODAY + timedelta(days=1)


def test_second_good_gives_3_days():
    s1, _ = review(SrsState(), GOOD, TODAY)
    s2, due = review(s1, GOOD, TODAY)
    assert s2.interval == 3.0
    assert due == TODAY + timedelta(days=3)


def test_third_good_multiplies_by_ease():
    s = SrsState(interval=3.0, ease=2.5, repetitions=2)
    s2, due = review(s, GOOD, TODAY)
    assert s2.interval == pytest.approx(7.5)
    assert due == TODAY + timedelta(days=8)  # 7.5 làm tròn nửa-lên = 8 (xem note làm tròn dưới)


def test_again_resets_and_stays_today():
    s = SrsState(interval=20.0, ease=2.5, repetitions=5)
    s2, due = review(s, AGAIN, TODAY)
    assert (s2.interval, s2.repetitions, s2.lapses) == (1.0, 0, 1)
    assert s2.ease == pytest.approx(2.3)
    assert due == TODAY  # lặp lại ngay trong phiên hôm nay


def test_hard_grows_slow_and_drops_ease():
    s = SrsState(interval=10.0, ease=2.5, repetitions=3)
    s2, due = review(s, HARD, TODAY)
    assert s2.interval == pytest.approx(12.0)
    assert s2.ease == pytest.approx(2.35)
    assert due == TODAY + timedelta(days=12)


def test_easy_boosts():
    s = SrsState(interval=3.0, ease=2.5, repetitions=2)
    s2, _ = review(s, EASY, TODAY)
    assert s2.ease == pytest.approx(2.65)
    assert s2.interval == pytest.approx(3.0 * 2.65 * 1.3)


def test_ease_floor():
    s = SrsState(interval=5.0, ease=1.3, repetitions=3)
    s2, _ = review(s, AGAIN, TODAY)
    assert s2.ease == 1.3


def test_input_state_not_mutated():
    s = SrsState(interval=5.0, ease=2.0, repetitions=2)
    review(s, GOOD, TODAY)
    assert (s.interval, s.ease, s.repetitions) == (5.0, 2.0, 2)
```

**Lưu ý làm tròn:** dùng `int(x + 0.5)` (làm tròn nửa-lên), KHÔNG dùng `round()` (banker's rounding của Python cho `round(7.5) == 8` nhưng `round(8.5) == 8`). Test số 3 kỳ vọng 7.5 → 8 ngày.

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_srs.py -v`

- [ ] **Step 3: Viết `app/srs.py`**

```python
from dataclasses import dataclass, replace
from datetime import date, timedelta

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
MIN_EASE = 1.3


@dataclass(frozen=True)
class SrsState:
    interval: float = 0.0
    ease: float = 2.5
    repetitions: int = 0
    lapses: int = 0


def review(state: SrsState, rating: int, today: date) -> tuple[SrsState, date]:
    if rating == AGAIN:
        s = replace(state, interval=1.0, repetitions=0,
                    lapses=state.lapses + 1,
                    ease=max(MIN_EASE, state.ease - 0.20))
        return s, today  # lặp lại ngay trong phiên hôm nay
    if rating == HARD:
        interval = 1.0 if state.repetitions == 0 else max(state.interval * 1.2, state.interval + 1)
        s = replace(state, interval=interval, repetitions=state.repetitions + 1,
                    ease=max(MIN_EASE, state.ease - 0.15))
    elif rating == GOOD:
        if state.repetitions == 0:
            interval = 1.0
        elif state.repetitions == 1:
            interval = 3.0
        else:
            interval = state.interval * state.ease
        s = replace(state, interval=interval, repetitions=state.repetitions + 1)
    elif rating == EASY:
        ease = state.ease + 0.15
        interval = 4.0 if state.repetitions == 0 else state.interval * ease * 1.3
        s = replace(state, interval=interval, repetitions=state.repetitions + 1, ease=ease)
    else:
        raise ValueError(f"rating không hợp lệ: {rating}")
    days = max(1, int(s.interval + 0.5))
    return s, today + timedelta(days=days)
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_srs.py -v`
- [ ] **Step 5: Commit** — `git commit -am "feat: SM-2 scheduler (pure functions)"`

---

### Task 3: Tra cứu — pinyin + CC-CEDICT (`app/lookup.py`)

**Files:** Create `app/lookup.py`; Test `tests/test_lookup.py`

**Interfaces:**
- Consumes: `db.connect` (bảng `dict_entries`), `config.CEDICT_URL`, `config.DATA_DIR`
- Produces: `lookup.gen_pinyin(hanzi: str) -> str` (có dấu thanh, cách nhau bởi space); `lookup.parse_cedict_line(line: str) -> tuple[str,str,str,str] | None` (simp, trad, pinyin, meaning); `lookup.ensure_cedict(conn) -> int` (số dòng đã nạp, 0 nếu đã có sẵn; tải file nếu chưa có); `lookup.lookup_meaning(conn, hanzi: str) -> str` ('' nếu không thấy)

- [ ] **Step 1: Viết test (fail trước)**

`tests/test_lookup.py`:
```python
from app import db, lookup


def test_gen_pinyin_with_tones():
    assert lookup.gen_pinyin("学习") == "xué xí"
    assert lookup.gen_pinyin("你好") == "nǐ hǎo"


def test_parse_cedict_line():
    line = "學習 学习 [xue2 xi2] /to learn/to study/"
    assert lookup.parse_cedict_line(line) == (
        "学习", "學習", "xue2 xi2", "to learn; to study")


def test_parse_cedict_skips_comments_and_garbage():
    assert lookup.parse_cedict_line("# CC-CEDICT") is None
    assert lookup.parse_cedict_line("not a dict line") is None


def test_lookup_meaning_by_simplified_and_traditional(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO dict_entries VALUES(?,?,?,?)",
                 ("学习", "學習", "xue2 xi2", "to learn; to study"))
    conn.commit()
    assert lookup.lookup_meaning(conn, "学习") == "to learn; to study"
    assert lookup.lookup_meaning(conn, "學習") == "to learn; to study"
    assert lookup.lookup_meaning(conn, "不存在的词") == ""
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_lookup.py -v`

- [ ] **Step 3: Viết `app/lookup.py`**

```python
import gzip
import re
import urllib.request

from pypinyin import Style, pinyin

from app import config

_CEDICT_LINE = re.compile(r"^(\S+) (\S+) \[([^\]]+)\] /(.+)/\s*$")


def gen_pinyin(hanzi: str) -> str:
    return " ".join(p[0] for p in pinyin(hanzi, style=Style.TONE))


def parse_cedict_line(line):
    if line.startswith("#"):
        return None
    m = _CEDICT_LINE.match(line.strip())
    if not m:
        return None
    trad, simp, pin, meaning = m.groups()
    return simp, trad, pin, "; ".join(meaning.split("/"))


def ensure_cedict(conn) -> int:
    if conn.execute("SELECT COUNT(*) c FROM dict_entries").fetchone()["c"] > 0:
        return 0
    path = config.DATA_DIR / "cedict.txt.gz"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(config.CEDICT_URL, path)
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            parsed = parse_cedict_line(line)
            if parsed:
                rows.append(parsed)
    conn.executemany("INSERT INTO dict_entries VALUES(?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def lookup_meaning(conn, hanzi: str) -> str:
    rows = conn.execute(
        "SELECT meaning FROM dict_entries WHERE simplified=? OR traditional=? LIMIT 3",
        (hanzi, hanzi)).fetchall()
    return " | ".join(r["meaning"] for r in rows)
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_lookup.py -v`
- [ ] **Step 5: Commit** — `git commit -am "feat: pinyin generation + CC-CEDICT import/lookup"`

---

### Task 4: TTS wrapper (`app/tts.py`)

**Files:** Create `app/tts.py`; Test `tests/test_tts.py`

**Interfaces:**
- Produces: `async tts.synthesize(text: str, voice: str, out_path: Path) -> bool` — True nếu file mp3 tồn tại và >0 byte; mọi exception nuốt vào và trả False (spec §8: TTS lỗi không được chặn tạo thẻ).

- [ ] **Step 1: Viết test (fail trước)** — mock edge_tts, không gọi mạng:

`tests/test_tts.py`:
```python
import pytest

from app import tts


class FakeCommOK:
    def __init__(self, text, voice):
        pass

    async def save(self, path):
        with open(path, "wb") as f:
            f.write(b"mp3data")


class FakeCommFail:
    def __init__(self, text, voice):
        pass

    async def save(self, path):
        raise RuntimeError("network down")


@pytest.mark.asyncio
async def test_synthesize_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.edge_tts, "Communicate", FakeCommOK)
    out = tmp_path / "m" / "1.mp3"
    assert await tts.synthesize("学习", "zh-CN-XiaoxiaoNeural", out) is True
    assert out.read_bytes() == b"mp3data"


@pytest.mark.asyncio
async def test_synthesize_failure_returns_false_and_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.edge_tts, "Communicate", FakeCommFail)
    out = tmp_path / "1.mp3"
    assert await tts.synthesize("学习", "voice", out) is False
    assert not out.exists()
```

Thêm `pytest.ini` ở gốc repo:
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_tts.py -v`

- [ ] **Step 3: Viết `app/tts.py`**

```python
import edge_tts


async def synthesize(text, voice, out_path) -> bool:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await edge_tts.Communicate(text, voice).save(str(out_path))
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        try:
            if out_path.exists():
                out_path.unlink()
        except OSError:
            pass
        return False
```

- [ ] **Step 4: Run PASS**, rồi kiểm tra thật 1 lần (cần mạng): `python -c "import asyncio,pathlib; from app import tts; print(asyncio.run(tts.synthesize('学习','zh-CN-XiaoxiaoNeural',pathlib.Path('data/media/smoke.mp3'))))"` — Expected: `True`, nghe thử file `data/media/smoke.mp3` rồi xóa.
- [ ] **Step 5: Commit** — `git commit -am "feat: edge-tts wrapper with graceful failure"`

---

### Task 5: CSV parser (`app/csv_import.py`)

**Files:** Create `app/csv_import.py`; Test `tests/test_csv_import.py`

**Interfaces:**
- Produces: `@dataclass CsvRow(hanzi, pinyin, meaning, example)` (đều `str`, có thể rỗng trừ hanzi); `@dataclass CsvResult(rows: list[CsvRow], errors: list[tuple[int, str]])` (int = số dòng trong file, 1-based, tính cả header); `csv_import.parse_csv(text: str) -> CsvResult`. Header nhận alias: `hán|han|hanzi`, `pinyin`, `nghĩa|nghia|meaning`, `ví_dụ|vi_du|example`; thiếu cột `hán` trong header → toàn bộ là lỗi dòng 1.

- [ ] **Step 1: Viết test (fail trước)**

`tests/test_csv_import.py`:
```python
from app.csv_import import parse_csv


def test_parse_full_and_partial_rows():
    text = "hán,pinyin,nghĩa,ví_dụ\n学习,,to learn,我在学习\n你好,nǐ hǎo,,\n"
    r = parse_csv(text)
    assert not r.errors
    assert [row.hanzi for row in r.rows] == ["学习", "你好"]
    assert r.rows[0].meaning == "to learn"
    assert r.rows[0].example == "我在学习"
    assert r.rows[1].pinyin == "nǐ hǎo"


def test_missing_hanzi_cell_is_error_with_line_number():
    text = "hán,pinyin,nghĩa,ví_dụ\n,,x,\n好,,,\n"
    r = parse_csv(text)
    assert len(r.rows) == 1
    assert r.errors == [(2, "thiếu chữ Hán")]


def test_header_aliases_and_bom():
    text = "﻿hanzi,meaning\n学,to study\n"
    r = parse_csv(text)
    assert r.rows[0].hanzi == "学"
    assert r.rows[0].meaning == "to study"


def test_missing_hanzi_column():
    r = parse_csv("pinyin,nghĩa\nxue,to learn\n")
    assert r.rows == []
    assert r.errors == [(1, "thiếu cột 'hán' trong header")]


def test_blank_lines_skipped():
    r = parse_csv("hán\n学\n\n习\n")
    assert [row.hanzi for row in r.rows] == ["学", "习"]
    assert not r.errors
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_csv_import.py -v`

- [ ] **Step 3: Viết `app/csv_import.py`**

```python
import csv
import io
from dataclasses import dataclass, field

_ALIASES = {
    "hán": "hanzi", "han": "hanzi", "hanzi": "hanzi",
    "pinyin": "pinyin",
    "nghĩa": "meaning", "nghia": "meaning", "meaning": "meaning",
    "ví_dụ": "example", "vi_du": "example", "example": "example",
}


@dataclass
class CsvRow:
    hanzi: str
    pinyin: str = ""
    meaning: str = ""
    example: str = ""


@dataclass
class CsvResult:
    rows: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def parse_csv(text: str) -> CsvResult:
    result = CsvResult()
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = next(reader)
    except StopIteration:
        result.errors.append((1, "file rỗng"))
        return result
    cols = {}
    for i, name in enumerate(header):
        key = _ALIASES.get(name.strip().lower())
        if key:
            cols[key] = i
    if "hanzi" not in cols:
        result.errors.append((1, "thiếu cột 'hán' trong header"))
        return result

    def cell(row, key):
        i = cols.get(key)
        return row[i].strip() if i is not None and i < len(row) else ""

    for line_no, row in enumerate(reader, start=2):
        if not any(c.strip() for c in row):
            continue
        hanzi = cell(row, "hanzi")
        if not hanzi:
            result.errors.append((line_no, "thiếu chữ Hán"))
            continue
        result.rows.append(CsvRow(
            hanzi=hanzi, pinyin=cell(row, "pinyin"),
            meaning=cell(row, "meaning"), example=cell(row, "example")))
    return result
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_csv_import.py -v`
- [ ] **Step 5: Commit** — `git commit -am "feat: CSV parser with header aliases and per-line errors"`

---

### Task 6: Stats & streak (`app/stats.py`)

**Files:** Create `app/stats.py`; Test `tests/test_stats.py`

**Interfaces:**
- Consumes: bảng `daily_log`, `cards`
- Produces: `stats.bump_review(conn, day_iso: str, was_new: bool)`; `stats.reviews_today(conn, day_iso) -> int`; `stats.new_used_today(conn, day_iso) -> int`; `stats.streak(conn, today: date) -> int` (hôm nay chưa ôn thì tính chuỗi kết thúc hôm qua); `stats.overview(conn, today_iso) -> dict` với khóa `total, due, new_waiting, streak, total_reviews, total_lapses`

- [ ] **Step 1: Viết test (fail trước)**

`tests/test_stats.py`:
```python
from datetime import date

from app import db, stats


def make(tmp_path):
    return db.connect(tmp_path / "t.db")


def test_bump_and_counts(tmp_path):
    conn = make(tmp_path)
    stats.bump_review(conn, "2026-07-22", was_new=True)
    stats.bump_review(conn, "2026-07-22", was_new=False)
    assert stats.reviews_today(conn, "2026-07-22") == 2
    assert stats.new_used_today(conn, "2026-07-22") == 1
    assert stats.reviews_today(conn, "2026-07-23") == 0


def test_streak_counts_consecutive_days(tmp_path):
    conn = make(tmp_path)
    for d in ["2026-07-19", "2026-07-20", "2026-07-21"]:
        stats.bump_review(conn, d, was_new=False)
    # hôm nay 22 chưa ôn -> chuỗi kết thúc hôm qua vẫn là 3
    assert stats.streak(conn, date(2026, 7, 22)) == 3
    stats.bump_review(conn, "2026-07-22", was_new=False)
    assert stats.streak(conn, date(2026, 7, 22)) == 4


def test_streak_broken(tmp_path):
    conn = make(tmp_path)
    stats.bump_review(conn, "2026-07-15", was_new=False)
    assert stats.streak(conn, date(2026, 7, 22)) == 0
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_stats.py -v`

- [ ] **Step 3: Viết `app/stats.py`**

```python
from datetime import timedelta


def bump_review(conn, day_iso, was_new):
    conn.execute(
        "INSERT INTO daily_log(day, reviews, new_introduced) VALUES(?, 1, ?) "
        "ON CONFLICT(day) DO UPDATE SET reviews=reviews+1, "
        "new_introduced=new_introduced+excluded.new_introduced",
        (day_iso, 1 if was_new else 0))
    conn.commit()


def reviews_today(conn, day_iso):
    row = conn.execute("SELECT reviews FROM daily_log WHERE day=?", (day_iso,)).fetchone()
    return row["reviews"] if row else 0


def new_used_today(conn, day_iso):
    row = conn.execute("SELECT new_introduced FROM daily_log WHERE day=?", (day_iso,)).fetchone()
    return row["new_introduced"] if row else 0


def streak(conn, today):
    days = {r["day"] for r in conn.execute("SELECT day FROM daily_log WHERE reviews>0")}
    d = today
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def overview(conn, today_iso):
    from datetime import date
    total = conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
    due = conn.execute(
        "SELECT COUNT(*) c FROM cards WHERE due_date<=? AND NOT(repetitions=0 AND lapses=0)",
        (today_iso,)).fetchone()["c"]
    new_waiting = conn.execute(
        "SELECT COUNT(*) c FROM cards WHERE repetitions=0 AND lapses=0 AND due_date<=?",
        (today_iso,)).fetchone()["c"]
    agg = conn.execute("SELECT COALESCE(SUM(repetitions),0) r, COALESCE(SUM(lapses),0) l FROM cards").fetchone()
    return {
        "total": total, "due": due, "new_waiting": new_waiting,
        "streak": streak(conn, date.fromisoformat(today_iso)),
        "total_reviews": agg["r"], "total_lapses": agg["l"],
    }
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_stats.py -v`
- [ ] **Step 5: Commit** — `git commit -am "feat: daily log, streak, stats overview"`

---

### Task 7: Card service (`app/cards.py`)

**Files:** Create `app/cards.py`; Test `tests/test_cards.py`

**Interfaces:**
- Consumes: `lookup.gen_pinyin/lookup_meaning`, `tts.synthesize`, `srs.review/SrsState`, `stats.bump_review/new_used_today`, `db.get_setting`
- Produces:
  - `async cards.create_card(conn, hanzi, deck_id=1, pinyin_override='', meaning_override='', example='', image_file_id='') -> sqlite3.Row` (due = hôm nay; audio synth sau khi insert, lỗi TTS thì `audio_path=''`)
  - `cards.get_card(conn, cid) -> Row | None`
  - `cards.is_new(row) -> bool` (repetitions==0 và lapses==0)
  - `cards.exists_hanzi(conn, hanzi) -> bool`
  - `cards.build_queue(conn, today_iso) -> list[int]` (review trước, new sau, new bị chặn bởi `new_per_day` − đã dùng hôm nay)
  - `cards.apply_rating(conn, cid, rating, today: date) -> None` (cập nhật SRS + bump stats)
  - `async cards.retry_audio(conn, cid) -> bool` (synth lại nếu `audio_path` rỗng)

- [ ] **Step 1: Viết test (fail trước)** — mock TTS để không gọi mạng:

`tests/test_cards.py`:
```python
from datetime import date

import pytest

from app import cards, db, srs, stats


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.MEDIA_DIR", tmp_path / "media")

    async def fake_synth(text, voice, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp3")
        return True

    monkeypatch.setattr("app.cards.tts.synthesize", fake_synth)
    c = db.connect(tmp_path / "t.db")
    c.execute("INSERT INTO dict_entries VALUES('学习','學習','xue2 xi2','to learn; to study')")
    c.commit()
    return c


async def test_create_card_autofills(conn):
    row = await cards.create_card(conn, "学习")
    assert row["pinyin"] == "xué xí"
    assert row["meaning"] == "to learn; to study"
    assert row["audio_path"].endswith(".mp3")
    assert cards.is_new(row)


async def test_create_card_overrides_and_unknown_word(conn):
    row = await cards.create_card(conn, "抽象词", meaning_override="")
    assert row["meaning"] == ""  # không có trong dict -> rỗng, không chặn tạo thẻ
    row2 = await cards.create_card(conn, "学习", pinyin_override="XX", meaning_override="YY")
    assert (row2["pinyin"], row2["meaning"]) == ("XX", "YY")


async def test_tts_failure_leaves_audio_empty(conn, monkeypatch):
    async def fail(text, voice, out):
        return False

    monkeypatch.setattr("app.cards.tts.synthesize", fail)
    row = await cards.create_card(conn, "你好")
    assert row["audio_path"] == ""


async def test_queue_reviews_first_then_new_with_limit(conn):
    db.set_setting(conn, "new_per_day", "2")
    ids = [(await cards.create_card(conn, h))["id"] for h in "一二三四"]
    today = date(2026, 7, 22)
    cards.apply_rating(conn, ids[0], srs.AGAIN, today)  # thành review, due hôm nay
    q = cards.build_queue(conn, today.isoformat())
    assert q[0] == ids[0]      # review đứng trước
    # apply_rating trên thẻ mới đã tính 1 suất new_introduced -> chỉ còn 1 suất new
    assert q[1:] == [ids[1]]


async def test_apply_rating_updates_card_and_stats(conn):
    row = await cards.create_card(conn, "学习")
    today = date(2026, 7, 22)
    cards.apply_rating(conn, row["id"], srs.GOOD, today)
    after = cards.get_card(conn, row["id"])
    assert after["repetitions"] == 1
    assert after["due_date"] == "2026-07-23"
    assert stats.reviews_today(conn, "2026-07-22") == 1
    assert stats.new_used_today(conn, "2026-07-22") == 1
```

Chú ý test 4: sau `apply_rating(AGAIN)` trên thẻ mới, `new_introduced` = 1, nên với `new_per_day=2` chỉ còn 1 suất new → kỳ vọng đúng là `q[1:] == [ids[1]]`. **Sửa dòng assert trong test cho khớp: `assert q[1:] == [ids[1]]`.**

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_cards.py -v`

- [ ] **Step 3: Viết `app/cards.py`**

```python
from app import config, db, lookup, srs, stats, tts


async def create_card(conn, hanzi, deck_id=1, pinyin_override="",
                      meaning_override="", example="", image_file_id=""):
    pin = pinyin_override or lookup.gen_pinyin(hanzi)
    meaning = meaning_override if meaning_override else lookup.lookup_meaning(conn, hanzi)
    today = config.today_iso()
    cur = conn.execute(
        "INSERT INTO cards(deck_id,hanzi,pinyin,meaning,example,image_file_id,"
        "created_at,due_date) VALUES(?,?,?,?,?,?,?,?)",
        (deck_id, hanzi, pin, meaning, example, image_file_id, today, today))
    cid = cur.lastrowid
    conn.commit()
    await retry_audio(conn, cid)
    return get_card(conn, cid)


async def retry_audio(conn, cid) -> bool:
    row = get_card(conn, cid)
    if not row or row["audio_path"]:
        return bool(row and row["audio_path"])
    out = config.MEDIA_DIR / f"{cid}.mp3"
    voice = db.get_setting(conn, "tts_voice")
    if await tts.synthesize(row["hanzi"], voice, out):
        conn.execute("UPDATE cards SET audio_path=? WHERE id=?", (str(out), cid))
        conn.commit()
        return True
    return False


def get_card(conn, cid):
    return conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()


def is_new(row) -> bool:
    return row["repetitions"] == 0 and row["lapses"] == 0


def exists_hanzi(conn, hanzi) -> bool:
    return conn.execute("SELECT 1 FROM cards WHERE hanzi=? LIMIT 1", (hanzi,)).fetchone() is not None


def build_queue(conn, today_iso):
    reviews = [r["id"] for r in conn.execute(
        "SELECT id FROM cards WHERE due_date<=? AND NOT(repetitions=0 AND lapses=0) "
        "ORDER BY due_date, id", (today_iso,))]
    limit = max(0, int(db.get_setting(conn, "new_per_day")) - stats.new_used_today(conn, today_iso))
    news = [r["id"] for r in conn.execute(
        "SELECT id FROM cards WHERE repetitions=0 AND lapses=0 AND due_date<=? "
        "ORDER BY id LIMIT ?", (today_iso, limit))]
    return reviews + news


def apply_rating(conn, cid, rating, today):
    row = get_card(conn, cid)
    state = srs.SrsState(row["interval"], row["ease"], row["repetitions"], row["lapses"])
    was_new = is_new(row)
    new_state, due = srs.review(state, rating, today)
    conn.execute(
        "UPDATE cards SET interval=?, ease=?, repetitions=?, lapses=?, due_date=? WHERE id=?",
        (new_state.interval, new_state.ease, new_state.repetitions,
         new_state.lapses, due.isoformat(), cid))
    conn.commit()
    stats.bump_review(conn, today.isoformat(), was_new)
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/ -v` (toàn bộ, đảm bảo không vỡ gì)
- [ ] **Step 5: Commit** — `git commit -am "feat: card service — create pipeline, review queue, rating"`

---

### Task 8: Bot skeleton — auth, /start, main

**Files:** Create `app/bot/__init__.py` (rỗng), `app/bot/auth.py`, `app/bot/misc.py` (mới chỉ /start), `app/bot/main.py`

**Interfaces:**
- Produces: `auth.owner_filter` (filters.User theo `config.OWNER_ID`); decorator `auth.owner_only_callback(fn)` — dùng cho MỌI CallbackQueryHandler về sau: nếu `update.effective_user.id != config.OWNER_ID` thì `await update.callback_query.answer()` rồi return; `main.build_app() -> Application` với `bot_data["conn"]` là kết nối SQLite; `main.main()` chạy polling. Các task sau sẽ **thêm handler vào `build_app`** — mỗi task ghi rõ dòng thêm.

- [ ] **Step 1: Viết `app/bot/auth.py`**

```python
from functools import wraps

from telegram.ext import filters

from app import config

owner_filter = filters.User(user_id=config.OWNER_ID)


def owner_only_callback(fn):
    @wraps(fn)
    async def wrapper(update, context):
        if not update.effective_user or update.effective_user.id != config.OWNER_ID:
            if update.callback_query:
                await update.callback_query.answer()
            return
        return await fn(update, context)
    return wrapper
```

- [ ] **Step 2: Viết `app/bot/misc.py` (bản đầu)**

```python
HELP = (
    "🀄 <b>Bot học tiếng Trung SRS</b>\n\n"
    "• Gõ chữ Hán bất kỳ (VD: 学习) → tạo thẻ mới\n"
    "• /on — ôn thẻ đến hạn ngay\n"
    "• /csv — nhập hàng loạt từ file CSV\n"
    "• /bo — quản lý bộ thẻ\n"
    "• /tim &lt;từ&gt; — tìm thẻ\n"
    "• /thongke — thống kê & streak\n"
    "• /settings — giờ nhắc, giới hạn thẻ mới, giọng đọc\n"
    "• /backup — nhận file dữ liệu"
)


async def cmd_start(update, context):
    await update.message.reply_html(HELP)
```

- [ ] **Step 3: Viết `app/bot/main.py`**

```python
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler

from app import config, db, lookup
from app.bot import misc
from app.bot.auth import owner_filter

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def post_init(app):
    conn = db.connect()
    app.bot_data["conn"] = conn
    n = lookup.ensure_cedict(conn)
    if n:
        logging.info("Đã nạp CC-CEDICT: %d mục", n)


def build_app() -> Application:
    app = (Application.builder().token(config.BOT_TOKEN)
           .post_init(post_init).build())
    app.add_handler(CommandHandler("start", misc.cmd_start, filters=owner_filter))
    return app


def main():
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test thủ công**

1. Tạo bot với @BotFather trên Telegram (`/newbot`) → lấy token.
2. Lấy Telegram ID của chủ bot: nhắn cho @userinfobot.
3. Chạy local (PowerShell): `$env:BOT_TOKEN="<token>"; $env:OWNER_ID="<id>"; python -m app.bot.main`
4. Nhắn `/start` cho bot → Expected: menu tiếng Việt. Lần chạy đầu log hiện "Đã nạp CC-CEDICT" (tải ~2 phút).
5. Nhờ một tài khoản khác nhắn `/start` → Expected: bot im lặng.

- [ ] **Step 5: Commit** — `git commit -am "feat: bot skeleton — single-user auth, /start, polling"`

---

### Task 9: Text router + luồng tạo thẻ

**Files:** Create `app/bot/textrouter.py`, `app/bot/create_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `cards.create_card/exists_hanzi`, `lookup.gen_pinyin/lookup_meaning`, `db.kv_*`
- Produces:
  - kv `pending_input`: dict `{"action": str, ...}` — hợp đồng chung mọi flow. Actions của task này: `pc_field` (`{"field": "pinyin"|"meaning"|"example"}`). Task sau thêm action mới vào `textrouter.TEXT_ACTIONS` bằng `textrouter.register(action, async_fn(update, context, pending, text))`.
  - kv `pending_card`: `{"hanzi","pinyin","meaning","example","image_file_id","deck_id"}`
  - `textrouter.on_text(update, context)` — nếu có `pending_input` → dispatch; elif text chứa ký tự CJK (`[一-鿿]`) → `create_flow.start_pending(update, context, text)`; else gợi ý dùng /start.
  - `textrouter.on_photo(update, context)` — nếu có `pending_card` → gắn ảnh (photo lớn nhất: `update.message.photo[-1].file_id`), render lại preview.
  - `create_flow.render_preview(context, chat_id) -> None` (gửi/sửa message preview, msg id lưu kv `pending_msg`)
  - Callback data: `pc_save`, `pc_cancel`, `pc_edit:pinyin`, `pc_edit:meaning`, `pc_edit:example`, `pc_deck`, `pc_deck_set:<id>`

- [ ] **Step 1: Viết `app/bot/textrouter.py`**

```python
import re

from app import db
from app.bot import create_flow

_HAN = re.compile(r"[一-鿿]")
TEXT_ACTIONS = {}


def register(action, fn):
    TEXT_ACTIONS[action] = fn


async def on_text(update, context):
    conn = context.bot_data["conn"]
    text = update.message.text.strip()
    pending = db.kv_get(conn, "pending_input")
    if pending:
        fn = TEXT_ACTIONS.get(pending.get("action"))
        if fn:
            db.kv_del(conn, "pending_input")
            await fn(update, context, pending, text)
            return
    if _HAN.search(text):
        await create_flow.start_pending(update, context, text)
    else:
        await update.message.reply_text(
            "Gõ chữ Hán để tạo thẻ (VD: 学习), hoặc /start để xem lệnh.")


async def on_photo(update, context):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if not pc:
        return
    pc["image_file_id"] = update.message.photo[-1].file_id
    db.kv_set(conn, "pending_card", pc)
    await update.message.reply_text("🖼 Đã đính kèm ảnh vào thẻ đang tạo.")
    await create_flow.render_preview(context, update.effective_chat.id)
```

- [ ] **Step 2: Viết `app/bot/create_flow.py`**

```python
from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup
from telegram.error import BadRequest

from app import cards, db, lookup
from app.bot.auth import owner_only_callback

FIELD_LABEL = {"pinyin": "pinyin", "meaning": "nghĩa tiếng Anh", "example": "câu ví dụ"}


async def start_pending(update, context, hanzi):
    conn = context.bot_data["conn"]
    pc = {
        "hanzi": hanzi,
        "pinyin": lookup.gen_pinyin(hanzi),
        "meaning": lookup.lookup_meaning(conn, hanzi),
        "example": "", "image_file_id": "", "deck_id": 1,
    }
    db.kv_set(conn, "pending_card", pc)
    db.kv_del(conn, "pending_msg")
    await render_preview(context, update.effective_chat.id)


def _preview(conn, pc):
    deck = conn.execute("SELECT name FROM decks WHERE id=?", (pc["deck_id"],)).fetchone()
    lines = [f"🀄 <b>{pc['hanzi']}</b>", f"📖 {pc['pinyin']}",
             f"🇬🇧 {pc['meaning'] or '<i>(chưa có nghĩa — bấm Sửa nghĩa)</i>'}"]
    if pc["example"]:
        lines.append(f"💬 {pc['example']}")
    if pc["image_file_id"]:
        lines.append("🖼 Có ảnh đính kèm")
    if cards.exists_hanzi(conn, pc["hanzi"]):
        lines.append("⚠️ <b>Đã có thẻ trùng chữ Hán này</b>")
    lines.append(f"📦 Bộ: {deck['name'] if deck else '?'}")
    lines.append("\nXem lại rồi bấm Lưu nhé:")
    kb = Markup([
        [Btn("💾 Lưu", callback_data="pc_save"), Btn("❌ Hủy", callback_data="pc_cancel")],
        [Btn("✏️ Pinyin", callback_data="pc_edit:pinyin"),
         Btn("✏️ Nghĩa", callback_data="pc_edit:meaning")],
        [Btn("💬 Ví dụ", callback_data="pc_edit:example"),
         Btn("📦 Đổi bộ", callback_data="pc_deck")],
    ])
    return "\n".join(lines), kb


async def render_preview(context, chat_id):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if not pc:
        return
    text, kb = _preview(conn, pc)
    msg_id = db.kv_get(conn, "pending_msg")
    if msg_id:
        try:
            await context.bot.edit_message_text(
                text, chat_id=chat_id, message_id=msg_id,
                reply_markup=kb, parse_mode="HTML")
            return
        except BadRequest:
            pass
    m = await context.bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
    db.kv_set(conn, "pending_msg", m.message_id)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    await q.answer()
    if not pc:
        await q.edit_message_text("Phiên tạo thẻ đã kết thúc.")
        return
    data = q.data
    if data == "pc_cancel":
        db.kv_del(conn, "pending_card")
        db.kv_del(conn, "pending_msg")
        await q.edit_message_text("❌ Đã hủy tạo thẻ.")
    elif data == "pc_save":
        row = await cards.create_card(
            conn, pc["hanzi"], deck_id=pc["deck_id"],
            pinyin_override=pc["pinyin"], meaning_override=pc["meaning"],
            example=pc["example"], image_file_id=pc["image_file_id"])
        db.kv_del(conn, "pending_card")
        db.kv_del(conn, "pending_msg")
        note = "" if row["audio_path"] else "\n⚠️ Chưa tạo được audio, sẽ thử lại khi ôn."
        await q.edit_message_text(
            f"✅ Đã lưu thẻ <b>{row['hanzi']}</b> ({row['pinyin']}){note}",
            parse_mode="HTML")
    elif data.startswith("pc_edit:"):
        field = data.split(":", 1)[1]
        db.kv_set(conn, "pending_input", {"action": "pc_field", "field": field})
        await context.bot.send_message(
            q.message.chat_id, f"Nhập {FIELD_LABEL[field]} mới:")
    elif data == "pc_deck":
        decks = conn.execute("SELECT id, name FROM decks ORDER BY id").fetchall()
        kb = Markup([[Btn(d["name"], callback_data=f"pc_deck_set:{d['id']}")] for d in decks])
        await context.bot.send_message(q.message.chat_id, "Chọn bộ thẻ:", reply_markup=kb)
    elif data.startswith("pc_deck_set:"):
        pc["deck_id"] = int(data.split(":")[1])
        db.kv_set(conn, "pending_card", pc)
        await q.message.delete()
        await render_preview(context, q.message.chat_id)


async def field_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if not pc:
        return
    pc[pending["field"]] = text
    db.kv_set(conn, "pending_card", pc)
    await render_preview(context, update.effective_chat.id)
```

- [ ] **Step 3: Nối vào `main.py` và `textrouter`**

Trong `app/bot/main.py` thêm import và handler (trong `build_app`, sau handler /start):
```python
from telegram.ext import CallbackQueryHandler, MessageHandler, filters
from app.bot import create_flow, textrouter
from app.bot.textrouter import register

register("pc_field", create_flow.field_input)
app.add_handler(CallbackQueryHandler(create_flow.on_callback, pattern=r"^pc_"))
app.add_handler(MessageHandler(owner_filter & filters.TEXT & ~filters.COMMAND, textrouter.on_text))
app.add_handler(MessageHandler(owner_filter & filters.PHOTO, textrouter.on_photo))
```
(`register(...)` đặt ở mức module của `main.py`, ngay sau các import.)

- [ ] **Step 4: Test thủ công**

Chạy bot local. Kịch bản: (1) gõ `学习` → preview có pinyin `xué xí` + nghĩa Anh; (2) bấm ✏️ Nghĩa → gõ nghĩa mới → preview cập nhật; (3) gửi 1 ảnh → preview hiện "Có ảnh"; (4) 💾 Lưu → "✅ Đã lưu"; (5) gõ lại `学习` → preview cảnh báo trùng; (6) ❌ Hủy hoạt động; (7) gõ `hello` không CJK → nhận gợi ý.

- [ ] **Step 5: Commit** — `git commit -am "feat: card creation flow with auto-lookup preview"`

---

### Task 10: Luồng ôn tập (`app/bot/review_flow.py`)

**Files:** Create `app/bot/review_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `cards.build_queue/get_card/apply_rating/retry_audio`, `stats.streak`, `db.kv_*`, `config.today/today_iso`
- Produces:
  - kv `session`: `{"queue": [ids], "pos": int, "done": int, "chat": int, "msg": int|None, "aux": [msg_ids]}`
  - `review_flow.cmd_review(update, context)` (lệnh /on); `review_flow.start_session(context, chat_id)` — task Reminders sẽ gọi lại hàm này qua callback `rv_start`
  - `review_flow.send_card_audio(context, chat_id, row) -> Message|None` — gửi voice từ `audio_file_id` (cache) hoặc từ file rồi lưu file_id; nếu chưa có audio thì thử `retry_audio` một lần; hết cách trả None. Task voice_flow dùng lại hàm này.
  - Callback data: `rv_start`, `rv_listen:<cid>`, `rv_show:<cid>`, `rv_rate:<cid>:<rating>`

- [ ] **Step 1: Viết `app/bot/review_flow.py`**

```python
from pathlib import Path

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup
from telegram.error import BadRequest, TelegramError

from app import cards, config, db, stats
from app.bot.auth import owner_only_callback

RATE = [("🔁 Lại", 1), ("😓 Khó", 2), ("🙂 Tốt", 3), ("😎 Dễ", 4)]


def _front_kb(cid):
    return Markup([[Btn("🔊 Nghe", callback_data=f"rv_listen:{cid}"),
                    Btn("👀 Xem đáp án", callback_data=f"rv_show:{cid}")]])


def _answer_kb(cid):
    return Markup([
        [Btn("🎤 Thu âm thử", callback_data=f"vc_rec:{cid}")],
        [Btn(label, callback_data=f"rv_rate:{cid}:{r}") for label, r in RATE],
    ])


async def cmd_review(update, context):
    await start_session(context, update.effective_chat.id)


async def start_session(context, chat_id):
    conn = context.bot_data["conn"]
    queue = cards.build_queue(conn, config.today_iso())
    if not queue:
        await context.bot.send_message(chat_id, "🎉 Không có thẻ nào đến hạn. Nghỉ ngơi đi!")
        return
    db.kv_set(conn, "session", {"queue": queue, "pos": 0, "done": 0,
                                "chat": chat_id, "msg": None, "aux": []})
    await _show_front(context)


async def _edit_or_send(context, s, text, kb):
    conn = context.bot_data["conn"]
    if s["msg"]:
        try:
            await context.bot.edit_message_text(
                text, chat_id=s["chat"], message_id=s["msg"],
                reply_markup=kb, parse_mode="HTML")
            return
        except BadRequest:
            pass
    m = await context.bot.send_message(s["chat"], text, reply_markup=kb, parse_mode="HTML")
    s["msg"] = m.message_id
    db.kv_set(conn, "session", s)


async def _show_front(context):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    cid = s["queue"][s["pos"]]
    row = cards.get_card(conn, cid)
    if row is None:  # thẻ đã bị xóa giữa chừng
        await _advance(context)
        return
    text = f"🀄 <b>{row['hanzi']}</b>\n\n({s['pos'] + 1}/{len(s['queue'])})"
    await _edit_or_send(context, s, text, _front_kb(cid))


async def _clear_aux(context, s):
    for mid in s["aux"]:
        try:
            await context.bot.delete_message(s["chat"], mid)
        except TelegramError:
            pass
    s["aux"] = []


async def send_card_audio(context, chat_id, row):
    conn = context.bot_data["conn"]
    if row["audio_file_id"]:
        return await context.bot.send_voice(chat_id, row["audio_file_id"])
    path = row["audio_path"]
    if not path:
        if not await cards.retry_audio(conn, row["id"]):
            return None
        row = cards.get_card(conn, row["id"])
        path = row["audio_path"]
    if not Path(path).exists():
        return None
    with open(path, "rb") as f:
        m = await context.bot.send_voice(chat_id, f)
    conn.execute("UPDATE cards SET audio_file_id=? WHERE id=?",
                 (m.voice.file_id, row["id"]))
    conn.commit()
    return m


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    if q.data == "rv_start":
        await start_session(context, q.message.chat_id)
        return
    s = db.kv_get(conn, "session")
    if not s:
        await q.edit_message_text("Phiên ôn đã kết thúc. Gõ /on để ôn tiếp.")
        return
    parts = q.data.split(":")
    action, cid = parts[0], int(parts[1])

    if action == "rv_listen":
        row = cards.get_card(conn, cid)
        m = await send_card_audio(context, s["chat"], row)
        if m is None:
            await context.bot.send_message(s["chat"], "⚠️ Thẻ này chưa có audio.")
        else:
            s["aux"].append(m.message_id)
            db.kv_set(conn, "session", s)

    elif action == "rv_show":
        row = cards.get_card(conn, cid)
        lines = [f"🀄 <b>{row['hanzi']}</b>", f"📖 {row['pinyin']}",
                 f"🇬🇧 {row['meaning'] or '<i>(chưa có nghĩa)</i>'}"]
        if row["example"]:
            lines.append(f"💬 {row['example']}")
        lines.append(f"\n({s['pos'] + 1}/{len(s['queue'])})")
        await _edit_or_send(context, s, "\n".join(lines), _answer_kb(cid))
        if row["image_file_id"]:
            m = await context.bot.send_photo(s["chat"], row["image_file_id"])
            s["aux"].append(m.message_id)
        m = await send_card_audio(context, s["chat"], row)
        if m:
            s["aux"].append(m.message_id)
        db.kv_set(conn, "session", s)

    elif action == "rv_rate":
        rating = int(parts[2])
        cards.apply_rating(conn, cid, rating, config.today())
        if rating == 1:
            s["queue"].append(cid)  # Lại -> lặp lại cuối phiên
        s["done"] += 1
        await _clear_aux(context, s)
        db.kv_set(conn, "session", s)
        await _advance(context)


async def _advance(context):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    s["pos"] += 1
    if s["pos"] >= len(s["queue"]):
        n = stats.streak(conn, config.today())
        await _edit_or_send(
            context, s,
            f"🎉 <b>Hoàn thành!</b> Đã ôn {s['done']} lượt.\n🔥 Chuỗi: {n} ngày liên tiếp.",
            None)
        db.kv_del(conn, "session")
        return
    db.kv_set(conn, "session", s)
    await _show_front(context)
```

- [ ] **Step 2: Nối vào `main.py`**

```python
from app.bot import review_flow
app.add_handler(CommandHandler("on", review_flow.cmd_review, filters=owner_filter))
app.add_handler(CallbackQueryHandler(review_flow.on_callback, pattern=r"^rv_"))
```

- [ ] **Step 3: Test thủ công**

Kịch bản: tạo 3 thẻ mới → `/on` → (1) mặt trước chỉ có chữ Hán + đếm (1/3); (2) 🔊 gửi voice; (3) 👀 sửa tin nhắn thành đáp án + tự gửi audio (+ảnh nếu có); (4) bấm 🙂 Tốt → aux bị xóa, chuyển thẻ sau trong CÙNG tin nhắn; (5) bấm 🔁 Lại ở 1 thẻ → thẻ đó quay lại cuối phiên; (6) hết queue → "🎉 Hoàn thành" + streak; (7) `/on` lại → "Không có thẻ nào đến hạn"; (8) giết bot giữa phiên, chạy lại, bấm nút cũ → vẫn hoạt động (session trong SQLite).

- [ ] **Step 4: Commit** — `git commit -am "feat: in-chat review session with SM-2 rating buttons"`

---

### Task 11: Thu âm & tự so giọng (`app/bot/voice_flow.py`)

**Files:** Create `app/bot/voice_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `review_flow.send_card_audio`, `db.kv_*`, `cards.get_card`
- Produces: kv `awaiting_voice` = card id; callback `vc_rec:<cid>` (đã được `_answer_kb` trong Task 10 phát ra); `voice_flow.on_voice(update, context)` cho MessageHandler VOICE. **Khe cắm Azure (spec §10):** sau khi lưu voice, nếu setting `azure_speech_key` không rỗng thì (tương lai) gọi chấm điểm — bản này chỉ để comment đánh dấu chỗ cắm.

- [ ] **Step 1: Viết `app/bot/voice_flow.py`**

```python
from app import cards, db
from app.bot import review_flow
from app.bot.auth import owner_only_callback


@owner_only_callback
async def on_rec_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    cid = int(q.data.split(":")[1])
    db.kv_set(conn, "awaiting_voice", cid)
    await q.answer("Gửi tin nhắn thoại 🎙 ngay bây giờ")
    m = await context.bot.send_message(
        q.message.chat_id, "🎙 Nhấn giữ nút mic của Telegram, đọc từ này rồi gửi nhé.")
    s = db.kv_get(conn, "session")
    if s:
        s["aux"].append(m.message_id)
        db.kv_set(conn, "session", s)


async def on_voice(update, context):
    conn = context.bot_data["conn"]
    cid = db.kv_get(conn, "awaiting_voice")
    if cid is None:
        return
    db.kv_del(conn, "awaiting_voice")
    row = cards.get_card(conn, cid)
    if row is None:
        return
    file_id = update.message.voice.file_id
    conn.execute("UPDATE cards SET voice_file_id=? WHERE id=?", (file_id, cid))
    conn.commit()
    chat_id = update.effective_chat.id
    aux = [update.message.message_id]
    m1 = await review_flow.send_card_audio(context, chat_id, row)
    if m1:
        aux.append(m1.message_id)
    m2 = await context.bot.send_voice(chat_id, file_id)
    m3 = await context.bot.send_message(chat_id, "👂 Giọng chuẩn ở trên, giọng bạn ở dưới — nghe lại và tự so nhé.")
    aux += [m2.message_id, m3.message_id]
    # AZURE-SLOT: nếu db.get_setting(conn, "azure_speech_key") != "" thì gọi
    # Pronunciation Assessment ở đây và gửi kèm điểm số (spec §10, ngoài phạm vi bản đầu).
    s = db.kv_get(conn, "session")
    if s:
        s["aux"] += aux
        db.kv_set(conn, "session", s)
```

- [ ] **Step 2: Nối vào `main.py`**

```python
from app.bot import voice_flow
app.add_handler(CallbackQueryHandler(voice_flow.on_rec_callback, pattern=r"^vc_rec:"))
app.add_handler(MessageHandler(owner_filter & filters.VOICE, voice_flow.on_voice))
```

- [ ] **Step 3: Test thủ công** — trong phiên ôn, mở đáp án → 🎤 → gửi voice → nhận cặp audio chuẩn/của mình + lời nhắc; chấm điểm thẻ → mọi tin phụ (kể cả voice mình gửi) bị dọn. Gửi voice khi KHÔNG bấm 🎤 → bot im lặng.

- [ ] **Step 4: Commit** — `git commit -am "feat: voice self-comparison with Azure slot marker"`

---

### Task 12: Nhắc theo lịch (`app/bot/reminders.py`)

**Files:** Create `app/bot/reminders.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `cards.build_queue/get_card/is_new`, `stats.reviews_today/streak`, `db.get_setting`, `config.OWNER_ID/TZ`
- Produces: `reminders.schedule_jobs(app)` — xóa mọi job tên bắt đầu `rem:` rồi đăng ký lại từ settings (settings_flow Task 15 gọi lại hàm này sau khi đổi giờ). Nút "▶️ Ôn ngay" dùng callback `rv_start` (đã có ở Task 10).

- [ ] **Step 1: Viết `app/bot/reminders.py`**

```python
import logging
from datetime import time as dtime

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import cards, config, db, stats

START_KB = Markup([[Btn("▶️ Ôn ngay", callback_data="rv_start")]])


def _parse_hhmm(s):
    h, m = s.strip().split(":")
    return dtime(int(h), int(m), tzinfo=config.TZ)


def schedule_jobs(app):
    conn = app.bot_data["conn"]
    for job in app.job_queue.jobs():
        if job.name and job.name.startswith("rem:"):
            job.schedule_removal()
    for t in db.get_setting(conn, "reminder_times").split(","):
        t = t.strip()
        if t:
            app.job_queue.run_daily(reminder_job, _parse_hhmm(t), name=f"rem:{t}")
    ev = db.get_setting(conn, "evening_nudge").strip()
    if ev and ev.lower() != "off":
        app.job_queue.run_daily(evening_job, _parse_hhmm(ev), name="rem:evening")
    logging.info("Đã đặt lịch nhắc: %s / nudge: %s",
                 db.get_setting(conn, "reminder_times"), ev)


async def reminder_job(context):
    conn = context.application.bot_data["conn"]
    queue = cards.build_queue(conn, config.today_iso())
    if not queue:
        return  # đã ôn hết / không có gì -> im lặng (spec §6)
    n_new = sum(1 for cid in queue
                if (r := cards.get_card(conn, cid)) and cards.is_new(r))
    await context.bot.send_message(
        config.OWNER_ID,
        f"📚 Bạn có <b>{len(queue)}</b> thẻ đến hạn ({n_new} thẻ mới).",
        reply_markup=START_KB, parse_mode="HTML")


async def evening_job(context):
    conn = context.application.bot_data["conn"]
    if stats.reviews_today(conn, config.today_iso()) > 0:
        return
    queue = cards.build_queue(conn, config.today_iso())
    if not queue:
        return
    n = stats.streak(conn, config.today())
    flame = f"🔥 Chuỗi {n} ngày của bạn sắp mất! " if n > 0 else ""
    await context.bot.send_message(
        config.OWNER_ID,
        f"🌙 {flame}Hôm nay bạn chưa ôn — còn {len(queue)} thẻ chờ.",
        reply_markup=START_KB)
```

- [ ] **Step 2: Nối vào `main.py`** — cuối `post_init` thêm:

```python
from app.bot import reminders
reminders.schedule_jobs(app)
```

- [ ] **Step 3: Test thủ công** — đặt tạm `reminder_times` = 2 phút tới (`sqlite3 data/reminder.db "UPDATE settings SET value='HH:MM' WHERE key='reminder_times'"`), chạy bot, chờ: có thẻ đến hạn → nhận tin nhắn + nút ▶️ hoạt động; ôn hết rồi chờ mốc kế → bot im. Trả lại giá trị cũ sau khi test.

- [ ] **Step 4: Commit** — `git commit -am "feat: scheduled reminders with streak nudge"`

---

### Task 13: Quản lý bộ thẻ (`app/bot/decks_flow.py`)

**Files:** Create `app/bot/decks_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `db.kv_*`, textrouter `register`
- Produces: lệnh `/bo`; callbacks `dk_view:<id>`, `dk_new`, `dk_rename:<id>`, `dk_del:<id>`, `dk_del_ok:<id>`, `dk_back`; text actions `deck_new`, `deck_rename` (`{"deck_id": id}`). Bộ id=1 ("Mặc định") không xóa/đổi tên được. Xóa bộ = xóa cả thẻ trong bộ (FK CASCADE) — confirm bắt buộc nêu số thẻ.

- [ ] **Step 1: Viết `app/bot/decks_flow.py`**

```python
from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import db
from app.bot.auth import owner_only_callback


def _list_view(conn):
    rows = conn.execute(
        "SELECT d.id, d.name, COUNT(c.id) n FROM decks d "
        "LEFT JOIN cards c ON c.deck_id=d.id GROUP BY d.id ORDER BY d.id").fetchall()
    kb = [[Btn(f"📦 {r['name']} ({r['n']} thẻ)", callback_data=f"dk_view:{r['id']}")]
          for r in rows]
    kb.append([Btn("➕ Tạo bộ mới", callback_data="dk_new")])
    return "📦 <b>Các bộ thẻ:</b>", Markup(kb)


async def cmd_decks(update, context):
    text, kb = _list_view(context.bot_data["conn"])
    await update.message.reply_html(text, reply_markup=kb)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    data = q.data
    if data == "dk_back":
        text, kb = _list_view(conn)
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    elif data == "dk_new":
        db.kv_set(conn, "pending_input", {"action": "deck_new"})
        await context.bot.send_message(q.message.chat_id, "Nhập tên bộ thẻ mới:")
    elif data.startswith("dk_view:"):
        did = int(data.split(":")[1])
        row = conn.execute(
            "SELECT d.name, COUNT(c.id) n FROM decks d LEFT JOIN cards c ON c.deck_id=d.id "
            "WHERE d.id=? GROUP BY d.id", (did,)).fetchone()
        if not row:
            return
        kb = [[Btn("⬅️ Quay lại", callback_data="dk_back")]]
        if did != 1:
            kb.insert(0, [Btn("✏️ Đổi tên", callback_data=f"dk_rename:{did}"),
                          Btn("🗑 Xóa bộ", callback_data=f"dk_del:{did}")])
        await q.edit_message_text(
            f"📦 <b>{row['name']}</b> — {row['n']} thẻ",
            reply_markup=Markup(kb), parse_mode="HTML")
    elif data.startswith("dk_rename:"):
        did = int(data.split(":")[1])
        db.kv_set(conn, "pending_input", {"action": "deck_rename", "deck_id": did})
        await context.bot.send_message(q.message.chat_id, "Nhập tên mới cho bộ:")
    elif data.startswith("dk_del_ok:"):
        did = int(data.split(":")[1])
        if did != 1:
            conn.execute("DELETE FROM decks WHERE id=?", (did,))
            conn.commit()
        text, kb = _list_view(conn)
        await q.edit_message_text("🗑 Đã xóa bộ.\n\n" + text, reply_markup=kb, parse_mode="HTML")
    elif data.startswith("dk_del:"):
        did = int(data.split(":")[1])
        n = conn.execute("SELECT COUNT(*) c FROM cards WHERE deck_id=?", (did,)).fetchone()["c"]
        await q.edit_message_text(
            f"⚠️ Xóa bộ sẽ xóa VĨNH VIỄN {n} thẻ bên trong. Chắc chắn?",
            reply_markup=Markup([[Btn("🗑 Xóa luôn", callback_data=f"dk_del_ok:{did}"),
                                  Btn("⬅️ Thôi", callback_data=f"dk_view:{did}")]]))


async def deck_new_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    try:
        conn.execute("INSERT INTO decks(name) VALUES(?)", (text,))
        conn.commit()
        await update.message.reply_text(f"✅ Đã tạo bộ “{text}”. Xem /bo")
    except Exception:
        await update.message.reply_text("⚠️ Tên bộ đã tồn tại.")


async def deck_rename_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    conn.execute("UPDATE decks SET name=? WHERE id=? AND id<>1", (text, pending["deck_id"]))
    conn.commit()
    await update.message.reply_text(f"✅ Đã đổi tên bộ thành “{text}”.")
```

- [ ] **Step 2: Nối vào `main.py`**

```python
from app.bot import decks_flow
register("deck_new", decks_flow.deck_new_input)
register("deck_rename", decks_flow.deck_rename_input)
app.add_handler(CommandHandler("bo", decks_flow.cmd_decks, filters=owner_filter))
app.add_handler(CallbackQueryHandler(decks_flow.on_callback, pattern=r"^dk_"))
```

- [ ] **Step 3: Test thủ công** — `/bo` → tạo bộ "HSK 1" → vào bộ → đổi tên → xóa (confirm nêu đúng số thẻ; thẻ trong bộ biến mất; bộ "Mặc định" không có nút xóa).

- [ ] **Step 4: Commit** — `git commit -am "feat: deck management (/bo)"`

---

### Task 14: Tìm & sửa thẻ (`app/bot/manage_flow.py`)

**Files:** Create `app/bot/manage_flow.py`; Modify `app/bot/main.py`, `app/bot/textrouter.py` (on_photo)

**Interfaces:**
- Consumes: `cards.get_card`, `review_flow.send_card_audio`, `db.kv_*`
- Produces: lệnh `/tim <query>`; callbacks `cd_view:<id>`, `cd_listen:<id>`, `cd_myvoice:<id>`, `cd_edit:<id>:<field>` (field ∈ pinyin|meaning|example), `cd_img:<id>`, `cd_move:<id>`, `cd_move_set:<id>:<deck>`, `cd_del:<id>`, `cd_del_ok:<id>`; text action `card_edit` (`{"cid", "field"}`); kv `awaiting_image` = cid (on_photo của textrouter ưu tiên `pending_card` trước, rồi tới `awaiting_image`).

- [ ] **Step 1: Viết `app/bot/manage_flow.py`**

```python
from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import cards, db
from app.bot import review_flow
from app.bot.auth import owner_only_callback

FIELDS = {"pinyin": "pinyin", "meaning": "nghĩa", "example": "ví dụ"}


async def cmd_search(update, context):
    conn = context.bot_data["conn"]
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Dùng: /tim <chữ Hán, pinyin hoặc nghĩa>")
        return
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT id, hanzi, pinyin FROM cards "
        "WHERE hanzi LIKE ? OR pinyin LIKE ? OR meaning LIKE ? LIMIT 8",
        (like, like, like)).fetchall()
    if not rows:
        await update.message.reply_text("Không tìm thấy thẻ nào.")
        return
    kb = Markup([[Btn(f"{r['hanzi']} — {r['pinyin']}", callback_data=f"cd_view:{r['id']}")]
                 for r in rows])
    await update.message.reply_text(f"🔎 Kết quả cho “{query}”:", reply_markup=kb)


def _detail(conn, row):
    deck = conn.execute("SELECT name FROM decks WHERE id=?", (row["deck_id"],)).fetchone()
    lines = [f"🀄 <b>{row['hanzi']}</b>", f"📖 {row['pinyin']}",
             f"🇬🇧 {row['meaning'] or '<i>(trống)</i>'}"]
    if row["example"]:
        lines.append(f"💬 {row['example']}")
    lines += [f"📦 {deck['name'] if deck else '?'}",
              f"📅 Đến hạn: {row['due_date']} · interval {row['interval']:.0f}d "
              f"· ease {row['ease']:.2f} · ôn {row['repetitions']} · quên {row['lapses']}"]
    cid = row["id"]
    kb = [[Btn("🔊 Nghe", callback_data=f"cd_listen:{cid}"),
           Btn("🎙 Bản thu của tôi", callback_data=f"cd_myvoice:{cid}")],
          [Btn("✏️ Pinyin", callback_data=f"cd_edit:{cid}:pinyin"),
           Btn("✏️ Nghĩa", callback_data=f"cd_edit:{cid}:meaning"),
           Btn("✏️ Ví dụ", callback_data=f"cd_edit:{cid}:example")],
          [Btn("🖼 Đổi ảnh", callback_data=f"cd_img:{cid}"),
           Btn("📦 Chuyển bộ", callback_data=f"cd_move:{cid}")],
          [Btn("🗑 Xóa thẻ", callback_data=f"cd_del:{cid}")]]
    return "\n".join(lines), Markup(kb)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    parts = q.data.split(":")
    action, cid = parts[0], int(parts[1])
    row = cards.get_card(conn, cid)
    if action != "cd_del_ok" and row is None:
        await q.edit_message_text("Thẻ này đã bị xóa.")
        return

    if action == "cd_view":
        text, kb = _detail(conn, row)
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        if row["image_file_id"]:
            await context.bot.send_photo(q.message.chat_id, row["image_file_id"])
    elif action == "cd_listen":
        m = await review_flow.send_card_audio(context, q.message.chat_id, row)
        if m is None:
            await context.bot.send_message(q.message.chat_id, "⚠️ Thẻ chưa có audio.")
    elif action == "cd_myvoice":
        if row["voice_file_id"]:
            await context.bot.send_voice(q.message.chat_id, row["voice_file_id"])
        else:
            await context.bot.send_message(q.message.chat_id, "Chưa có bản thu nào cho thẻ này.")
    elif action == "cd_edit":
        field = parts[2]
        db.kv_set(conn, "pending_input",
                  {"action": "card_edit", "cid": cid, "field": field})
        await context.bot.send_message(q.message.chat_id, f"Nhập {FIELDS[field]} mới:")
    elif action == "cd_img":
        db.kv_set(conn, "awaiting_image", cid)
        await context.bot.send_message(q.message.chat_id, "Gửi ảnh mới cho thẻ này:")
    elif action == "cd_move":
        decks = conn.execute("SELECT id, name FROM decks ORDER BY id").fetchall()
        kb = Markup([[Btn(d["name"], callback_data=f"cd_move_set:{cid}:{d['id']}")]
                     for d in decks])
        await q.edit_message_text("Chuyển thẻ sang bộ:", reply_markup=kb)
    elif action == "cd_move_set":
        conn.execute("UPDATE cards SET deck_id=? WHERE id=?", (int(parts[2]), cid))
        conn.commit()
        text, kb = _detail(conn, cards.get_card(conn, cid))
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    elif action == "cd_del":
        await q.edit_message_text(
            f"⚠️ Xóa vĩnh viễn thẻ <b>{row['hanzi']}</b>?", parse_mode="HTML",
            reply_markup=Markup([[Btn("🗑 Xóa", callback_data=f"cd_del_ok:{cid}"),
                                  Btn("⬅️ Thôi", callback_data=f"cd_view:{cid}")]]))
    elif action == "cd_del_ok":
        conn.execute("DELETE FROM cards WHERE id=?", (cid,))
        conn.commit()
        await q.edit_message_text("🗑 Đã xóa thẻ.")


async def card_edit_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    field = pending["field"]  # đã whitelist ở callback
    conn.execute(f"UPDATE cards SET {field}=? WHERE id=?", (text, pending["cid"]))
    conn.commit()
    await update.message.reply_text("✅ Đã cập nhật. Xem lại: /tim " + text[:20])
```

- [ ] **Step 2: Thêm nhánh `awaiting_image` vào `textrouter.on_photo`** — thay hàm bằng:

```python
async def on_photo(update, context):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if pc:
        pc["image_file_id"] = update.message.photo[-1].file_id
        db.kv_set(conn, "pending_card", pc)
        await update.message.reply_text("🖼 Đã đính kèm ảnh vào thẻ đang tạo.")
        await create_flow.render_preview(context, update.effective_chat.id)
        return
    cid = db.kv_get(conn, "awaiting_image")
    if cid is not None:
        db.kv_del(conn, "awaiting_image")
        conn.execute("UPDATE cards SET image_file_id=? WHERE id=?",
                     (update.message.photo[-1].file_id, cid))
        conn.commit()
        await update.message.reply_text("🖼 Đã cập nhật ảnh cho thẻ.")
```

- [ ] **Step 3: Nối vào `main.py`**

```python
from app.bot import manage_flow
register("card_edit", manage_flow.card_edit_input)
app.add_handler(CommandHandler("tim", manage_flow.cmd_search, filters=owner_filter))
app.add_handler(CallbackQueryHandler(manage_flow.on_callback, pattern=r"^cd_"))
```

- [ ] **Step 4: Test thủ công** — `/tim 学` ra kết quả → xem chi tiết (đủ SRS info) → sửa nghĩa → đổi ảnh → chuyển bộ → nghe audio + bản thu → xóa có confirm.

- [ ] **Step 5: Commit** — `git commit -am "feat: card search/edit/delete (/tim)"`

---

### Task 15: Settings (`app/bot/settings_flow.py`)

**Files:** Create `app/bot/settings_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `db.get_setting/set_setting`, `reminders.schedule_jobs`
- Produces: lệnh `/settings`; callbacks `st_times`, `st_nudge`, `st_newlimit`, `st_voice`, `st_voice_set:<voice>`; text actions `set_times`, `set_nudge`, `set_newlimit`. Validate: times = danh sách `HH:MM` phân cách phẩy; nudge = `HH:MM` hoặc `off`; newlimit = số nguyên 0–200. Sau khi đổi times/nudge phải gọi `reminders.schedule_jobs(context.application)`.

- [ ] **Step 1: Viết `app/bot/settings_flow.py`**

```python
import re

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import db
from app.bot import reminders
from app.bot.auth import owner_only_callback

VOICES = ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural",
          "zh-CN-XiaoyiNeural", "zh-CN-YunjianNeural"]
_TIME = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def _view(conn):
    text = ("⚙️ <b>Cài đặt</b>\n"
            f"⏰ Giờ nhắc: {db.get_setting(conn, 'reminder_times')}\n"
            f"🌙 Nhắc cuối ngày: {db.get_setting(conn, 'evening_nudge')}\n"
            f"🆕 Thẻ mới/ngày: {db.get_setting(conn, 'new_per_day')}\n"
            f"🗣 Giọng đọc: {db.get_setting(conn, 'tts_voice')}")
    kb = Markup([[Btn("⏰ Giờ nhắc", callback_data="st_times"),
                  Btn("🌙 Cuối ngày", callback_data="st_nudge")],
                 [Btn("🆕 Thẻ mới/ngày", callback_data="st_newlimit"),
                  Btn("🗣 Giọng đọc", callback_data="st_voice")]])
    return text, kb


async def cmd_settings(update, context):
    text, kb = _view(context.bot_data["conn"])
    await update.message.reply_html(text, reply_markup=kb)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    if q.data == "st_times":
        db.kv_set(conn, "pending_input", {"action": "set_times"})
        await context.bot.send_message(
            q.message.chat_id, "Nhập các giờ nhắc, phân cách bằng phẩy (VD: 07:30,12:30,20:00):")
    elif q.data == "st_nudge":
        db.kv_set(conn, "pending_input", {"action": "set_nudge"})
        await context.bot.send_message(
            q.message.chat_id, "Nhập giờ nhắc cuối ngày (VD: 21:30) hoặc gõ off để tắt:")
    elif q.data == "st_newlimit":
        db.kv_set(conn, "pending_input", {"action": "set_newlimit"})
        await context.bot.send_message(q.message.chat_id, "Nhập số thẻ mới tối đa mỗi ngày (0–200):")
    elif q.data == "st_voice":
        kb = Markup([[Btn(v, callback_data=f"st_voice_set:{v}")] for v in VOICES])
        await q.edit_message_text("Chọn giọng đọc:", reply_markup=kb)
    elif q.data.startswith("st_voice_set:"):
        db.set_setting(conn, "tts_voice", q.data.split(":", 1)[1])
        text, kb = _view(conn)
        await q.edit_message_text("✅ Đã đổi giọng (áp dụng cho thẻ tạo mới).\n\n" + text,
                                  reply_markup=kb, parse_mode="HTML")


async def times_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts or not all(_TIME.match(p) for p in parts):
        await update.message.reply_text("⚠️ Sai định dạng. VD hợp lệ: 07:30,12:30,20:00")
        return
    db.set_setting(conn, "reminder_times", ",".join(parts))
    reminders.schedule_jobs(context.application)
    await update.message.reply_text(f"✅ Giờ nhắc mới: {', '.join(parts)}")


async def nudge_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    v = text.strip().lower()
    if v != "off" and not _TIME.match(v):
        await update.message.reply_text("⚠️ Nhập HH:MM hoặc off.")
        return
    db.set_setting(conn, "evening_nudge", v)
    reminders.schedule_jobs(context.application)
    await update.message.reply_text("✅ Đã cập nhật nhắc cuối ngày.")


async def newlimit_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    if not text.strip().isdigit() or not 0 <= int(text.strip()) <= 200:
        await update.message.reply_text("⚠️ Nhập số nguyên 0–200.")
        return
    db.set_setting(conn, "new_per_day", text.strip())
    await update.message.reply_text(f"✅ Giới hạn thẻ mới/ngày: {text.strip()}")
```

- [ ] **Step 2: Nối vào `main.py`**

```python
from app.bot import settings_flow
register("set_times", settings_flow.times_input)
register("set_nudge", settings_flow.nudge_input)
register("set_newlimit", settings_flow.newlimit_input)
app.add_handler(CommandHandler("settings", settings_flow.cmd_settings, filters=owner_filter))
app.add_handler(CallbackQueryHandler(settings_flow.on_callback, pattern=r"^st_"))
```

- [ ] **Step 3: Test thủ công** — `/settings` hiện giá trị; đổi giờ nhắc sai định dạng bị từ chối; đổi đúng → log "Đã đặt lịch nhắc" chạy lại; đổi giọng → tạo thẻ mới nghe khác giọng.

- [ ] **Step 4: Commit** — `git commit -am "feat: /settings with live reschedule"`

---

### Task 16: CSV upload (`app/bot/csv_flow.py`)

**Files:** Create `app/bot/csv_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `csv_import.parse_csv`, `cards.create_card/exists_hanzi`, `db.kv_*`
- Produces: lệnh `/csv` (hướng dẫn); document handler nhận file `.csv` → hỏi bộ đích (callback `cs_deck:<id>`) → nhập. kv `pending_csv` = nội dung text file. Trùng chữ Hán → bỏ qua, đếm. Cứ 10 thẻ cập nhật message tiến độ.

- [ ] **Step 1: Viết `app/bot/csv_flow.py`**

```python
from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup
from telegram.error import BadRequest

from app import cards, db
from app.bot.auth import owner_only_callback

GUIDE = (
    "📄 <b>Nhập thẻ từ CSV</b>\n\n"
    "Soạn file .csv (UTF-8) với header:\n"
    "<code>hán,pinyin,nghĩa,ví_dụ</code>\n\n"
    "Chỉ cột <b>hán</b> bắt buộc — pinyin/nghĩa bỏ trống sẽ được tra tự động.\n"
    "VD:\n<code>hán,pinyin,nghĩa,ví_dụ\n学习,,,我在学习中文\n你好,nǐ hǎo,hello; hi,</code>\n\n"
    "Rồi gửi file vào đây."
)


async def cmd_csv(update, context):
    await update.message.reply_html(GUIDE)


async def on_document(update, context):
    conn = context.bot_data["conn"]
    doc = update.message.document
    if not (doc.file_name or "").lower().endswith(".csv"):
        return
    f = await doc.get_file()
    data = await f.download_as_bytearray()
    try:
        text = bytes(data).decode("utf-8-sig")
    except UnicodeDecodeError:
        await update.message.reply_text("⚠️ File không phải UTF-8. Lưu lại với encoding UTF-8 nhé.")
        return
    db.kv_set(conn, "pending_csv", text)
    decks = conn.execute("SELECT id, name FROM decks ORDER BY id").fetchall()
    kb = Markup([[Btn(d["name"], callback_data=f"cs_deck:{d['id']}")] for d in decks])
    await update.message.reply_text("Nhập các thẻ này vào bộ nào?", reply_markup=kb)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    deck_id = int(q.data.split(":")[1])
    text = db.kv_get(conn, "pending_csv")
    if not text:
        await q.edit_message_text("Không còn file chờ nhập. Gửi lại file .csv nhé.")
        return
    db.kv_del(conn, "pending_csv")
    from app.csv_import import parse_csv
    result = parse_csv(text)
    total = len(result.rows)
    await q.edit_message_text(f"⏳ Đang nhập {total} thẻ...")
    created = skipped = 0
    for i, r in enumerate(result.rows, 1):
        if cards.exists_hanzi(conn, r.hanzi):
            skipped += 1
        else:
            await cards.create_card(conn, r.hanzi, deck_id=deck_id,
                                    pinyin_override=r.pinyin,
                                    meaning_override=r.meaning, example=r.example)
            created += 1
        if i % 10 == 0:
            try:
                await q.edit_message_text(f"⏳ Đang nhập... {i}/{total}")
            except BadRequest:
                pass
    lines = [f"✅ Nhập xong: {created} thẻ mới, {skipped} trùng (bỏ qua)."]
    if result.errors:
        lines.append("⚠️ Dòng lỗi (bỏ qua):")
        lines += [f"  • dòng {ln}: {reason}" for ln, reason in result.errors[:15]]
    await q.edit_message_text("\n".join(lines))
```

- [ ] **Step 2: Nối vào `main.py`**

```python
from app.bot import csv_flow
app.add_handler(CommandHandler("csv", csv_flow.cmd_csv, filters=owner_filter))
app.add_handler(CallbackQueryHandler(csv_flow.on_callback, pattern=r"^cs_deck:"))
app.add_handler(MessageHandler(
    owner_filter & filters.Document.FileExtension("csv"), csv_flow.on_document))
```

- [ ] **Step 3: Test thủ công** — `/csv` hiện hướng dẫn; gửi file 15 dòng (1 dòng thiếu hán, 1 dòng trùng thẻ có sẵn) → chọn bộ → tiến độ chạy → báo cáo đúng: N mới, 1 trùng, 1 dòng lỗi kèm số dòng; audio các thẻ mới nghe được khi ôn.

- [ ] **Step 4: Commit** — `git commit -am "feat: bulk CSV import with deck picker and progress"`

---

### Task 17: /thongke + /backup

**Files:** Modify `app/bot/misc.py`, `app/bot/main.py`

**Interfaces:**
- Consumes: `stats.overview`, `config.DB_PATH/today_iso`

- [ ] **Step 1: Thêm vào `app/bot/misc.py`**

```python
from app import config, stats


async def cmd_stats(update, context):
    conn = context.bot_data["conn"]
    o = stats.overview(conn, config.today_iso())
    total_r = o["total_reviews"]
    rate = 100 * (1 - o["total_lapses"] / total_r) if total_r else 100.0
    await update.message.reply_html(
        "📊 <b>Thống kê</b>\n"
        f"🗂 Tổng số thẻ: {o['total']}\n"
        f"📚 Đến hạn hôm nay: {o['due']} (+{o['new_waiting']} thẻ mới chờ)\n"
        f"🔥 Chuỗi: {o['streak']} ngày\n"
        f"✅ Tỉ lệ nhớ: {rate:.0f}% ({total_r} lượt ôn, {o['total_lapses']} lần quên)")


async def cmd_backup(update, context):
    with open(config.DB_PATH, "rb") as f:
        await update.message.reply_document(
            f, filename=f"reminder-backup-{config.today_iso()}.db",
            caption="💾 Bản sao lưu dữ liệu (SQLite). Cất giữ cẩn thận nhé.")
```

- [ ] **Step 2: Nối vào `main.py`**

```python
app.add_handler(CommandHandler("thongke", misc.cmd_stats, filters=owner_filter))
app.add_handler(CommandHandler("backup", misc.cmd_backup, filters=owner_filter))
```

- [ ] **Step 3: Test thủ công** — `/thongke` số liệu khớp thực tế; `/backup` tải file .db về mở được bằng sqlite3.

- [ ] **Step 4: Chạy toàn bộ test tự động lần cuối** — `python -m pytest tests/ -v` → tất cả PASS.

- [ ] **Step 5: Commit** — `git commit -am "feat: stats and backup commands"`

---

### Task 18: Deploy lên Fly.io

**Files:** Create `Dockerfile`, `fly.toml`, `docs/DEPLOY.md`

- [ ] **Step 1: Viết `Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["python", "-m", "app.bot.main"]
```

- [ ] **Step 2: Viết `fly.toml`**

```toml
app = "reminder-zh-bot"
primary_region = "sin"

[env]
  DATA_DIR = "/data"

[mounts]
  source = "reminder_data"
  destination = "/data"

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

Lưu ý: KHÔNG có `[http_service]` — đây là worker thuần, không mở port, nên Fly không auto-stop máy.

- [ ] **Step 3: Viết `docs/DEPLOY.md`** — runbook:

```markdown
# Deploy lên Fly.io

1. Cài flyctl: https://fly.io/docs/flyctl/install/ rồi `fly auth signup` (hoặc login).
2. Từ thư mục repo: `fly launch --no-deploy --copy-config --name reminder-zh-bot --region sin`
   (chọn KHÔNG tạo Postgres/Redis khi được hỏi).
3. Tạo volume: `fly volumes create reminder_data --region sin --size 1`
4. Đặt secrets: `fly secrets set BOT_TOKEN=<token> OWNER_ID=<telegram-id>`
5. Deploy: `fly deploy`
6. Giữ đúng 1 máy (tránh 2 bot polling cùng lúc — Telegram sẽ lỗi Conflict):
   `fly scale count 1`
7. Xem log: `fly logs` — lần đầu sẽ thấy "Đã nạp CC-CEDICT" (~1-2 phút).
8. Nhắn /start cho bot để kiểm tra.

## Cập nhật phiên bản mới
`fly deploy`

## Khôi phục từ backup
Lấy file .db từ /backup của bot, rồi:
`fly ssh sftp shell` → put vào `/data/reminder.db` → `fly apps restart reminder-zh-bot`
```

- [ ] **Step 4: Deploy thật & smoke test** — làm theo runbook; xác nhận: /start trả lời từ cloud, tạo thẻ 学习 nghe được audio, /on ôn được, đặt giờ nhắc 2 phút tới nhận được tin nhắn, `fly apps restart` xong bot vẫn nhớ dữ liệu (volume).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: Fly.io deployment (Dockerfile, fly.toml, runbook)"`

---

## Self-Review Notes

- Spec coverage: §2 kiến trúc (T1,8,18), §3 dữ liệu+CSV (T1,5,7,16), §4 SM-2 (T2), §5 luồng ôn+voice (T10,11), §6 nhắc+streak (T12), §7 lệnh (T8–17), §8 lỗi (T4,5,7,10,16), §9 test (T1–7 unit, còn lại manual), §10 khe Azure (T11 marker + setting key).
- Callback prefix không đụng nhau: `pc_` `rv_` `vc_` `dk_` `cd_` `st_` `cs_`.
- `_answer_kb` (T10) phát callback `vc_rec:` mà handler đến T11 mới có — giữa 2 task nút này bấm không có phản hồi; chấp nhận được vì T11 liền sau.
```
