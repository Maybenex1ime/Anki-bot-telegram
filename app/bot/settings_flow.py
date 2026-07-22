import html
import re

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import db
from app.bot import reminders
from app.bot.auth import owner_only_callback

VOICES = ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural",
          "zh-CN-XiaoyiNeural", "zh-CN-YunjianNeural"]
_TIME = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def _view(conn):
    e = lambda k: html.escape(str(db.get_setting(conn, k)))
    text = ("⚙️ <b>Cài đặt</b>\n"
            f"⏰ Giờ nhắc: {e('reminder_times')}\n"
            f"🌙 Nhắc cuối ngày: {e('evening_nudge')}\n"
            f"🆕 Thẻ mới/ngày: {e('new_per_day')}\n"
            f"🗣 Giọng đọc: {e('tts_voice')}")
    kb = Markup([[Btn("⏰ Giờ nhắc", callback_data="st_times"),
                  Btn("🌙 Cuối ngày", callback_data="st_nudge")],
                 [Btn("🆕 Thẻ mới/ngày", callback_data="st_newlimit"),
                  Btn("🗣 Giọng đọc", callback_data="st_voice")]])
    return text, kb


async def cmd_settings(update, context):
    text, kb = _view(context.bot_data["conn"])
    await update.message.reply_html(text, reply_markup=kb)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    if q.data == "st_times":
        db.kv_set(conn, "pending_input", {"action": "set_times"})
        await context.bot.send_message(
            q.message.chat_id, "Nhập các giờ nhắc, phân cách bằng phẩy (VD: 07:30,12:30,20:00):")
    elif q.data == "st_nudge":
        db.kv_set(conn, "pending_input", {"action": "set_nudge"})
        await context.bot.send_message(
            q.message.chat_id, "Nhập giờ nhắc cuối ngày (VD: 21:30) hoặc gõ off để tắt:")
    elif q.data == "st_newlimit":
        db.kv_set(conn, "pending_input", {"action": "set_newlimit"})
        await context.bot.send_message(q.message.chat_id, "Nhập số thẻ mới tối đa mỗi ngày (0–200):")
    elif q.data == "st_voice":
        kb = Markup([[Btn(v, callback_data=f"st_voice_set:{v}")] for v in VOICES])
        await q.edit_message_text("Chọn giọng đọc:", reply_markup=kb)
    elif q.data.startswith("st_voice_set:"):
        db.set_setting(conn, "tts_voice", q.data.split(":", 1)[1])
        text, kb = _view(conn)
        await q.edit_message_text("✅ Đã đổi giọng (áp dụng cho thẻ tạo mới).\n\n" + text,
                                  reply_markup=kb, parse_mode="HTML")


async def times_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts or not all(_TIME.match(p) for p in parts):
        await update.message.reply_text("⚠️ Sai định dạng. VD hợp lệ: 07:30,12:30,20:00")
        return
    db.set_setting(conn, "reminder_times", ",".join(parts))
    reminders.schedule_jobs(context.application)
    await update.message.reply_text(f"✅ Giờ nhắc mới: {', '.join(parts)}")


async def nudge_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    v = text.strip().lower()
    if v != "off" and not _TIME.match(v):
        await update.message.reply_text("⚠️ Nhập HH:MM hoặc off.")
        return
    db.set_setting(conn, "evening_nudge", v)
    reminders.schedule_jobs(context.application)
    await update.message.reply_text("✅ Đã cập nhật nhắc cuối ngày.")


async def newlimit_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    if not text.strip().isdigit() or not 0 <= int(text.strip()) <= 200:
        await update.message.reply_text("⚠️ Nhập số nguyên 0–200.")
        return
    db.set_setting(conn, "new_per_day", text.strip())
    await update.message.reply_text(f"✅ Giới hạn thẻ mới/ngày: {text.strip()}")
