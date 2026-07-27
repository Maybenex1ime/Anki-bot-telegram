# Task 3 Report — Gemini prompts + help title driven by language pack

**Status:** DONE. Full suite green (64 passed), offline build OK.

## Changes
- `app/gemini.py`: added `config` import; reworked all 5 prompt-builders
  (make_distractors, judge_meaning, gen_sentences, segment_translate,
  judge_word_order) to use `config.PACK["gemini_name"]`; gen_sentences also
  uses `config.PACK["function_words"]`. Prompts rewritten in English per brief.
  JSON output keys (`hanzi`/`pinyin`/`words`/`meaning`/`options`/`verdict`/`ok`)
  left unchanged — sentences.py contract intact.
- `app/bot/misc.py`: HELP title now f-string `Bot học {config.PACK['display_name']} SRS`.
- `tests/test_gemini.py`: added `test_prompt_uses_pack_language_name` (intercepts
  ask_json, asserts prompt carries pack language name "Chinese").

## TDD
- New test FAILED first (prompt still had "tiếng Trung", no "Chinese").
- After rework: PASS. Full suite `python -m pytest tests/ -v` → 64 passed.
- Offline build (`build_app()`) → BUILD_OK.

## Self-review
- JSON keys hanzi/pinyin/words/meaning: intact (not renamed).
- All 5 prompts converted to pack language name: yes.
- gen_sentences function_words wired: yes.
- HELP title dynamic: yes.

## Commit
- ed68823 feat: gemini prompts and help title driven by language pack

## Concerns
None. Existing structural-validation tests (make_distractors, judge_meaning,
gen_sentences, judge_word_order) still pass unchanged — they only assert
output shape, unaffected by prompt wording.
