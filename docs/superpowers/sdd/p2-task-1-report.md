# P2 Task 1 Report — Schema + settings + practice_log helpers

**Status:** DONE
**Commit:** c30036a — `feat: schema + settings + practice log for practice modes`

## TDD Evidence

### RED (Step 2)
`python -m pytest tests/test_practice_schema.py -v` → **2 failed**
- `test_new_tables_and_settings` — AssertionError: sentences/distractors/practice_log missing from tables.
- `test_bump_practice_and_summary` — AttributeError: module 'app.stats' has no attribute 'bump_practice'.

### GREEN (Step 4)
`python -m pytest tests/ -v` → **32 passed, 1 failed** (the failure is pre-existing, see Concerns).
- Both new tests pass.
- Isolated verify: `pytest tests/test_practice_schema.py tests/test_stats.py -v` → **6 passed**.

## Files Changed
- `app/db.py` — appended `sentences`, `distractors`, `practice_log` tables to `SCHEMA` (verbatim from brief).
- `app/config.py` — added 6 settings to `DEFAULT_SETTINGS`: review_mode, quiz_fast_sec, quiz_slow_sec, gemini_api_key, gemini_model, max_sentences.
- `app/stats.py` — added `bump_practice()` and `practice_summary()`.
- `tests/test_practice_schema.py` — new test file (verbatim from brief).

## Self-Review
- Changes are purely additive: `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE` on new settings only. No existing table or setting altered → live Fly DB migrates safely on next `connect()`.
- SQL/settings/functions match the brief text exactly.
- `bump_practice` uses `ON CONFLICT(day,mode)` upsert; `correct=correct+excluded.correct` correctly accumulates only on True. Verified by summary test: mc=(2,1), dict=(1,1).

## Concerns
- **Pre-existing failure (NOT mine):** `tests/test_cards.py::test_queue_reviews_first_then_new_with_limit` fails on the clean base (confirmed via `git stash`). It is date-dependent — the test builds the queue for `2026-07-22` while newly created cards get the real system date `2026-07-23` as due_date, so the new card is not yet due. This predates Task 1 and is out of scope. Recommend a follow-up fix (freeze `today` or inject due_date) in whichever task owns queue tests.
- The brief anticipated "31+2" tests; the base branch (HEAD at 3c9df78) already carried this failing card-queue test, so the live count is 33 total / 32 passing.

## Fix: date-dependent test

`test_queue_reviews_first_then_new_with_limit` in `tests/test_cards.py` hardcoded `today = date(2026, 7, 22)` while `cards.create_card` stamps cards with the real current date via `config.today_iso()`, so `build_queue` for 2026-07-22 found no cards due on the real date and the test failed on any later day. Replaced the hardcoded date with `today = config.today()` (added `config` to the `from app import ...` line). No production code changed; the self-consistent `test_apply_rating_updates_card_and_stats` was left untouched.

Test output: `tests/test_cards.py` 5 passed; full `tests/` 33 passed, 2 warnings.
