# Handoff — trạng thái dự án

**Cập nhật:** 2026-07-22 (đêm) · **Branch:** `feature/srs-bot`

## Trạng thái

- **Hoàn thành: Task 1–18 / 18** — mỗi task qua review riêng, mọi finding ≥ Important đã sửa và re-review.
- **Final whole-branch review:** verdict **Ready to merge: Yes** (sau fix `5bbcfde`: guard double-tap chấm điểm, guard thẻ bị xóa giữa phiên, `total_reviews` tính từ `daily_log`, chống gửi trùng khi "message not modified").
- **ĐÃ DEPLOY LÊN FLY.IO và đang chạy**: app `reminder-zh-bot`, region `sin`, machine `683d61df269398`, volume `reminder_data`. Bot đã nhận lệnh thật từ owner (kể cả import CSV).
- Test: `python -m pytest tests/ -v` → **31 passed** (venv local: `.venv\Scripts\python.exe`).

## Sự cố đã xử lý (2026-07-22)

**Triệu chứng:** `/start` chạy nhưng mọi lệnh khác im lặng.
**Nguyên nhân gốc:** chủ dự án chạy `fly launch` → flyctl ghi đè `fly.toml`, thêm `[http_service]` với `auto_stop_machines='stop'` → Fly tắt máy sau ~10 phút không có HTTP traffic (bot là polling worker, không mở port) → cả bot chết, không riêng lệnh nào.
**Fix:** khôi phục `fly.toml` về bản commit (KHÔNG có `[http_service]`), `fly deploy`, `fly machine start`. Máy giờ chạy 24/7.
**Bài học:** cập nhật code chỉ dùng `fly deploy` — **đừng chạy `fly launch` lần nữa**; nếu lỡ, kiểm tra `fly.toml` không bị thêm `[http_service]`.

## Việc còn lại (cần chủ dự án)

1. **Test thủ công Telegram** các kịch bản trong plan (Tasks 8–17), ưu tiên 3 ca chưa ai chạy: xóa thẻ giữa phiên ôn, double-tap nút chấm điểm, boot đầu nạp CC-CEDICT (đã qua trên Fly).
2. Tùy chọn: gọi `set_my_commands` / khai lệnh với @BotFather để menu "/" của Telegram hiện gợi ý lệnh (hiện gõ tay vẫn chạy bình thường — chưa có trong code).
3. Quyết định merge/PR cho `feature/srs-bot`.
4. `.github/workflows/fly-deploy.yml` (flyctl tạo) auto-deploy khi push nhánh `main` — muốn dùng thì thêm secret `FLY_API_TOKEN` vào GitHub repo (`fly tokens create deploy`); không dùng thì xóa file.

## Vận hành

- Chi phí Fly ước tính ~$2.4/tháng (máy 256MB 24/7 + volume 1GB); hóa đơn <$5 thường được Fly miễn thu.
- Backup: lệnh `/backup` trong bot gửi file `reminder.db` về chat.
- Log: `fly logs -a reminder-zh-bot`; trạng thái: `fly status -a reminder-zh-bot` (flyctl tại `~\.fly\bin\`).

## Tài liệu

- Plan: `docs/superpowers/plans/2026-07-22-chinese-srs-telegram-bot.md`
- Spec: `docs/superpowers/specs/2026-07-22-chinese-srs-telegram-bot-design.md`
- Deploy runbook: `docs/DEPLOY.md`
- Ledger + brief/report từng task + final review fixes: thư mục này (`docs/superpowers/sdd/`).
