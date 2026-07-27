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

