# Handoff — trạng thái dự án

**Cập nhật:** 2026-07-23 · **Branch:** `feature/srs-bot`

## Trạng thái

- **Phase 1 (bot SRS lõi, Task 1–18/18):** đã code xong, qua final whole-branch review (**Ready to merge: Yes**) và **ĐÃ DEPLOY LÊN FLY.IO, đang chạy 24/7** — app `reminder-zh-bot`, region `sin`, machine `683d61df269398`, volume `reminder_data`. Bot đã nhận lệnh thật từ owner (kể cả import CSV).
- **Phase 2 (chế độ luyện tập, P2 T1–13/13):** đã **code xong** trên nền phase-1 đã deploy — thêm lệnh `/luyen` (trắc nghiệm / tự luận / chính tả / ghép câu, không tác động lịch SM-2), tích hợp Gemini (MCQ nhiễu, chấm tự luận 2 tầng, sinh câu ví dụ) với fallback offline, khối thống kê luyện tập 7 ngày trong `/thongke`, và settings cho Gemini key/model + ngưỡng giờ quiz.
- **Chờ:** final whole-branch review cho phase 2 → **test tay Telegram** (kịch bản 9 bước trong plan Task 13 Step 5) → `fly deploy`.
- Test: `python -m pytest tests/ -q` → **58 passed** (local Python).

## Sự cố đã xử lý (2026-07-22)

**Triệu chứng:** `/start` chạy nhưng mọi lệnh khác im lặng.
**Nguyên nhân gốc:** chủ dự án chạy `fly launch` → flyctl ghi đè `fly.toml`, thêm `[http_service]` với `auto_stop_machines='stop'` → Fly tắt máy sau ~10 phút không có HTTP traffic (bot là polling worker, không mở port) → cả bot chết, không riêng lệnh nào.
**Fix:** khôi phục `fly.toml` về bản commit (KHÔNG có `[http_service]`), `fly deploy`, `fly machine start`. Máy giờ chạy 24/7.
**Bài học:** cập nhật code chỉ dùng `fly deploy` — **đừng chạy `fly launch` lần nữa**; nếu lỡ, kiểm tra `fly.toml` không bị thêm `[http_service]`.

## Việc còn lại (cần chủ dự án)

1. **Test thủ công Telegram**: (a) phase-2 chạy kịch bản 9 bước trong plan Task 13 Step 5 (`/luyen` 3 chế độ, Gemini bật/tắt, restart giữa câu); (b) phase-1 3 ca chưa ai chạy: xóa thẻ giữa phiên ôn, double-tap nút chấm điểm, boot đầu nạp CC-CEDICT (đã qua trên Fly).
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
