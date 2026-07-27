### Task 4: Redeploy bot Trung + dựng bot Hàn

**Files:** Create `docs/DEPLOY-ko.md`; Modify `Dockerfile`, `docs/superpowers/sdd/HANDOFF.md`

- [ ] **Step 1: Sửa `Dockerfile`** — set `BOT_LANG` mặc định để container tường minh (bị secret ghi đè khi cần):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
ENV BOT_LANG=zh
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["python", "-m", "app.bot.main"]
```

- [ ] **Step 2: Redeploy bot Trung TRƯỚC (điểm kiểm chứng an toàn)** — bot Trung phải chạy y hệt sau refactor trước khi đụng tới bot Hàn:

```bash
flyctl deploy -a reminder-zh-bot
flyctl logs -a reminder-zh-bot --no-tail
```
Expected: khởi động sạch, KHÔNG có dòng "Đã nạp CC-CEDICT" (dict cũ còn nguyên), scheduler đặt lại job, polling chạy. Tạo thử 1 thẻ `学习` trên bot → pinyin/nghĩa/audio đúng như trước. Nếu lỗi → `flyctl releases -a reminder-zh-bot` + deploy lại image trước, dừng plan, báo user.

- [ ] **Step 3: Viết `docs/DEPLOY-ko.md`** — runbook bot Hàn:

```markdown
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
   - Lần đầu thấy "Đã nạp CC-KEDICT: N mục" (tải + parse ~vài giây).
   - Nhắn /start cho bot Hàn → tiêu đề "Bot học tiếng Hàn SRS".
   - Gõ 학교 → thẻ có romaja "hakgyo", nghĩa "school", audio giọng ko-KR.
6. Đặt Gemini key (tùy chọn) qua /settings như bot Trung — dùng chung key được.

## Lưu ý
- 2 app = 2 volume = 2 DB riêng biệt. Không chia sẻ thẻ.
- Cập nhật code cho CẢ HAI bot: sửa 1 lần, deploy 2 lần (deploy -a reminder-zh-bot; deploy -a reminder-ko-bot).
- KHÔNG chạy fly launch (ghi đè fly.toml, thêm http_service autostop — xem HANDOFF.md).
```

- [ ] **Step 4: Cập nhật `docs/superpowers/sdd/HANDOFF.md`** — thêm mục: kiến trúc langpack (BOT_LANG), 2 app song song, quy trình "sửa 1 lần deploy 2 lần", trỏ tới `docs/DEPLOY-ko.md`. Ghi rõ bot Hàn dùng CC-KEDICT (kho nhỏ, tra rỗng nhiều — nhập tay).

- [ ] **Step 5: Deploy bot Hàn thật** (cần BOT_TOKEN từ user — nếu chưa có, dừng ở đây, report cho user chạy runbook). Làm theo `docs/DEPLOY-ko.md`, xác nhận Step 5 của runbook.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "build: BOT_LANG in Dockerfile + Korean bot deploy runbook + handoff"`

---

## Self-Review Notes

- Spec coverage: §2 kiến trúc langpack (T1), §3 gói + 6 thành phần (T1 zh, T2 ko), §4 sửa 5 điểm (T1 lookup/quiz/grading + T3 gemini + T1 config), §5 đặc thù Hàn khoảng trắng (T2 `_make_normalize` xóa space cho cả 2), §6 refactor an toàn + khóa hành vi (T1 dùng 58 test cũ làm lưới + T4 redeploy-verify trước khi đụng ko), §7 deploy 2 app (T4), §8 lỗi (T2 `_ko_romanize` try/except, T1 `get` raise), §9 test (T1/T2/T3).
- **Đổi so với spec:** dùng env `BOT_LANG` thay `LANG` (LANG đụng locale Linux) — đã ghi rõ Step 2/2b + runbook. Giữ tên hàm cũ (`gen_pinyin`/`normalize_hanzi`/`pinyin_key`/`ensure_cedict`) thay vì đổi tên — lazy, khóa hành vi bằng test cũ.
- **Rủi ro cần verify khi chạy:** (a) import path của `korean-romanizer` (Step 4 Task 2 có lệnh kiểm) — kết quả `annyeong` cho `안녕`; nếu lib trả khác (VD viết hoa/khoảng trắng), điều chỉnh `_ko_romanize` + test cho khớp OUTPUT THẬT của lib, không ép output. (b) URL/định dạng cc-kedict `.yml` vs `.yml.gz` (Step 4 note). Cả hai là điểm implementer phải xác nhận với runtime thật, plan đã chỉ chỗ.
- Không đụng schema/migration; `dict_entries` dùng lại cho ko (word,word,romaja,meaning). `sentences`/`quiz` JSON giữ khóa `hanzi`/`pinyin` (chỉ là tên trường) — ko điền chữ Hàn/romaja vào, không phải đổi 2 module đó.
```
