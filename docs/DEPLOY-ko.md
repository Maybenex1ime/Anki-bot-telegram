# Dựng bot tiếng Hàn (reminder-ko-bot)

Tiền đề: bot Trung đã redeploy OK sau refactor langpack (Task 4 Step 2).

1. BotFather: /newbot → lấy BOT_TOKEN mới cho bot Hàn.
2. Tạo app + volume (region sin, KHÔNG http_service — dùng lại fly.toml qua --copy-config):
   flyctl apps create reminder-ko-bot
   flyctl volumes create reminder_data -a reminder-ko-bot --region sin --size 1
3. Secrets (LANG dùng khóa BOT_LANG để tránh đụng locale hệ thống):
   flyctl secrets set -a reminder-ko-bot BOT_TOKEN=<token-ko> OWNER_ID=<telegram-id> BOT_LANG=ko
4. Deploy cùng image codebase:
   flyctl deploy -a reminder-ko-bot
5. Kiểm chứng: flyctl logs -a reminder-ko-bot --no-tail
   - Lần đầu thấy "Đã nạp từ điển: N mục" (tải + parse ~vài giây).
   - Nhắn /start cho bot Hàn → tiêu đề "Bot học tiếng Hàn SRS".
   - Gõ 학교 → thẻ có romaja "hakgyo", nghĩa "school", audio giọng ko-KR.
6. Đặt Gemini key (tùy chọn) qua /settings như bot Trung — dùng chung key được.

## Lưu ý
- 2 app = 2 volume = 2 DB riêng biệt. Không chia sẻ thẻ.
- Cập nhật code cho CẢ HAI bot: sửa 1 lần, deploy 2 lần (deploy -a reminder-zh-bot; deploy -a reminder-ko-bot).
- KHÔNG chạy fly launch (ghi đè fly.toml, thêm http_service autostop — xem HANDOFF.md).
