# Handoff — trạng thái dự án

**Cập nhật:** 2026-07-23 · **Branch:** `feature/srs-bot`

## Trạng thái

- **Phase 1 (bot SRS lõi, Task 1–18/18):** đã code xong, qua final whole-branch review (**Ready to merge: Yes**) và **ĐÃ DEPLOY LÊN FLY.IO, đang chạy 24/7** — app `reminder-zh-bot`, region `sin`, machine `683d61df269398`, volume `reminder_data`. Bot đã nhận lệnh thật từ owner (kể cả import CSV).
- **Phase 2 (chế độ luyện tập, P2 T1–13/13):** code xong, final whole-branch review **Ready to merge: Yes** (`docs/superpowers/sdd/p2-final-review.md`), qua thêm một lượt `/simplify` (commit `a3c4ae1`), và **ĐÃ DEPLOY 2026-07-23 07:16Z** (release version 3, image `deployment-01KY6X9FDGMHXVZ3CYP1WWMN7Y`). Thêm `/luyen` (trắc nghiệm / tự luận / chính tả / ghép câu, không tác động lịch SM-2), tích hợp Gemini (MCQ nhiễu, chấm tự luận 2 tầng, sinh câu) với fallback offline, thống kê luyện tập 7 ngày trong `/thongke`, settings Gemini key/model + ngưỡng giờ quiz.
- **Xác minh sau deploy:** log khởi động sạch (scheduler đặt lại 4 job, polling chạy); **không** có dòng "Đã nạp CC-CEDICT" → bảng từ điển cũ còn nguyên; volume `/data` 19M/974M, `reminder.db` 15.1MB được ghi lúc 07:19 → migration additive chạy, không mất dữ liệu.
- **Chờ:** test tay Telegram (9 bước trong plan Task 13 Step 5 + 8 ca bổ sung trong `p2-final-review.md`) — làm trực tiếp trên bot đang chạy.
- Test tự động: `python -m pytest tests/ -q` → **58 passed** (local Python).

## Sự cố đã xử lý (2026-07-22)

**Triệu chứng:** `/start` chạy nhưng mọi lệnh khác im lặng.
**Nguyên nhân gốc:** chủ dự án chạy `fly launch` → flyctl ghi đè `fly.toml`, thêm `[http_service]` với `auto_stop_machines='stop'` → Fly tắt máy sau ~10 phút không có HTTP traffic (bot là polling worker, không mở port) → cả bot chết, không riêng lệnh nào.
**Fix:** khôi phục `fly.toml` về bản commit (KHÔNG có `[http_service]`), `fly deploy`, `fly machine start`. Máy giờ chạy 24/7.
**Bài học:** cập nhật code chỉ dùng `fly deploy` — **đừng chạy `fly launch` lần nữa**; nếu lỡ, kiểm tra `fly.toml` không bị thêm `[http_service]`.

## Việc còn lại (cần chủ dự án)

1. **Test thủ công Telegram trên bot đang chạy**: (a) phase-2 kịch bản 9 bước trong plan Task 13 Step 5 + 8 ca bổ sung trong `p2-final-review.md`; (b) phase-1 3 ca chưa ai chạy: xóa thẻ giữa phiên ôn, double-tap nút chấm điểm, boot đầu nạp CC-CEDICT (đã qua trên Fly).
   - Lùi bản nếu hỏng: `flyctl releases -a reminder-zh-bot` rồi `flyctl deploy --image registry.fly.io/reminder-zh-bot:<deployment-cũ>`. Bản trước phase 2 là version 2 (`deployment-01KY5AKFV9EM5X5Y14Y5C8F7EZ`).
1b. **Bật Gemini (tùy chọn)**: lấy key miễn phí tại aistudio.google.com → `/settings` → 🤖 Gemini key (bot tự xóa tin nhắn chứa key). Không có key thì mọi chế độ vẫn chạy offline.
2. Tùy chọn: gọi `set_my_commands` / khai lệnh với @BotFather để menu "/" của Telegram hiện gợi ý lệnh (hiện gõ tay vẫn chạy bình thường — chưa có trong code).
3. Quyết định merge/PR cho `feature/srs-bot`.
4. `.github/workflows/fly-deploy.yml` (flyctl tạo) auto-deploy khi push nhánh `main` — muốn dùng thì thêm secret `FLY_API_TOKEN` vào GitHub repo (`fly tokens create deploy`); không dùng thì xóa file.

## Vận hành

- Chi phí Fly ước tính ~$2.4/tháng (máy 256MB 24/7 + volume 1GB); hóa đơn <$5 thường được Fly miễn thu.
- Backup: lệnh `/backup` trong bot gửi file `reminder.db` về chat.
- Log: `flyctl logs -a reminder-zh-bot`; trạng thái: `flyctl status -a reminder-zh-bot`.
- flyctl: máy cũ ở `~\.fly\bin\`; máy D:\Reminder hiện tại cài qua `winget install --id Fly-io.flyctl` (nằm trong `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Fly-io.flyctl_*\flyctl.exe`).
- `flyctl ssh console -C` tách tham số theo dấu cách và PowerShell nuốt dấu nháy → chỉ chạy được lệnh không có dấu nháy (VD `ls -la /data`); muốn chạy script thì upload trước.
- Push GitHub từ máy này: `$env:GCM_INTERACTIVE='always'; $env:GIT_TERMINAL_PROMPT='1'; git -c credential.interactive=always push`.

## Kiến trúc langpack — 2 bot song song (Task 4)

- **BOT_LANG env** chọn ngôn ngữ lúc chạy: `zh` (tiếng Trung, mặc định trong `Dockerfile`) hoặc `ko` (tiếng Hàn). Cùng một codebase/image, khác ngôn ngữ chỉ qua biến môi trường — secret `BOT_LANG=ko` ghi đè mặc định của Dockerfile.
- **2 app Fly riêng biệt:** `reminder-zh-bot` (đang chạy) và `reminder-ko-bot` (dựng theo runbook). 2 app = 2 volume = 2 DB độc lập, không chia sẻ thẻ.
- **Quy trình "sửa 1 lần, deploy 2 lần":** mọi cập nhật code chạy `flyctl deploy -a reminder-zh-bot` rồi `flyctl deploy -a reminder-ko-bot` (cùng codebase). KHÔNG `fly launch` (xem sự cố 2026-07-22).
- **Dựng bot Hàn:** làm theo `docs/DEPLOY-ko.md`.
- **Từ điển Hàn:** bot `ko` dùng **CC-KEDICT** (kho nhỏ) — nhiều lượt tra trả rỗng; khi rỗng thì **nhập nghĩa tay** vào thẻ. Bot `zh` dùng CC-CEDICT như cũ.

## Tài liệu

- Plan: `docs/superpowers/plans/2026-07-22-chinese-srs-telegram-bot.md`
- Spec: `docs/superpowers/specs/2026-07-22-chinese-srs-telegram-bot-design.md`
- Deploy runbook: `docs/DEPLOY.md` (bot Trung); `docs/DEPLOY-ko.md` (bot Hàn)
- Ledger + brief/report từng task + final review fixes: thư mục này (`docs/superpowers/sdd/`).
