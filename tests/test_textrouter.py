from app import langpack
from app.bot import textrouter


def test_detection_is_pack_driven_zh(monkeypatch):
    # default config = zh: Hán tự là "từ", Latin thì không
    monkeypatch.setattr("app.config.PACK", langpack.get("zh"))
    assert textrouter.looks_like_word("学习") is True
    assert textrouter.looks_like_word("hello") is False


def test_detection_is_pack_driven_ko(monkeypatch):
    # ko pack: Hangul là "từ" (Hán tự thì không)
    monkeypatch.setattr("app.config.PACK", langpack.get("ko"))
    assert textrouter.looks_like_word("안녕") is True
    assert textrouter.looks_like_word("hello") is False
