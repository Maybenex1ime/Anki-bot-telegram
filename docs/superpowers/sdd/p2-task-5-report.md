# P2 Task 5 Report — Sentence bank (`app/sentences.py`)

## Status: COMPLETE

## Commit
- `103565a` feat: sentence bank — dedupe, refill cap, enrich, audio with local-file cleanup

## TDD evidence
- **RED**: `tests/test_sentences.py` collection error (module `app.sentences` absent) — 1 error.
- **GREEN (module)**: `python -m pytest tests/test_sentences.py -v` → 5 passed
  (add_and_dedupe, ingest_examples, maybe_refill_respects_cap_and_min_cards, enrich_one, pick_prefers_least_used_and_need_words).
- **GREEN (full)**: `python -m pytest tests/ -q` → 57 passed (52 baseline + 5 new), 0 failures.

## Files changed
- `app/sentences.py` (new) — add_sentence, ingest_examples, maybe_refill, enrich_one, pick, mark_used, send_audio.
- `tests/test_sentences.py` (new) — 5 tests per brief.

## Interfaces verified before coding
- `grading.normalize_hanzi`, `gemini.gen_sentences/segment_translate`, `tts.synthesize` (via `app.cards.tts`), `db.get_setting/set_setting`, `config.MEDIA_DIR/today_iso`, `cards.create_card(..., meaning_override=)`.
- Schema `sentences` has `norm TEXT NOT NULL UNIQUE` — dedupe via caught IntegrityError. Columns words_json/pinyin/meaning/source/card_id/audio_path/audio_file_id/times_used/created_at all present.

## Self-review
- Implemented verbatim per brief. Dedupe (UNIQUE norm), empty-after-normalize → None, refill triple gate (unused<10 AND gemini_total<max_sentences AND cards>=5), enrich COALESCE preserves existing pinyin/meaning, pick orders by times_used then RANDOM with optional need_words filter, send_audio follows spec §6 volume policy (synth → send_voice → store file_id, clear audio_path, unlink local mp3; file_id-first with TelegramError fallback).
- Minor nit: `from pathlib import Path` unused in `app/sentences.py` — retained to honor "exact code verbatim" instruction. Harmless.

## Concerns
- `send_audio` requires a live Telegram context; not unit-tested (brief scope). Verified by read only.
