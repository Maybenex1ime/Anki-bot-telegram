# Task 4 Report: TTS wrapper (app/tts.py)

## Status: COMPLETE

## Files changed
- `app/tts.py` (new) — `async synthesize(text, voice, out_path) -> bool`, edge-tts wrapper with graceful failure (swallows all exceptions, cleans up partial file, returns False).
- `tests/test_tts.py` (new) — 2 mocked unit tests (no network): OK path + failure path.
- `pytest.ini` (new) — `asyncio_mode = auto` at repo root.

## TDD evidence
- **RED:** `python -m pytest tests/test_tts.py -v` → collection error `ImportError: cannot import name 'tts' from 'app'` (module not yet created).
- **GREEN:** after implementing `app/tts.py` → `2 passed in 0.24s`.
  - `test_synthesize_ok` PASSED
  - `test_synthesize_failure_returns_false_and_no_file` PASSED

## Smoke test (real network, Step 4)
`asyncio.run(tts.synthesize('学习','zh-CN-XiaoxiaoNeural', Path('data/media/smoke.mp3')))` → returned `True`; file created at 10656 bytes; file deleted afterward (confirmed gone). Network path works.

## Full suite
`python -m pytest -v` → **17 passed, 2 warnings in 0.57s**. Warnings are pre-existing third-party `pypinyin` `codecs.open()` DeprecationWarnings, unrelated to this task.

## Commit
- `5dfa353` — `feat: edge-tts wrapper with graceful failure` (3 files, 53 insertions).
- Note: used `git add` + `git commit -m` instead of the brief's `git commit -am`, because all three files were untracked and `-am` only stages already-tracked files.

## Self-review
- Implementation matches brief verbatim.
- `except Exception` swallows all errors per spec §8 (TTS failure must not block card creation). Confirmed by failure test.
- Partial-file cleanup guarded by nested try/except OSError — safe.
- `data/` is gitignored, so the empty `data/media/` dir created by the smoke test is not committed.

## Concerns
- None blocking. Git reported CRLF conversion warnings on the new files (repo has no `.gitattributes` normalizing line endings) — cosmetic on Windows, consistent with existing files.
