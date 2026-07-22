### Task 18: Deploy lên Fly.io

**Files:** Create `Dockerfile`, `fly.toml`, `docs/DEPLOY.md`

- [ ] **Step 1: Viết `Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["python", "-m", "app.bot.main"]
```

- [ ] **Step 2: Viết `fly.toml`**

```toml
app = "reminder-zh-bot"
primary_region = "sin"

[env]
  DATA_DIR = "/data"

[mounts]
  source = "reminder_data"
  destination = "/data"

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

Lưu ý: KHÔNG có `[http_service]` — đây là worker thuần, không mở port, nên Fly không auto-stop máy.

- [ ] **Step 3: Viết `docs/DEPLOY.md`** — runbook:

```markdown
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
```

- [ ] **Step 4: Deploy thật & smoke test** — làm theo runbook; xác nhận: /start trả lời từ cloud, tạo thẻ 学习 nghe được audio, /on ôn được, đặt giờ nhắc 2 phút tới nhận được tin nhắn, `fly apps restart` xong bot vẫn nhớ dữ liệu (volume).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: Fly.io deployment (Dockerfile, fly.toml, runbook)"`

---

## Self-Review Notes

- Spec coverage: §2 kiến trúc (T1,8,18), §3 dữ liệu+CSV (T1,5,7,16), §4 SM-2 (T2), §5 luồng ôn+voice (T10,11), §6 nhắc+streak (T12), §7 lệnh (T8–17), §8 lỗi (T4,5,7,10,16), §9 test (T1–7 unit, còn lại manual), §10 khe Azure (T11 marker + setting key).
- Callback prefix không đụng nhau: `pc_` `rv_` `vc_` `dk_` `cd_` `st_` `cs_`.
- `_answer_kb` (T10) phát callback `vc_rec:` mà handler đến T11 mới có — giữa 2 task nút này bấm không có phản hồi; chấp nhận được vì T11 liền sau.
```
