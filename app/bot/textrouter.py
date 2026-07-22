import re

from app import db
from app.bot import create_flow

_HAN = re.compile(r"[一-鿿]")
TEXT_ACTIONS = {}


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
    if _HAN.search(text):
        await create_flow.start_pending(update, context, text)
    else:
        await update.message.reply_text(
            "Gõ chữ Hán để tạo thẻ (VD: 学习), hoặc /start để xem lệnh.")


async def on_photo(update, context):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if not pc:
        return
    pc["image_file_id"] = update.message.photo[-1].file_id
    db.kv_set(conn, "pending_card", pc)
    await update.message.reply_text("🖼 Đã đính kèm ảnh vào thẻ đang tạo.")
    await create_flow.render_preview(context, update.effective_chat.id)
