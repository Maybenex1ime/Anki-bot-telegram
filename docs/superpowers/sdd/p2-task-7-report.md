# Task 7 Report — Mode picker cho `/on`

**Status:** DONE — all steps implemented, verified, committed.

**Commit:** `67bd969` feat: /on mode picker + session mode plumbing (classic path intact)

## Changes
- `app/bot/review_flow.py`:
  - Added `MODE_LABEL` map.
  - `cmd_review` now calls `show_mode_picker`; new `show_mode_picker(context, chat_id)`
    guards on empty queue, offers "▶️ Như lần trước" row when `review_mode` setting is a
    known mode, plus 🃏/🔘/⌨️ rows.
  - `start_session(context, chat_id, mode="classic", level="", practice=False, queue=None)` —
    extended signature; session dict now carries `ok`, `mode`, `level`, `practice`, `q`.
  - `_show_front` branches to `quiz_flow.show_question` when `mode != "classic"` (local import).
  - `_advance` renamed to public `advance`; alias `_advance = advance` retained. End branch
    now shows `🏁 Luyện xong! Đúng {ok}/{done}` when `practice`, else the classic streak summary.
  - `on_callback`: `rv_start` now opens the picker; new `rv_mc_levels` (level sub-menu) and
    `rv_mode:<...>` (persists `review_mode`, deletes picker msg, starts session) branches placed
    BEFORE the `session` load — they need no open session. int-parse of later `rv_*` callbacks
    stays safe because these branches return first.
- `app/bot/quiz_flow.py`: minimal stub `show_question` showing "⚠️ Chế độ này đang được xây."
  (Task 8 replaces it).

## Classic path
Byte-identical behavior preserved for `mode="classic"`; stale-tap and deleted-card guards
in `rv_rate`/`rv_listen`/`rv_show` left intact.

## Verification
- `python -m pytest tests/ -q` → **58 passed**.
- Offline build (`BOT_TOKEN=123:dummy OWNER_ID=1`, `build_app()`) → **BUILD_OK**.
- REPL: `advance` callable, `_advance is advance` True, signature correct, `quiz_flow.show_question` importable.

## Concerns
None. `quiz_flow.py` intentionally minimal per brief (Task 8 will replace).
