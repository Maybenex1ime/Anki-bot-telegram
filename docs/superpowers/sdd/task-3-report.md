# Task 3 Report: Lookup — pinyin + CC-CEDICT (`app/lookup.py`)

## Status: COMPLETE

## TDD Evidence
- **RED**: After writing `tests/test_lookup.py`, ran `python -m pytest tests/test_lookup.py -v`
  → collection error `ImportError: cannot import name 'lookup' from 'app'` (module absent). Confirmed failing.
- **GREEN**: After creating `app/lookup.py`, `python -m pytest tests/test_lookup.py -v`
  → `4 passed`.
- **Full suite**: `python -m pytest -q` → `15 passed, 2 warnings`.
  (Warnings are pypinyin's internal `codecs.open()` DeprecationWarning — third-party, not our code.)

## Files Changed
- `app/lookup.py` (new) — `gen_pinyin`, `parse_cedict_line`, `ensure_cedict`, `lookup_meaning`. Verbatim from brief.
- `tests/test_lookup.py` (new) — 4 tests, verbatim from brief.

## Commit
- `d9cf249  feat: pinyin generation + CC-CEDICT import/lookup`

## Self-Review
- Interfaces match brief exactly (signatures and return contracts).
- No network in unit tests: tests insert fixture rows directly and never call `ensure_cedict`.
  `ensure_cedict` only downloads when the table is empty AND the local gz is missing.
- `lookup_meaning` returns `''` for a miss via empty `" | ".join([])` — matches assertion.
- `parse_cedict_line` correctly maps regex group order (trad, simp) → returns (simp, trad, ...); comment/garbage lines → `None`.
- Consumes `config.CEDICT_URL` / `config.DATA_DIR` and the `dict_entries` schema (with simp/trad indexes) as provided by Task 1.

## Concerns
- None blocking. Minor: pypinyin emits a DeprecationWarning (upstream library, out of scope).
