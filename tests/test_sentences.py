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
