import re

from app import config, db
from app.bot import create_flow

TEXT_ACTIONS = {}


def looks_like_word(text):
    return bool(re.search(f"[{config.PACK['script_range']}]", text))


def register(action, fn):
    TEXT_ACTIONS[action] = fn


async def on_text(update, context):
    conn = context.bot_data["conn"]
    text = update.message.text.strip()
    pending = db.kv_get(conn, "pending_input")
    if pending:
        fn = TEXT_ACTIONS.get(pending.get("action"))
        if fn:
            db.kv_del(conn, "pending_input")
            await fn(update, context, pending, text)
            return
    if looks_like_word(text):
        await create_flow.start_pending(update, context, text)
    else:
        await update.message.reply_text(
            "Gõ một từ để tạo thẻ, hoặc /start để xem lệnh.")


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
