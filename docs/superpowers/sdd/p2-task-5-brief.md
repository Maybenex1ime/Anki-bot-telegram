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

