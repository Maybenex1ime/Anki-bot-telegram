### Task 1: langpack + route toàn bộ `zh` qua nó (khóa hành vi)

**Files:**
- Create: `app/langpack.py`
- Modify: `app/config.py`, `app/lookup.py`, `app/quiz.py`, `app/grading.py`
- Test: `tests/test_langpack.py` (mới) + toàn bộ suite cũ phải xanh

**Interfaces:**
- Produces:
  - `langpack.LANGS: dict[str, dict]` — mỗi gói có khóa: `display_name, romanize(str)->str, phonetic_key(str)->str, normalize_text(str)->str, tts_voice, gemini_name, function_words, dict_url, dict_file, parse_dict(path)->list[tuple]`
  - `langpack.get(lang) -> dict` — trả `LANGS[lang]`, raise `ValueError` nếu không có
  - `config.LANG: str` (từ env, default `"zh"`), `config.PACK: dict` (= `langpack.get(config.LANG)`)
  - Các hàm cũ giữ chữ ký, đổi ruột: `lookup.gen_pinyin(text)`, `lookup.ensure_cedict(conn)`, `quiz.pinyin_key(s)`, `grading.normalize_hanzi(s)`

- [ ] **Step 1: Viết `app/langpack.py`** (chỉ gói `zh` ở task này; `ko` ở Task 2):

```python
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
```

- [ ] **Step 2: Sửa `app/config.py`** — thêm `LANG`/`PACK`, lấy `tts_voice` từ PACK, bỏ `CEDICT_URL` cứng:

```python
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app import langpack

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DB_PATH = DATA_DIR / "reminder.db"
MEDIA_DIR = DATA_DIR / "media"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
LANG = os.environ.get("LANG", "zh")
PACK = langpack.get(LANG)
DEFAULT_SETTINGS = {
    "reminder_times": "07:30,12:30,20:00",
    "evening_nudge": "21:30",
    "new_per_day": "20",
    "tts_voice": PACK["tts_voice"],
    "review_mode": "",
    "quiz_fast_sec": "5",
    "quiz_slow_sec": "15",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "max_sentences": "3000",
}


def today():
    return datetime.now(TZ).date()


def today_iso():
    return today().isoformat()
```

> ⚠️ `LANG` là một biến môi trường phổ biến của Linux (locale, VD `en_US.UTF-8`). Trên máy/agent có thể đã set sẵn → `langpack.get` raise. Xử lý: trong Dockerfile/fly ta set `LANG=zh`/`ko` tường minh (locale không dùng tới ở app này). Để test cục bộ không vỡ vì locale hệ thống, **Step 2 dùng khóa riêng**: đổi `os.environ.get("LANG", "zh")` thành `os.environ.get("BOT_LANG", "zh")`. Cập nhật mọi chỗ nhắc `LANG` trong plan/spec/runbook thành `BOT_LANG`.

- [ ] **Step 2b: Áp cảnh báo trên** — dùng `BOT_LANG` (không phải `LANG`) ở `config.py` và toàn bộ runbook Task 4.

- [ ] **Step 3: Sửa `app/lookup.py`** — ruột đọc PACK, tên hàm giữ nguyên:

```python
import urllib.request

from app import config

# parse_cedict_line giữ lại cho test_lookup (parser zh, không đổi hành vi)
_CEDICT_LINE = config  # placeholder tránh unused; xem dưới
```

Thay thân file bằng:

```python
import urllib.request

from app import config, langpack


def gen_pinyin(text: str) -> str:
    return config.PACK["romanize"](text)


def parse_cedict_line(line):
    # Giữ cho test_lookup — là parser dòng CC-CEDICT (zh). Ủy cho langpack regex.
    if line.startswith("#"):
        return None
    m = langpack._CEDICT_LINE.match(line.strip())
    if not m:
        return None
    trad, simp, pin, meaning = m.groups()
    return simp, trad, pin, "; ".join(meaning.split("/"))


def ensure_cedict(conn) -> int:
    if conn.execute("SELECT COUNT(*) c FROM dict_entries").fetchone()["c"] > 0:
        return 0
    pack = config.PACK
    path = config.DATA_DIR / pack["dict_file"]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(pack["dict_url"], path)
    rows = pack["parse_dict"](path)
    conn.executemany("INSERT INTO dict_entries VALUES(?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def lookup_meaning(conn, hanzi: str) -> str:
    rows = conn.execute(
        "SELECT meaning FROM dict_entries WHERE simplified=? OR traditional=? LIMIT 3",
        (hanzi, hanzi)).fetchall()
    return " | ".join(r["meaning"] for r in rows)
```

(Bỏ dòng `_CEDICT_LINE = config` placeholder — đó chỉ để minh hoạ; bản cuối chỉ có 4 hàm trên.)

- [ ] **Step 4: Sửa `app/quiz.py`** — `pinyin_key` ủy cho PACK:

```python
def pinyin_key(pinyin):
    return config.PACK["phonetic_key"](pinyin)
```

Thêm `from app import config` (đã import `gemini, grading` — thêm `config`). Xóa `import unicodedata` nếu không còn dùng chỗ khác (kiểm tra: chỉ `pinyin_key` dùng → xóa được).

- [ ] **Step 5: Sửa `app/grading.py`** — `normalize_hanzi` ủy cho PACK:

```python
def normalize_hanzi(s):
    return config.PACK["normalize_text"](s)
```

Thêm `from app import config`. Xóa hằng `_HANZI_PUNCT` (chuyển sang langpack rồi). Giữ nguyên mọi hàm khác (`normalize_meaning`, `meaning_variants`, `time_to_rating`, `diff_chars`...).

- [ ] **Step 6: Viết `tests/test_langpack.py`**:

```python
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
```

- [ ] **Step 7: Chạy TOÀN BỘ suite** — `python -m pytest tests/ -v`. Expected: 58 test cũ + 3 mới = **61 passed**. Nếu bất kỳ test `zh` cũ nào đỏ → hành vi đã đổi, sửa lại delegation cho khớp, KHÔNG sửa test.

- [ ] **Step 8: Offline build check** — `$env:BOT_TOKEN='123:dummy'; $env:OWNER_ID='1'; python -c "from app.bot.main import build_app; build_app()"` không lỗi.

- [ ] **Step 9: Commit** — `git add -A && git commit -m "refactor: extract language pack, route zh through it (behavior unchanged)"`

---

