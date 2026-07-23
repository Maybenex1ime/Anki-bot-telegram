### Task 1: Schema + settings + practice_log helpers

**Files:**
- Modify: `app/db.py` (SCHEMA), `app/config.py` (DEFAULT_SETTINGS), `app/stats.py`
- Test: `tests/test_practice_schema.py`

**Interfaces:**
- Produces: bảng `sentences(id, hanzi, norm UNIQUE, words_json, pinyin, meaning, source, card_id, audio_path, audio_file_id, times_used, created_at)`; `distractors(card_id, level, options_json, PK(card_id,level))`; `practice_log(day, mode, attempts, correct, PK(day,mode))`; settings mới `review_mode='' , quiz_fast_sec='5', quiz_slow_sec='15', gemini_api_key='', gemini_model='gemini-2.5-flash', max_sentences='3000'`; `stats.bump_practice(conn, day_iso, mode, correct: bool)`; `stats.practice_summary(conn, since_iso) -> dict[mode, (attempts, correct)]`.

- [ ] **Step 1: Viết test (fail trước)** — `tests/test_practice_schema.py`:

```python
from app import db, stats


def test_new_tables_and_settings(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sentences", "distractors", "practice_log"} <= tables
    assert db.get_setting(conn, "quiz_fast_sec") == "5"
    assert db.get_setting(conn, "quiz_slow_sec") == "15"
    assert db.get_setting(conn, "gemini_model") == "gemini-2.5-flash"
    assert db.get_setting(conn, "max_sentences") == "3000"
    assert db.get_setting(conn, "gemini_api_key") == ""
    assert db.get_setting(conn, "review_mode") == ""


def test_bump_practice_and_summary(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    stats.bump_practice(conn, "2026-07-23", "mc", True)
    stats.bump_practice(conn, "2026-07-23", "mc", False)
    stats.bump_practice(conn, "2026-07-23", "dict", True)
    stats.bump_practice(conn, "2026-07-20", "mc", True)
    s = stats.practice_summary(conn, "2026-07-21")
    assert s == {"mc": (2, 1), "dict": (1, 1)}
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_practice_schema.py -v`

- [ ] **Step 3: Implement.** Thêm vào cuối `SCHEMA` trong `app/db.py` (trước dấu `"""` đóng):

```sql
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
```

Thêm vào `DEFAULT_SETTINGS` trong `app/config.py`:

```python
    "review_mode": "",
    "quiz_fast_sec": "5",
    "quiz_slow_sec": "15",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "max_sentences": "3000",
```

Thêm vào cuối `app/stats.py`:

```python
def bump_practice(conn, day_iso, mode, correct):
    conn.execute(
        "INSERT INTO practice_log(day, mode, attempts, correct) VALUES(?, ?, 1, ?) "
        "ON CONFLICT(day, mode) DO UPDATE SET attempts=attempts+1, "
        "correct=correct+excluded.correct",
        (day_iso, mode, 1 if correct else 0))
    conn.commit()


def practice_summary(conn, since_iso):
    rows = conn.execute(
        "SELECT mode, SUM(attempts) a, SUM(correct) c FROM practice_log "
        "WHERE day>=? GROUP BY mode", (since_iso,)).fetchall()
    return {r["mode"]: (r["a"], r["c"]) for r in rows}
```

- [ ] **Step 4: Run PASS toàn suite** — `python -m pytest tests/ -v` (31+2 test; DB cũ trên Fly được migrate tự nhiên nhờ `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE` settings trong `connect()`).
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: schema + settings + practice log for practice modes"`

---

