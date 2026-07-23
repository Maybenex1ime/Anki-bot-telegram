### Task 2: Grading core (`app/grading.py`)

**Files:** Create `app/grading.py`; Test `tests/test_grading.py`

**Interfaces:**
- Produces (tất cả thuần, không I/O):
  - `meaning_variants(meaning: str) -> list[str]` — tách theo `;` `|` `,`, bỏ rỗng
  - `normalize_meaning(s: str) -> str` — lowercase, bỏ nội dung trong `()`/`[]`, bỏ "to " đầu, bỏ dấu câu, gộp space
  - `grade_typed_offline(card_meaning: str, answer: str) -> str` — `'correct'` nếu answer chuẩn hóa trùng nguyên 1 biến thể; ngược lại `'unsure'`
  - `fallback_partial(card_meaning: str, answer: str) -> str` — `'partial'` nếu ≥1 content-word (không stopword) của answer nằm trong content-words của biến thể nào đó; ngược lại `'wrong'`
  - `time_to_rating(correct: bool, elapsed: float, level: str, fast: float, slow: float) -> int` — theo Global Constraints, trả hằng của `app.srs`
  - `normalize_hanzi(s: str) -> str` — bỏ whitespace + dấu câu CJK/ASCII `。，！？、；：""''…·.,!?;:'"()（）`
  - `diff_chars(expected: str, got: str) -> tuple[str, int, int]` — (html đã escape có `<s>` cho sai/thừa và `<u>` cho thiếu, số ký tự đúng, len(expected)); so trên chuỗi CHƯA escape, escape khi build
  - `shuffle_words(words: list[str], rng) -> list[int]` — hoán vị chỉ số, khác thứ tự gốc nếu len>1 (thử tối đa 10 lần)

- [ ] **Step 1: Viết test (fail trước)** — `tests/test_grading.py`:

```python
import random

from app import grading, srs


def test_variants_and_normalize():
    assert grading.meaning_variants("to learn; to study | learning") == \
        ["to learn", "to study", "learning"]
    assert grading.normalize_meaning("To Learn (a skill)!") == "learn"
    assert grading.normalize_meaning("AT&T [company]") == "at&t"


def test_grade_typed_offline():
    m = "to learn; to study"
    assert grading.grade_typed_offline(m, "study") == "correct"
    assert grading.grade_typed_offline(m, "To Learn") == "correct"
    assert grading.grade_typed_offline(m, "acquire knowledge") == "unsure"


def test_fallback_partial():
    m = "to learn; to study a subject"
    assert grading.fallback_partial(m, "study hard") == "partial"
    assert grading.fallback_partial(m, "the a of") == "wrong"
    assert grading.fallback_partial(m, "banana") == "wrong"


def test_time_to_rating():
    assert grading.time_to_rating(False, 1, "hard", 5, 15) == srs.AGAIN
    assert grading.time_to_rating(True, 20, "easy", 5, 15) == srs.HARD
    assert grading.time_to_rating(True, 10, "easy", 5, 15) == srs.GOOD
    assert grading.time_to_rating(True, 4, "hard", 5, 15) == srs.EASY
    assert grading.time_to_rating(True, 4, "easy", 5, 15) == srs.GOOD  # fast nhưng không phải hard
    assert grading.time_to_rating(True, 15, "hard", 5, 15) == srs.GOOD  # biên slow


def test_normalize_hanzi():
    assert grading.normalize_hanzi("我在 学习。中文！") == "我在学习中文"


def test_diff_chars_correct_and_wrong():
    html_out, ok, total = grading.diff_chars("我在学习", "我在学习")
    assert (ok, total) == (4, 4) and "<s>" not in html_out
    html_out, ok, total = grading.diff_chars("我在学习", "我再学习")
    assert (ok, total) == (3, 4)
    assert "<s>再</s>" in html_out and "<u>在</u>" in html_out
    html_out, ok, total = grading.diff_chars("我学习", "我的学习")   # thừa 的
    assert "<s>的</s>" in html_out and ok == 3
    html_out, ok, total = grading.diff_chars("我在学习", "我学习")   # thiếu 在
    assert "<u>在</u>" in html_out and ok == 3


def test_shuffle_words():
    rng = random.Random(42)
    words = ["我", "在", "学习", "中文"]
    perm = grading.shuffle_words(words, rng)
    assert sorted(perm) == [0, 1, 2, 3] and perm != [0, 1, 2, 3]
    assert grading.shuffle_words(["一"], rng) == [0]
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_grading.py -v`

- [ ] **Step 3: Implement** — `app/grading.py`:

```python
import html
import re
from difflib import SequenceMatcher

from app import srs

STOPWORDS = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "and",
             "or", "is", "are", "be", "it", "its", "sth", "sb", "one", "ones",
             "something", "somebody", "someone"}
_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_PUNCT = re.compile(r"[^\w\s&']", re.UNICODE)
_HANZI_PUNCT = "。，！？、；：“”‘’…·.,!?;:'\"()（）"


def meaning_variants(meaning):
    parts = re.split(r"[;|,]", meaning)
    return [p.strip() for p in parts if p.strip()]


def normalize_meaning(s):
    s = _PAREN.sub(" ", s.lower())
    s = _PUNCT.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("to "):
        s = s[3:]
    return s


def _content_words(s):
    return {w for w in normalize_meaning(s).split() if w not in STOPWORDS}


def grade_typed_offline(card_meaning, answer):
    ans = normalize_meaning(answer)
    if not ans:
        return "unsure"
    for v in meaning_variants(card_meaning):
        if normalize_meaning(v) == ans:
            return "correct"
    return "unsure"


def fallback_partial(card_meaning, answer):
    ans_words = _content_words(answer)
    if not ans_words:
        return "wrong"
    for v in meaning_variants(card_meaning):
        if ans_words & _content_words(v):
            return "partial"
    return "wrong"


def time_to_rating(correct, elapsed, level, fast, slow):
    if not correct:
        return srs.AGAIN
    if elapsed <= fast and level == "hard":
        return srs.EASY
    if elapsed <= slow:
        return srs.GOOD
    return srs.HARD


def normalize_hanzi(s):
    return "".join(c for c in s if not c.isspace() and c not in _HANZI_PUNCT)


def diff_chars(expected, got):
    out, ok = [], 0
    for op, i1, i2, j1, j2 in SequenceMatcher(None, expected, got).get_opcodes():
        if op == "equal":
            out.append(html.escape(expected[i1:i2]))
            ok += i2 - i1
        elif op == "delete":      # thiếu ký tự
            out.append(f"<u>{html.escape(expected[i1:i2])}</u>")
        elif op == "insert":      # thừa ký tự
            out.append(f"<s>{html.escape(got[j1:j2])}</s>")
        else:                     # replace: sai — hiện cả hai
            out.append(f"<s>{html.escape(got[j1:j2])}</s><u>{html.escape(expected[i1:i2])}</u>")
    return "".join(out), ok, len(expected)


def shuffle_words(words, rng):
    idx = list(range(len(words)))
    if len(idx) < 2:
        return idx
    for _ in range(10):
        perm = rng.sample(idx, len(idx))
        if perm != idx:
            return perm
    return list(reversed(idx))
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_grading.py tests/ -v`
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: grading core — offline typed grading, timing rating, dictation diff, word shuffle"`

---

