# P2 Task 4 Report — Distractor service (`app/quiz.py`)

## Status: DONE — 51/51 tests green, committed `5f2b377`

## TDD evidence
- **RED**: `python -m pytest tests/test_quiz.py -v` → collection ImportError
  (`cannot import name 'quiz' from 'app'`) before `app/quiz.py` existed.
- **GREEN (module)**: `tests/test_quiz.py` → 5 passed
  (test_pinyin_key, test_easy_options_offline, test_hard_uses_homophones_and_gemini,
  test_not_enough_cards_returns_none, test_distractor_never_equals_correct).
- **GREEN (full)**: `python -m pytest tests/ -q` → **51 passed, 2 warnings**
  (46 pre-existing + 5 new; the 2 warnings are pre-existing pypinyin
  `codecs.open` DeprecationWarnings, unrelated to this task).

## Files changed
- `app/quiz.py` (new) — `pinyin_key`, `get_options`, offline helpers, cache.
- `tests/test_quiz.py` (new) — 5 tests, verbatim per brief.

## Design (per brief, verbatim)
- `pinyin_key(pinyin)` — NFD-normalize, keep ASCII letters only; maps both
  tone-mark pinyin ("xué xí") and CEDICT numeric pinyin ("xue2 xi2") → "xuexi".
- `get_options(conn, row, level)` — returns 3 distractors or `None`:
  - cache hit in `distractors(card_id, level)` → return stored JSON.
  - `normal`: Gemini synonym-traps + same-deck random meanings.
  - `hard`: homophones (cards then CEDICT) prioritized, interleaved with Gemini.
  - `easy`/fallback: random meanings from other cards.
  - `_pick_valid` de-dupes and bans anything equal-to / substring-of the correct
    meaning's variants; caches result on success; `None` if < 3 gathered.

## Self-review
- 3-column positional `INSERT OR REPLACE INTO distractors VALUES(?,?,?)` matches
  schema PK(card_id, level). OK.
- Gemini is monkeypatched at `app.quiz.gemini.make_distractors` per brief; import
  path (`from app import gemini, grading`) confirmed compatible. OK.
- Homophone test (是/事 both shì) passes → pypinyin tone-mark output and CEDICT
  numeric form collapse to the same key. OK.
- Cache determinism: offline/random path is persisted, so repeat calls return the
  identical set (asserted in test_easy_options_offline). OK.

## Concerns (minor, non-blocking)
- The substring-ban in `_pick_valid` (`nm in b or b in nm`) is intentionally
  aggressive for safety: a short legit distractor (e.g. "tea") could be excluded
  if it is a substring of a correct-meaning variant. This only shrinks the
  candidate pool (safe, never surfaces a wrong-as-correct); the random-meaning
  tail normally backfills to 3. Acceptable per the "never equals correct" intent.
- `easy` level has no dedicated branch (falls through to random meanings), matching
  the brief which only specifies `normal`/`hard` sourcing. Caller falls back to
  card-flip when `None` is returned.

## Fix: review findings

### What changed (app/quiz.py)
- **Finding 1a — CEDICT prefix filter**: `_homophone_meanings` now takes the first
  space-separated syllable of the card pinyin, converts it via `pinyin_key()` to an
  ascii prefix (e.g. "xué xí" → "xue"), and narrows the dict scan with
  `WHERE simplified<>? AND pinyin LIKE ?` (`prefix + '%'`). The exact
  `pinyin_key(...) == key` check still runs on the narrowed rows. Empty prefix →
  CEDICT step skipped entirely. Eliminates the full ~120k-row scan per uncached
  hard card.
- **Finding 1b — negative caching**: when `get_options` cannot gather 3 valid
  options it now stores `"[]"` in the distractors cache and returns None. Cache-hit
  path is `json.loads(...) or None`, so `[]` → None and a 3-item list is returned as
  before. Failing cards no longer re-scan on every question. Public contract
  unchanged (list of exactly 3, or None).
- **Finding 2 — empty-ban guard**: `_ban_set` now filters out empty strings; and
  `_pick_valid`'s substring test is guarded with non-empty `b`
  (`any(b and (nm in b or b in nm) for b in ban)`), so a purely-parenthetical gloss
  normalizing to "" no longer rejects every candidate.

### Tests (tests/test_quiz.py)
- Added `test_negative_cache_no_rederive`: single-card deck → `get_options(...) is None`
  twice, and asserts the distractors row exists with `options_json == "[]"`.
- Existing homophone test (是/事) stays green — "shi%" LIKE matches the narrowed path.

### Commands + output
```
python -m pytest tests/test_quiz.py -v   → 6 passed
python -m pytest tests/ -v               → 52 passed
```
