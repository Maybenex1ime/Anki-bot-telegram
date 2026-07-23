# Practice Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Model policy (user requirement):** dispatch implementation subagents with **model Opus**.

**Goal:** Thêm 4 chế độ luyện tập (trắc nghiệm, tự luận, chép chính tả, ghép câu) + engine Gemini có fallback offline vào bot SRS đang chạy.

**Architecture:** 4 module thuần mới (`grading`, `gemini`, `quiz`, `sentences`) + 2 flow bot mới (`quiz_flow`, `practice_flow`) cắm vào session-kv hiện có của `review_flow`. Trắc nghiệm/tự luận chạy trong `/on` (quy ra SM-2) và trong `/luyen` (cờ `practice` — không đụng SM-2); chính tả/ghép câu chỉ ở `/luyen` dùng kho câu `sentences`.

**Tech Stack:** Python 3.12, python-telegram-bot v21, SQLite, httpx (đã có sẵn — dependency của PTB), edge-tts, pytest.

**Spec:** `docs/superpowers/specs/2026-07-23-practice-modes-design.md`
**Code nền:** branch `feature/srs-bot` — bot đã deploy Fly.io. KHÔNG sửa hành vi lật thẻ cổ điển hiện có ngoài những điểm plan nêu rõ.

## Global Constraints

- Mọi chuỗi hiển thị tiếng Việt; mọi giá trị người dùng/Gemini chèn vào tin nhắn `parse_mode="HTML"` phải qua `html.escape`.
- Mọi đường Gemini: lỗi/timeout/thiếu key → `None` → caller dùng nhánh offline; không bao giờ chặn phiên.
- Quy điểm `/on`: sai=AGAIN; đúng >slow=HARD; đúng ≤slow=GOOD; đúng ≤fast VÀ mức hard=EASY (mặc định fast=5, slow=15, settings `quiz_fast_sec`/`quiz_slow_sec`). Tự luận không tính giờ: wrong=AGAIN, partial=HARD, correct=GOOD (+nút Dễ nâng lên EASY trước khi sang câu).
- `/luyen` không gọi `cards.apply_rating` — chỉ `stats.bump_practice`.
- Kho câu: `max_sentences=3000` chặn sinh Gemini (câu `source='example'` luôn được nhận); audio câu xóa mp3 local sau khi có `audio_file_id`.
- Guard chống double-tap/thẻ-bị-xóa: theo pattern có sẵn trong `review_flow.on_callback` (kiểm tra `s["queue"][s["pos"]] == cid`, row None → advance).
- Test: `python -m pytest tests/ -v` từ gốc repo; Gemini/TTS/Telegram mock toàn bộ trong unit test.
- Callback prefix mới không đụng cũ: `qz_` (quiz), `pr_` (practice). `rv_mode`/`rv_mc_levels` nằm dưới pattern `^rv_` có sẵn.
- Commit sau mỗi task.

## File Structure

```
app/grading.py        # MỚI: chấm thuần — normalize nghĩa, chấm tự luận offline, time→rating, diff chính tả, trộn từ
app/gemini.py         # MỚI: client REST + 5 hàm use-case, mọi lỗi → None
app/quiz.py           # MỚI: sinh/cache đáp án nhiễu 3 mức
app/sentences.py      # MỚI: kho câu — thêm/dedupe/chọn/refill/enrich/audio
app/bot/quiz_flow.py  # MỚI: câu hỏi MCQ + tự luận trong session /on và /luyen
app/bot/practice_flow.py # MỚI: /luyen menu, chính tả, ghép câu
app/db.py             # SỬA: +3 bảng sentences/distractors/practice_log
app/config.py         # SỬA: +6 settings mặc định
app/stats.py          # SỬA: +bump_practice, practice_summary
app/csv_import.py     # SỬA: +cột ví_dụ_thêm
app/bot/csv_flow.py   # SỬA: ingest câu ví dụ vào kho
app/bot/create_flow.py# SỬA: ingest ví dụ khi lưu thẻ
app/bot/review_flow.py# SỬA: mode picker /on, session +mode/level/q, _show_front rẽ nhánh
app/bot/settings_flow.py # SỬA: Gemini key/model, ngưỡng giờ
app/bot/misc.py       # SỬA: HELP +/luyen, /thongke +luyện tập
app/bot/main.py       # SỬA: wiring handler mới
```

---

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

### Task 2: Grading core (`app/grading.py`)

**Files:** Create `app/grading.py`; Test `tests/test_grading.py`

**Interfaces:**
- Produces (tất cả thuần, không I/O):
  - `meaning_variants(meaning: str) -> list[str]` — tách theo `;` `|` `,`, bỏ rỗng
  - `normalize_meaning(s: str) -> str` — lowercase, bỏ nội dung trong `()`/`[]`, bỏ "to " đầu, bỏ dấu câu, gộp space
  - `grade_typed_offline(card_meaning: str, answer: str) -> str` — `'correct'` nếu answer chuẩn hóa trùng nguyên 1 biến thể; ngược lại `'unsure'`
  - `fallback_partial(card_meaning: str, answer: str) -> str` — `'partial'` nếu ≥1 content-word (không stopword) của answer nằm trong content-words của biến thể nào đó; ngược lại `'wrong'`
  - `time_to_rating(correct: bool, elapsed: float, level: str, fast: float, slow: float) -> int` — theo Global Constraints, trả hằng của `app.srs`
  - `normalize_hanzi(s: str) -> str` — bỏ whitespace + dấu câu CJK/ASCII `。，！？、；：""''…·.,!?;:'"()（）`
  - `diff_chars(expected: str, got: str) -> tuple[str, int, int]` — (html đã escape có `<s>` cho sai/thừa và `<u>` cho thiếu, số ký tự đúng, len(expected)); so trên chuỗi CHƯA escape, escape khi build
  - `shuffle_words(words: list[str], rng) -> list[int]` — hoán vị chỉ số, khác thứ tự gốc nếu len>1 (thử tối đa 10 lần)

- [ ] **Step 1: Viết test (fail trước)** — `tests/test_grading.py`:

```python
import random

from app import grading, srs


def test_variants_and_normalize():
    assert grading.meaning_variants("to learn; to study | learning") == \
        ["to learn", "to study", "learning"]
    assert grading.normalize_meaning("To Learn (a skill)!") == "learn"
    assert grading.normalize_meaning("AT&T [company]") == "at&t"


def test_grade_typed_offline():
    m = "to learn; to study"
    assert grading.grade_typed_offline(m, "study") == "correct"
    assert grading.grade_typed_offline(m, "To Learn") == "correct"
    assert grading.grade_typed_offline(m, "acquire knowledge") == "unsure"


def test_fallback_partial():
    m = "to learn; to study a subject"
    assert grading.fallback_partial(m, "study hard") == "partial"
    assert grading.fallback_partial(m, "the a of") == "wrong"
    assert grading.fallback_partial(m, "banana") == "wrong"


def test_time_to_rating():
    assert grading.time_to_rating(False, 1, "hard", 5, 15) == srs.AGAIN
    assert grading.time_to_rating(True, 20, "easy", 5, 15) == srs.HARD
    assert grading.time_to_rating(True, 10, "easy", 5, 15) == srs.GOOD
    assert grading.time_to_rating(True, 4, "hard", 5, 15) == srs.EASY
    assert grading.time_to_rating(True, 4, "easy", 5, 15) == srs.GOOD  # fast nhưng không phải hard
    assert grading.time_to_rating(True, 15, "hard", 5, 15) == srs.GOOD  # biên slow


def test_normalize_hanzi():
    assert grading.normalize_hanzi("我在 学习。中文！") == "我在学习中文"


def test_diff_chars_correct_and_wrong():
    html_out, ok, total = grading.diff_chars("我在学习", "我在学习")
    assert (ok, total) == (4, 4) and "<s>" not in html_out
    html_out, ok, total = grading.diff_chars("我在学习", "我再学习")
    assert (ok, total) == (3, 4)
    assert "<s>再</s>" in html_out and "<u>在</u>" in html_out
    html_out, ok, total = grading.diff_chars("我学习", "我的学习")   # thừa 的
    assert "<s>的</s>" in html_out and ok == 3
    html_out, ok, total = grading.diff_chars("我在学习", "我学习")   # thiếu 在
    assert "<u>在</u>" in html_out and ok == 3


def test_shuffle_words():
    rng = random.Random(42)
    words = ["我", "在", "学习", "中文"]
    perm = grading.shuffle_words(words, rng)
    assert sorted(perm) == [0, 1, 2, 3] and perm != [0, 1, 2, 3]
    assert grading.shuffle_words(["一"], rng) == [0]
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_grading.py -v`

- [ ] **Step 3: Implement** — `app/grading.py`:

```python
import html
import re
from difflib import SequenceMatcher

from app import srs

STOPWORDS = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "and",
             "or", "is", "are", "be", "it", "its", "sth", "sb", "one", "ones",
             "something", "somebody", "someone"}
_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_PUNCT = re.compile(r"[^\w\s&']", re.UNICODE)
_HANZI_PUNCT = "。，！？、；：“”‘’…·.,!?;:'\"()（）"


def meaning_variants(meaning):
    parts = re.split(r"[;|,]", meaning)
    return [p.strip() for p in parts if p.strip()]


def normalize_meaning(s):
    s = _PAREN.sub(" ", s.lower())
    s = _PUNCT.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("to "):
        s = s[3:]
    return s


def _content_words(s):
    return {w for w in normalize_meaning(s).split() if w not in STOPWORDS}


def grade_typed_offline(card_meaning, answer):
    ans = normalize_meaning(answer)
    if not ans:
        return "unsure"
    for v in meaning_variants(card_meaning):
        if normalize_meaning(v) == ans:
            return "correct"
    return "unsure"


def fallback_partial(card_meaning, answer):
    ans_words = _content_words(answer)
    if not ans_words:
        return "wrong"
    for v in meaning_variants(card_meaning):
        if ans_words & _content_words(v):
            return "partial"
    return "wrong"


def time_to_rating(correct, elapsed, level, fast, slow):
    if not correct:
        return srs.AGAIN
    if elapsed <= fast and level == "hard":
        return srs.EASY
    if elapsed <= slow:
        return srs.GOOD
    return srs.HARD


def normalize_hanzi(s):
    return "".join(c for c in s if not c.isspace() and c not in _HANZI_PUNCT)


def diff_chars(expected, got):
    out, ok = [], 0
    for op, i1, i2, j1, j2 in SequenceMatcher(None, expected, got).get_opcodes():
        if op == "equal":
            out.append(html.escape(expected[i1:i2]))
            ok += i2 - i1
        elif op == "delete":      # thiếu ký tự
            out.append(f"<u>{html.escape(expected[i1:i2])}</u>")
        elif op == "insert":      # thừa ký tự
            out.append(f"<s>{html.escape(got[j1:j2])}</s>")
        else:                     # replace: sai — hiện cả hai
            out.append(f"<s>{html.escape(got[j1:j2])}</s><u>{html.escape(expected[i1:i2])}</u>")
    return "".join(out), ok, len(expected)


def shuffle_words(words, rng):
    idx = list(range(len(words)))
    if len(idx) < 2:
        return idx
    for _ in range(10):
        perm = rng.sample(idx, len(idx))
        if perm != idx:
            return perm
    return list(reversed(idx))
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_grading.py tests/ -v`
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: grading core — offline typed grading, timing rating, dictation diff, word shuffle"`

---

### Task 3: Gemini client (`app/gemini.py`)

**Files:** Create `app/gemini.py`; Test `tests/test_gemini.py`

**Interfaces:**
- Consumes: `db.get_setting` (`gemini_api_key`, `gemini_model`), env `GEMINI_API_KEY`, `httpx`
- Produces:
  - `available(conn) -> bool`
  - `async ask_json(conn, prompt: str) -> dict | list | None` — POST `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=...`, body `{"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"response_mime_type":"application/json"}}`, timeout 20s, tối đa 2 lần thử; parse `candidates[0].content.parts[0].text` là JSON; **mọi lỗi → None**
  - `async make_distractors(conn, hanzi, meaning, level) -> list[str] | None` (đúng 3 chuỗi, mỗi chuỗi cắt 80 ký tự)
  - `async judge_meaning(conn, hanzi, meaning, answer) -> {"verdict": "correct|partial|wrong", "note": str} | None`
  - `async gen_sentences(conn, vocab: list[str], n=10) -> list[{"hanzi","words","pinyin","meaning"}] | None` (lọc item thiếu hanzi/words)
  - `async segment_translate(conn, hanzi) -> {"words": list[str], "pinyin": str, "meaning": str} | None`
  - `async judge_word_order(conn, original, attempt, meaning) -> {"ok": bool, "note": str} | None`

- [ ] **Step 1: Viết test (fail trước)** — `tests/test_gemini.py` (mock `httpx.AsyncClient`):

```python
import json

import pytest

from app import db, gemini


class FakeResp:
    def __init__(self, status_code=200, payload_text=""):
        self.status_code = status_code
        self._t = payload_text

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._t}]}}]}


class FakeClient:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc = resp, exc

    def __call__(self, *a, **k):  # đóng vai httpx.AsyncClient(...)
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        if self.exc:
            raise self.exc
        return self.resp


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.set_setting(c, "gemini_api_key", "test-key")
    return c


async def test_ask_json_ok(conn, monkeypatch):
    monkeypatch.setattr(gemini.httpx, "AsyncClient",
                        FakeClient(FakeResp(200, json.dumps({"x": 1}))))
    assert await gemini.ask_json(conn, "p") == {"x": 1}


async def test_ask_json_no_key_http_error_and_garbage(tmp_path, conn, monkeypatch):
    bare = db.connect(tmp_path / "nokey.db")
    assert await gemini.ask_json(bare, "p") is None          # không key
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(429, "{}")))
    assert await gemini.ask_json(conn, "p") is None          # HTTP lỗi
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, "not json")))
    assert await gemini.ask_json(conn, "p") is None          # JSON hỏng
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(exc=RuntimeError("net")))
    assert await gemini.ask_json(conn, "p") is None          # exception


async def test_make_distractors_validates(conn, monkeypatch):
    good = json.dumps({"options": ["to teach", "to read", "to test"]})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, good)))
    assert await gemini.make_distractors(conn, "学", "to learn", "normal") == \
        ["to teach", "to read", "to test"]
    bad = json.dumps({"options": ["one", "two"]})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, bad)))
    assert await gemini.make_distractors(conn, "学", "to learn", "normal") is None


async def test_judge_meaning_validates(conn, monkeypatch):
    ok = json.dumps({"verdict": "partial", "note": "thiếu ý"})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, ok)))
    assert (await gemini.judge_meaning(conn, "学", "to learn", "study"))["verdict"] == "partial"
    bad = json.dumps({"verdict": "maybe"})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, bad)))
    assert await gemini.judge_meaning(conn, "学", "to learn", "x") is None


async def test_gen_sentences_filters(conn, monkeypatch):
    payload = json.dumps({"sentences": [
        {"hanzi": "我学习", "words": ["我", "学习"], "pinyin": "wǒ xuéxí", "meaning": "I study"},
        {"hanzi": "", "words": []},
    ]})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, payload)))
    out = await gemini.gen_sentences(conn, ["我", "学习"])
    assert len(out) == 1 and out[0]["hanzi"] == "我学习"


async def test_judge_word_order_validates(conn, monkeypatch):
    ok = json.dumps({"ok": True, "note": "đảo trạng ngữ hợp lệ"})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, ok)))
    assert (await gemini.judge_word_order(conn, "昨天我去", "我昨天去", "x"))["ok"] is True
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_gemini.py -v`

- [ ] **Step 3: Implement** — `app/gemini.py`:

```python
import json
import os

import httpx

from app import db

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _key(conn):
    return db.get_setting(conn, "gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")


def available(conn):
    return bool(_key(conn))


async def ask_json(conn, prompt):
    key = _key(conn)
    if not key:
        return None
    model = db.get_setting(conn, "gemini_model")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}}
    for _ in range(2):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(API_URL.format(model=model),
                                      params={"key": key}, json=body)
            if r.status_code != 200:
                continue
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception:
            continue
    return None


async def make_distractors(conn, hanzi, meaning, level):
    kind = ("nghĩa tiếng Anh cùng nhóm chủ đề nhưng SAI"
            if level == "normal"
            else "nghĩa tiếng Anh RẤT GIỐNG nghĩa đúng nhưng SAI (bẫy gần-đồng-nghĩa)")
    data = await ask_json(conn, (
        f"Từ tiếng Trung: {hanzi}\nNghĩa đúng (tiếng Anh): {meaning}\n"
        f"Sinh đúng 3 {kind}, ngắn gọn kiểu từ điển.\n"
        'Trả JSON: {"options": ["...", "...", "..."]}'))
    if not isinstance(data, dict) or not isinstance(data.get("options"), list):
        return None
    opts = [str(o).strip()[:80] for o in data["options"] if str(o).strip()][:3]
    return opts if len(opts) == 3 else None


async def judge_meaning(conn, hanzi, meaning, answer):
    data = await ask_json(conn, (
        f'Từ tiếng Trung: {hanzi}. Nghĩa chuẩn (tiếng Anh): "{meaning}". '
        f'Người học trả lời: "{answer}".\n'
        "Chấm verdict: correct (đúng hoặc tương đương), partial (đúng một phần), wrong.\n"
        'Trả JSON: {"verdict": "...", "note": "giải thích 1 câu tiếng Việt"}'))
    if not isinstance(data, dict) or data.get("verdict") not in ("correct", "partial", "wrong"):
        return None
    return {"verdict": data["verdict"], "note": str(data.get("note", ""))[:200]}


async def gen_sentences(conn, vocab, n=10):
    data = await ask_json(conn, (
        f"Sinh {n} câu tiếng Trung giản thể ngắn (4-10 từ), CHỈ dùng các từ sau "
        "cộng từ chức năng cơ bản (的了吗在是我你他她们不很和有个这那):\n"
        + "、".join(vocab[:300]) + "\n"
        'Trả JSON: {"sentences": [{"hanzi": "...", "words": ["từ", "đã", "tách"], '
        '"pinyin": "...", "meaning": "bản dịch tiếng Anh"}]}'))
    if not isinstance(data, dict) or not isinstance(data.get("sentences"), list):
        return None
    out = []
    for it in data["sentences"]:
        if (isinstance(it, dict) and str(it.get("hanzi", "")).strip()
                and isinstance(it.get("words"), list) and it["words"]):
            out.append({"hanzi": str(it["hanzi"]).strip()[:100],
                        "words": [str(w)[:20] for w in it["words"]][:20],
                        "pinyin": str(it.get("pinyin", ""))[:200],
                        "meaning": str(it.get("meaning", ""))[:200]})
    return out or None


async def segment_translate(conn, hanzi):
    data = await ask_json(conn, (
        f"Câu tiếng Trung: {hanzi}\nTách từ và dịch sang tiếng Anh.\n"
        'Trả JSON: {"words": ["từ", "đã", "tách"], "pinyin": "...", "meaning": "..."}'))
    if not isinstance(data, dict) or not isinstance(data.get("words"), list) or not data["words"]:
        return None
    return {"words": [str(w)[:20] for w in data["words"]][:20],
            "pinyin": str(data.get("pinyin", ""))[:200],
            "meaning": str(data.get("meaning", ""))[:200]}


async def judge_word_order(conn, original, attempt, meaning):
    data = await ask_json(conn, (
        f"Câu gốc: {original}\nNghĩa: {meaning}\nHọc viên xếp lại thành: {attempt}\n"
        "Câu xếp lại có đúng ngữ pháp tiếng Trung và giữ nguyên nghĩa không?\n"
        'Trả JSON: {"ok": true/false, "note": "1 câu tiếng Việt"}'))
    if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
        return None
    return {"ok": data["ok"], "note": str(data.get("note", ""))[:200]}
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/ -v`
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: gemini client with JSON mode, validation, None-on-error"`

---

### Task 4: Distractor service (`app/quiz.py`)

**Files:** Create `app/quiz.py`; Test `tests/test_quiz.py`

**Interfaces:**
- Consumes: `gemini.make_distractors`, `grading.normalize_meaning/meaning_variants`, bảng `cards`, `dict_entries`, `distractors`
- Produces:
  - `pinyin_key(pinyin: str) -> str` — bỏ dấu thanh (NFD, giữ chữ cái), bỏ số + space; dùng được cho cả pinyin có dấu ("xué xí") lẫn CEDICT dạng số ("xue2 xi2") → cùng "xuexi"
  - `async get_options(conn, row, level) -> list[str] | None` — 3 nhiễu (cache bảng `distractors`); None nếu không gom đủ 3 (caller rơi về lật thẻ cho thẻ đó)

- [ ] **Step 1: Viết test (fail trước)** — `tests/test_quiz.py`:

```python
import pytest

from app import cards, db, quiz


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.MEDIA_DIR", tmp_path / "m")

    async def fake_synth(text, voice, out):
        return False

    monkeypatch.setattr("app.cards.tts.synthesize", fake_synth)
    return db.connect(tmp_path / "t.db")


def test_pinyin_key():
    assert quiz.pinyin_key("xué xí") == "xuexi"
    assert quiz.pinyin_key("xue2 xi2") == "xuexi"
    assert quiz.pinyin_key("nǐ hǎo") == "nihao"


async def _seed(conn, n=6):
    rows = []
    for i, (h, m) in enumerate([("学习", "to learn; to study"), ("你好", "hello"),
                                ("苹果", "apple"), ("跑", "to run"),
                                ("美", "beautiful"), ("茶", "tea")][:n]):
        rows.append(await cards.create_card(conn, h, meaning_override=m))
    return rows


async def test_easy_options_offline(conn, monkeypatch):
    async def no_gemini(*a, **k):
        return None

    monkeypatch.setattr("app.quiz.gemini.make_distractors", no_gemini)
    rows = await _seed(conn)
    opts = await quiz.get_options(conn, rows[0], "easy")
    assert len(opts) == 3
    assert "to learn; to study" not in opts
    # cache: gọi lại trả đúng bộ cũ
    assert await quiz.get_options(conn, rows[0], "easy") == opts


async def test_hard_uses_homophones_and_gemini(conn, monkeypatch):
    await _seed(conn)
    # 是 (shì) và 事 (shì) là cặp đồng âm thật
    row_shi = await cards.create_card(conn, "是", meaning_override="to be; yes")
    await cards.create_card(conn, "事", meaning_override="matter; affair")

    async def fake_gemini(conn_, h, m, level):
        return ["to exist", "to seem", "to become"]

    monkeypatch.setattr("app.quiz.gemini.make_distractors", fake_gemini)
    opts = await quiz.get_options(conn, row_shi, "hard")
    assert len(opts) == 3
    assert "matter; affair" in opts     # đồng âm được ưu tiên
    assert "to be; yes" not in opts


async def test_not_enough_cards_returns_none(conn, monkeypatch):
    async def no_gemini(*a, **k):
        return None

    monkeypatch.setattr("app.quiz.gemini.make_distractors", no_gemini)
    row = (await _seed(conn, 1))[0]
    assert await quiz.get_options(conn, row, "easy") is None


async def test_distractor_never_equals_correct(conn, monkeypatch):
    async def echo_gemini(conn_, h, m, level):
        return ["to learn", "to study", "to teach"]  # 2 cái trùng nghĩa đúng

    monkeypatch.setattr("app.quiz.gemini.make_distractors", echo_gemini)
    rows = await _seed(conn)
    opts = await quiz.get_options(conn, rows[0], "normal")
    assert opts is not None
    for o in opts:
        assert quiz.grading.normalize_meaning(o) not in \
            {quiz.grading.normalize_meaning(v)
             for v in quiz.grading.meaning_variants("to learn; to study")}
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_quiz.py -v`

- [ ] **Step 3: Implement** — `app/quiz.py`:

```python
import json
import unicodedata

from app import gemini, grading


def pinyin_key(pinyin):
    s = unicodedata.normalize("NFD", pinyin.lower())
    return "".join(c for c in s if c.isascii() and c.isalpha())


def _ban_set(correct_meaning):
    return {grading.normalize_meaning(v)
            for v in grading.meaning_variants(correct_meaning)} | \
           {grading.normalize_meaning(correct_meaning)}


def _pick_valid(cands, correct_meaning, need=3):
    out, seen, ban = [], set(), _ban_set(correct_meaning)
    for m in cands:
        nm = grading.normalize_meaning(m)
        if not nm or nm in seen or nm in ban:
            continue
        if any(nm in b or b in nm for b in ban):
            continue
        seen.add(nm)
        out.append(m)
        if len(out) == need:
            break
    return out


def _random_meanings(conn, exclude_id, limit=25):
    return [r["meaning"] for r in conn.execute(
        "SELECT meaning FROM cards WHERE id<>? AND meaning<>'' "
        "ORDER BY RANDOM() LIMIT ?", (exclude_id, limit))]


def _same_deck_meanings(conn, row, limit=25):
    return [r["meaning"] for r in conn.execute(
        "SELECT meaning FROM cards WHERE id<>? AND deck_id=? AND meaning<>'' "
        "ORDER BY RANDOM() LIMIT ?", (row["id"], row["deck_id"], limit))]


def _homophone_meanings(conn, row, limit=10):
    key = pinyin_key(row["pinyin"])
    if not key:
        return []
    out = [r["meaning"] for r in conn.execute(
        "SELECT pinyin, meaning FROM cards WHERE id<>? AND meaning<>''",
        (row["id"],)) if pinyin_key(r["pinyin"]) == key][:limit]
    if len(out) < limit:
        cur = conn.execute(
            "SELECT pinyin, meaning FROM dict_entries WHERE simplified<>?",
            (row["hanzi"],))
        for r in cur:
            if pinyin_key(r["pinyin"]) == key:
                out.append(r["meaning"])
                if len(out) >= limit:
                    break
    return out


async def get_options(conn, row, level):
    cached = conn.execute(
        "SELECT options_json FROM distractors WHERE card_id=? AND level=?",
        (row["id"], level)).fetchone()
    if cached:
        return json.loads(cached["options_json"])
    correct = row["meaning"]
    cands = []
    if level == "normal":
        g = await gemini.make_distractors(conn, row["hanzi"], correct, level)
        if g:
            cands += g
        cands += _same_deck_meanings(conn, row)
    elif level == "hard":
        homo = _homophone_meanings(conn, row)
        g = await gemini.make_distractors(conn, row["hanzi"], correct, level)
        # ưu tiên trộn: đồng âm trước, rồi đồng nghĩa giả
        cands += homo[:2] + (g or []) + homo[2:]
    cands += _random_meanings(conn, row["id"])
    opts = _pick_valid(cands, correct)
    if len(opts) < 3:
        return None
    conn.execute("INSERT OR REPLACE INTO distractors VALUES(?, ?, ?)",
                 (row["id"], level, json.dumps(opts, ensure_ascii=False)))
    conn.commit()
    return opts
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/ -v`
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: distractor service — 3 levels, homophone offline, cache"`

---

### Task 5: Sentence bank (`app/sentences.py`)

**Files:** Create `app/sentences.py`; Test `tests/test_sentences.py`

**Interfaces:**
- Consumes: `grading.normalize_hanzi`, `gemini.gen_sentences/segment_translate`, `tts.synthesize`, `db.get_setting`, `config.MEDIA_DIR/today_iso`, bảng `sentences`, `cards`
- Produces:
  - `add_sentence(conn, hanzi, words=None, pinyin='', meaning='', source='gemini', card_id=None) -> int | None` — None nếu trùng (`norm` UNIQUE) hoặc hanzi rỗng sau chuẩn hóa
  - `ingest_examples(conn, raw: str, card_id) -> int` — tách theo `|`, add từng câu `source='example'`, trả số câu thêm mới
  - `async maybe_refill(conn) -> int` — nếu (số câu `times_used=0`) < 10 VÀ tổng câu `source='gemini'` < `max_sentences` VÀ có ≥5 thẻ → gọi `gemini.gen_sentences` với vocab = mọi hanzi của thẻ, add kết quả; trả số câu thêm
  - `async enrich_one(conn) -> bool` — lấy 1 câu `words_json=''`, gọi `segment_translate`, cập nhật; False nếu không có gì làm/Gemini fail
  - `pick(conn, need_words: bool) -> Row | None` — `times_used` thấp nhất, RANDOM trong nhóm; `need_words=True` chỉ lấy `words_json != ''`
  - `mark_used(conn, sid)`
  - `async send_audio(context, chat_id, srow) -> Message | None` — ưu tiên `audio_file_id` (nếu Telegram từ chối file_id → synth lại); chưa có → synth `MEDIA_DIR/sent_{id}.mp3`, gửi, lưu `file_id`, **xóa mp3 local + audio_path=''** (chính sách volume của spec §6)

- [ ] **Step 1: Viết test (fail trước)** — `tests/test_sentences.py`:

```python
import pytest

from app import cards, db, sentences


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.MEDIA_DIR", tmp_path / "m")

    async def fake_synth(text, voice, out):
        return False

    monkeypatch.setattr("app.cards.tts.synthesize", fake_synth)
    return db.connect(tmp_path / "t.db")


def test_add_and_dedupe(conn):
    sid = sentences.add_sentence(conn, "我在学习。", words=["我", "在", "学习"],
                                 pinyin="p", meaning="m")
    assert sid is not None
    assert sentences.add_sentence(conn, "我 在 学习") is None   # trùng sau chuẩn hóa
    assert sentences.add_sentence(conn, "。！") is None          # rỗng sau chuẩn hóa


def test_ingest_examples(conn):
    n = sentences.ingest_examples(conn, "我们一起学习吧|他学习很努力||", card_id=1)
    assert n == 2
    row = conn.execute("SELECT * FROM sentences WHERE card_id=1").fetchone()
    assert row["source"] == "example" and row["words_json"] == ""


async def test_maybe_refill_respects_cap_and_min_cards(conn, monkeypatch):
    called = {"n": 0}

    async def fake_gen(conn_, vocab, n=10):
        called["n"] += 1
        return [{"hanzi": f"句子{i}", "words": ["句", f"子{i}"],
                 "pinyin": "p", "meaning": "m"} for i in range(3)]

    monkeypatch.setattr("app.sentences.gemini.gen_sentences", fake_gen)
    assert await sentences.maybe_refill(conn) == 0      # <5 thẻ → không gọi
    for h in ["一", "二", "三", "四", "五"]:
        await cards.create_card(conn, h, meaning_override="x")
    assert await sentences.maybe_refill(conn) == 3
    db.set_setting(conn, "max_sentences", "3")
    assert await sentences.maybe_refill(conn) == 0      # chạm trần → không gọi thêm
    assert called["n"] == 1


async def test_enrich_one(conn, monkeypatch):
    sentences.ingest_examples(conn, "我在学习中文", card_id=None)

    async def fake_seg(conn_, hanzi):
        return {"words": ["我", "在", "学习", "中文"], "pinyin": "p", "meaning": "m"}

    monkeypatch.setattr("app.sentences.gemini.segment_translate", fake_seg)
    assert await sentences.enrich_one(conn) is True
    row = conn.execute("SELECT * FROM sentences").fetchone()
    assert row["words_json"] != "" and row["meaning"] == "m"
    assert await sentences.enrich_one(conn) is False    # hết việc


def test_pick_prefers_least_used_and_need_words(conn):
    a = sentences.add_sentence(conn, "甲句", words=["甲", "句"])
    b = sentences.add_sentence(conn, "乙句")             # không words
    sentences.mark_used(conn, a)
    assert sentences.pick(conn, need_words=False)["id"] == b
    assert sentences.pick(conn, need_words=True)["id"] == a
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_sentences.py -v`

- [ ] **Step 3: Implement** — `app/sentences.py`:

```python
import json
from pathlib import Path

from telegram.error import TelegramError

from app import config, db, gemini, grading, tts


def add_sentence(conn, hanzi, words=None, pinyin="", meaning="",
                 source="gemini", card_id=None):
    hanzi = hanzi.strip()
    norm = grading.normalize_hanzi(hanzi)
    if not norm:
        return None
    try:
        cur = conn.execute(
            "INSERT INTO sentences(hanzi, norm, words_json, pinyin, meaning, "
            "source, card_id, created_at) VALUES(?,?,?,?,?,?,?,?)",
            (hanzi, norm,
             json.dumps(words, ensure_ascii=False) if words else "",
             pinyin, meaning, source, card_id, config.today_iso()))
        conn.commit()
        return cur.lastrowid
    except Exception:   # UNIQUE(norm) — câu trùng
        return None


def ingest_examples(conn, raw, card_id):
    n = 0
    for part in raw.split("|"):
        if part.strip() and add_sentence(conn, part, source="example",
                                         card_id=card_id) is not None:
            n += 1
    return n


async def maybe_refill(conn):
    unused = conn.execute(
        "SELECT COUNT(*) c FROM sentences WHERE times_used=0").fetchone()["c"]
    if unused >= 10:
        return 0
    gen_total = conn.execute(
        "SELECT COUNT(*) c FROM sentences WHERE source='gemini'").fetchone()["c"]
    if gen_total >= int(db.get_setting(conn, "max_sentences")):
        return 0
    vocab = [r["hanzi"] for r in conn.execute("SELECT hanzi FROM cards")]
    if len(vocab) < 5:
        return 0
    items = await gemini.gen_sentences(conn, vocab)
    if not items:
        return 0
    n = 0
    for it in items:
        if add_sentence(conn, it["hanzi"], words=it["words"],
                        pinyin=it["pinyin"], meaning=it["meaning"]) is not None:
            n += 1
    return n


async def enrich_one(conn):
    row = conn.execute(
        "SELECT * FROM sentences WHERE words_json='' LIMIT 1").fetchone()
    if not row:
        return False
    data = await gemini.segment_translate(conn, row["hanzi"])
    if not data:
        return False
    conn.execute(
        "UPDATE sentences SET words_json=?, pinyin=COALESCE(NULLIF(pinyin,''),?), "
        "meaning=COALESCE(NULLIF(meaning,''),?) WHERE id=?",
        (json.dumps(data["words"], ensure_ascii=False),
         data["pinyin"], data["meaning"], row["id"]))
    conn.commit()
    return True


def pick(conn, need_words):
    where = "WHERE words_json<>''" if need_words else ""
    return conn.execute(
        f"SELECT * FROM sentences {where} "
        "ORDER BY times_used, RANDOM() LIMIT 1").fetchone()


def mark_used(conn, sid):
    conn.execute("UPDATE sentences SET times_used=times_used+1 WHERE id=?", (sid,))
    conn.commit()


async def send_audio(context, chat_id, srow):
    conn = context.bot_data["conn"]
    if srow["audio_file_id"]:
        try:
            return await context.bot.send_voice(chat_id, srow["audio_file_id"])
        except TelegramError:   # file_id hỏng — synth lại bên dưới
            pass
    out = config.MEDIA_DIR / f"sent_{srow['id']}.mp3"
    voice = db.get_setting(conn, "tts_voice")
    if not await tts.synthesize(srow["hanzi"], voice, out):
        return None
    with open(out, "rb") as f:
        m = await context.bot.send_voice(chat_id, f)
    conn.execute("UPDATE sentences SET audio_file_id=?, audio_path='' WHERE id=?",
                 (m.voice.file_id, srow["id"]))
    conn.commit()
    try:
        out.unlink()            # chính sách volume: xóa mp3 sau khi có file_id
    except OSError:
        pass
    return m
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/ -v`
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: sentence bank — dedupe, refill cap, enrich, audio with local-file cleanup"`

---

### Task 6: CSV `ví_dụ_thêm` + ingest ví dụ vào kho câu

**Files:**
- Modify: `app/csv_import.py`, `app/bot/csv_flow.py`, `app/bot/create_flow.py`
- Test: `tests/test_csv_import.py` (thêm test)

**Interfaces:**
- Consumes: `sentences.ingest_examples`
- Produces: `CsvRow.extra_examples: str` (chuỗi thô còn nguyên `|`, mặc định `""`); alias header `ví_dụ_thêm|vi_du_them`

- [ ] **Step 1: Thêm test vào `tests/test_csv_import.py` (fail trước)**:

```python
def test_extra_examples_column():
    text = "hán,nghĩa,ví_dụ,ví_dụ_thêm\n学习,to study,我在学习,我们一起学习吧|他学习很努力\n"
    r = parse_csv(text)
    assert r.rows[0].extra_examples == "我们一起学习吧|他学习很努力"
    r2 = parse_csv("hán\n学\n")
    assert r2.rows[0].extra_examples == ""
```

- [ ] **Step 2: Run FAIL**, rồi sửa `app/csv_import.py`: thêm alias `"ví_dụ_thêm": "extra_examples", "vi_du_them": "extra_examples"` vào `_ALIASES`; thêm field `extra_examples: str = ""` vào `CsvRow`; trong vòng lặp append thêm `extra_examples=cell(row, "extra_examples")`.

- [ ] **Step 3: Run PASS** — `python -m pytest tests/test_csv_import.py -v`

- [ ] **Step 4: Nối vào flow.** Trong `app/bot/csv_flow.py`:
  - Sửa `GUIDE`: header mẫu thành `<code>hán,pinyin,nghĩa,ví_dụ,ví_dụ_thêm</code>` và thêm dòng `"Cột <b>ví_dụ_thêm</b>: nhiều câu cho kho luyện tập, ngăn cách bằng dấu |."`
  - Trong `on_callback`, sau nhánh tạo thẻ mới (cả nhánh created lẫn skipped), ingest ví dụ:

```python
    from app import sentences
    # ... trong vòng for, sau khi xử lý created/skipped:
        crow = conn.execute("SELECT id FROM cards WHERE hanzi=? LIMIT 1", (r.hanzi,)).fetchone()
        card_id = crow["id"] if crow else None
        n_sent = 0
        if r.example:
            n_sent += sentences.ingest_examples(conn, r.example, card_id)
        if r.extra_examples:
            n_sent += sentences.ingest_examples(conn, r.extra_examples, card_id)
```

  Cộng dồn `n_sent` vào biến `sent_added` khởi tạo 0 trước vòng lặp; thêm vào báo cáo cuối: `lines.append(f"📚 Thêm {sent_added} câu vào kho luyện tập.")` khi `sent_added > 0`.
  - Trong `app/bot/create_flow.py`, nhánh `pc_save` sau khi `cards.create_card(...)` thành công:

```python
        from app import sentences
        if row["example"]:
            sentences.ingest_examples(conn, row["example"], row["id"])
```

- [ ] **Step 5: Run toàn suite PASS + offline check** — `python -m pytest tests/ -v`; env `BOT_TOKEN=123:dummy OWNER_ID=1` rồi `python -c "from app.bot.main import build_app; build_app()"` không lỗi.
- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: CSV vi_du_them column + example ingestion into sentence bank"`

---

### Task 7: Mode picker cho `/on` (`app/bot/review_flow.py`)

**Files:** Modify `app/bot/review_flow.py`

**Interfaces:**
- Consumes: setting `review_mode`
- Produces:
  - session kv `session` thêm khóa: `"mode"` (`"classic"|"mc"|"typed"`), `"level"` (`"easy"|"normal"|"hard"|""`), `"q"` (dict trạng thái câu hỏi hiện tại hoặc None), `"practice"` (bool), `"ok"` (đếm câu đúng — dùng ở /luyen)
  - callbacks mới dưới pattern `^rv_` có sẵn: `rv_mode:<classic|typed|mc:easy|mc:normal|mc:hard>`, `rv_mc_levels`
  - `start_session(context, chat_id, mode="classic", level="", practice=False, queue=None)` — chữ ký mở rộng; Task 8-10 gọi
  - `_show_front` rẽ nhánh: mode != "classic" → import cục bộ `from app.bot import quiz_flow; await quiz_flow.show_question(context)` (Task 8 tạo hàm này; TRONG task này để tạm stub thông báo — xem Step 2)
  - `advance(context)` — đổi tên public từ `_advance` (giữ alias `_advance = advance`); nhánh kết thúc: nếu `s.get("practice")` → tổng kết `"🏁 Luyện xong! Đúng {ok}/{done}."` không streak, không đụng review_mode

- [ ] **Step 1: Sửa `cmd_review` + thêm picker.** Trong `app/bot/review_flow.py`:

```python
MODE_LABEL = {"classic": "🃏 Lật thẻ", "typed": "⌨️ Tự luận",
              "mc:easy": "🔘 Trắc nghiệm 😌 Dễ",
              "mc:normal": "🔘 Trắc nghiệm 🙂 Thường",
              "mc:hard": "🔘 Trắc nghiệm 🔥 Khó"}


async def cmd_review(update, context):
    await show_mode_picker(context, update.effective_chat.id)


async def show_mode_picker(context, chat_id):
    conn = context.bot_data["conn"]
    if not cards.build_queue(conn, config.today_iso()):
        await context.bot.send_message(chat_id, "🎉 Không có thẻ nào đến hạn. Nghỉ ngơi đi!")
        return
    last = db.get_setting(conn, "review_mode")
    rows = []
    if last in MODE_LABEL:
        rows.append([Btn(f"▶️ Như lần trước: {MODE_LABEL[last]}",
                         callback_data=f"rv_mode:{last}")])
    rows += [[Btn("🃏 Lật thẻ", callback_data="rv_mode:classic")],
             [Btn("🔘 Trắc nghiệm", callback_data="rv_mc_levels")],
             [Btn("⌨️ Tự luận", callback_data="rv_mode:typed")]]
    await context.bot.send_message(chat_id, "Chọn chế độ ôn:", reply_markup=Markup(rows))
```

- [ ] **Step 2: Mở rộng `start_session` + `_show_front` + `advance`:**

```python
async def start_session(context, chat_id, mode="classic", level="",
                        practice=False, queue=None):
    conn = context.bot_data["conn"]
    queue = queue if queue is not None else cards.build_queue(conn, config.today_iso())
    if not queue:
        await context.bot.send_message(chat_id, "🎉 Không có thẻ nào đến hạn. Nghỉ ngơi đi!")
        return
    db.kv_set(conn, "session", {"queue": queue, "pos": 0, "done": 0, "ok": 0,
                                "chat": chat_id, "msg": None, "aux": [],
                                "mode": mode, "level": level,
                                "practice": practice, "q": None})
    await _show_front(context)
```

`_show_front`: sau guard `row is None`, thêm trước phần render cũ:

```python
    if s.get("mode", "classic") != "classic":
        from app.bot import quiz_flow
        await quiz_flow.show_question(context)
        return
```

(Task này `app/bot/quiz_flow.py` CHƯA tồn tại — tạo stub tối thiểu để import không vỡ:)

```python
# app/bot/quiz_flow.py (stub — Task 8 thay bằng bản đầy đủ)
async def show_question(context):
    from app.bot import review_flow
    conn = context.bot_data["conn"]
    s = review_flow.db.kv_get(conn, "session")
    await review_flow._edit_or_send(context, s, "⚠️ Chế độ này đang được xây.", None)
```

Đổi tên `_advance` → `advance` (giữ dòng `_advance = advance` ngay dưới để chỗ gọi cũ không vỡ), sửa nhánh kết thúc:

```python
    if s["pos"] >= len(s["queue"]):
        if s.get("practice"):
            await _edit_or_send(context, s,
                f"🏁 <b>Luyện xong!</b> Đúng {s.get('ok', 0)}/{s['done']} câu.", None)
        else:
            n = stats.streak(conn, config.today())
            await _edit_or_send(context, s,
                f"🎉 <b>Hoàn thành!</b> Đã ôn {s['done']} lượt.\n🔥 Chuỗi: {n} ngày liên tiếp.",
                None)
        db.kv_del(conn, "session")
        return
```

- [ ] **Step 3: Thêm nhánh callback trong `on_callback`** (sau nhánh `rv_start`; đổi luôn `rv_start` thành gọi `show_mode_picker(context, q.message.chat_id)`):

```python
    if q.data == "rv_mc_levels":
        kb = Markup([[Btn("😌 Dễ", callback_data="rv_mode:mc:easy"),
                      Btn("🙂 Thường", callback_data="rv_mode:mc:normal"),
                      Btn("🔥 Khó", callback_data="rv_mode:mc:hard")]])
        await q.edit_message_text("Chọn mức trắc nghiệm:", reply_markup=kb)
        return
    if q.data.startswith("rv_mode:"):
        choice = q.data.split(":", 1)[1]          # classic | typed | mc:easy...
        db.set_setting(conn, "review_mode", choice)
        mode, _, level = choice.partition(":")
        try:
            await q.message.delete()
        except TelegramError:
            pass
        await start_session(context, q.message.chat_id, mode=mode, level=level)
        return
```

Lưu ý: hai nhánh này đặt TRƯỚC đoạn `s = db.kv_get(conn, "session")` (chúng không cần session đang mở).

- [ ] **Step 4: Verify offline + suite** — `python -m pytest tests/ -v`; với env dummy: `python -c "from app.bot.main import build_app; build_app()"`; kiểm tra nhanh session mới có đủ khóa bằng REPL nhỏ nếu cần.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: /on mode picker + session mode plumbing (classic path intact)"`

---

### Task 8: MCQ trong session (`app/bot/quiz_flow.py` bản đầy đủ — phần 1)

**Files:** Rewrite `app/bot/quiz_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `quiz.get_options`, `grading.time_to_rating`, `cards.apply_rating/get_card`, `stats.bump_practice`, `review_flow._edit_or_send/_clear_aux/advance/send_card_audio/_front_kb`, session kv như Task 7
- Produces:
  - `quiz_flow.show_question(context)` — rẽ theo `s["mode"]`: `"mc"` → câu hỏi 4 lựa chọn (options trong text, nút `[A][B][C][D]` = `qz_ans:<cid>:<idx>`); `"typed"` → Task 9
  - `s["q"]` cho MCQ: `{"kind":"mc","options":[4 chuỗi],"correct":int,"asked_at":float}`
  - Callback `qz_ans` chấm + hiện mặt sau + nút `[▶️ Tiếp]` (`qz_next:<cid>`); rating áp khi bấm Tiếp (AGAIN → requeue)
  - Fallback: `get_options` trả None → thẻ đó hiển thị dạng lật thẻ cổ điển (`s["q"]={"kind":"fallback"}`)

- [ ] **Step 1: Viết `app/bot/quiz_flow.py`** (thay stub):

```python
import html
import random
import time

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import cards, config, db, gemini, grading, quiz, srs, stats
from app.bot import review_flow
from app.bot.auth import owner_only_callback

LETTERS = ["A", "B", "C", "D"]


def _back_lines(row):
    lines = [f"🀄 <b>{html.escape(row['hanzi'])}</b>",
             f"📖 {html.escape(row['pinyin'])}",
             f"🇬🇧 {html.escape(row['meaning']) if row['meaning'] else '<i>(chưa có nghĩa)</i>'}"]
    if row["example"]:
        lines.append(f"💬 {html.escape(row['example'])}")
    return lines


async def _send_back_aux(context, s, row):
    if row["image_file_id"]:
        m = await context.bot.send_photo(s["chat"], row["image_file_id"])
        s["aux"].append(m.message_id)
    m = await review_flow.send_card_audio(context, s["chat"], row)
    if m:
        s["aux"].append(m.message_id)


async def show_question(context):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    cid = s["queue"][s["pos"]]
    row = cards.get_card(conn, cid)
    if row is None:
        await review_flow.advance(context)
        return
    if s["mode"] == "typed":
        await _show_typed(context, s, row)          # Task 9 định nghĩa; Task 8 tạo stub tạm:
        # async def _show_typed(context, s, row):
        #     await review_flow._edit_or_send(context, s, "⚠️ Tự luận đang được xây.", None)
        return
    opts3 = await quiz.get_options(conn, row, s["level"]) if row["meaning"] else None
    if not opts3:                                   # không đủ nhiễu
        if s["practice"]:                           # /luyen: bỏ qua thẻ (không được rơi về rv_rate → SM-2)
            await review_flow.advance(context)
            return
        s["q"] = {"kind": "fallback"}               # /on: rơi về lật thẻ cổ điển
        db.kv_set(conn, "session", s)
        text = f"🀄 <b>{html.escape(row['hanzi'])}</b>\n\n({s['pos'] + 1}/{len(s['queue'])})"
        await review_flow._edit_or_send(context, s, text, review_flow._front_kb(cid))
        return
    options = opts3 + [row["meaning"]]
    rng = random.Random()
    order = grading.shuffle_words(options, rng)     # hoán vị 4 chỉ số
    options = [options[i] for i in order]
    correct = order.index(3)
    s["q"] = {"kind": "mc", "options": options, "correct": correct,
              "asked_at": time.time()}
    db.kv_set(conn, "session", s)
    lines = [f"🀄 <b>{html.escape(row['hanzi'])}</b> — nghĩa là gì?", ""]
    for i, o in enumerate(options):
        lines.append(f"<b>{LETTERS[i]}.</b> {html.escape(o)}")
    lines.append(f"\n({s['pos'] + 1}/{len(s['queue'])})")
    kb = Markup([[Btn(l, callback_data=f"qz_ans:{cid}:{i}")
                  for i, l in enumerate(LETTERS)]])
    await review_flow._edit_or_send(context, s, "\n".join(lines), kb)


def _thresholds(conn):
    return (float(db.get_setting(conn, "quiz_fast_sec")),
            float(db.get_setting(conn, "quiz_slow_sec")))


RATING_LABEL = {srs.AGAIN: "🔁 Lại", srs.HARD: "😓 Khó",
                srs.GOOD: "🙂 Tốt", srs.EASY: "😎 Dễ"}


async def _reveal(context, s, row, header, rating, extra_buttons=None):
    """Hiện mặt sau + lưu rating chờ áp ở qz_next."""
    conn = context.bot_data["conn"]
    s["q"] = {"kind": "reveal", "rating": rating}
    lines = [header, ""] + _back_lines(row)
    lines.append(f"\n({s['pos'] + 1}/{len(s['queue'])})")
    btns = (extra_buttons or []) + [Btn("▶️ Tiếp", callback_data=f"qz_next:{row['id']}")]
    await review_flow._edit_or_send(context, s, "\n".join(lines), Markup([btns]))
    await _send_back_aux(context, s, row)
    db.kv_set(conn, "session", s)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    s = db.kv_get(conn, "session")
    if not s:
        await q.edit_message_text("Phiên đã kết thúc. Gõ /on hoặc /luyen.")
        return
    parts = q.data.split(":")
    action, cid = parts[0], int(parts[1])
    if s["pos"] >= len(s["queue"]) or s["queue"][s["pos"]] != cid:
        return                                       # stale/double-tap
    row = cards.get_card(conn, cid)
    if row is None:
        await review_flow._clear_aux(context, s)
        db.kv_set(conn, "session", s)
        await review_flow.advance(context)
        return

    if action == "qz_ans":
        qst = s.get("q") or {}
        if qst.get("kind") != "mc":
            return
        idx = int(parts[2])
        correct = idx == qst["correct"]
        elapsed = time.time() - qst["asked_at"]
        fast, slow = _thresholds(conn)
        rating = grading.time_to_rating(correct, elapsed, s["level"], fast, slow)
        s["done"] += 1
        if correct:
            s["ok"] += 1
            header = f"✅ Đúng! ({elapsed:.0f}s → {RATING_LABEL[rating]})" \
                if not s["practice"] else "✅ Đúng!"
        else:
            right = html.escape(qst["options"][qst["correct"]])
            header = f"❌ Sai — đáp án: <b>{right}</b>"
        if s["practice"]:
            stats.bump_practice(conn, config.today_iso(), "mc", correct)
            rating = None
        await _reveal(context, s, row, header, rating)

    elif action == "qz_next":
        qst = s.get("q") or {}
        if qst.get("kind") != "reveal":
            return
        rating = qst.get("rating")
        if rating is not None and not s["practice"]:
            cards.apply_rating(conn, cid, rating, config.today())
            if rating == srs.AGAIN:
                s["queue"].append(cid)
        await review_flow._clear_aux(context, s)
        s["q"] = None
        db.kv_set(conn, "session", s)
        await review_flow.advance(context)
```

- [ ] **Step 2: Wiring `app/bot/main.py`** — thêm import `quiz_flow` vào khối import `app.bot`, và:

```python
app.add_handler(CallbackQueryHandler(quiz_flow.on_callback, pattern=r"^qz_"))
```

- [ ] **Step 3: Verify** — `python -m pytest tests/ -v`; offline build_app check (handler count tăng 1); REPL smoke: gọi `grading.shuffle_words(["a","b","c","d"], random.Random(1))` hợp lệ.
- [ ] **Step 4: Commit** — `git add -A && git commit -m "feat: MCQ questions in review session with timed auto-rating"`

---

### Task 9: Tự luận trong session (`quiz_flow` phần 2)

**Files:** Modify `app/bot/quiz_flow.py`, `app/bot/main.py`

**Interfaces:**
- Produces: `_show_typed` (đã gọi từ `show_question`); text action `"quiz_typed"` (`typed_input(update, context, pending, text)`); callback `qz_easy:<cid>` (nâng GOOD→EASY ở màn reveal); `s["q"]` typed: `{"kind":"typed","asked_at":float}`; pending_input `{"action":"quiz_typed","cid":cid}` đặt mỗi lần hiện câu.

- [ ] **Step 1: Thêm vào `app/bot/quiz_flow.py`:**

```python
async def _show_typed(context, s, row):
    conn = context.bot_data["conn"]
    s["q"] = {"kind": "typed", "asked_at": time.time()}
    db.kv_set(conn, "session", s)
    db.kv_set(conn, "pending_input", {"action": "quiz_typed", "cid": row["id"]})
    text = (f"🀄 <b>{html.escape(row['hanzi'])}</b>\n\n"
            f"⌨️ Gõ nghĩa tiếng Anh của từ này:\n\n({s['pos'] + 1}/{len(s['queue'])})")
    kb = Markup([[Btn("🔊 Nghe", callback_data=f"rv_listen:{row['id']}")]])
    await review_flow._edit_or_send(context, s, text, kb)


async def typed_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    cid = pending.get("cid")
    if (not s or s.get("mode") != "typed" or (s.get("q") or {}).get("kind") != "typed"
            or s["pos"] >= len(s["queue"]) or s["queue"][s["pos"]] != cid):
        return
    row = cards.get_card(conn, cid)
    if row is None:
        await review_flow.advance(context)
        return
    s["aux"].append(update.message.message_id)      # dọn tin trả lời khi sang câu
    verdict, note = grading.grade_typed_offline(row["meaning"], text), ""
    if verdict == "unsure":
        g = await gemini.judge_meaning(conn, row["hanzi"], row["meaning"], text)
        if g:
            verdict, note = g["verdict"], g["note"]
        else:
            verdict = grading.fallback_partial(row["meaning"], text)
    correct = verdict == "correct"
    s["done"] += 1
    extra = []
    if correct:
        s["ok"] += 1
        header, rating = "✅ Đúng!", srs.GOOD
        if not s["practice"]:
            extra = [Btn("😎 Dễ", callback_data=f"qz_easy:{cid}")]
    elif verdict == "partial":
        header, rating = "🟡 Đúng một phần.", srs.HARD
    else:
        header, rating = "❌ Chưa đúng.", srs.AGAIN
    if note:
        header += f"\n💡 {html.escape(note)}"
    if s["practice"]:
        stats.bump_practice(conn, config.today_iso(), "typed", correct)
        rating = None
    await _reveal(context, s, row, header, rating, extra_buttons=extra)
```

Và trong `on_callback`, thêm nhánh (cùng cấp `qz_ans`/`qz_next`):

```python
    elif action == "qz_easy":
        qst = s.get("q") or {}
        if qst.get("kind") != "reveal" or qst.get("rating") != srs.GOOD:
            return
        qst["rating"] = srs.EASY
        s["q"] = qst
        db.kv_set(conn, "session", s)
        await q.answer("😎 Sẽ tính là Dễ")
```

(lưu ý: nhánh này gọi `q.answer(...)` lần nữa với text — chấp nhận được, PTB cho phép; hoặc chuyển `await q.answer()` đầu hàm xuống từng nhánh — chọn cách nào cũng được, miễn không lỗi.)

- [ ] **Step 2: Wiring `main.py`** — thêm `register("quiz_typed", quiz_flow.typed_input)` cạnh các register khác.

- [ ] **Step 3: Dọn pending_input khi phiên kết thúc** — trong `review_flow.advance`, nhánh kết thúc (trước `db.kv_del(conn, "session")`), thêm:

```python
        pi = db.kv_get(conn, "pending_input")
        if pi and pi.get("action") == "quiz_typed":
            db.kv_del(conn, "pending_input")
```

- [ ] **Step 4: Verify** — `python -m pytest tests/ -v`; offline build_app; kiểm tra `textrouter.TEXT_ACTIONS` chứa `quiz_typed` sau import main.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: typed-answer questions with two-tier grading and Easy upgrade"`

---

### Task 10: `/luyen` menu + trắc nghiệm/tự luận tự do (`app/bot/practice_flow.py`)

**Files:** Create `app/bot/practice_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `review_flow.start_session(practice=True, queue=...)`, bảng cards/decks
- Produces: lệnh `/luyen`; callbacks `pr_menu`, `pr_quiz:<mc|typed>`, `pr_qd:<mode>:<deck_id>`, `pr_ql:<deck_id>:<level>` (level chỉ cho mc), `pr_dict`, `pr_build` (dict/build stub ở task này — Task 11/12 thay); text action + handlers đăng ký một lần tại đây.

- [ ] **Step 1: Viết `app/bot/practice_flow.py`:**

```python
import random

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import db
from app.bot import review_flow
from app.bot.auth import owner_only_callback

MENU = Markup([[Btn("🔘 Trắc nghiệm", callback_data="pr_quiz:mc"),
                Btn("⌨️ Tự luận", callback_data="pr_quiz:typed")],
               [Btn("✍️ Chép chính tả", callback_data="pr_dict"),
                Btn("🧩 Ghép câu", callback_data="pr_build")]])


async def cmd_practice(update, context):
    await update.message.reply_text(
        "🏋️ Luyện tự do (không ảnh hưởng lịch ôn). Chọn trò:", reply_markup=MENU)


def _practice_queue(conn, deck_id, n=10):
    where = "" if deck_id == 0 else "AND deck_id=?"
    args = () if deck_id == 0 else (deck_id,)
    rows = conn.execute(
        f"SELECT id FROM cards WHERE meaning<>'' {where}", args).fetchall()
    ids = [r["id"] for r in rows]
    random.shuffle(ids)
    return ids[:n]


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    data = q.data

    if data == "pr_menu":
        await q.edit_message_text("🏋️ Chọn trò:", reply_markup=MENU)

    elif data.startswith("pr_quiz:"):
        mode = data.split(":")[1]
        decks = conn.execute(
            "SELECT d.id, d.name, COUNT(c.id) n FROM decks d "
            "LEFT JOIN cards c ON c.deck_id=d.id AND c.meaning<>'' "
            "GROUP BY d.id ORDER BY d.id").fetchall()
        kb = [[Btn(f"Tất cả các bộ", callback_data=f"pr_qd:{mode}:0")]]
        kb += [[Btn(f"{d['name']} ({d['n']})", callback_data=f"pr_qd:{mode}:{d['id']}")]
               for d in decks if d["n"]]
        await q.edit_message_text("Luyện bộ nào?", reply_markup=Markup(kb))

    elif data.startswith("pr_qd:"):
        _, mode, deck_id = data.split(":")
        if mode == "typed":
            await _start_quiz(context, q, "typed", "", int(deck_id))
        else:
            kb = Markup([[Btn("😌 Dễ", callback_data=f"pr_ql:{deck_id}:easy"),
                          Btn("🙂 Thường", callback_data=f"pr_ql:{deck_id}:normal"),
                          Btn("🔥 Khó", callback_data=f"pr_ql:{deck_id}:hard")]])
            await q.edit_message_text("Chọn mức:", reply_markup=kb)

    elif data.startswith("pr_ql:"):
        _, deck_id, level = data.split(":")
        await _start_quiz(context, q, "mc", level, int(deck_id))

    elif data == "pr_dict":
        await q.edit_message_text("⚠️ Chép chính tả đang được xây.")   # Task 11 thay

    elif data == "pr_build":
        await q.edit_message_text("⚠️ Ghép câu đang được xây.")        # Task 12 thay


async def _start_quiz(context, q, mode, level, deck_id):
    conn = context.bot_data["conn"]
    queue = _practice_queue(conn, deck_id)
    if len(queue) < (4 if mode == "mc" else 1):
        await q.edit_message_text("⚠️ Chưa đủ thẻ có nghĩa trong phạm vi này.")
        return
    try:
        await q.message.delete()
    except Exception:
        pass
    await review_flow.start_session(context, q.message.chat_id, mode=mode,
                                    level=level, practice=True, queue=queue)
```

- [ ] **Step 2: Wiring `main.py`** — import `practice_flow`; thêm:

```python
app.add_handler(CommandHandler("luyen", practice_flow.cmd_practice, filters=owner_filter))
app.add_handler(CallbackQueryHandler(practice_flow.on_callback, pattern=r"^pr_"))
```

- [ ] **Step 3: Verify** — suite + offline build_app (handler +2).
- [ ] **Step 4: Commit** — `git add -A && git commit -m "feat: /luyen menu + free quiz sessions (no SRS impact)"`

---

### Task 11: Chép chính tả (`practice_flow` phần 2)

**Files:** Modify `app/bot/practice_flow.py`, `app/bot/main.py`

**Interfaces:**
- Consumes: `sentences.pick/mark_used/send_audio/maybe_refill/enrich_one`, `grading.normalize_hanzi/diff_chars`, `stats.bump_practice`
- Produces: kv `dict_state` = `{"sid": int, "tries": int, "chat": int, "aux": [msg_ids], "first_ok": bool}`; text action `"dictation"`; callbacks `pr_d_repeat`, `pr_d_next`, `pr_d_stop` (+ thay stub `pr_dict`).

- [ ] **Step 1: Thay stub `pr_dict` và thêm hàm.** Trong `practice_flow.py` thêm import `html`, `from app import config, gemini, grading, sentences, stats`, rồi:

```python
async def _dict_next(context, chat_id):
    conn = context.bot_data["conn"]
    await sentences.maybe_refill(conn)              # nạp thêm nếu sắp cạn (Gemini có thì chạy)
    srow = sentences.pick(conn, need_words=False)
    if not srow:
        await context.bot.send_message(
            chat_id, "⚠️ Kho câu trống. Thêm câu ví dụ vào thẻ (cột ví_dụ/ví_dụ_thêm "
                     "trong CSV) hoặc đặt Gemini API key trong /settings.")
        return
    aux = []
    m = await sentences.send_audio(context, chat_id, srow)
    if m is None:
        await context.bot.send_message(chat_id, "⚠️ Không tạo được audio (mạng?). Thử lại sau.")
        return
    aux.append(m.message_id)
    kb = Markup([[Btn("🔁 Nghe lại", callback_data="pr_d_repeat"),
                  Btn("⏭ Bỏ qua", callback_data="pr_d_next"),
                  Btn("🏁 Dừng", callback_data="pr_d_stop")]])
    m2 = await context.bot.send_message(
        chat_id, "🎧 Nghe và gõ lại câu (chữ Hán):", reply_markup=kb)
    aux.append(m2.message_id)
    db.kv_set(conn, "dict_state", {"sid": srow["id"], "tries": 0,
                                   "chat": chat_id, "aux": aux, "first_ok": False})
    db.kv_set(conn, "pending_input", {"action": "dictation"})
    sentences.mark_used(conn, srow["id"])


def _sentence_reveal(srow):
    lines = [f"🀄 {html.escape(srow['hanzi'])}"]
    if srow["pinyin"]:
        lines.append(f"📖 {html.escape(srow['pinyin'])}")
    if srow["meaning"]:
        lines.append(f"🇬🇧 {html.escape(srow['meaning'])}")
    return "\n".join(lines)


DICT_NEXT_KB = Markup([[Btn("▶️ Câu tiếp", callback_data="pr_d_next"),
                        Btn("🏁 Dừng", callback_data="pr_d_stop")]])


async def dictation_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    st = db.kv_get(conn, "dict_state")
    if not st:
        return
    srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
    if not srow:
        db.kv_del(conn, "dict_state")
        return
    expected = grading.normalize_hanzi(srow["hanzi"])
    got = grading.normalize_hanzi(text)
    if got == expected:
        stats.bump_practice(conn, config.today_iso(), "dict", st["tries"] == 0)
        db.kv_del(conn, "dict_state")
        await update.message.reply_html(
            "✅ <b>Chính xác!</b>\n" + _sentence_reveal(srow), reply_markup=DICT_NEXT_KB)
        return
    diff_html, ok, total = grading.diff_chars(expected, got)
    if st["tries"] == 0:
        st["tries"] = 1
        db.kv_set(conn, "dict_state", st)
        db.kv_set(conn, "pending_input", {"action": "dictation"})
        await update.message.reply_html(
            f"❌ {ok}/{total} ký tự đúng: {diff_html}\n✍️ Thử lại lần nữa nhé:")
    else:
        stats.bump_practice(conn, config.today_iso(), "dict", False)
        db.kv_del(conn, "dict_state")
        await update.message.reply_html(
            f"❌ {ok}/{total} ký tự đúng: {diff_html}\n\nĐáp án:\n"
            + _sentence_reveal(srow), reply_markup=DICT_NEXT_KB)
```

Trong `on_callback` thay nhánh `pr_dict` và thêm:

```python
    elif data == "pr_dict":
        try:
            await q.message.delete()
        except Exception:
            pass
        await _dict_next(context, q.message.chat_id)

    elif data == "pr_d_repeat":
        st = db.kv_get(conn, "dict_state")
        if st:
            srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
            if srow:
                await sentences.send_audio(context, st["chat"], srow)

    elif data == "pr_d_next":
        db.kv_del(conn, "dict_state")
        pi = db.kv_get(conn, "pending_input")
        if pi and pi.get("action") == "dictation":
            db.kv_del(conn, "pending_input")
        await _dict_next(context, q.message.chat_id)

    elif data == "pr_d_stop":
        db.kv_del(conn, "dict_state")
        pi = db.kv_get(conn, "pending_input")
        if pi and pi.get("action") == "dictation":
            db.kv_del(conn, "pending_input")
        await q.edit_message_text("🏁 Nghỉ chính tả. /luyen để chơi tiếp.")
```

- [ ] **Step 2: Wiring `main.py`** — `register("dictation", practice_flow.dictation_input)`.
- [ ] **Step 3: Verify** — suite + offline build_app; REPL: `grading.diff_chars("我在学习","我再学习")` cho kết quả như test Task 2.
- [ ] **Step 4: Commit** — `git add -A && git commit -m "feat: dictation practice with char diff and one retry"`

---

### Task 12: Ghép từ thành câu (`practice_flow` phần 3)

**Files:** Modify `app/bot/practice_flow.py`

**Interfaces:**
- Consumes: `sentences.pick(need_words=True)/mark_used/enrich_one/maybe_refill`, `grading.shuffle_words/normalize_hanzi`, `gemini.judge_word_order`, `stats.bump_practice`
- Produces: kv `build_state` = `{"sid": int, "words": [str], "perm": [int], "chosen": [int], "chat": int, "msg": int}`; callbacks `pr_build`, `pr_b_w:<i>`, `pr_b_undo`, `pr_b_sub`, `pr_b_skip`, `pr_b_next`, `pr_b_stop`.

- [ ] **Step 1: Thêm vào `practice_flow.py`** (import thêm `json`):

```python
async def _build_next(context, chat_id):
    conn = context.bot_data["conn"]
    await sentences.maybe_refill(conn)
    await sentences.enrich_one(conn)                 # tranh thủ tách từ 1 câu tồn đọng
    srow = sentences.pick(conn, need_words=True)
    if not srow:
        await context.bot.send_message(
            chat_id, "⚠️ Chưa có câu đã tách từ. Đặt Gemini API key trong /settings "
                     "để bot tự sinh/tách câu nhé.")
        return
    words = json.loads(srow["words_json"])
    perm = grading.shuffle_words(words, random.Random())
    st = {"sid": srow["id"], "words": words, "perm": perm, "chosen": [],
          "chat": chat_id, "msg": None}
    db.kv_set(conn, "build_state", st)
    sentences.mark_used(conn, srow["id"])
    await _build_render(context, st, srow)


def _build_kb(st):
    rows, row = [], []
    for i in st["perm"]:
        if i in st["chosen"]:
            continue
        row.append(Btn(st["words"][i], callback_data=f"pr_b_w:{i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Btn("↩️ Xóa từ cuối", callback_data="pr_b_undo"),
                 Btn("✅ Nộp", callback_data="pr_b_sub"),
                 Btn("⏭ Bỏ qua", callback_data="pr_b_skip")])
    return Markup(rows)


async def _build_render(context, st, srow):
    conn = context.bot_data["conn"]
    current = " ".join(st["words"][i] for i in st["chosen"]) or "…"
    text = (f"🧩 <b>Ghép các từ thành câu</b>\n"
            f"🇬🇧 {html.escape(srow['meaning']) if srow['meaning'] else '(không có gợi ý)'}\n\n"
            f"Câu của bạn: {html.escape(current)}")
    if st["msg"]:
        try:
            await context.bot.edit_message_text(text, chat_id=st["chat"],
                                                message_id=st["msg"],
                                                reply_markup=_build_kb(st),
                                                parse_mode="HTML")
            db.kv_set(conn, "build_state", st)
            return
        except Exception:
            pass
    m = await context.bot.send_message(st["chat"], text,
                                       reply_markup=_build_kb(st), parse_mode="HTML")
    st["msg"] = m.message_id
    db.kv_set(conn, "build_state", st)


BUILD_NEXT_KB = Markup([[Btn("▶️ Câu tiếp", callback_data="pr_b_next"),
                         Btn("🏁 Dừng", callback_data="pr_b_stop")]])
```

Và trong `on_callback` thay stub `pr_build` + thêm các nhánh:

```python
    elif data == "pr_build":
        try:
            await q.message.delete()
        except Exception:
            pass
        await _build_next(context, q.message.chat_id)

    elif data.startswith("pr_b_w:"):
        st = db.kv_get(conn, "build_state")
        if not st:
            return
        i = int(data.split(":")[1])
        if i in st["chosen"] or i not in st["perm"]:
            return
        st["chosen"].append(i)
        srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
        await _build_render(context, st, srow)

    elif data == "pr_b_undo":
        st = db.kv_get(conn, "build_state")
        if not st or not st["chosen"]:
            return
        st["chosen"].pop()
        srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
        await _build_render(context, st, srow)

    elif data == "pr_b_sub":
        st = db.kv_get(conn, "build_state")
        if not st:
            return
        srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
        if len(st["chosen"]) < len(st["words"]):
            await q.answer("Dùng hết các từ đã rồi nộp nhé!", show_alert=False)
            return
        attempt = "".join(st["words"][i] for i in st["chosen"])
        original = grading.normalize_hanzi(srow["hanzi"])
        db.kv_del(conn, "build_state")
        if attempt == original:
            ok, note = True, ""
        else:
            g = await gemini.judge_word_order(conn, srow["hanzi"],
                                              attempt, srow["meaning"])
            ok = bool(g and g["ok"])
            note = (g or {}).get("note", "")
        stats.bump_practice(conn, config.today_iso(), "build", ok)
        if ok and attempt == original:
            head = "✅ <b>Chính xác!</b>"
        elif ok:
            head = "✅ <b>Cũng đúng!</b> (trật tự thay thế hợp lệ)"
        else:
            head = "❌ Chưa đúng."
        if note:
            head += f"\n💡 {html.escape(note)}"
        await q.edit_message_text(
            head + "\n\n" + _sentence_reveal(srow),
            parse_mode="HTML", reply_markup=BUILD_NEXT_KB)

    elif data == "pr_b_skip":
        st = db.kv_get(conn, "build_state")
        db.kv_del(conn, "build_state")
        if st:
            srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
            if srow:
                await q.edit_message_text("⏭ Bỏ qua.\n\n" + _sentence_reveal(srow),
                                          parse_mode="HTML", reply_markup=BUILD_NEXT_KB)

    elif data == "pr_b_next":
        try:
            await q.message.delete()
        except Exception:
            pass
        await _build_next(context, q.message.chat_id)

    elif data == "pr_b_stop":
        db.kv_del(conn, "build_state")
        await q.edit_message_text("🏁 Nghỉ ghép câu. /luyen để chơi tiếp.")
```

- [ ] **Step 2: Verify** — suite + offline build_app.
- [ ] **Step 3: Commit** — `git add -A && git commit -m "feat: sentence-builder practice with tap-to-arrange and alt-order judging"`

---

### Task 13: Settings + /thongke + HELP + hoàn thiện

**Files:** Modify `app/bot/settings_flow.py`, `app/bot/misc.py`; docs `docs/superpowers/sdd/HANDOFF.md`

**Interfaces:**
- Produces: settings UI cho `gemini_api_key` (hiển thị che `AIza...****`), `gemini_model`, `quiz_fast_sec`/`quiz_slow_sec` (nhập "5,15"); text actions `set_gemkey`, `set_gmodel`, `set_quiztime`; `/thongke` thêm khối luyện tập 7 ngày; HELP thêm `/luyen`.

- [ ] **Step 1: `settings_flow.py`.** Trong `_view`, thêm 2 dòng hiển thị + 1 hàng nút:

```python
    key = db.get_setting(conn, "gemini_api_key")
    masked = (key[:4] + "..." + "*" * 4) if key else "(chưa đặt — chế độ offline)"
    # thêm vào chuỗi text:
    #  f"\n🤖 Gemini: {html.escape(masked)} · model {e('gemini_model')}\n"
    #  f"⏱ Ngưỡng trắc nghiệm: {e('quiz_fast_sec')}s / {e('quiz_slow_sec')}s"
    # thêm hàng nút:
    #  [Btn("🤖 Gemini key", callback_data="st_gemkey"), Btn("🧠 Model", callback_data="st_gmodel")],
    #  [Btn("⏱ Ngưỡng giờ quiz", callback_data="st_quiztime")],
```

Trong `on_callback` thêm 3 nhánh đặt `pending_input` với prompt:
- `st_gemkey` → `{"action": "set_gemkey"}`, prompt: `"Dán Gemini API key (tạo miễn phí tại aistudio.google.com), hoặc gõ off để xóa:"`
- `st_gmodel` → `{"action": "set_gmodel"}`, prompt: `"Nhập tên model (mặc định gemini-2.5-flash):"`
- `st_quiztime` → `{"action": "set_quiztime"}`, prompt: `"Nhập 2 số giây fast,slow (VD: 5,15):"`

Và 3 input handler:

```python
async def gemkey_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    v = text.strip()
    db.set_setting(conn, "gemini_api_key", "" if v.lower() == "off" else v)
    try:
        await update.message.delete()       # không để key nằm lại trong chat
    except Exception:
        pass
    await update.message.chat.send_message(
        "✅ Đã cập nhật Gemini API key." if v.lower() != "off" else "✅ Đã xóa key — chạy offline.")


async def gmodel_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    db.set_setting(conn, "gemini_model", text.strip() or "gemini-2.5-flash")
    await update.message.reply_text(f"✅ Model: {text.strip() or 'gemini-2.5-flash'}")


async def quiztime_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 2 or not all(p.isdigit() for p in parts) \
            or not (0 < int(parts[0]) < int(parts[1]) <= 120):
        await update.message.reply_text("⚠️ Nhập dạng fast,slow (0 < fast < slow ≤ 120). VD: 5,15")
        return
    db.set_setting(conn, "quiz_fast_sec", parts[0])
    db.set_setting(conn, "quiz_slow_sec", parts[1])
    await update.message.reply_text(f"✅ Ngưỡng: {parts[0]}s / {parts[1]}s")
```

- [ ] **Step 2: `misc.py`.** HELP thêm dòng `"• /luyen — trắc nghiệm, chính tả, ghép câu (không tính lịch ôn)\n"`. `cmd_stats` thêm sau dòng tỉ lệ nhớ:

```python
    from datetime import timedelta
    since = (config.today() - timedelta(days=6)).isoformat()
    p = stats.practice_summary(conn, since)
    if p:
        label = {"mc": "🔘 Trắc nghiệm", "typed": "⌨️ Tự luận",
                 "dict": "✍️ Chính tả", "build": "🧩 Ghép câu"}
        extra = "\n🏋️ <b>Luyện tập 7 ngày:</b>\n" + "\n".join(
            f"  {label.get(m, m)}: {c}/{a} đúng" for m, (a, c) in sorted(p.items()))
        # nối extra vào chuỗi reply
```

- [ ] **Step 3: Wiring `main.py`** — `register("set_gemkey", settings_flow.gemkey_input)`, `register("set_gmodel", settings_flow.gmodel_input)`, `register("set_quiztime", settings_flow.quiztime_input)`.

- [ ] **Step 4: Verify tổng** — `python -m pytest tests/ -v` toàn xanh; offline build_app đếm handler; cập nhật `docs/superpowers/sdd/HANDOFF.md` (trạng thái: practice modes đã code xong, chờ test tay + `fly deploy`).

- [ ] **Step 5: Kịch bản test tay (chạy sau khi deploy, cần chủ dự án):**
1. `/settings` → đặt Gemini key → hiển thị che key.
2. `/on` → picker 3 chế độ; chọn Trắc nghiệm Khó → 4 đáp án có bẫy; trả lời nhanh <5s → reveal ghi 😎 Dễ; bấm Tiếp.
3. `/on` → Tự luận → gõ đúng lời khác ("study hard") → Gemini chấm partial/correct kèm note; nút 😎 Dễ hoạt động.
4. Sai ở MCQ → thẻ quay lại cuối phiên (AGAIN requeue).
5. `/luyen` → Trắc nghiệm tự do → kết thúc hiện "Đúng x/y", `/thongke` có khối luyện tập; lịch SM-2 của thẻ KHÔNG đổi (check /tim).
6. `/luyen` → Chính tả: nghe lại nhiều lần, gõ sai 1 ký tự → diff + thử lại; câu do Gemini sinh chỉ dùng từ đã học.
7. `/luyen` → Ghép câu: bấm từ, undo, nộp thiếu từ bị nhắc, nộp trật tự khác được Gemini phán "Cũng đúng!" khi hợp lệ.
8. Xóa Gemini key (`off`) → mọi thứ vẫn chạy: MCQ dễ/khó (đồng âm), tự luận fallback, chính tả từ câu ví dụ; ghép câu báo thiếu câu tách từ nếu kho chưa có.
9. Restart bot giữa câu hỏi → /on tiếp tục, câu hiện lại, đồng hồ tính lại.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: settings for gemini/thresholds, practice stats, help; handoff update"`

---

## Self-Review Notes

- Spec coverage: §3 modes+/luyen (T7,8,9,10), §4 MCQ+nhiễu 3 mức+cache (T4,8), §5 tự luận 2 tầng (T2,3,9), §6 kho câu+cap+audio cleanup (T5), §7 chính tả (T11), §8 ghép câu (T12), §9 CSV (T6), §10 gemini module (T3), §11 bảng/settings/thongke (T1,13), §12 lỗi (fallback mọi task, guard theo pattern cũ), §13 test (T1-6 unit, T13 kịch bản tay).
- Callback prefix: `qz_`, `pr_` mới; `rv_mode`/`rv_mc_levels` dưới `^rv_` sẵn có — không cần thêm handler.
- Type-consistency đã rà: `grading.shuffle_words` dùng cho cả MCQ (4 options) lẫn builder; `sentences.pick(need_words)` bool; `stats.bump_practice(mode)` nhận `"mc"|"typed"|"dict"|"build"`.
- Lưu ý cho implementer T8: `quiz_flow` import `review_flow` (một chiều — `review_flow` chỉ import `quiz_flow` cục bộ trong `_show_front`), tránh vòng import.
- Stub `pr_dict`/`pr_build` ở T10 bị thay ở T11/T12 — reviewer T10 đừng coi stub là thiếu sót (plan chủ đích).
```
