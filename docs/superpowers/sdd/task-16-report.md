# Task 16 Report: CSV import (`/csv` flow)

## What I implemented
- Created `app/bot/csv_flow.py` exactly per brief: `cmd_csv` (guide), `on_document`
  (accepts `.csv`, UTF-8-sig decode, stores content in kv `pending_csv`, deck-picker
  keyboard `cs_deck:<id>`), `on_callback` (parses, skips duplicate hanzi, progress
  message every 10 cards, final report with up to 15 error lines).
- Wired into `app/bot/main.py`: import `csv_flow`; `CommandHandler("csv")`,
  `CallbackQueryHandler(pattern=r"^cs_deck:")`, and
  `MessageHandler(owner_filter & filters.Document.FileExtension("csv"))`.

## HTML escaping decision
Reviewed per binding decision #1. The only `parse_mode="HTML"` message is the static
`GUIDE` constant — no user-authored content is interpolated into any HTML message.
All prompts, progress, and the final report use plain-text `reply_text` /
`edit_message_text` (error reasons from `parse_csv` are fixed Vietnamese strings).
Nothing to escape. Deck names appear only in InlineKeyboardButton labels (plain text).

## Verification (offline, per decision #2)
Command (env: `BOT_TOKEN=x OWNER_ID=1 DATA_DIR=<temp>`):
```
python -c "build_app(); inspect handlers"
```
Output:
```
build_app OK
csv command: [['csv']]
cs_deck callback: ['^cs_deck:']
document handler: ["<filters.User(1) and filters.Document.FileExtension('csv')>"]
```

Full test suite:
```
.venv/Scripts/python.exe -m pytest tests/ -q
..............................                                           [100%]
30 passed in 4.20s
```

## Files changed
- `app/bot/csv_flow.py` (new)
- `app/bot/main.py` (import + 3 handler registrations)

## Self-review findings
- Interfaces verified against source: `parse_csv` returns `CsvResult(rows, errors)`
  with `CsvRow(hanzi, pinyin, meaning, example)`; `cards.create_card` is async with
  matching kwargs; `cards.exists_hanzi`, `db.kv_get/set/del` signatures match.
- YAGNI: no extra abstractions; code matches brief verbatim.
- Suite green, pristine output.

## Issues/concerns
None. Manual Telegram testing deferred project-wide (no BOT_TOKEN).
