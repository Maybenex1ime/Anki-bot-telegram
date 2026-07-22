# Handoff — trạng thái dự án

**Cập nhật:** 2026-07-22 · **Branch:** `feature/srs-bot`

## Trạng thái

- **Hoàn thành: Task 1–18 / 18** — toàn bộ plan đã xong, mỗi task qua review riêng, mọi finding ≥ Important đã sửa và re-review.
- **Final whole-branch review:** verdict **Ready to merge: Yes** (sau fix commit `5bbcfde`: guard double-tap chấm điểm, guard thẻ bị xóa giữa phiên, `total_reviews` tính từ `daily_log`, chống gửi trùng khi "message not modified").
- Test: `python -m pytest tests/ -v` → **31 passed** (venv: `.venv\Scripts\python.exe`).

## Việc còn lại (cần chủ dự án — không làm tự động được)

1. **Test thủ công qua Telegram** (kịch bản trong từng task của plan, Tasks 8–17): cần `BOT_TOKEN` (@BotFather) + `OWNER_ID` (@userinfobot). Chạy local: `$env:BOT_TOKEN="…"; $env:OWNER_ID="…"; .venv\Scripts\python.exe -m app.bot.main`. Chú ý test riêng: xóa thẻ giữa phiên ôn, double-tap nút chấm điểm, lần đầu nạp CC-CEDICT.
2. **Deploy Fly.io** (Task 18 Step 4): theo runbook `docs/DEPLOY.md`.
3. Quyết định merge/PR cho branch `feature/srs-bot`.

## Tài liệu

- Plan: `docs/superpowers/plans/2026-07-22-chinese-srs-telegram-bot.md`
- Spec: `docs/superpowers/specs/2026-07-22-chinese-srs-telegram-bot-design.md`
- Ledger + brief/report từng task + final review fixes: thư mục này (`docs/superpowers/sdd/`).
