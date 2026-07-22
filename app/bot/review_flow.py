import html
from pathlib import Path

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup
from telegram.error import BadRequest, TelegramError

from app import cards, config, db, stats
from app.bot.auth import owner_only_callback

RATE = [("🔁 Lại", 1), ("😓 Khó", 2), ("🙂 Tốt", 3), ("😎 Dễ", 4)]


def _front_kb(cid):
    return Markup([[Btn("🔊 Nghe", callback_data=f"rv_listen:{cid}"),
                    Btn("👀 Xem đáp án", callback_data=f"rv_show:{cid}")]])


def _answer_kb(cid):
    return Markup([
        [Btn("🎤 Thu âm thử", callback_data=f"vc_rec:{cid}")],
        [Btn(label, callback_data=f"rv_rate:{cid}:{r}") for label, r in RATE],
    ])


async def cmd_review(update, context):
    await start_session(context, update.effective_chat.id)


async def start_session(context, chat_id):
    conn = context.bot_data["conn"]
    queue = cards.build_queue(conn, config.today_iso())
    if not queue:
        await context.bot.send_message(chat_id, "🎉 Không có thẻ nào đến hạn. Nghỉ ngơi đi!")
        return
    db.kv_set(conn, "session", {"queue": queue, "pos": 0, "done": 0,
                                "chat": chat_id, "msg": None, "aux": []})
    await _show_front(context)


async def _edit_or_send(context, s, text, kb):
    conn = context.bot_data["conn"]
    if s["msg"]:
        try:
            await context.bot.edit_message_text(
                text, chat_id=s["chat"], message_id=s["msg"],
                reply_markup=kb, parse_mode="HTML")
            return
        except BadRequest as e:
            if "not modified" in str(e).lower():
                return  # double-tap on same view — nothing to send
            pass
    m = await context.bot.send_message(s["chat"], text, reply_markup=kb, parse_mode="HTML")
    s["msg"] = m.message_id
    db.kv_set(conn, "session", s)


async def _show_front(context):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    cid = s["queue"][s["pos"]]
    row = cards.get_card(conn, cid)
    if row is None:  # thẻ đã bị xóa giữa chừng
        await _advance(context)
        return
    text = f"🀄 <b>{html.escape(row['hanzi'])}</b>\n\n({s['pos'] + 1}/{len(s['queue'])})"
    await _edit_or_send(context, s, text, _front_kb(cid))


async def _clear_aux(context, s):
    for mid in s["aux"]:
        try:
            await context.bot.delete_message(s["chat"], mid)
        except TelegramError:
            pass
    s["aux"] = []


async def send_card_audio(context, chat_id, row):
    conn = context.bot_data["conn"]
    if row["audio_file_id"]:
        return await context.bot.send_voice(chat_id, row["audio_file_id"])
    path = row["audio_path"]
    if not path:
        if not await cards.retry_audio(conn, row["id"]):
            return None
        row = cards.get_card(conn, row["id"])
        path = row["audio_path"]
    if not Path(path).exists():
        return None
    with open(path, "rb") as f:
        m = await context.bot.send_voice(chat_id, f)
    conn.execute("UPDATE cards SET audio_file_id=? WHERE id=?",
                 (m.voice.file_id, row["id"]))
    conn.commit()
    return m


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    if q.data == "rv_start":
        await start_session(context, q.message.chat_id)
        return
    s = db.kv_get(conn, "session")
    if not s:
        await q.edit_message_text("Phiên ôn đã kết thúc. Gõ /on để ôn tiếp.")
        return
    parts = q.data.split(":")
    action, cid = parts[0], int(parts[1])
    row = cards.get_card(conn, cid)

    if action == "rv_listen":
        if row is None:  # thẻ đã bị xóa giữa chừng
            await context.bot.send_message(s["chat"], "⚠️ Thẻ này đã bị xóa.")
            await _advance(context)
            return
        m = await send_card_audio(context, s["chat"], row)
        if m is None:
            await context.bot.send_message(s["chat"], "⚠️ Thẻ này chưa có audio.")
        else:
            s["aux"].append(m.message_id)
            db.kv_set(conn, "session", s)

    elif action == "rv_show":
        if row is None:  # thẻ đã bị xóa giữa chừng
            await context.bot.send_message(s["chat"], "⚠️ Thẻ này đã bị xóa.")
            await _advance(context)
            return
        lines = [f"🀄 <b>{html.escape(row['hanzi'])}</b>", f"📖 {html.escape(row['pinyin'])}",
                 f"🇬🇧 {html.escape(row['meaning']) if row['meaning'] else '<i>(chưa có nghĩa)</i>'}"]
        if row["example"]:
            lines.append(f"💬 {html.escape(row['example'])}")
        lines.append(f"\n({s['pos'] + 1}/{len(s['queue'])})")
        await _edit_or_send(context, s, "\n".join(lines), _answer_kb(cid))
        if row["image_file_id"]:
            m = await context.bot.send_photo(s["chat"], row["image_file_id"])
            s["aux"].append(m.message_id)
        m = await send_card_audio(context, s["chat"], row)
        if m:
            s["aux"].append(m.message_id)
        db.kv_set(conn, "session", s)

    elif action == "rv_rate":
        # Ignore stale/double taps: an old session message or a fast repeat
        # would re-apply SM-2 and skip the next card. Only the current card counts.
        if s["pos"] >= len(s["queue"]) or s["queue"][s["pos"]] != cid:
            return
        if row is None:  # thẻ đã bị xóa giữa chừng — skip without rating
            await _clear_aux(context, s)
            db.kv_set(conn, "session", s)
            await _advance(context)
            return
        rating = int(parts[2])
        cards.apply_rating(conn, cid, rating, config.today())
        if rating == 1:
            s["queue"].append(cid)  # Lại -> lặp lại cuối phiên
        s["done"] += 1
        await _clear_aux(context, s)
        db.kv_set(conn, "session", s)
        await _advance(context)


async def _advance(context):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    s["pos"] += 1
    if s["pos"] >= len(s["queue"]):
        n = stats.streak(conn, config.today())
        await _edit_or_send(
            context, s,
            f"🎉 <b>Hoàn thành!</b> Đã ôn {s['done']} lượt.\n🔥 Chuỗi: {n} ngày liên tiếp.",
            None)
        db.kv_del(conn, "session")
        return
    db.kv_set(conn, "session", s)
    await _show_front(context)
