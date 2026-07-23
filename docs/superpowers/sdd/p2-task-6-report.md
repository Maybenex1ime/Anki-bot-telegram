# Task 6 Report: CSV `ví_dụ_thêm` + ingest ví dụ vào kho câu

**Status:** DONE
**Commit:** `beec631` — feat: CSV vi_du_them column + example ingestion into sentence bank
**Branch:** feature/srs-bot

## Changes
- `app/csv_import.py`: added aliases `ví_dụ_thêm`/`vi_du_them` → `extra_examples`; new
  `CsvRow.extra_examples: str = ""` field; populated via `cell(row, "extra_examples")`.
- `app/bot/csv_flow.py`: GUIDE header sample now `hán,pinyin,nghĩa,ví_dụ,ví_dụ_thêm` +
  description line for `ví_dụ_thêm`. In `on_callback` loop, after create/skip branch,
  look up `card_id` (works for both created and duplicate cards) and call
  `sentences.ingest_examples` for `r.example` and `r.extra_examples`, accumulating into
  `sent_added`; report line `📚 Thêm {sent_added} câu...` appended when `sent_added > 0`.
- `app/bot/create_flow.py`: `pc_save` branch ingests `row["example"]` (card_id `row["id"]`)
  after successful `create_card`.
- `tests/test_csv_import.py`: added `test_extra_examples_column` (TDD: failed → green).

## Verification
- `pytest tests/test_csv_import.py -v` → 6 passed.
- Full suite `pytest tests/` → 58 passed (was 57; +1 new).
- Offline build: `BOT_TOKEN=123:dummy OWNER_ID=1 python -c "from app.bot.main import build_app; build_app()"` → BUILD_OK.

## Concerns
- None blocking. GUIDE's example row (`VD:`) still shows the 4-column form; brief only
  required updating the header-sample line and adding the description line, so left as-is.
