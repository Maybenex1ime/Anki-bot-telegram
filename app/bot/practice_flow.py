import html
import random

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import config, db, gemini, grading, sentences, stats
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
        try:
            await q.message.delete()
        except Exception:
            pass
        await _dict_next(context, q.message.chat_id)

    elif data == "pr_d_repeat":
        st = db.kv_get(conn, "dict_state")
        if st:
            srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
            if srow:
                await sentences.send_audio(context, st["chat"], srow)

    elif data == "pr_d_next":
        db.kv_del(conn, "dict_state")
        pi = db.kv_get(conn, "pending_input")
        if pi and pi.get("action") == "dictation":
            db.kv_del(conn, "pending_input")
        await _dict_next(context, q.message.chat_id)

    elif data == "pr_d_stop":
        db.kv_del(conn, "dict_state")
        pi = db.kv_get(conn, "pending_input")
        if pi and pi.get("action") == "dictation":
            db.kv_del(conn, "pending_input")
        await q.edit_message_text("🏁 Nghỉ chính tả. /luyen để chơi tiếp.")

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


async def _dict_next(context, chat_id):
    conn = context.bot_data["conn"]
    await sentences.maybe_refill(conn)              # nạp thêm nếu sắp cạn (Gemini có thì chạy)
    srow = sentences.pick(conn, need_words=False)
    if not srow:
        await context.bot.send_message(
            chat_id, "⚠️ Kho câu trống. Thêm câu ví dụ vào thẻ (cột ví_dụ/ví_dụ_thêm "
                     "trong CSV) hoặc đặt Gemini API key trong /settings.")
        return
    aux = []
    m = await sentences.send_audio(context, chat_id, srow)
    if m is None:
        await context.bot.send_message(chat_id, "⚠️ Không tạo được audio (mạng?). Thử lại sau.")
        return
    aux.append(m.message_id)
    kb = Markup([[Btn("🔁 Nghe lại", callback_data="pr_d_repeat"),
                  Btn("⏭ Bỏ qua", callback_data="pr_d_next"),
                  Btn("🏁 Dừng", callback_data="pr_d_stop")]])
    m2 = await context.bot.send_message(
        chat_id, "🎧 Nghe và gõ lại câu (chữ Hán):", reply_markup=kb)
    aux.append(m2.message_id)
    db.kv_set(conn, "dict_state", {"sid": srow["id"], "tries": 0,
                                   "chat": chat_id, "aux": aux, "first_ok": False})
    db.kv_set(conn, "pending_input", {"action": "dictation"})
    sentences.mark_used(conn, srow["id"])


def _sentence_reveal(srow):
    lines = [f"🀄 {html.escape(srow['hanzi'])}"]
    if srow["pinyin"]:
        lines.append(f"📖 {html.escape(srow['pinyin'])}")
    if srow["meaning"]:
        lines.append(f"🇬🇧 {html.escape(srow['meaning'])}")
    return "\n".join(lines)


DICT_NEXT_KB = Markup([[Btn("▶️ Câu tiếp", callback_data="pr_d_next"),
                        Btn("🏁 Dừng", callback_data="pr_d_stop")]])


async def dictation_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    st = db.kv_get(conn, "dict_state")
    if not st:
        return
    srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
    if not srow:
        db.kv_del(conn, "dict_state")
        return
    expected = grading.normalize_hanzi(srow["hanzi"])
    got = grading.normalize_hanzi(text)
    if got == expected:
        stats.bump_practice(conn, config.today_iso(), "dict", st["tries"] == 0)
        db.kv_del(conn, "dict_state")
        await update.message.reply_html(
            "✅ <b>Chính xác!</b>\n" + _sentence_reveal(srow), reply_markup=DICT_NEXT_KB)
        return
    diff_html, ok, total = grading.diff_chars(expected, got)
    if st["tries"] == 0:
        st["tries"] = 1
        db.kv_set(conn, "dict_state", st)
        db.kv_set(conn, "pending_input", {"action": "dictation"})
        await update.message.reply_html(
            f"❌ {ok}/{total} ký tự đúng: {diff_html}\n✍️ Thử lại lần nữa nhé:")
    else:
        stats.bump_practice(conn, config.today_iso(), "dict", False)
        db.kv_del(conn, "dict_state")
        await update.message.reply_html(
            f"❌ {ok}/{total} ký tự đúng: {diff_html}\n\nĐáp án:\n"
            + _sentence_reveal(srow), reply_markup=DICT_NEXT_KB)
