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
