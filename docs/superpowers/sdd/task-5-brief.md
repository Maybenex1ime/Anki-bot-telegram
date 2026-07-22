### Task 5: CSV parser (`app/csv_import.py`)

**Files:** Create `app/csv_import.py`; Test `tests/test_csv_import.py`

**Interfaces:**
- Produces: `@dataclass CsvRow(hanzi, pinyin, meaning, example)` (đều `str`, có thể rỗng trừ hanzi); `@dataclass CsvResult(rows: list[CsvRow], errors: list[tuple[int, str]])` (int = số dòng trong file, 1-based, tính cả header); `csv_import.parse_csv(text: str) -> CsvResult`. Header nhận alias: `hán|han|hanzi`, `pinyin`, `nghĩa|nghia|meaning`, `ví_dụ|vi_du|example`; thiếu cột `hán` trong header → toàn bộ là lỗi dòng 1.

- [ ] **Step 1: Viết test (fail trước)**

`tests/test_csv_import.py`:
```python
from app.csv_import import parse_csv


def test_parse_full_and_partial_rows():
    text = "hán,pinyin,nghĩa,ví_dụ\n学习,,to learn,我在学习\n你好,nǐ hǎo,,\n"
    r = parse_csv(text)
    assert not r.errors
    assert [row.hanzi for row in r.rows] == ["学习", "你好"]
    assert r.rows[0].meaning == "to learn"
    assert r.rows[0].example == "我在学习"
    assert r.rows[1].pinyin == "nǐ hǎo"


def test_missing_hanzi_cell_is_error_with_line_number():
    text = "hán,pinyin,nghĩa,ví_dụ\n,,x,\n好,,,\n"
    r = parse_csv(text)
    assert len(r.rows) == 1
    assert r.errors == [(2, "thiếu chữ Hán")]


def test_header_aliases_and_bom():
    text = "﻿hanzi,meaning\n学,to study\n"
    r = parse_csv(text)
    assert r.rows[0].hanzi == "学"
    assert r.rows[0].meaning == "to study"


def test_missing_hanzi_column():
    r = parse_csv("pinyin,nghĩa\nxue,to learn\n")
    assert r.rows == []
    assert r.errors == [(1, "thiếu cột 'hán' trong header")]


def test_blank_lines_skipped():
    r = parse_csv("hán\n学\n\n习\n")
    assert [row.hanzi for row in r.rows] == ["学", "习"]
    assert not r.errors
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_csv_import.py -v`

- [ ] **Step 3: Viết `app/csv_import.py`**

```python
import csv
import io
from dataclasses import dataclass, field

_ALIASES = {
    "hán": "hanzi", "han": "hanzi", "hanzi": "hanzi",
    "pinyin": "pinyin",
    "nghĩa": "meaning", "nghia": "meaning", "meaning": "meaning",
    "ví_dụ": "example", "vi_du": "example", "example": "example",
}


@dataclass
class CsvRow:
    hanzi: str
    pinyin: str = ""
    meaning: str = ""
    example: str = ""


@dataclass
class CsvResult:
    rows: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def parse_csv(text: str) -> CsvResult:
    result = CsvResult()
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = next(reader)
    except StopIteration:
        result.errors.append((1, "file rỗng"))
        return result
    cols = {}
    for i, name in enumerate(header):
        key = _ALIASES.get(name.strip().lower())
        if key:
            cols[key] = i
    if "hanzi" not in cols:
        result.errors.append((1, "thiếu cột 'hán' trong header"))
        return result

    def cell(row, key):
        i = cols.get(key)
        return row[i].strip() if i is not None and i < len(row) else ""

    for line_no, row in enumerate(reader, start=2):
        if not any(c.strip() for c in row):
            continue
        hanzi = cell(row, "hanzi")
        if not hanzi:
            result.errors.append((line_no, "thiếu chữ Hán"))
            continue
        result.rows.append(CsvRow(
            hanzi=hanzi, pinyin=cell(row, "pinyin"),
            meaning=cell(row, "meaning"), example=cell(row, "example")))
    return result
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_csv_import.py -v`
- [ ] **Step 5: Commit** — `git commit -am "feat: CSV parser with header aliases and per-line errors"`

---

