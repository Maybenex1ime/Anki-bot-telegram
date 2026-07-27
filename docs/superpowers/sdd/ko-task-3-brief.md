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

