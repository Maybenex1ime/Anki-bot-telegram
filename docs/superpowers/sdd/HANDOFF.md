# Handoff — tiếp tục dự án trên thiết bị khác

**Cập nhật:** 2026-07-22 · **Branch:** `feature/srs-bot`

## Trạng thái

- **Hoàn thành: Task 1–9 / 18** (đã qua review từng task, mọi finding Important đã sửa).
  - Lõi: config + SQLite (Task 1), SM-2 (2), pinyin + CC-CEDICT (3), edge-tts (4), CSV parser (5), stats/streak (6), card service (7).
  - Bot: skeleton + auth 1 người + /start (8), text router + luồng tạo thẻ với preview (9, kèm fix html.escape `fe8a630`).
- **Tiếp theo: Task 10** (luồng ôn tập /on) rồi 11–18 theo plan.
- Test: `python -m pytest tests/ -v` → 30 passed.

## Cách tiếp tục

1. Clone repo, checkout `feature/srs-bot`.
2. `python -m pip install -r requirements-dev.txt` (Python 3.12+).
3. Đọc plan: `docs/superpowers/plans/2026-07-22-chinese-srs-telegram-bot.md` — làm tiếp từ **Task 10**.
4. Quy trình đang dùng: superpowers:subagent-driven-development — mỗi task: brief → implementer (model **Opus** theo yêu cầu chủ dự án) → review-package → task reviewer → fix nếu có finding ≥ Important → re-review → ghi ledger.
5. Ledger + brief/report từng task: thư mục này (`docs/superpowers/sdd/`). Trên máy mới, chép lại vào `.git/sdd/` nếu muốn dùng đúng đường dẫn cũ của script, hoặc trỏ trực tiếp vào đây.

## Lưu ý đã ghi nhận cho các task sau

- Task 10 & 14: nhớ `html.escape` mọi trường thẻ chèn vào tin nhắn `parse_mode="HTML"` (bài học từ Task 9).
- Test thủ công qua Telegram (Task 8–17) đang **hoãn đến cuối** — cần BOT_TOKEN từ BotFather + OWNER_ID (@userinfobot); kịch bản test nằm trong từng task của plan.
- Python local 3.14 chạy OK; Docker image dùng 3.12.
- Minor findings tồn đọng (chuyển cho final review): xem `progress.md`.
