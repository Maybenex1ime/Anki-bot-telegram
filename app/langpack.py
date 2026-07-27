import gzip
import re
import unicodedata

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
}


def get(lang):
    if lang not in LANGS:
        raise ValueError(f"LANG không hợp lệ: {lang!r} (có: {sorted(LANGS)})")
    return LANGS[lang]
