# Task 11 Report: Thu âm & tự so giọng (voice self-comparison)

## What I implemented
- Created `app/bot/voice_flow.py` verbatim from the brief spec:
  - `on_rec_callback` (`@owner_only_callback`): handles `vc_rec:<cid>`, sets kv `awaiting_voice`, prompts user to record, tracks the prompt message in `session["aux"]` for later cleanup.
  - `on_voice`: no-op if not awaiting; else stores `voice_file_id`, replays standard audio + user's voice + a compare prompt, appends all sent message ids (incl. the user's voice) to `session["aux"]`. AZURE-SLOT kept as a comment marker only.
- Wired `app/bot/main.py`:
  - Import added: `voice_flow`.
  - `CallbackQueryHandler(voice_flow.on_rec_callback, pattern=r"^vc_rec:")`.
  - `MessageHandler(owner_filter & filters.VOICE, voice_flow.on_voice)`.

## Verification (offline, per binding decision 1)

Registration check:
```
BOT_TOKEN=x OWNER_ID=1 DATA_DIR="$(mktemp -d)" .venv/Scripts/python.exe -c "...build_app + handler scan..."
```
Output:
```
build_app OK
vc_rec CallbackQueryHandler registered: True
VOICE MessageHandler (on_voice) registered: True
```

Full suite:
```
.venv/Scripts/python.exe -m pytest tests/ -q
30 passed in 3.99s
```

## Files changed
- `app/bot/voice_flow.py` (new)
- `app/bot/main.py` (import + 2 handler registrations)

## Self-review findings
- Code matches the brief spec exactly. No extra abstractions, no Azure implementation (comment marker only per decision 3).
- `voice_file_id` column already exists in `db.SCHEMA` — UPDATE is safe.
- `send_card_audio` signature `(context, chat_id, row)` matches Task 10.
- Manual Telegram test (brief Step 3) deferred per decision 1.
- Full suite green, pristine output.

## Issues/concerns
None.
