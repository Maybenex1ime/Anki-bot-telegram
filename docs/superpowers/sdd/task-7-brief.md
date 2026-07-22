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

