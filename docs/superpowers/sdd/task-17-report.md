# Task 17 Report: /thongke (stats) + /backup

## What I implemented
- `app/bot/misc.py`: added `from app import config, stats` import; added `cmd_stats`
  (`/thongke`) and `cmd_backup` (`/backup`) coroutines, verbatim from the brief.
- `app/bot/main.py`: registered both as `CommandHandler`s with `owner_filter`,
  after the existing `/csv` handler.

No escaping needed: `cmd_stats` interpolates only DB-derived integers/floats from
`stats.overview`; `cmd_backup` interpolates no user-authored text. Matches decision 1.

## Verification

Interfaces confirmed present:
```
app/config.py:7:DB_PATH = DATA_DIR / "reminder.db"
app/config.py:25:def today_iso():
app/stats.py:35:def overview(conn, today_iso):
```

Offline build + handler registration (decision 2):
```
$ BOT_TOKEN=x OWNER_ID=1 DATA_DIR="$(mktemp -d)" .venv/Scripts/python.exe -c \
  "from app.bot import main; app = main.build_app(); cmds = set(); \
   [cmds.update(h.commands) for hg in app.handlers.values() for h in hg if hasattr(h, 'commands')]; \
   print('build_app OK'); print('thongke registered:', 'thongke' in cmds); \
   print('backup registered:', 'backup' in cmds); print('commands:', sorted(cmds))"
build_app OK
thongke registered: True
backup registered: True
commands: ['backup', 'bo', 'csv', 'on', 'settings', 'start', 'thongke', 'tim']
```

Full test suite:
```
$ .venv/Scripts/python.exe -m pytest tests/ -q
30 passed in 3.61s
```

Manual Telegram test (brief Step 3) skipped per decision 2 (no BOT_TOKEN).

## Files changed
- `app/bot/misc.py`
- `app/bot/main.py`

## Self-review findings
- Completeness: both commands implemented and wired; matches brief exactly.
- Quality: reuses existing `stats.overview`/`config` interfaces; no new deps.
- Discipline (YAGNI): nothing beyond the brief. No escaping added since no
  user-authored text is interpolated.
- Tests: full suite green, pristine output (30 passed).

## Issues / concerns
None.
