### Task 8: Bot skeleton — auth, /start, main

**Files:** Create `app/bot/__init__.py` (rỗng), `app/bot/auth.py`, `app/bot/misc.py` (mới chỉ /start), `app/bot/main.py`

**Interfaces:**
- Produces: `auth.owner_filter` (filters.User theo `config.OWNER_ID`); decorator `auth.owner_only_callback(fn)` — dùng cho MỌI CallbackQueryHandler về sau: nếu `update.effective_user.id != config.OWNER_ID` thì `await update.callback_query.answer()` rồi return; `main.build_app() -> Application` với `bot_data["conn"]` là kết nối SQLite; `main.main()` chạy polling. Các task sau sẽ **thêm handler vào `build_app`** — mỗi task ghi rõ dòng thêm.

- [ ] **Step 1: Viết `app/bot/auth.py`**

```python
from functools import wraps

from telegram.ext import filters

from app import config

owner_filter = filters.User(user_id=config.OWNER_ID)


def owner_only_callback(fn):
    @wraps(fn)
    async def wrapper(update, context):
        if not update.effective_user or update.effective_user.id != config.OWNER_ID:
            if update.callback_query:
                await update.callback_query.answer()
            return
        return await fn(update, context)
    return wrapper
```

- [ ] **Step 2: Viết `app/bot/misc.py` (bản đầu)**

```python
HELP = (
    "🀄 <b>Bot học tiếng Trung SRS</b>\n\n"
    "• Gõ chữ Hán bất kỳ (VD: 学习) → tạo thẻ mới\n"
    "• /on — ôn thẻ đến hạn ngay\n"
    "• /csv — nhập hàng loạt từ file CSV\n"
    "• /bo — quản lý bộ thẻ\n"
    "• /tim &lt;từ&gt; — tìm thẻ\n"
    "• /thongke — thống kê & streak\n"
    "• /settings — giờ nhắc, giới hạn thẻ mới, giọng đọc\n"
    "• /backup — nhận file dữ liệu"
)


async def cmd_start(update, context):
    await update.message.reply_html(HELP)
```

- [ ] **Step 3: Viết `app/bot/main.py`**

```python
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler

from app import config, db, lookup
from app.bot import misc
from app.bot.auth import owner_filter

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def post_init(app):
    conn = db.connect()
    app.bot_data["conn"] = conn
    n = lookup.ensure_cedict(conn)
    if n:
        logging.info("Đã nạp CC-CEDICT: %d mục", n)


def build_app() -> Application:
    app = (Application.builder().token(config.BOT_TOKEN)
           .post_init(post_init).build())
    app.add_handler(CommandHandler("start", misc.cmd_start, filters=owner_filter))
    return app


def main():
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test thủ công**

1. Tạo bot với @BotFather trên Telegram (`/newbot`) → lấy token.
2. Lấy Telegram ID của chủ bot: nhắn cho @userinfobot.
3. Chạy local (PowerShell): `$env:BOT_TOKEN="<token>"; $env:OWNER_ID="<id>"; python -m app.bot.main`
4. Nhắn `/start` cho bot → Expected: menu tiếng Việt. Lần chạy đầu log hiện "Đã nạp CC-CEDICT" (tải ~2 phút).
5. Nhờ một tài khoản khác nhắn `/start` → Expected: bot im lặng.

- [ ] **Step 5: Commit** — `git commit -am "feat: bot skeleton — single-user auth, /start, polling"`

---

