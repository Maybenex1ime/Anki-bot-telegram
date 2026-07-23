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

