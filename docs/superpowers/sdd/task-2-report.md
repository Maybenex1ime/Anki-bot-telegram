# Task 2 Report: SM-2 spaced-repetition scheduler (`app/srs.py`)

## Status: DONE

## TDD Evidence

### RED — `python -m pytest tests/test_srs.py -v`
Wrote `tests/test_srs.py` (8 tests, verbatim from brief) before implementation.
```
collected 0 items / 1 error
E   ModuleNotFoundError: No module named 'app.srs'
!!!!!!! Interrupted: 1 error during collection !!!!!!!
```
Fails as expected — module does not yet exist.

### GREEN — `python -m pytest tests/test_srs.py -v`
Implemented `app/srs.py` (verbatim from brief, half-up rounding `int(x + 0.5)`).
```
tests/test_srs.py::test_new_card_good_gives_1_day PASSED       [ 12%]
tests/test_srs.py::test_second_good_gives_3_days PASSED        [ 25%]
tests/test_srs.py::test_third_good_multiplies_by_ease PASSED   [ 37%]
tests/test_srs.py::test_again_resets_and_stays_today PASSED    [ 50%]
tests/test_srs.py::test_hard_grows_slow_and_drops_ease PASSED  [ 62%]
tests/test_srs.py::test_easy_boosts PASSED                     [ 75%]
tests/test_srs.py::test_ease_floor PASSED                      [ 87%]
tests/test_srs.py::test_input_state_not_mutated PASSED         [100%]
8 passed in 0.02s
```

### Full suite — `python -m pytest tests/ -v`
```
11 passed in 0.14s
```
(3 from test_db.py + 8 from test_srs.py) — all green before commit.

## Files Changed
- `app/srs.py` (new) — SM-2 pure scheduler: `AGAIN/HARD/GOOD/EASY` constants, `MIN_EASE=1.3`, frozen `SrsState` dataclass, `review(state, rating, today) -> (SrsState, date)`.
- `tests/test_srs.py` (new) — 8 tests verbatim from brief.

## Self-Review Findings
- Rounding: uses `int(s.interval + 0.5)` (half-up), NOT `round()` — verified test 3 (7.5 → 8 days) passes.
- Immutability: `@dataclass(frozen=True)` + `replace()` guarantees the input state is never mutated (test_input_state_not_mutated confirms).
- Purity: no I/O, no DB, no global state; deterministic given inputs.
- Invalid rating raises `ValueError` (not exercised by brief tests but present as defensive guard).
- No issues found; code matches brief exactly.

## Concerns
None. Commit: `fc35c94 feat: SM-2 scheduler (pure functions)`.
