# Task 2 Report — Korean language pack

## Status: DONE (63 passed, committed)

Commit: `647d60d feat: Korean language pack (romanizer + cc-kedict parser + ko voice)`

## Changed files
- `requirements.txt` — added `korean-romanizer>=0.25`, `PyYAML>=6` (installed korean-romanizer 0.28.0, PyYAML 6.0.3).
- `app/langpack.py` — added imports (`yaml`, `Romanizer`), `_KO_PUNCT`, `_ko_romanize`, `_ko_phonetic_key`, `_parse_kedict`, and the `"ko"` LANGS entry (10 keys). `zh` untouched.
- `tests/test_langpack.py` — added `test_ko_pack_romanize_and_normalize` + `test_ko_parse_kedict`.

## Two runtime-verification points (verified empirically)

1. **korean-romanizer output** — `Romanizer('안녕').romanize()` → `'annyeong'`; `Romanizer('안녕하세요').romanize()` → `'annyeonghaseyo'`. Matches the brief's assertions exactly; no adjustment needed. Import path `from korean_romanizer.romanizer import Romanizer` is correct.

2. **cc-kedict file form** — `.gz` variant is **404 Not Found**. Only the **uncompressed** `kedict.yml` exists (raw.githubusercontent, 1,953,328 bytes, `text/plain`). Adjusted from the brief:
   - `dict_file="kedict.yml"` (was `kedict.yml.gz`)
   - `dict_url="https://github.com/mhagiwara/cc-kedict/raw/master/kedict.yml"` (uncompressed raw)
   - `_parse_kedict` opens with `open(path, encoding="utf-8")` (not `gzip.open`)
   - Test fixture rewritten to plain `p.write_text(...)` instead of `gzip.open`, so it matches the real uncompressed form. Assertions unchanged.
   - Verified real schema against a live sample: entries use `word` / `romaja` / `defs[].def` keys — matches the parser. (Duplicate `word` entries with different `pos` exist; parser emits one row each, same as cedict — fine.)

Boot loader (`app/lookup.py:ensure_cedict`) just downloads `dict_url` to `dict_file` then calls `parse_dict(path)` — uncompressed plain-open path is correct end-to-end.

## Test output
`python -m pytest tests/ -v` → **63 passed, 2 warnings** (the 2 warnings are pre-existing pypinyin `codecs.open` DeprecationWarnings, unrelated).

## Self-review
- zh entry and helpers untouched; 61 prior tests still green.
- `_ko_phonetic_key` needs no NFD normalize (romaja is plain ASCII, unlike toned pinyin) — verified `"an nyeong"` → `"annyeong"`.
- `_ko_romanize` wrapped in try/except returning original text for non-Hangul (mixed Hanja/digits) — non-blocking, matches brief intent.
- `~` added to `_KO_PUNCT` beyond zh set — intentional per brief.
- No findings requiring fixes.

## Concerns
- None blocking. Real dict download at boot untested against network (unit tests use local fixture, by design); schema confirmed via live sample so boot load should succeed on first `ensure_cedict`.
