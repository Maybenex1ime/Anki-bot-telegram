# Deploy lên Fly.io

1. Cài flyctl: https://fly.io/docs/flyctl/install/ rồi `fly auth signup` (hoặc login).
2. Từ thư mục repo: `fly launch --no-deploy --copy-config --name reminder-zh-bot --region sin`
   (chọn KHÔNG tạo Postgres/Redis khi được hỏi).
3. Tạo volume: `fly volumes create reminder_data --region sin --size 1`
4. Đặt secrets: `fly secrets set BOT_TOKEN=<token> OWNER_ID=<telegram-id>`
5. Deploy: `fly deploy`
6. Giữ đúng 1 máy (tránh 2 bot polling cùng lúc — Telegram sẽ lỗi Conflict):
   `fly scale count 1`
7. Xem log: `fly logs` — lần đầu sẽ thấy "Đã nạp CC-CEDICT" (~1-2 phút).
8. Nhắn /start cho bot để kiểm tra.

## Cập nhật phiên bản mới
`fly deploy`

## Khôi phục từ backup
Lấy file .db từ /backup của bot, rồi:
`fly ssh sftp shell` → put vào `/data/reminder.db` → `fly apps restart reminder-zh-bot`
