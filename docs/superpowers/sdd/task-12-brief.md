### Task 12: Nhắc theo lịch (`app/bot/reminders.py`)

**Files:** Create `app/bot/reminders.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `cards.build_queue/get_card/is_new`, `stats.reviews_today/streak`, `db.get_setting`, `config.OWNER_ID/TZ`
- Produces: `reminders.schedule_jobs(app)` — xóa mọi job tên bắt đầu `rem:` rồi đăng ký lại từ settings (settings_flow Task 15 gọi lại hàm này sau khi đổi giờ). Nút "▶️ Ôn ngay" dùng callback `rv_start` (đã có ở Task 10).

- [ ] **Step 1: Viết `app/bot/reminders.py`**

```python
import logging
from datetime import time as dtime

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import cards, config, db, stats

START_KB = Markup([[Btn("▶️ Ôn ngay", callback_data="rv_start")]])


def _parse_hhmm(s):
    h, m = s.strip().split(":")
    return dtime(int(h), int(m), tzinfo=config.TZ)


def schedule_jobs(app):
    conn = app.bot_data["conn"]
    for job in app.job_queue.jobs():
        if job.name and job.name.startswith("rem:"):
            job.schedule_removal()
    for t in db.get_setting(conn, "reminder_times").split(","):
        t = t.strip()
        if t:
            app.job_queue.run_daily(reminder_job, _parse_hhmm(t), name=f"rem:{t}")
    ev = db.get_setting(conn, "evening_nudge").strip()
    if ev and ev.lower() != "off":
        app.job_queue.run_daily(evening_job, _parse_hhmm(ev), name="rem:evening")
    logging.info("Đã đặt lịch nhắc: %s / nudge: %s",
                 db.get_setting(conn, "reminder_times"), ev)


async def reminder_job(context):
    conn = context.application.bot_data["conn"]
    queue = cards.build_queue(conn, config.today_iso())
    if not queue:
        return  # đã ôn hết / không có gì -> im lặng (spec §6)
    n_new = sum(1 for cid in queue
                if (r := cards.get_card(conn, cid)) and cards.is_new(r))
    await context.bot.send_message(
        config.OWNER_ID,
        f"📚 Bạn có <b>{len(queue)}</b> thẻ đến hạn ({n_new} thẻ mới).",
        reply_markup=START_KB, parse_mode="HTML")


async def evening_job(context):
    conn = context.application.bot_data["conn"]
    if stats.reviews_today(conn, config.today_iso()) > 0:
        return
    queue = cards.build_queue(conn, config.today_iso())
    if not queue:
        return
    n = stats.streak(conn, config.today())
    flame = f"🔥 Chuỗi {n} ngày của bạn sắp mất! " if n > 0 else ""
    await context.bot.send_message(
        config.OWNER_ID,
        f"🌙 {flame}Hôm nay bạn chưa ôn — còn {len(queue)} thẻ chờ.",
        reply_markup=START_KB)
```

- [ ] **Step 2: Nối vào `main.py`** — cuối `post_init` thêm:

```python
from app.bot import reminders
reminders.schedule_jobs(app)
```

- [ ] **Step 3: Test thủ công** — đặt tạm `reminder_times` = 2 phút tới (`sqlite3 data/reminder.db "UPDATE settings SET value='HH:MM' WHERE key='reminder_times'"`), chạy bot, chờ: có thẻ đến hạn → nhận tin nhắn + nút ▶️ hoạt động; ôn hết rồi chờ mốc kế → bot im. Trả lại giá trị cũ sau khi test.

- [ ] **Step 4: Commit** — `git commit -am "feat: scheduled reminders with streak nudge"`

---

