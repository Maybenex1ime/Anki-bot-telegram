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
    assert zh["script_range"] == "一-鿿"


def test_get_invalid_lang_raises():
    with pytest.raises(ValueError):
        langpack.get("xx")


def test_ko_pack_romanize_and_normalize():
    ko = langpack.get("ko")
    assert ko["display_name"] == "tiếng Hàn"
    assert ko["romanize"]("안녕") == "annyeong"
    # normalize xóa khoảng trắng + dấu câu, giữ Hangul
    assert ko["normalize_text"]("안녕 하세요.") == "안녕하세요"
    assert ko["phonetic_key"]("an nyeong") == "annyeong"
    assert ko["tts_voice"] == "ko-KR-SunHiNeural"
    assert ko["gemini_name"] == "Korean"
    assert ko["script_range"] == "가-힣"


def test_ko_parse_kedict(tmp_path):
    # cc-kedict phát hành file KHÔNG nén (kedict.yml) — fixture cũng plain
    p = tmp_path / "kedict.yml"
    p.write_text(
        "- word: 가\n"
        "  romaja: ga\n"
        "  pos: n\n"
        "  defs:\n"
        "    - def: \"edge, side\"\n"
        "    - def: \"price\"\n"
        "- word: 학교\n"
        "  romaja: hakgyo\n"
        "  pos: n\n"
        "  defs:\n"
        "    - def: \"school\"\n",
        encoding="utf-8",
    )
    rows = langpack.get("ko")["parse_dict"](p)
    # mỗi entry -> 1 row (simplified=traditional=word, pinyin=romaja, meaning=nối defs)
    assert ("학교", "학교", "hakgyo", "school") in rows
    ga = [r for r in rows if r[0] == "가"][0]
    assert ga[2] == "ga" and "edge, side" in ga[3] and "price" in ga[3]


def test_config_defaults_to_zh(monkeypatch):
    monkeypatch.delenv("BOT_LANG", raising=False)
    import importlib

    from app import config
    importlib.reload(config)
    assert config.LANG == "zh"
    assert config.PACK["gemini_name"] == "Chinese"
    assert config.DEFAULT_SETTINGS["tts_voice"] == "zh-CN-XiaoxiaoNeural"
