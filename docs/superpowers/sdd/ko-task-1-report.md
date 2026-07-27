# Task 1 Report — langpack extraction + route zh through it

## Status: DONE — 61/61 tests green, committed.

## Commit
- `59571fa` refactor: extract language pack, route zh through it (behavior unchanged)

## What changed
- **Created `app/langpack.py`** — `LANGS` dict with the `zh` pack (display_name, romanize, phonetic_key, normalize_text, tts_voice, gemini_name, function_words, dict_url, dict_file, parse_dict) + `get(lang)` raising `ValueError` on unknown. Only `zh` (ko is Task 2). All zh-specific logic (pypinyin romanize, NFD phonetic key, punctuation normalize, CC-CEDICT regex+parser) moved here verbatim.
- **`app/config.py`** — added `LANG = os.environ.get("BOT_LANG", "zh")` and `PACK = langpack.get(LANG)`; `DEFAULT_SETTINGS["tts_voice"]` now reads `PACK["tts_voice"]`; removed hardcoded `CEDICT_URL`.
- **`app/lookup.py`** — `gen_pinyin`/`ensure_cedict` now read `config.PACK` (romanize, dict_file, dict_url, parse_dict); `parse_cedict_line` kept, delegates to `langpack._CEDICT_LINE`. Public names unchanged.
- **`app/quiz.py`** — `pinyin_key` delegates to `config.PACK["phonetic_key"]`; dropped now-unused `import unicodedata`, added `config` import.
- **`app/grading.py`** — `normalize_hanzi` delegates to `config.PACK["normalize_text"]`; removed `_HANZI_PUNCT` constant, added `config` import.
- **`tests/test_langpack.py`** — 3 new TDD tests (pack shape, invalid-lang raises, config defaults to zh).

## Test output
`python -m pytest tests/ -v` → **61 passed** (58 pre-existing + 3 new).
- The 3 new: `test_langpack.py::{test_zh_pack_present_and_shaped, test_get_invalid_lang_raises, test_config_defaults_to_zh}`.
- The 58 pre-existing behavior-lock tests (test_cards, test_csv_import, test_db, test_gemini, test_grading, test_lookup, test_practice_schema, test_quiz, test_sentences, test_srs, test_stats, test_tts) all stayed green with **no edits** — confirms zero zh behavior drift.
- Offline build check passed: `BOT_LANG` unset, `build_app()` → BUILD OK.

## Self-review
- **zh behavior drift?** None. Each delegated function's internals are byte-identical logic to before (same pypinyin TONE style, same NFD/isascii/isalpha key, same punct string, same CC-CEDICT regex + `"; ".join(meaning.split("/"))`). The 5 relevant behavior-lock tests (gen_pinyin, parse_cedict_line, pinyin_key, normalize_hanzi, lookup) pass unmodified.
- **Circular import?** No. `langpack.py` imports only stdlib + pypinyin (never `config`). `config` imports `langpack`; lookup/quiz/grading import `config`. `build_app()` succeeds.
- **BOT_LANG not LANG?** Confirmed — `config.py` reads `os.environ.get("BOT_LANG", "zh")`, avoiding the Linux `LANG` locale collision.

## Concerns
- `gemini_name` and `function_words` pack keys are defined but not yet consumed by any app code (gemini.py still hardcodes prompts) — intended for the ko refactor in a later task. No action needed for Task 1.
- Line-ending warnings (LF→CRLF) on commit are cosmetic (Windows autocrlf), no functional impact.
