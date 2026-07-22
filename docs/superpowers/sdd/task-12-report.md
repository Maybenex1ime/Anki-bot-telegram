# Task 12 Report: Nhắc theo lịch (scheduled reminders)

## What I implemented
- Created `app/bot/reminders.py` verbatim from the brief: `schedule_jobs(app)` (clears all `rem:*` jobs then re-registers from `reminder_times` + optional `evening_nudge`), async `reminder_job` (due-card count + new count, `▶️ Ôn ngay` button), async `evening_job` (streak nudge, silent if already reviewed today or queue empty), `_parse_hhmm` helper, `START_KB`.
- Wired into `app/bot/main.py`: added `reminders` to the existing `from app.bot import ...` import (top, alphabetical, matching style) and appended `reminders.schedule_jobs(app)` as the last line of `post_init`.

## Verification (offline — no BOT_TOKEN this session)

Consumed signatures pre-checked against source: `db.get_setting`, `cards.build_queue/get_card/is_new`, `stats.reviews_today/streak`, `config.OWNER_ID/TZ/today/today_iso`, and defaults `reminder_times="07:30,12:30,20:00"` / `evening_nudge="21:30"` — all match.

`app.initialize()` requires a live token (calls getMe → InvalidToken), so I verified `schedule_jobs` directly: `build_app()`, set `bot_data["conn"]`, start the job queue's APScheduler, call `schedule_jobs`, list jobs.

Command:
```
BOT_TOKEN=x OWNER_ID=1 DATA_DIR="$(mktemp -d)" PYTHONPATH=. \
  .venv/Scripts/python.exe scratchpad/verify.py
```
Output:
```
build_app OK
job names: ['rem:07:30', 'rem:12:30', 'rem:20:00', 'rem:evening']
  rem:07:30: next 07:30 +07
  rem:12:30: next 12:30 +07
  rem:20:00: next 20:00 +07
  rem:evening: next 21:30 +07
```
Confirms: `build_app()` succeeds with reminders wired; default settings produce exactly the four expected `rem:*` jobs at the correct times in the `Asia/Ho_Chi_Minh` (+07) tz.

Full suite:
```
.venv/Scripts/python.exe -m pytest tests/ -q
30 passed in 3.13s
```

## Files changed
- `app/bot/reminders.py` (new)
- `app/bot/main.py` (import + one line in post_init)

## Self-review findings
- Code matches brief exactly; no additions beyond spec (YAGNI clean).
- `schedule_jobs` is idempotent by design (removes `rem:*` first) so the Task 15 settings re-call is safe.
- Deferred manual Telegram test per project decision; the offline check covers registration/scheduling logic.
- No new tests added — logic is a thin wrapper over already-tested modules and PTB's scheduler; the offline script serves as the runnable check.

## Concerns
None.
