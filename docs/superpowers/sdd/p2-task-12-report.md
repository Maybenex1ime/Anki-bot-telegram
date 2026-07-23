# Task 12 Report: Ghép từ thành câu (sentence-builder)

**Status:** Done. Committed `51d1589`.

## What was implemented
- Added `import json` to `app/bot/practice_flow.py`.
- Replaced the `pr_build` stub with the full sentence-builder flow.
- Added helpers `_build_next`, `_build_kb`, `_build_render` and constant `BUILD_NEXT_KB`.
- Added callback branches: `pr_build`, `pr_b_w:<i>`, `pr_b_undo`, `pr_b_sub`, `pr_b_skip`, `pr_b_next`, `pr_b_stop`.

Flow: `_build_next` refills + enriches (fire-and-forget await), picks a `need_words=True` sentence,
shuffles word indices via `grading.shuffle_words`, persists `build_state` kv, marks sentence used, renders.
Tap-to-arrange builds `chosen` (index list); submit requires all words used, compares
`"".join(chosen words)` against `grading.normalize_hanzi(hanzi)`, and on mismatch falls back to
`gemini.judge_word_order` for alternate-order acceptance. `stats.bump_practice(..., "build", ok)` records.

## Verification
- Full suite: **58 passed** (`python -m pytest -q`).
- Offline build: `BOT_TOKEN=123:dummy OWNER_ID=1` → build_app OK, **handler count = 22** (unchanged).

## Self-review findings
- Duplicate-word buttons: handled — callback_data keyed by index `i`, distinct even for identical word strings.
- Undo on empty `chosen`: guarded (returns early).
- Submit with unused words: guarded (alert, no state mutation).
- HTML escaping: meaning, current attempt, judge note, and `_sentence_reveal` output all `html.escape`d;
  button labels are plain text (not HTML-parsed).

## Concerns
- **Double `q.answer` on the "submit with unused words" path (brief-specified):** `on_callback` calls
  `await q.answer()` unconditionally at the top (line 36), and the `pr_b_sub` guard then calls
  `await q.answer("Dùng hết các từ đã rồi nộp nhé!")` again. Telegram rejects a second answer for the
  same callback query, so on that guard path the toast may not show and PTB can raise BadRequest
  (uncaught in `on_callback`). Implemented verbatim per the approved brief; not exercised by the mocked
  suite. Flagging in case the guard-path UX should instead answer once (e.g. move the top-level answer
  into branches, or drop the redundant top answer for build branches).

## Report path
`D:\Reminder\.git\sdd\p2-task-12-report.md`

## Fix: callback ack (completed by controller)
Implementer agent hit session limit mid-fix (had converted 7 branches). Controller completed remaining branches mechanically per the same pattern: per-branch `await q.answer()` for pr_d_stop, pr_build, pr_b_w, pr_b_undo, pr_b_skip, pr_b_next, pr_b_stop; pr_b_sub answers exactly once per path (not-st ack+return / unused-words toast / success plain ack). Verified: 58 passed, build_app OK handlers=22. Commit 206a5b6.
