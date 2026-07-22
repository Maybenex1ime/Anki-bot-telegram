# Task 8 Report: Bot skeleton — auth, /start, main

**Status:** COMPLETE
**Commit:** `72a5fd8` — feat: bot skeleton — single-user auth, /start, polling
**Branch:** feature/srs-bot

## Files created (verbatim from brief)
- `app/bot/__init__.py` — empty package marker
- `app/bot/auth.py` — `owner_filter` (filters.User on config.OWNER_ID) + `owner_only_callback(fn)` decorator
- `app/bot/misc.py` — `HELP` text + `cmd_start` handler (/start)
- `app/bot/main.py` — `post_init`, `build_app() -> Application`, `main()` run_polling

## Interfaces produced (per brief)
- `auth.owner_filter`, `auth.owner_only_callback`
- `main.build_app()` → Application with `bot_data["conn"]` set in `post_init`
- `main.main()` → run_polling(allowed_updates=Update.ALL_TYPES)
- Future tasks add handlers into `build_app`.

## Verification (offline — manual-test adaptation per controller)
Live Telegram test (BotFather token + human on Telegram) is **DEFERRED TO THE USER**
(Step 4 of the brief). Verified offline instead:

1. Handler registration (env vars set in PowerShell before invoking python):
   `BOT_TOKEN='123:dummy' OWNER_ID='1' python -c "from app.bot import main; app = main.build_app(); print([h.callback.__name__ for g in app.handlers.values() for h in g])"`
   → prints `['cmd_start']` without raising. PASS.
   (Chose the env-vars-first approach over the importlib.reload dance — simpler, same result.)
2. Full test suite: **30 passed**, 2 warnings (pypinyin codecs.open DeprecationWarning, pre-existing/unrelated). PASS.

`run_polling` was NOT executed, as instructed.

## Concerns
None. Code matches brief verbatim; module dependencies (config, db, lookup) all present and compatible.
