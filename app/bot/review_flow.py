import html
from pathlib import Path

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup
from telegram.error import BadRequest, TelegramError

from app import cards, config, db, stats
from app.bot.auth import owner_only_callback

RATE = [("🔁 Lại", 1), ("😓 Khó", 2), ("🙂 Tốt", 3), ("😎 Dễ", 4)]

MODE_LABEL = {"classic": "🃏 Lật thẻ", "typed": "⌨️ Tự luận",
              "mc:easy": "🔘 Trắc nghiệm 😌 Dễ",
              "mc:normal": "🔘 Trắc nghiệm 🙂 Thường",
              "mc:hard": "🔘 Trắc nghiệm 🔥 Khó"}


def _front_kb(cid):
    return Markup([[Btn("🔊 Nghe", callback_data=f"rv_listen:{cid}"),
                    Btn("👀 Xem đáp án", callback_data=f"rv_show:{cid}")]])


def _answer_kb(cid):
    return Markup([
        [Btn("🎤 Thu âm thử", callback_data=f"vc_rec:{cid}")],
        [Btn(label, callback_data=f"rv_rate:{cid}:{r}") for label, r in RATE],
    ])


async def cmd_review(update, context):
    await show_mode_picker(context, update.effective_chat.id)


async def show_mode_picker(context, chat_id):
    conn = context.bot_data["conn"]
    if not cards.build_queue(conn, config.today_iso()):
        await context.bot.send_message(chat_id, "🎉 Không có thẻ nào đến hạn. Nghỉ ngơi đi!")
        return
    last = db.get_setting(conn, "review_mode")
    rows = []
    if last in MODE_LABEL:
        rows.append([Btn(f"▶️ Như lần trước: {MODE_LABEL[last]}",
                         callback_data=f"rv_mode:{last}")])
    rows += [[Btn("🃏 Lật thẻ", callback_data="rv_mode:classic")],
             [Btn("🔘 Trắc nghiệm", callback_data="rv_mc_levels")],
             [Btn("⌨️ Tự luận", callback_data="rv_mode:typed")]]
    await context.bot.send_message(chat_id, "Chọn chế độ ôn:", reply_markup=Markup(rows))


async def start_session(context, chat_id, mode="classic", level="",
                        practice=False, queue=None):
    conn = context.bot_data["conn"]
    queue = queue if queue is not None else cards.build_queue(conn, config.today_iso())
    if not queue:
        await context.bot.send_message(chat_id, "🎉 Không có thẻ nào đến hạn. Nghỉ ngơi đi!")
        return
    db.kv_set(conn, "session", {"queue": queue, "pos": 0, "done": 0, "ok": 0,
                                "chat": chat_id, "msg": None, "aux": [],
                                "mode": mode, "level": level,
                                "practice": practice, "q": None})
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
    if s.get("mode", "classic") != "classic":
        from app.bot import quiz_flow
        await quiz_flow.show_question(context)
        return
    cid = s["queue"][s["pos"]]
    row = cards.get_card(conn, cid)
    if row is None:  # thẻ đã bị xóa giữa chừng
        await advance(context)
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
        await show_mode_picker(context, q.message.chat_id)
        return
    if q.data == "rv_mc_levels":
        kb = Markup([[Btn("😌 Dễ", callback_data="rv_mode:mc:easy"),
                      Btn("🙂 Thường", callback_data="rv_mode:mc:normal"),
                      Btn("🔥 Khó", callback_data="rv_mode:mc:hard")]])
        await q.edit_message_text("Chọn mức trắc nghiệm:", reply_markup=kb)
        return
    if q.data.startswith("rv_mode:"):
        choice = q.data.split(":", 1)[1]          # classic | typed | mc:easy...
        db.set_setting(conn, "review_mode", choice)
        mode, _, level = choice.partition(":")
        try:
            await q.message.delete()
        except TelegramError:
            pass
        await start_session(context, q.message.chat_id, mode=mode, level=level)
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


async def advance(context):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    s["pos"] += 1
    if s["pos"] >= len(s["queue"]):
        if s.get("practice"):
            await _edit_or_send(
                context, s,
                f"🏁 <b>Luyện xong!</b> Đúng {s.get('ok', 0)}/{s['done']} câu.", None)
        else:
            n = stats.streak(conn, config.today())
            await _edit_or_send(
                context, s,
                f"🎉 <b>Hoàn thành!</b> Đã ôn {s['done']} lượt.\n🔥 Chuỗi: {n} ngày liên tiếp.",
                None)
        pi = db.kv_get(conn, "pending_input")
        if pi and pi.get("action") == "quiz_typed":
            db.kv_del(conn, "pending_input")
        db.kv_del(conn, "session")
        return
    db.kv_set(conn, "session", s)
    await _show_front(context)


_advance = advance
