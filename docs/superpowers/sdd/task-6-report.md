# Task 6 Report: Stats & streak (`app/stats.py`)

## Status: COMPLETE

## TDD Evidence

### RED
Wrote `tests/test_stats.py` (verbatim from brief). Ran `python -m pytest tests/test_stats.py -v`:
```
ImportError: cannot import name 'stats' from 'app'
1 error during collection
```

### GREEN
Implemented `app/stats.py` (verbatim from brief). Re-ran:
```
tests/test_stats.py::test_bump_and_counts PASSED
tests/test_stats.py::test_streak_counts_consecutive_days PASSED
tests/test_stats.py::test_streak_broken PASSED
3 passed in 0.13s
```

### Full suite
`python -m pytest` → **25 passed, 2 warnings** (warnings are pre-existing pypinyin DeprecationWarnings, unrelated).

## Files Changed
- `app/stats.py` (new) — `bump_review`, `reviews_today`, `new_used_today`, `streak`, `overview`
- `tests/test_stats.py` (new)

## Commit
- `c743faa` feat: daily log, streak, stats overview

## Self-Review
- Signatures match brief and Task 7 needs exactly: `bump_review(conn, day_iso, was_new)`, `new_used_today(conn, day_iso)`, `reviews_today(conn, day_iso)`, `streak(conn, today: date)`, `overview(conn, today_iso) -> dict` with keys `total, due, new_waiting, streak, total_reviews, total_lapses`.
- `bump_review` uses UPSERT on `daily_log.day` (matches db.py schema PRIMARY KEY on `day`).
- `streak` correctly treats "today not yet reviewed" as ending streak at yesterday (test_streak_counts_consecutive_days confirms 3 before today's bump, 4 after).
- Uses `sqlite3.Row` factory (set in db.connect) → column-name access (`row["reviews"]`) works.

## Concerns
- `overview()` has no dedicated test in the brief; verified only by inspection against `cards` schema (columns `due_date, repetitions, lapses` exist). Its `due`/`new_waiting` logic matches brief verbatim.
- No other concerns.
