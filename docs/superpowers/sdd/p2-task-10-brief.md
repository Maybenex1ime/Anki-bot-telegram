### Task 10: `/luyen` menu + trắc nghiệm/tự luận tự do (`app/bot/practice_flow.py`)

**Files:** Create `app/bot/practice_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `review_flow.start_session(practice=True, queue=...)`, bảng cards/decks
- Produces: lệnh `/luyen`; callbacks `pr_menu`, `pr_quiz:<mc|typed>`, `pr_qd:<mode>:<deck_id>`, `pr_ql:<deck_id>:<level>` (level chỉ cho mc), `pr_dict`, `pr_build` (dict/build stub ở task này — Task 11/12 thay); text action + handlers đăng ký một lần tại đây.

- [ ] **Step 1: Viết `app/bot/practice_flow.py`:**

```python
import random

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import db
from app.bot import review_flow
from app.bot.auth import owner_only_callback

MENU = Markup([[Btn("🔘 Trắc nghiệm", callback_data="pr_quiz:mc"),
                Btn("⌨️ Tự luận", callback_data="pr_quiz:typed")],
               [Btn("✍️ Chép chính tả", callback_data="pr_dict"),
                Btn("🧩 Ghép câu", callback_data="pr_build")]])


async def cmd_practice(update, context):
    await update.message.reply_text(
        "🏋️ Luyện tự do (không ảnh hưởng lịch ôn). Chọn trò:", reply_markup=MENU)


def _practice_queue(conn, deck_id, n=10):
    where = "" if deck_id == 0 else "AND deck_id=?"
    args = () if deck_id == 0 else (deck_id,)
    rows = conn.execute(
        f"SELECT id FROM cards WHERE meaning<>'' {where}", args).fetchall()
    ids = [r["id"] for r in rows]
    random.shuffle(ids)
    return ids[:n]


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    data = q.data

    if data == "pr_menu":
        await q.edit_message_text("🏋️ Chọn trò:", reply_markup=MENU)

    elif data.startswith("pr_quiz:"):
        mode = data.split(":")[1]
        decks = conn.execute(
            "SELECT d.id, d.name, COUNT(c.id) n FROM decks d "
            "LEFT JOIN cards c ON c.deck_id=d.id AND c.meaning<>'' "
            "GROUP BY d.id ORDER BY d.id").fetchall()
        kb = [[Btn(f"Tất cả các bộ", callback_data=f"pr_qd:{mode}:0")]]
        kb += [[Btn(f"{d['name']} ({d['n']})", callback_data=f"pr_qd:{mode}:{d['id']}")]
               for d in decks if d["n"]]
        await q.edit_message_text("Luyện bộ nào?", reply_markup=Markup(kb))

    elif data.startswith("pr_qd:"):
        _, mode, deck_id = data.split(":")
        if mode == "typed":
            await _start_quiz(context, q, "typed", "", int(deck_id))
        else:
            kb = Markup([[Btn("😌 Dễ", callback_data=f"pr_ql:{deck_id}:easy"),
                          Btn("🙂 Thường", callback_data=f"pr_ql:{deck_id}:normal"),
                          Btn("🔥 Khó", callback_data=f"pr_ql:{deck_id}:hard")]])
            await q.edit_message_text("Chọn mức:", reply_markup=kb)

    elif data.startswith("pr_ql:"):
        _, deck_id, level = data.split(":")
        await _start_quiz(context, q, "mc", level, int(deck_id))

    elif data == "pr_dict":
        await q.edit_message_text("⚠️ Chép chính tả đang được xây.")   # Task 11 thay

    elif data == "pr_build":
        await q.edit_message_text("⚠️ Ghép câu đang được xây.")        # Task 12 thay


async def _start_quiz(context, q, mode, level, deck_id):
    conn = context.bot_data["conn"]
    queue = _practice_queue(conn, deck_id)
    if len(queue) < (4 if mode == "mc" else 1):
        await q.edit_message_text("⚠️ Chưa đủ thẻ có nghĩa trong phạm vi này.")
        return
    try:
        await q.message.delete()
    except Exception:
        pass
    await review_flow.start_session(context, q.message.chat_id, mode=mode,
                                    level=level, practice=True, queue=queue)
```

- [ ] **Step 2: Wiring `main.py`** — import `practice_flow`; thêm:

```python
app.add_handler(CommandHandler("luyen", practice_flow.cmd_practice, filters=owner_filter))
app.add_handler(CallbackQueryHandler(practice_flow.on_callback, pattern=r"^pr_"))
```

- [ ] **Step 3: Verify** — suite + offline build_app (handler +2).
- [ ] **Step 4: Commit** — `git add -A && git commit -m "feat: /luyen menu + free quiz sessions (no SRS impact)"`

---

