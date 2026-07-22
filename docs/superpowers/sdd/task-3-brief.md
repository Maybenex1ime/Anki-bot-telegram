### Task 3: Tra cứu — pinyin + CC-CEDICT (`app/lookup.py`)

**Files:** Create `app/lookup.py`; Test `tests/test_lookup.py`

**Interfaces:**
- Consumes: `db.connect` (bảng `dict_entries`), `config.CEDICT_URL`, `config.DATA_DIR`
- Produces: `lookup.gen_pinyin(hanzi: str) -> str` (có dấu thanh, cách nhau bởi space); `lookup.parse_cedict_line(line: str) -> tuple[str,str,str,str] | None` (simp, trad, pinyin, meaning); `lookup.ensure_cedict(conn) -> int` (số dòng đã nạp, 0 nếu đã có sẵn; tải file nếu chưa có); `lookup.lookup_meaning(conn, hanzi: str) -> str` ('' nếu không thấy)

- [ ] **Step 1: Viết test (fail trước)**

`tests/test_lookup.py`:
```python
from app import db, lookup


def test_gen_pinyin_with_tones():
    assert lookup.gen_pinyin("学习") == "xué xí"
    assert lookup.gen_pinyin("你好") == "nǐ hǎo"


def test_parse_cedict_line():
    line = "學習 学习 [xue2 xi2] /to learn/to study/"
    assert lookup.parse_cedict_line(line) == (
        "学习", "學習", "xue2 xi2", "to learn; to study")


def test_parse_cedict_skips_comments_and_garbage():
    assert lookup.parse_cedict_line("# CC-CEDICT") is None
    assert lookup.parse_cedict_line("not a dict line") is None


def test_lookup_meaning_by_simplified_and_traditional(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO dict_entries VALUES(?,?,?,?)",
                 ("学习", "學習", "xue2 xi2", "to learn; to study"))
    conn.commit()
    assert lookup.lookup_meaning(conn, "学习") == "to learn; to study"
    assert lookup.lookup_meaning(conn, "學習") == "to learn; to study"
    assert lookup.lookup_meaning(conn, "不存在的词") == ""
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_lookup.py -v`

- [ ] **Step 3: Viết `app/lookup.py`**

```python
import gzip
import re
import urllib.request

from pypinyin import Style, pinyin

from app import config

_CEDICT_LINE = re.compile(r"^(\S+) (\S+) \[([^\]]+)\] /(.+)/\s*$")


def gen_pinyin(hanzi: str) -> str:
    return " ".join(p[0] for p in pinyin(hanzi, style=Style.TONE))


def parse_cedict_line(line):
    if line.startswith("#"):
        return None
    m = _CEDICT_LINE.match(line.strip())
    if not m:
        return None
    trad, simp, pin, meaning = m.groups()
    return simp, trad, pin, "; ".join(meaning.split("/"))


def ensure_cedict(conn) -> int:
    if conn.execute("SELECT COUNT(*) c FROM dict_entries").fetchone()["c"] > 0:
        return 0
    path = config.DATA_DIR / "cedict.txt.gz"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(config.CEDICT_URL, path)
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            parsed = parse_cedict_line(line)
            if parsed:
                rows.append(parsed)
    conn.executemany("INSERT INTO dict_entries VALUES(?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def lookup_meaning(conn, hanzi: str) -> str:
    rows = conn.execute(
        "SELECT meaning FROM dict_entries WHERE simplified=? OR traditional=? LIMIT 3",
        (hanzi, hanzi)).fetchall()
    return " | ".join(r["meaning"] for r in rows)
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_lookup.py -v`
- [ ] **Step 5: Commit** — `git commit -am "feat: pinyin generation + CC-CEDICT import/lookup"`

---

