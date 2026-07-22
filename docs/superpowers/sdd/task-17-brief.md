### Task 17: /thongke + /backup

**Files:** Modify `app/bot/misc.py`, `app/bot/main.py`

**Interfaces:**
- Consumes: `stats.overview`, `config.DB_PATH/today_iso`

- [ ] **Step 1: Thêm vào `app/bot/misc.py`**

```python
from app import config, stats


async def cmd_stats(update, context):
    conn = context.bot_data["conn"]
    o = stats.overview(conn, config.today_iso())
    total_r = o["total_reviews"]
    rate = 100 * (1 - o["total_lapses"] / total_r) if total_r else 100.0
    await update.message.reply_html(
        "📊 <b>Thống kê</b>\n"
        f"🗂 Tổng số thẻ: {o['total']}\n"
        f"📚 Đến hạn hôm nay: {o['due']} (+{o['new_waiting']} thẻ mới chờ)\n"
        f"🔥 Chuỗi: {o['streak']} ngày\n"
        f"✅ Tỉ lệ nhớ: {rate:.0f}% ({total_r} lượt ôn, {o['total_lapses']} lần quên)")


async def cmd_backup(update, context):
    with open(config.DB_PATH, "rb") as f:
        await update.message.reply_document(
            f, filename=f"reminder-backup-{config.today_iso()}.db",
            caption="💾 Bản sao lưu dữ liệu (SQLite). Cất giữ cẩn thận nhé.")
```

- [ ] **Step 2: Nối vào `main.py`**

```python
app.add_handler(CommandHandler("thongke", misc.cmd_stats, filters=owner_filter))
app.add_handler(CommandHandler("backup", misc.cmd_backup, filters=owner_filter))
```

- [ ] **Step 3: Test thủ công** — `/thongke` số liệu khớp thực tế; `/backup` tải file .db về mở được bằng sqlite3.

- [ ] **Step 4: Chạy toàn bộ test tự động lần cuối** — `python -m pytest tests/ -v` → tất cả PASS.

- [ ] **Step 5: Commit** — `git commit -am "feat: stats and backup commands"`

---

