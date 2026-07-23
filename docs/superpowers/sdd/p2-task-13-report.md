# P2 Task 13 Report — Settings + /thongke + HELP + hoàn thiện

**Status:** Done. Commit `7628f86` on `feature/srs-bot`.

## What was implemented

### Step 1 — `app/bot/settings_flow.py`
- `_view`: added masked Gemini key line (`AIza...****`, or "(chưa đặt — chế độ offline)" when empty), model, and quiz thresholds; added 2 new button rows (`st_gemkey`/`st_gmodel`, `st_quiztime`).
- `on_callback`: 3 new branches setting `pending_input` with the specified prompts.
- 3 input handlers: `gemkey_input` (saves key, deletes user's message in try/except, confirms via `update.effective_chat.send_message`; `off` clears key), `gmodel_input` (default `gemini-2.5-flash`), `quiztime_input` (validates `0 < fast < slow <= 120`).

### Step 2 — `app/bot/misc.py`
- HELP: added `/luyen` line.
- `cmd_stats`: appends a 7-day practice block via `stats.practice_summary` with labels (🔘 Trắc nghiệm / ⌨️ Tự luận / ✍️ Chính tả / 🧩 Ghép câu), only when data exists.

### Step 3 — `app/bot/main.py`
- Registered `set_gemkey`, `set_gmodel`, `set_quiztime` text actions.

### Step 4 — `docs/superpowers/sdd/HANDOFF.md`
- Rewrote "Trạng thái" to reflect phase-2 practice modes (P2 T1–13) code-complete on the deployed phase-1 bot, awaiting final review + manual test + fly deploy; tests now 58; new `/luyen` command. Kept incident postmortem and remaining-work sections; refreshed stale numbers and item 1 to point at the phase-2 9-step manual script.

## Verification
- `python -m pytest tests/ -q` → **58 passed**.
- Offline build (`BOT_TOKEN=123:dummy OWNER_ID=1`): `build_app()` → BUILD_OK; `TEXT_ACTIONS` contains `set_gemkey`, `set_gmodel`, `set_quiztime`.

## Self-review
- Key masked in `_view`: yes (`key[:4] + "..." + "****"`).
- Key message deleted after save: yes (try/except, confirmation via effective_chat).
- Quiztime validation `0 < fast < slow <= 120`: yes.

## Concerns
- None. Note: local uses system Python `C:\Python314` (no `.venv` present); `python -m pytest` works.
- Manual Telegram test (Step 5, 9 steps) and `fly deploy` remain for the project owner.
