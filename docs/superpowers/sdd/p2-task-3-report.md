# P2 Task 3 Report — Gemini client (`app/gemini.py`)

## Status: DONE

## TDD Evidence
- **RED**: `python -m pytest tests/test_gemini.py -v` → `ImportError: cannot import name 'gemini' from 'app'` (1 error during collection) before implementation.
- **GREEN (module)**: 6 passed — `test_ask_json_ok`, `test_ask_json_no_key_http_error_and_garbage`, `test_make_distractors_validates`, `test_judge_meaning_validates`, `test_gen_sentences_filters`, `test_judge_word_order_validates`.
- **GREEN (full suite)**: `python -m pytest tests/` → **46 passed, 2 warnings in 1.42s** (40 prior + 6 new). The 2 warnings are pre-existing pypinyin `codecs.open()` deprecations, unrelated to this task.

## Files Changed
- `app/gemini.py` (new) — verbatim from brief: `available`, `ask_json` (JSON mode, 20s timeout, ≤2 retries, every error → None), `make_distractors`, `judge_meaning`, `gen_sentences`, `segment_translate`, `judge_word_order`.
- `tests/test_gemini.py` (new) — verbatim from brief (FakeResp/FakeClient mocks of `httpx.AsyncClient`).

## Dependencies
- `httpx` already importable (0.28.1, transitive via python-telegram-bot). `requirements.txt` NOT modified, per brief guidance.

## Self-Review
- All Gemini paths return `None` on any failure: no key, HTTP != 200 (retries then None), bad/garbage JSON, network exception, and each producer validates structure (options len==3, verdict in enum, ok is bool, words non-empty). Confirmed by `test_ask_json_no_key_http_error_and_garbage` covering all four failure classes.
- String length caps applied (options 80, notes 200, hanzi 100, words 20 chars / 20 items) per brief.
- `_key` falls back to `GEMINI_API_KEY` env when setting empty.
- Config seeds `gemini_api_key=""` and `gemini_model="gemini-2.5-flash"` (verified) so `db.get_setting` returns sane defaults.

## Concerns
- None functional. Code matches the brief exactly; no deviations. Git reported LF→CRLF normalization warnings on commit (cosmetic, Windows line-endings).

## Commit
- `50498db feat: gemini client with JSON mode, validation, None-on-error`
