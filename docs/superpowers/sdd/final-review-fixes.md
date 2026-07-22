# Final review fixes

Branch `feature/srs-bot`, applied on HEAD `ce3fcb5`.

## Fix 1 — double-tap / stale `rv_rate` guard (app/bot/review_flow.py)
Added a guard at the top of the `rv_rate` branch in `on_callback`:
```python
if s["pos"] >= len(s["queue"]) or s["queue"][s["pos"]] != cid:
    return
```
A fast double-tap or a tap on an old session message no longer re-applies SM-2,
double-bumps stats, or skips the next card via a double `_advance`.

## Fix 2 — None-guard for deleted cards (app/bot/review_flow.py)
The card row is now fetched once (`row = cards.get_card(conn, cid)`) right after
parsing `parts`, before the action branches.
- `rv_listen` / `rv_show`: if `row is None`, send "⚠️ Thẻ này đã bị xóa." then
  `_advance` past the deleted card.
- `rv_rate`: after the Fix 1 guard, if `row is None`, clear aux, persist session,
  and `_advance` — `apply_rating` is never called with a missing card.

## Fix 3 — correct total_reviews (app/stats.py)
`overview()` now computes `total_reviews` as
`SELECT COALESCE(SUM(reviews),0) FROM daily_log` instead of
`SUM(cards.repetitions)` (which SM-2 AGAIN resets to 0, erasing history).
`total_lapses` kept as `SUM(cards.lapses)`.

## Fix 4 — no duplicate message on "not modified" (app/bot/review_flow.py)
`_edit_or_send`'s `except BadRequest` now returns early when
`"not modified" in str(e).lower()`, instead of falling through to send a new
message (e.g. a double-tap on 👀).

## Tests
- Added `tests/test_stats.py::test_total_reviews_counts_reviews_after_again`:
  a review followed by an AGAIN rating (repetitions reset to 0) still counts as
  2 in `total_reviews`.
- Fix 1's guard was NOT unit-tested: no Telegram-handler test harness exists and
  mocking `on_callback` (async `context.bot`, `callback_query`, the
  `owner_only_callback` decorator) is disproportionate to the small guard. Per
  the test contract, covered Fix 3 with tests instead.

### Commands + output
```
.venv\Scripts\python.exe -m pytest tests/test_stats.py -v
  -> 4 passed in 1.74s

.venv\Scripts\python.exe -m pytest tests/ -v
  -> 31 passed in 3.06s
```
(Suite was 30 passed; +1 new test.)
