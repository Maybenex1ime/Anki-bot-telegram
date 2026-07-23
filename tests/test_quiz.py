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


async def test_negative_cache_no_rederive(conn, monkeypatch):
    calls = {"n": 0}

    async def counting_gemini(*a, **k):
        calls["n"] += 1
        return None

    monkeypatch.setattr("app.quiz.gemini.make_distractors", counting_gemini)
    row = (await _seed(conn, 1))[0]

    assert await quiz.get_options(conn, row, "easy") is None
    # negative cache persisted as "[]"
    cached = conn.execute(
        "SELECT options_json FROM distractors WHERE card_id=? AND level=?",
        (row["id"], "easy")).fetchone()
    assert cached is not None
    assert cached["options_json"] == "[]"

    # second call hits cache, does NOT re-derive
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
