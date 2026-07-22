from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup
from telegram.error import BadRequest

from app import cards, db, lookup
from app.bot.auth import owner_only_callback

FIELD_LABEL = {"pinyin": "pinyin", "meaning": "nghĩa tiếng Anh", "example": "câu ví dụ"}


async def start_pending(update, context, hanzi):
    conn = context.bot_data["conn"]
    pc = {
        "hanzi": hanzi,
        "pinyin": lookup.gen_pinyin(hanzi),
        "meaning": lookup.lookup_meaning(conn, hanzi),
        "example": "", "image_file_id": "", "deck_id": 1,
    }
    db.kv_set(conn, "pending_card", pc)
    db.kv_del(conn, "pending_msg")
    await render_preview(context, update.effective_chat.id)


def _preview(conn, pc):
    deck = conn.execute("SELECT name FROM decks WHERE id=?", (pc["deck_id"],)).fetchone()
    lines = [f"🀄 <b>{pc['hanzi']}</b>", f"📖 {pc['pinyin']}",
             f"🇬🇧 {pc['meaning'] or '<i>(chưa có nghĩa — bấm Sửa nghĩa)</i>'}"]
    if pc["example"]:
        lines.append(f"💬 {pc['example']}")
    if pc["image_file_id"]:
        lines.append("🖼 Có ảnh đính kèm")
    if cards.exists_hanzi(conn, pc["hanzi"]):
        lines.append("⚠️ <b>Đã có thẻ trùng chữ Hán này</b>")
    lines.append(f"📦 Bộ: {deck['name'] if deck else '?'}")
    lines.append("\nXem lại rồi bấm Lưu nhé:")
    kb = Markup([
        [Btn("💾 Lưu", callback_data="pc_save"), Btn("❌ Hủy", callback_data="pc_cancel")],
        [Btn("✏️ Pinyin", callback_data="pc_edit:pinyin"),
         Btn("✏️ Nghĩa", callback_data="pc_edit:meaning")],
        [Btn("💬 Ví dụ", callback_data="pc_edit:example"),
         Btn("📦 Đổi bộ", callback_data="pc_deck")],
    ])
    return "\n".join(lines), kb


async def render_preview(context, chat_id):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if not pc:
        return
    text, kb = _preview(conn, pc)
    msg_id = db.kv_get(conn, "pending_msg")
    if msg_id:
        try:
            await context.bot.edit_message_text(
                text, chat_id=chat_id, message_id=msg_id,
                reply_markup=kb, parse_mode="HTML")
            return
        except BadRequest:
            pass
    m = await context.bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
    db.kv_set(conn, "pending_msg", m.message_id)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    await q.answer()
    if not pc:
        await q.edit_message_text("Phiên tạo thẻ đã kết thúc.")
        return
    data = q.data
    if data == "pc_cancel":
        db.kv_del(conn, "pending_card")
        db.kv_del(conn, "pending_msg")
        await q.edit_message_text("❌ Đã hủy tạo thẻ.")
    elif data == "pc_save":
        row = await cards.create_card(
            conn, pc["hanzi"], deck_id=pc["deck_id"],
            pinyin_override=pc["pinyin"], meaning_override=pc["meaning"],
            example=pc["example"], image_file_id=pc["image_file_id"])
        db.kv_del(conn, "pending_card")
        db.kv_del(conn, "pending_msg")
        note = "" if row["audio_path"] else "\n⚠️ Chưa tạo được audio, sẽ thử lại khi ôn."
        await q.edit_message_text(
            f"✅ Đã lưu thẻ <b>{row['hanzi']}</b> ({row['pinyin']}){note}",
            parse_mode="HTML")
    elif data.startswith("pc_edit:"):
        field = data.split(":", 1)[1]
        db.kv_set(conn, "pending_input", {"action": "pc_field", "field": field})
        await context.bot.send_message(
            q.message.chat_id, f"Nhập {FIELD_LABEL[field]} mới:")
    elif data == "pc_deck":
        decks = conn.execute("SELECT id, name FROM decks ORDER BY id").fetchall()
        kb = Markup([[Btn(d["name"], callback_data=f"pc_deck_set:{d['id']}")] for d in decks])
        await context.bot.send_message(q.message.chat_id, "Chọn bộ thẻ:", reply_markup=kb)
    elif data.startswith("pc_deck_set:"):
        pc["deck_id"] = int(data.split(":")[1])
        db.kv_set(conn, "pending_card", pc)
        await q.message.delete()
        await render_preview(context, q.message.chat_id)


async def field_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if not pc:
        return
    pc[pending["field"]] = text
    db.kv_set(conn, "pending_card", pc)
    await render_preview(context, update.effective_chat.id)
