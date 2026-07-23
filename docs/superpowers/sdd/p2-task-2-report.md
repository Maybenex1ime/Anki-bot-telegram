# Task 2 Report: Grading core (`app/grading.py`)

## Status: COMPLETE

## Files changed
- `app/grading.py` (created, 90 lines) — pure module, no I/O/DB/network
- `tests/test_grading.py` (created, 57 lines) — 7 tests

## TDD evidence

### RED (Step 2)
`python -m pytest tests/test_grading.py -v`
→ `ImportError: cannot import name 'grading' from 'app'` — 1 error during collection (module absent).

### GREEN (Step 4)
`python -m pytest tests/test_grading.py -v` → **7 passed in 0.03s**
- test_variants_and_normalize PASSED
- test_grade_typed_offline PASSED
- test_fallback_partial PASSED
- test_time_to_rating PASSED
- test_normalize_hanzi PASSED
- test_diff_chars_correct_and_wrong PASSED
- test_shuffle_words PASSED

Full suite: `python -m pytest tests/` → **40 passed, 2 warnings in 1.14s** (was 33, +7; no regressions). Warnings are pre-existing pypinyin DeprecationWarnings, unrelated.

## Interfaces produced (all pure)
- `meaning_variants(meaning) -> list[str]` — split on `;|,`, drop empties
- `normalize_meaning(s) -> str` — lowercase, strip `()`/`[]`, drop leading "to ", strip punct (keeps `&` `'`), collapse spaces
- `grade_typed_offline(card_meaning, answer) -> str` — 'correct'/'unsure'
- `fallback_partial(card_meaning, answer) -> str` — 'partial'/'wrong' via content-word overlap
- `time_to_rating(correct, elapsed, level, fast, slow) -> int` — returns `app.srs` constants (AGAIN/HARD/GOOD/EASY)
- `normalize_hanzi(s) -> str` — strip whitespace + CJK/ASCII punct
- `diff_chars(expected, got) -> (html, ok, total)` — `<s>` wrong/extra, `<u>` missing; diffs unescaped, escapes on build
- `shuffle_words(words, rng) -> list[int]` — permutation != original when len>1 (≤10 tries, else reversed)

## Self-review
Implementation is verbatim from the brief. Verified against spec:
- `time_to_rating` branch order matches all 6 boundary cases (incl. fast-but-not-hard → GOOD, slow boundary elapsed==slow → GOOD).
- `diff_chars` escapes each segment via `html.escape` before wrapping in tags; comparison runs on raw strings — no double-escape, no tag injection.
- `shuffle_words` len<2 returns index list unchanged (single/empty safe).
- Import `from app import srs` confirmed; constants exist (srs.py line 4).

No findings; no fixes needed.

## Concerns
- None blocking. Minor: `normalize_meaning` intentionally preserves `&` and `'` (so "at&t" survives); downstream consumers should be aware apostrophes are retained (e.g. "it's" ≠ "its").
- `time_to_rating` EASY only reachable when `level == "hard"` and fast — by design per brief.

## Commit
`2e20d77` feat: grading core — offline typed grading, timing rating, dictation diff, word shuffle
