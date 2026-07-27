# Korean Language Pack — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Model policy (user requirement):** dispatch implementation subagents with **model Opus**.

**Goal:** Tách phần đặc thù ngôn ngữ vào một `app/langpack.py` chọn theo env `LANG`, giữ bot tiếng Trung chạy y hệt, rồi thêm gói tiếng Hàn + dựng Fly app thứ hai.

**Architecture:** Một `langpack.LANGS[lang]` gói 8 thứ đặc thù ngôn ngữ (tên hiển thị, romanize, phonetic_key, normalize_text, tts_voice, gemini_name, function_words, dict spec). `config.py` đọc `LANG` (default `zh`) → expose `config.PACK`. Năm điểm hard-code cũ (`lookup`, `quiz`, `grading`, `gemini`, `config`) đọc `config.PACK` thay vì hằng cứng — **giữ nguyên tên hàm public** nên 58 test hiện có vẫn xanh = khóa hành vi `zh`.

**Tech Stack:** Python 3.12, `korean-romanizer`, `PyYAML` (parse CC-KEDICT), edge-tts, pytest.

**Spec:** `docs/superpowers/specs/2026-07-27-korean-language-pack-design.md`
**Code nền:** branch `feature/srs-bot` — bot `reminder-zh-bot` đang chạy dữ liệu thật.

## Global Constraints

- Refactor `zh` phải **không đổi hành vi**: 58 test hiện có phải xanh sau mỗi task (đây là lưới an toàn — không cần viết lại test khóa hành vi mới cho `zh`, các test `test_lookup/test_grading/test_quiz` đã khóa sẵn).
- **Không đụng schema DB, không migration** — `LANG` chỉ ảnh hưởng code xử lý. Bảng `dict_entries(simplified, traditional, pinyin, meaning)` dùng lại cho cả `ko` (với ko: `simplified=traditional=từ Hàn`, `pinyin=romaja`).
- Giữ nguyên tên hàm public: `lookup.gen_pinyin`, `lookup.ensure_cedict`, `lookup.lookup_meaning`, `quiz.pinyin_key`, `grading.normalize_hanzi` — chỉ đổi ruột. (Tên vẫn mang chữ "pinyin/hanzi/cedict" dù giờ đa ngôn ngữ — chấp nhận, đổi tên tốn diff vô ích.)
- `LANG` mặc định `zh`; `LANG` không có trong `LANGS` → raise lúc import (fail fast).
- `langpack.py` KHÔNG import `config` (tránh vòng import) — nó là dữ liệu + hàm thuần; `config` import `langpack`.
- Mọi chuỗi hiển thị tiếng Việt; giá trị người dùng/dịch vụ chèn vào HTML vẫn `html.escape` như cũ.
- Test: `python -m pytest tests/ -v` từ gốc repo. Deps mới cài: `python -m pip install -r requirements-dev.txt`.
- Commit sau mỗi task.

## File Structure

```
app/langpack.py   # MỚI: LANGS dict (zh + ko), get(lang), 2 dict parser
app/config.py     # SỬA: đọc LANG env → config.PACK = langpack.LANGS[LANG]; DEFAULT_SETTINGS.tts_voice từ PACK; bỏ CEDICT_URL cứng
app/lookup.py     # SỬA: gen_pinyin→PACK romanize; ensure_cedict đọc dict spec từ PACK; parse_cedict_line giữ nguyên (là parser zh)
app/quiz.py       # SỬA: pinyin_key→PACK phonetic_key
app/grading.py    # SỬA: normalize_hanzi→PACK normalize_text
app/gemini.py     # SỬA: 5 prompt dùng PACK gemini_name + function_words
app/bot/misc.py   # SỬA: HELP dùng PACK display_name
requirements.txt  # SỬA: +korean-romanizer, +PyYAML
docs/DEPLOY-ko.md # MỚI: runbook dựng reminder-ko-bot
```

---

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

### Task 2: Gói tiếng Hàn trong langpack

**Files:** Modify `app/langpack.py`, `requirements.txt`; Test `tests/test_langpack.py` (thêm)

**Interfaces:**
- Consumes: cấu trúc gói ở Task 1
- Produces: `langpack.LANGS["ko"]` đầy đủ 10 khóa; `_parse_kedict(path)` trả `list[(word, word, romaja, meaning)]`

- [ ] **Step 1: Thêm deps** vào `requirements.txt`:

```
korean-romanizer>=0.25
PyYAML>=6
```

Cài: `python -m pip install -r requirements.txt`.

- [ ] **Step 2: Viết test (fail trước)** — thêm vào `tests/test_langpack.py`:

```python
def test_ko_pack_romanize_and_normalize():
    ko = langpack.get("ko")
    assert ko["display_name"] == "tiếng Hàn"
    assert ko["romanize"]("안녕") == "annyeong"
    # normalize xóa khoảng trắng + dấu câu, giữ Hangul
    assert ko["normalize_text"]("안녕 하세요.") == "안녕하세요"
    assert ko["phonetic_key"]("an nyeong") == "annyeong"
    assert ko["tts_voice"] == "ko-KR-SunHiNeural"
    assert ko["gemini_name"] == "Korean"


def test_ko_parse_kedict(tmp_path):
    import gzip
    p = tmp_path / "kedict.yml.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(
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
            "    - def: \"school\"\n")
    rows = langpack.get("ko")["parse_dict"](p)
    # mỗi entry -> 1 row (simplified=traditional=word, pinyin=romaja, meaning=nối defs)
    assert ("학교", "학교", "hakgyo", "school") in rows
    ga = [r for r in rows if r[0] == "가"][0]
    assert ga[2] == "ga" and "edge, side" in ga[3] and "price" in ga[3]
```

- [ ] **Step 3: Run FAIL** — `python -m pytest tests/test_langpack.py -v` (KeyError 'ko').

- [ ] **Step 4: Implement** — thêm vào `app/langpack.py`:

Thêm import đầu file: `from korean_romanizer.romanizer import Romanizer` và `import yaml`. (Nếu import path của lib khác, kiểm tra `python -c "from korean_romanizer.romanizer import Romanizer; print(Romanizer('안녕').romanize())"` → `annyeong`; điều chỉnh import cho khớp package thực tế.)

```python
_KO_PUNCT = "。，！？、；：“”‘’…·.,!?;:'\"()（）~"


def _ko_romanize(text):
    try:
        return Romanizer(text).romanize()
    except Exception:
        return text  # ký tự lạ (Hán tự lẫn, số) → trả nguyên văn, không chặn


def _ko_phonetic_key(s):
    return "".join(c for c in s.lower() if c.isascii() and c.isalpha())


def _parse_kedict(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
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
```

Thêm entry `"ko"` vào `LANGS`:

```python
    "ko": {
        "display_name": "tiếng Hàn",
        "romanize": _ko_romanize,
        "phonetic_key": _ko_phonetic_key,
        "normalize_text": _make_normalize(_KO_PUNCT),
        "tts_voice": "ko-KR-SunHiNeural",
        "gemini_name": "Korean",
        "function_words": "은 는 이 가 을 를 에 에서 와 과 도 만 의 로 으로",
        "dict_url": "https://github.com/mhagiwara/cc-kedict/raw/master/kedict.yml.gz",
        "dict_file": "kedict.yml.gz",
        "parse_dict": _parse_kedict,
    },
```

> Nếu URL `kedict.yml.gz` không tồn tại (repo chỉ có `kedict.yml` chưa nén): đổi `dict_file` thành `kedict.yml`, `dict_url` trỏ file thô, và `_parse_kedict` mở bằng `open(path, encoding="utf-8")` thay vì `gzip.open`. Kiểm tra bằng `curl -sI <url>` trước khi chốt; điều chỉnh cho khớp thực tế (test dùng fixture .gz nên không phụ thuộc mạng — chỉ ensure_cedict lúc boot mới tải thật).

- [ ] **Step 5: Run PASS** — `python -m pytest tests/ -v` (61 + 2 = 63 passed).
- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: Korean language pack (romanizer + cc-kedict parser + ko voice)"`

---

### Task 3: Gemini prompt + chuỗi hiển thị theo ngôn ngữ

**Files:** Modify `app/gemini.py`, `app/bot/misc.py`; Test `tests/test_gemini.py` (thêm)

**Interfaces:**
- Consumes: `config.PACK["gemini_name"]`, `config.PACK["function_words"]`, `config.PACK["display_name"]`

- [ ] **Step 1: Viết test (fail trước)** — thêm vào `tests/test_gemini.py` (mock sẵn có, chỉ kiểm prompt mang tên ngôn ngữ đúng). Dùng fixture `conn` có sẵn; bắt prompt bằng cách chặn `ask_json`:

```python
async def test_prompt_uses_pack_language_name(conn, monkeypatch):
    seen = {}

    async def fake_ask(conn_, prompt):
        seen["p"] = prompt
        return {"options": ["a", "b", "c"]}

    monkeypatch.setattr(gemini, "ask_json", fake_ask)
    await gemini.make_distractors(conn, "学习", "to learn", "normal")
    assert "Chinese" in seen["p"]
```

- [ ] **Step 2: Run FAIL** (prompt hiện ghi "tiếng Trung", chưa có "Chinese").

- [ ] **Step 3: Sửa `app/gemini.py`** — thêm `from app import config` (nếu chưa) và thay tên ngôn ngữ cứng trong 5 prompt bằng `config.PACK["gemini_name"]`, danh sách từ chức năng bằng `config.PACK["function_words"]`. Cụ thể:

`make_distractors`:
```python
async def make_distractors(conn, hanzi, meaning, level):
    lang = config.PACK["gemini_name"]
    kind = (f"an English meaning in the same topic but WRONG"
            if level == "normal"
            else "an English meaning VERY CLOSE to the correct one but WRONG (near-synonym trap)")
    data = await ask_json(conn, (
        f"{lang} word: {hanzi}\nCorrect English meaning: {meaning}\n"
        f"Generate exactly 3 distractors, each {kind}, short dictionary style.\n"
        'Return JSON: {"options": ["...", "...", "..."]}'))
    if not isinstance(data, dict) or not isinstance(data.get("options"), list):
        return None
    opts = [str(o).strip()[:80] for o in data["options"] if str(o).strip()][:3]
    return opts if len(opts) == 3 else None
```

`judge_meaning`:
```python
    lang = config.PACK["gemini_name"]
    data = await ask_json(conn, (
        f'{lang} word: {hanzi}. Correct English meaning: "{meaning}". '
        f'Learner answered: "{answer}".\n'
        "Grade verdict: correct (right or equivalent), partial, wrong.\n"
        'Return JSON: {"verdict": "...", "note": "one short note in Vietnamese"}'))
```

`gen_sentences`:
```python
    lang = config.PACK["gemini_name"]
    fw = config.PACK["function_words"]
    data = await ask_json(conn, (
        f"Generate {n} short {lang} sentences (4-10 words), using ONLY the words below "
        f"plus basic function words ({fw}):\n"
        + "、".join(vocab[:300]) + "\n"
        'Return JSON: {"sentences": [{"hanzi": "...", "words": ["tokenized"], '
        '"pinyin": "romanization", "meaning": "English translation"}]}'))
```
(giữ khóa JSON `hanzi`/`pinyin` để không phải đổi `sentences.py` — chúng chỉ là tên trường, ko vẫn điền chữ Hàn vào `hanzi`, romaja vào `pinyin`.)

`segment_translate`:
```python
    lang = config.PACK["gemini_name"]
    data = await ask_json(conn, (
        f"{lang} sentence: {hanzi}\nTokenize into words and translate to English.\n"
        'Return JSON: {"words": ["tokenized"], "pinyin": "romanization", "meaning": "..."}'))
```

`judge_word_order`:
```python
    lang = config.PACK["gemini_name"]
    data = await ask_json(conn, (
        f"Original sentence: {original}\nMeaning: {meaning}\nLearner arranged: {attempt}\n"
        f"Is the arrangement grammatical {lang} with the same meaning?\n"
        'Return JSON: {"ok": true/false, "note": "one short note in Vietnamese"}'))
```

- [ ] **Step 4: Sửa `app/bot/misc.py`** — dòng tiêu đề HELP dùng tên ngôn ngữ động:

```python
from app import config, stats

HELP = (
    f"🀄 <b>Bot học {config.PACK['display_name']} SRS</b>\n\n"
    ...
```
(giữ nguyên phần còn lại của HELP.)

- [ ] **Step 5: Run PASS** — `python -m pytest tests/ -v` (63 + 1 = 64 passed).
- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: gemini prompts and help title driven by language pack"`

---

### Task 4: Redeploy bot Trung + dựng bot Hàn

**Files:** Create `docs/DEPLOY-ko.md`; Modify `Dockerfile`, `docs/superpowers/sdd/HANDOFF.md`

- [ ] **Step 1: Sửa `Dockerfile`** — set `BOT_LANG` mặc định để container tường minh (bị secret ghi đè khi cần):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
ENV BOT_LANG=zh
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["python", "-m", "app.bot.main"]
```

- [ ] **Step 2: Redeploy bot Trung TRƯỚC (điểm kiểm chứng an toàn)** — bot Trung phải chạy y hệt sau refactor trước khi đụng tới bot Hàn:

```bash
flyctl deploy -a reminder-zh-bot
flyctl logs -a reminder-zh-bot --no-tail
```
Expected: khởi động sạch, KHÔNG có dòng "Đã nạp CC-CEDICT" (dict cũ còn nguyên), scheduler đặt lại job, polling chạy. Tạo thử 1 thẻ `学习` trên bot → pinyin/nghĩa/audio đúng như trước. Nếu lỗi → `flyctl releases -a reminder-zh-bot` + deploy lại image trước, dừng plan, báo user.

- [ ] **Step 3: Viết `docs/DEPLOY-ko.md`** — runbook bot Hàn:

```markdown
# Dựng bot tiếng Hàn (reminder-ko-bot)

Tiền đề: bot Trung đã redeploy OK sau refactor langpack (Task 4 Step 2).

1. BotFather: /newbot → lấy BOT_TOKEN mới cho bot Hàn.
2. Tạo app + volume (region sin, KHÔNG http_service — dùng lại fly.toml qua --copy-config):
   flyctl apps create reminder-ko-bot
   flyctl volumes create reminder_data -a reminder-ko-bot --region sin --size 1
3. Secrets (LANG dùng khóa BOT_LANG để tránh đụng locale hệ thống):
   flyctl secrets set -a reminder-ko-bot BOT_TOKEN=<token-ko> OWNER_ID=<telegram-id> BOT_LANG=ko
4. Deploy cùng image codebase:
   flyctl deploy -a reminder-ko-bot
5. Kiểm chứng: flyctl logs -a reminder-ko-bot --no-tail
   - Lần đầu thấy "Đã nạp CC-KEDICT: N mục" (tải + parse ~vài giây).
   - Nhắn /start cho bot Hàn → tiêu đề "Bot học tiếng Hàn SRS".
   - Gõ 학교 → thẻ có romaja "hakgyo", nghĩa "school", audio giọng ko-KR.
6. Đặt Gemini key (tùy chọn) qua /settings như bot Trung — dùng chung key được.

## Lưu ý
- 2 app = 2 volume = 2 DB riêng biệt. Không chia sẻ thẻ.
- Cập nhật code cho CẢ HAI bot: sửa 1 lần, deploy 2 lần (deploy -a reminder-zh-bot; deploy -a reminder-ko-bot).
- KHÔNG chạy fly launch (ghi đè fly.toml, thêm http_service autostop — xem HANDOFF.md).
```

- [ ] **Step 4: Cập nhật `docs/superpowers/sdd/HANDOFF.md`** — thêm mục: kiến trúc langpack (BOT_LANG), 2 app song song, quy trình "sửa 1 lần deploy 2 lần", trỏ tới `docs/DEPLOY-ko.md`. Ghi rõ bot Hàn dùng CC-KEDICT (kho nhỏ, tra rỗng nhiều — nhập tay).

- [ ] **Step 5: Deploy bot Hàn thật** (cần BOT_TOKEN từ user — nếu chưa có, dừng ở đây, report cho user chạy runbook). Làm theo `docs/DEPLOY-ko.md`, xác nhận Step 5 của runbook.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "build: BOT_LANG in Dockerfile + Korean bot deploy runbook + handoff"`

---

## Self-Review Notes

- Spec coverage: §2 kiến trúc langpack (T1), §3 gói + 6 thành phần (T1 zh, T2 ko), §4 sửa 5 điểm (T1 lookup/quiz/grading + T3 gemini + T1 config), §5 đặc thù Hàn khoảng trắng (T2 `_make_normalize` xóa space cho cả 2), §6 refactor an toàn + khóa hành vi (T1 dùng 58 test cũ làm lưới + T4 redeploy-verify trước khi đụng ko), §7 deploy 2 app (T4), §8 lỗi (T2 `_ko_romanize` try/except, T1 `get` raise), §9 test (T1/T2/T3).
- **Đổi so với spec:** dùng env `BOT_LANG` thay `LANG` (LANG đụng locale Linux) — đã ghi rõ Step 2/2b + runbook. Giữ tên hàm cũ (`gen_pinyin`/`normalize_hanzi`/`pinyin_key`/`ensure_cedict`) thay vì đổi tên — lazy, khóa hành vi bằng test cũ.
- **Rủi ro cần verify khi chạy:** (a) import path của `korean-romanizer` (Step 4 Task 2 có lệnh kiểm) — kết quả `annyeong` cho `안녕`; nếu lib trả khác (VD viết hoa/khoảng trắng), điều chỉnh `_ko_romanize` + test cho khớp OUTPUT THẬT của lib, không ép output. (b) URL/định dạng cc-kedict `.yml` vs `.yml.gz` (Step 4 note). Cả hai là điểm implementer phải xác nhận với runtime thật, plan đã chỉ chỗ.
- Không đụng schema/migration; `dict_entries` dùng lại cho ko (word,word,romaja,meaning). `sentences`/`quiz` JSON giữ khóa `hanzi`/`pinyin` (chỉ là tên trường) — ko điền chữ Hàn/romaja vào, không phải đổi 2 module đó.
```
