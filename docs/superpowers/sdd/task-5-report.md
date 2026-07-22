# Task 5 Report: CSV parser (`app/csv_import.py`)

## Status
COMPLETE — TDD cycle followed, full suite green, committed.

## Files changed
- `app/csv_import.py` (new) — `CsvRow`, `CsvResult` dataclasses + `parse_csv()`
- `tests/test_csv_import.py` (new) — 5 tests, verbatim from brief (BOM U+FEFF preserved at index 12 of the alias-test literal)

## TDD evidence
- **RED**: `python -m pytest tests/test_csv_import.py -v` → collection error `ModuleNotFoundError: No module named 'app.csv_import'`
- **GREEN (module)**: 5 passed in 0.02s
- **GREEN (full suite)**: `python -m pytest -q` → 22 passed, 2 warnings in 0.58s (warnings are pre-existing pypinyin `codecs.open()` DeprecationWarnings, unrelated)

## Self-review
- BOM stripped via `text.lstrip("﻿")`; verified BOM literal present in test file before running.
- Line numbers 1-based counting header (`enumerate(reader, start=2)`); missing-cell error reports line 2 correctly.
- Missing `hán` column in header → single error `(1, "thiếu cột 'hán' trong header")`, no rows.
- Blank/whitespace-only lines skipped.
- Empty file → `(1, "file rỗng")` (not covered by a test but present per brief).
- `CsvRow` fields all `str`, only `hanzi` required. Pure module, no DB/network. No findings.

## Commit
- `a9410f7` feat: CSV parser with header aliases and per-line errors

## Concerns
- None functional. Git reported LF→CRLF conversion warnings on commit (Windows autocrlf) — cosmetic only.
