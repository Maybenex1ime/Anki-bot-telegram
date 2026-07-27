import gzip
import re
import unicodedata

import yaml
from korean_romanizer.romanizer import Romanizer
from pypinyin import Style, pinyin

_CEDICT_LINE = re.compile(r"^(\S+) (\S+) \[([^\]]+)\] /(.+)/\s*$")
_ZH_PUNCT = "。，！？、；：“”‘’…·.,!?;:'\"()（）"


def _zh_romanize(text):
    return " ".join(p[0] for p in pinyin(text, style=Style.TONE))


def _zh_phonetic_key(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if c.isascii() and c.isalpha())


def _make_normalize(punct):
    def normalize_text(s):
        return "".join(c for c in s if not c.isspace() and c not in punct)
    return normalize_text


def _parse_cedict(path):
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            m = _CEDICT_LINE.match(line.strip())
            if not m:
                continue
            trad, simp, pin, meaning = m.groups()
            rows.append((simp, trad, pin, "; ".join(meaning.split("/"))))
    return rows


_KO_PUNCT = "。，！？、；：“”‘’…·.,!?;:'\"()（）~"


def _ko_romanize(text):
    try:
        return Romanizer(text).romanize()
    except Exception:
        return text  # ký tự lạ (Hán tự lẫn, số) → trả nguyên văn, không chặn


def _ko_phonetic_key(s):
    return "".join(c for c in s.lower() if c.isascii() and c.isalpha())


def _parse_kedict(path):
    # cc-kedict phát hành kedict.yml KHÔNG nén (.gz là 404) → open thường
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    rows = []
    for e in data or []:
        word = str(e.get("word", "")).strip()
        if not word:
            continue
        romaja = str(e.get("romaja", ""))
        defs = [str(d.get("def", "")).strip().lstrip(":").strip()
                for d in e.get("defs", []) if d.get("def")]
        meaning = "; ".join(d for d in defs if d)
        rows.append((word, word, romaja, meaning))
    return rows


LANGS = {
    "zh": {
        "display_name": "tiếng Trung",
        "romanize": _zh_romanize,
        "phonetic_key": _zh_phonetic_key,
        "normalize_text": _make_normalize(_ZH_PUNCT),
        "tts_voice": "zh-CN-XiaoxiaoNeural",
        "gemini_name": "Chinese",
        "function_words": "的了吗在是我你他她们不很和有个这那",
        "dict_url": "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz",
        "dict_file": "cedict.txt.gz",
        "parse_dict": _parse_cedict,
    },
    "ko": {
        "display_name": "tiếng Hàn",
        "romanize": _ko_romanize,
        "phonetic_key": _ko_phonetic_key,
        "normalize_text": _make_normalize(_KO_PUNCT),
        "tts_voice": "ko-KR-SunHiNeural",
        "gemini_name": "Korean",
        "function_words": "은 는 이 가 을 를 에 에서 와 과 도 만 의 로 으로",
        "dict_url": "https://github.com/mhagiwara/cc-kedict/raw/master/kedict.yml",
        "dict_file": "kedict.yml",
        "parse_dict": _parse_kedict,
    },
}


def get(lang):
    if lang not in LANGS:
        raise ValueError(f"LANG không hợp lệ: {lang!r} (có: {sorted(LANGS)})")
    return LANGS[lang]
