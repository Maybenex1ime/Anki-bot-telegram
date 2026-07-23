from datetime import date

import pytest

from app import cards, config, db, srs, stats


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
    today = config.today()
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
