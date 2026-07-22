# Task 14 Report: Tìm/xem/sửa/xóa thẻ (`/tim`)

## What I implemented
- Created `app/bot/manage_flow.py` per the brief: `/tim <query>` search, card detail view with full SRS info, callbacks `cd_view/cd_listen/cd_myvoice/cd_edit/cd_img/cd_move/cd_move_set/cd_del/cd_del_ok`, and the `card_edit` text action.
- Extended `app/bot/textrouter.on_photo` with the `awaiting_image` branch (pending_card takes priority, then awaiting_image), per Step 2.
- Wired `app/bot/main.py`: import `manage_flow`, `register("card_edit", ...)`, `/tim` CommandHandler, `^cd_` CallbackQueryHandler.

### HTML-escaping (binding decision 1, established Task 9)
The brief's code omits escaping; applied it anyway matching `review_flow.py`:
- `_detail`: `html.escape` on `hanzi`, `pinyin`, `meaning` (kept literal `<i>(trống)</i>` fallback), `example`, and deck `name`.
- `cd_del` confirm: `html.escape` on `hanzi`.
- Numeric/date fields (`due_date`, `interval`, `ease`, `repetitions`, `lapses`) are DB-controlled, not user-authored — left as-is.
- `cmd_search` reply and `card_edit_input` reply use plain `reply_text` (no parse_mode) — no escaping needed. Button labels are plain text — no escaping (per decision 1).

## Verification (offline — manual Telegram testing deferred, decision 2)
Command:
```
BOT_TOKEN=x OWNER_ID=1 DATA_DIR="$(mktemp -d)" .venv/Scripts/python.exe -c "
from app.bot import main, textrouter
from telegram.ext import CommandHandler, CallbackQueryHandler
app = main.build_app()
cmds = [h.commands for hs in app.handlers.values() for h in hs if isinstance(h, CommandHandler)]
cbs = [h.pattern.pattern for hs in app.handlers.values() for h in hs if isinstance(h, CallbackQueryHandler)]
print('build_app OK')
print('tim registered:', any('tim' in c for c in cmds))
print('cd_ callback registered:', any(p == '^cd_' for p in cbs))
print('card_edit action:', 'card_edit' in textrouter.TEXT_ACTIONS)
"
```
Output:
```
build_app OK
tim registered: True
cd_ callback registered: True
card_edit action: True
```

Full suite:
```
.venv/Scripts/python.exe -m pytest tests/ -q
30 passed in 3.19s
```

## Files changed
- `app/bot/manage_flow.py` (new)
- `app/bot/textrouter.py` (on_photo)
- `app/bot/main.py` (import + register + 2 handlers)

## Self-review findings
- Completeness: all brief steps done except deferred manual test (decision 2). Interfaces match brief exactly.
- Discipline (YAGNI): no code beyond the brief; escaping is the only deviation and it is a binding decision.
- `field` in `card_edit_input` f-string SQL is safe — whitelisted at callback time (only pinyin/meaning/example buttons produce it).
- Tests green, pristine output.

## Concerns
None.

## Fix (reviewer finding — edit field whitelist)
Reviewer flagged that `field = parts[2]` in the `cd_edit` branch was persisted to `pending_input` and later interpolated raw into SQL (`UPDATE cards SET {field}=?`) without validation; the `# đã whitelist ở callback` comment was false. Added guard `if field not in FIELDS: return` before `kv_set`, making the existing `card_edit_input` comment accurate.

Test command + output:
```
.venv/Scripts/python.exe -m pytest tests/ -q
30 passed in 3.43s
```
