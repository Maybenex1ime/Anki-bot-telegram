import html

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import db
from app.bot.auth import owner_only_callback


def _list_view(conn):
    rows = conn.execute(
        "SELECT d.id, d.name, COUNT(c.id) n FROM decks d "
        "LEFT JOIN cards c ON c.deck_id=d.id GROUP BY d.id ORDER BY d.id").fetchall()
    kb = [[Btn(f"📦 {r['name']} ({r['n']} thẻ)", callback_data=f"dk_view:{r['id']}")]
          for r in rows]
    kb.append([Btn("➕ Tạo bộ mới", callback_data="dk_new")])
    return "📦 <b>Các bộ thẻ:</b>", Markup(kb)


async def cmd_decks(update, context):
    text, kb = _list_view(context.bot_data["conn"])
    await update.message.reply_html(text, reply_markup=kb)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    data = q.data
    if data == "dk_back":
        text, kb = _list_view(conn)
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    elif data == "dk_new":
        db.kv_set(conn, "pending_input", {"action": "deck_new"})
        await context.bot.send_message(q.message.chat_id, "Nhập tên bộ thẻ mới:")
    elif data.startswith("dk_view:"):
        did = int(data.split(":")[1])
        row = conn.execute(
            "SELECT d.name, COUNT(c.id) n FROM decks d LEFT JOIN cards c ON c.deck_id=d.id "
            "WHERE d.id=? GROUP BY d.id", (did,)).fetchone()
        if not row:
            return
        kb = [[Btn("⬅️ Quay lại", callback_data="dk_back")]]
        if did != 1:
            kb.insert(0, [Btn("✏️ Đổi tên", callback_data=f"dk_rename:{did}"),
                          Btn("🗑 Xóa bộ", callback_data=f"dk_del:{did}")])
        await q.edit_message_text(
            f"📦 <b>{html.escape(row['name'])}</b> — {row['n']} thẻ",
            reply_markup=Markup(kb), parse_mode="HTML")
    elif data.startswith("dk_rename:"):
        did = int(data.split(":")[1])
        db.kv_set(conn, "pending_input", {"action": "deck_rename", "deck_id": did})
        await context.bot.send_message(q.message.chat_id, "Nhập tên mới cho bộ:")
    elif data.startswith("dk_del_ok:"):
        did = int(data.split(":")[1])
        if did != 1:
            conn.execute("DELETE FROM decks WHERE id=?", (did,))
            conn.commit()
        text, kb = _list_view(conn)
        await q.edit_message_text("🗑 Đã xóa bộ.\n\n" + text, reply_markup=kb, parse_mode="HTML")
    elif data.startswith("dk_del:"):
        did = int(data.split(":")[1])
        n = conn.execute("SELECT COUNT(*) c FROM cards WHERE deck_id=?", (did,)).fetchone()["c"]
        await q.edit_message_text(
            f"⚠️ Xóa bộ sẽ xóa VĨNH VIỄN {n} thẻ bên trong. Chắc chắn?",
            reply_markup=Markup([[Btn("🗑 Xóa luôn", callback_data=f"dk_del_ok:{did}"),
                                  Btn("⬅️ Thôi", callback_data=f"dk_view:{did}")]]))


async def deck_new_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    try:
        conn.execute("INSERT INTO decks(name) VALUES(?)", (text,))
        conn.commit()
        await update.message.reply_text(f"✅ Đã tạo bộ “{text}”. Xem /bo")
    except Exception:
        await update.message.reply_text("⚠️ Tên bộ đã tồn tại.")


async def deck_rename_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    conn.execute("UPDATE decks SET name=? WHERE id=? AND id<>1", (text, pending["deck_id"]))
    conn.commit()
    await update.message.reply_text(f"✅ Đã đổi tên bộ thành “{text}”.")
