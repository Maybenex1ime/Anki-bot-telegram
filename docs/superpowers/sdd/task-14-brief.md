### Task 14: Tìm & sửa thẻ (`app/bot/manage_flow.py`)

**Files:** Create `app/bot/manage_flow.py`; Modify `app/bot/main.py`, `app/bot/textrouter.py` (on_photo)

**Interfaces:**
- Consumes: `cards.get_card`, `review_flow.send_card_audio`, `db.kv_*`
- Produces: lệnh `/tim <query>`; callbacks `cd_view:<id>`, `cd_listen:<id>`, `cd_myvoice:<id>`, `cd_edit:<id>:<field>` (field ∈ pinyin|meaning|example), `cd_img:<id>`, `cd_move:<id>`, `cd_move_set:<id>:<deck>`, `cd_del:<id>`, `cd_del_ok:<id>`; text action `card_edit` (`{"cid", "field"}`); kv `awaiting_image` = cid (on_photo của textrouter ưu tiên `pending_card` trước, rồi tới `awaiting_image`).

- [ ] **Step 1: Viết `app/bot/manage_flow.py`**

```python
from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import cards, db
from app.bot import review_flow
from app.bot.auth import owner_only_callback

FIELDS = {"pinyin": "pinyin", "meaning": "nghĩa", "example": "ví dụ"}


async def cmd_search(update, context):
    conn = context.bot_data["conn"]
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Dùng: /tim <chữ Hán, pinyin hoặc nghĩa>")
        return
    like = f"%{query}%"
    rows = conn.execute(
        "SELECT id, hanzi, pinyin FROM cards "
        "WHERE hanzi LIKE ? OR pinyin LIKE ? OR meaning LIKE ? LIMIT 8",
        (like, like, like)).fetchall()
    if not rows:
        await update.message.reply_text("Không tìm thấy thẻ nào.")
        return
    kb = Markup([[Btn(f"{r['hanzi']} — {r['pinyin']}", callback_data=f"cd_view:{r['id']}")]
                 for r in rows])
    await update.message.reply_text(f"🔎 Kết quả cho “{query}”:", reply_markup=kb)


def _detail(conn, row):
    deck = conn.execute("SELECT name FROM decks WHERE id=?", (row["deck_id"],)).fetchone()
    lines = [f"🀄 <b>{row['hanzi']}</b>", f"📖 {row['pinyin']}",
             f"🇬🇧 {row['meaning'] or '<i>(trống)</i>'}"]
    if row["example"]:
        lines.append(f"💬 {row['example']}")
    lines += [f"📦 {deck['name'] if deck else '?'}",
              f"📅 Đến hạn: {row['due_date']} · interval {row['interval']:.0f}d "
              f"· ease {row['ease']:.2f} · ôn {row['repetitions']} · quên {row['lapses']}"]
    cid = row["id"]
    kb = [[Btn("🔊 Nghe", callback_data=f"cd_listen:{cid}"),
           Btn("🎙 Bản thu của tôi", callback_data=f"cd_myvoice:{cid}")],
          [Btn("✏️ Pinyin", callback_data=f"cd_edit:{cid}:pinyin"),
           Btn("✏️ Nghĩa", callback_data=f"cd_edit:{cid}:meaning"),
           Btn("✏️ Ví dụ", callback_data=f"cd_edit:{cid}:example")],
          [Btn("🖼 Đổi ảnh", callback_data=f"cd_img:{cid}"),
           Btn("📦 Chuyển bộ", callback_data=f"cd_move:{cid}")],
          [Btn("🗑 Xóa thẻ", callback_data=f"cd_del:{cid}")]]
    return "\n".join(lines), Markup(kb)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    parts = q.data.split(":")
    action, cid = parts[0], int(parts[1])
    row = cards.get_card(conn, cid)
    if action != "cd_del_ok" and row is None:
        await q.edit_message_text("Thẻ này đã bị xóa.")
        return

    if action == "cd_view":
        text, kb = _detail(conn, row)
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        if row["image_file_id"]:
            await context.bot.send_photo(q.message.chat_id, row["image_file_id"])
    elif action == "cd_listen":
        m = await review_flow.send_card_audio(context, q.message.chat_id, row)
        if m is None:
            await context.bot.send_message(q.message.chat_id, "⚠️ Thẻ chưa có audio.")
    elif action == "cd_myvoice":
        if row["voice_file_id"]:
            await context.bot.send_voice(q.message.chat_id, row["voice_file_id"])
        else:
            await context.bot.send_message(q.message.chat_id, "Chưa có bản thu nào cho thẻ này.")
    elif action == "cd_edit":
        field = parts[2]
        db.kv_set(conn, "pending_input",
                  {"action": "card_edit", "cid": cid, "field": field})
        await context.bot.send_message(q.message.chat_id, f"Nhập {FIELDS[field]} mới:")
    elif action == "cd_img":
        db.kv_set(conn, "awaiting_image", cid)
        await context.bot.send_message(q.message.chat_id, "Gửi ảnh mới cho thẻ này:")
    elif action == "cd_move":
        decks = conn.execute("SELECT id, name FROM decks ORDER BY id").fetchall()
        kb = Markup([[Btn(d["name"], callback_data=f"cd_move_set:{cid}:{d['id']}")]
                     for d in decks])
        await q.edit_message_text("Chuyển thẻ sang bộ:", reply_markup=kb)
    elif action == "cd_move_set":
        conn.execute("UPDATE cards SET deck_id=? WHERE id=?", (int(parts[2]), cid))
        conn.commit()
        text, kb = _detail(conn, cards.get_card(conn, cid))
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    elif action == "cd_del":
        await q.edit_message_text(
            f"⚠️ Xóa vĩnh viễn thẻ <b>{row['hanzi']}</b>?", parse_mode="HTML",
            reply_markup=Markup([[Btn("🗑 Xóa", callback_data=f"cd_del_ok:{cid}"),
                                  Btn("⬅️ Thôi", callback_data=f"cd_view:{cid}")]]))
    elif action == "cd_del_ok":
        conn.execute("DELETE FROM cards WHERE id=?", (cid,))
        conn.commit()
        await q.edit_message_text("🗑 Đã xóa thẻ.")


async def card_edit_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    field = pending["field"]  # đã whitelist ở callback
    conn.execute(f"UPDATE cards SET {field}=? WHERE id=?", (text, pending["cid"]))
    conn.commit()
    await update.message.reply_text("✅ Đã cập nhật. Xem lại: /tim " + text[:20])
```

- [ ] **Step 2: Thêm nhánh `awaiting_image` vào `textrouter.on_photo`** — thay hàm bằng:

```python
async def on_photo(update, context):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if pc:
        pc["image_file_id"] = update.message.photo[-1].file_id
        db.kv_set(conn, "pending_card", pc)
        await update.message.reply_text("🖼 Đã đính kèm ảnh vào thẻ đang tạo.")
        await create_flow.render_preview(context, update.effective_chat.id)
        return
    cid = db.kv_get(conn, "awaiting_image")
    if cid is not None:
        db.kv_del(conn, "awaiting_image")
        conn.execute("UPDATE cards SET image_file_id=? WHERE id=?",
                     (update.message.photo[-1].file_id, cid))
        conn.commit()
        await update.message.reply_text("🖼 Đã cập nhật ảnh cho thẻ.")
```

- [ ] **Step 3: Nối vào `main.py`**

```python
from app.bot import manage_flow
register("card_edit", manage_flow.card_edit_input)
app.add_handler(CommandHandler("tim", manage_flow.cmd_search, filters=owner_filter))
app.add_handler(CallbackQueryHandler(manage_flow.on_callback, pattern=r"^cd_"))
```

- [ ] **Step 4: Test thủ công** — `/tim 学` ra kết quả → xem chi tiết (đủ SRS info) → sửa nghĩa → đổi ảnh → chuyển bộ → nghe audio + bản thu → xóa có confirm.

- [ ] **Step 5: Commit** — `git commit -am "feat: card search/edit/delete (/tim)"`

---

