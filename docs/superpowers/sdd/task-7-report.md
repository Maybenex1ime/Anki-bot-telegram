# Task 7 Report: Card service (`app/cards.py`)

## Status: COMPLETE

## TDD cycle
- **RED**: Wrote `tests/test_cards.py` (5 tests) → `ImportError: cannot import name 'cards'` (collection error, 0 items).
- **GREEN**: Implemented `app/cards.py` per brief → `5 passed`.

## Files changed
- `app/cards.py` (new) — create_card, retry_audio, get_card, is_new, exists_hanzi, build_queue, apply_rating.
- `tests/test_cards.py` (new) — 5 tests, TTS mocked (no network).

## Test summary
- `tests/test_cards.py`: 5 passed.
- Full suite `tests/`: **30 passed**, 2 warnings (pypinyin `codecs.open` DeprecationWarning — third-party, pre-existing).

## Commit
- `cac8d25` feat: card service — create pipeline, review queue, rating

## Self-review
- Implementation matches brief interfaces verbatim; all consumed modules (lookup/tts/srs/stats/db/config) confirmed present with expected signatures before coding.
- Verified test 4 logic: `apply_rating(AGAIN)` on a new card sets lapses=1 (becomes a review) and records new_introduced=1, so with `new_per_day=2` only 1 new slot remains → `q[1:] == [ids[1]]`. Passes.
- Audio pipeline synths after insert; TTS failure leaves `audio_path=''` (verified by test_tts_failure).

## Concerns
- None functional. Minor: `retry_audio` reuses `f"{cid}.mp3"` filename, so a re-synth overwrites the same media file (intended). Git reports LF→CRLF line-ending normalization on Windows checkout (cosmetic).
