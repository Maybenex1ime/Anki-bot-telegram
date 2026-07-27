import pytest

from app import langpack


def test_zh_pack_present_and_shaped():
    zh = langpack.get("zh")
    assert zh["display_name"] == "tiếng Trung"
    assert zh["romanize"]("学习") == "xué xí"
    assert zh["phonetic_key"]("xué xí") == "xuexi"
    assert zh["normalize_text"]("我在 学习。") == "我在学习"
    assert zh["tts_voice"] == "zh-CN-XiaoxiaoNeural"
    assert zh["gemini_name"] == "Chinese"


def test_get_invalid_lang_raises():
    with pytest.raises(ValueError):
        langpack.get("xx")


def test_config_defaults_to_zh(monkeypatch):
    monkeypatch.delenv("BOT_LANG", raising=False)
    import importlib

    from app import config
    importlib.reload(config)
    assert config.LANG == "zh"
    assert config.PACK["gemini_name"] == "Chinese"
    assert config.DEFAULT_SETTINGS["tts_voice"] == "zh-CN-XiaoxiaoNeural"
