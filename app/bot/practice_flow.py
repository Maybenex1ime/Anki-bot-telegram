import html
import json
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
        try:
            await q.message.delete()
        except Exception:
            pass
        await _build_next(context, q.message.chat_id)

    elif data.startswith("pr_b_w:"):
        st = db.kv_get(conn, "build_state")
        if not st:
            return
        i = int(data.split(":")[1])
        if i in st["chosen"] or i not in st["perm"]:
            return
        st["chosen"].append(i)
        srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
        await _build_render(context, st, srow)

    elif data == "pr_b_undo":
        st = db.kv_get(conn, "build_state")
        if not st or not st["chosen"]:
            return
        st["chosen"].pop()
        srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
        await _build_render(context, st, srow)

    elif data == "pr_b_sub":
        st = db.kv_get(conn, "build_state")
        if not st:
            return
        srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
        if len(st["chosen"]) < len(st["words"]):
            await q.answer("Dùng hết các từ đã rồi nộp nhé!", show_alert=False)
            return
        attempt = "".join(st["words"][i] for i in st["chosen"])
        original = grading.normalize_hanzi(srow["hanzi"])
        db.kv_del(conn, "build_state")
        if attempt == original:
            ok, note = True, ""
        else:
            g = await gemini.judge_word_order(conn, srow["hanzi"],
                                              attempt, srow["meaning"])
            ok = bool(g and g["ok"])
            note = (g or {}).get("note", "")
        stats.bump_practice(conn, config.today_iso(), "build", ok)
        if ok and attempt == original:
            head = "✅ <b>Chính xác!</b>"
        elif ok:
            head = "✅ <b>Cũng đúng!</b> (trật tự thay thế hợp lệ)"
        else:
            head = "❌ Chưa đúng."
        if note:
            head += f"\n💡 {html.escape(note)}"
        await q.edit_message_text(
            head + "\n\n" + _sentence_reveal(srow),
            parse_mode="HTML", reply_markup=BUILD_NEXT_KB)

    elif data == "pr_b_skip":
        st = db.kv_get(conn, "build_state")
        db.kv_del(conn, "build_state")
        if st:
            srow = conn.execute("SELECT * FROM sentences WHERE id=?", (st["sid"],)).fetchone()
            if srow:
                await q.edit_message_text("⏭ Bỏ qua.\n\n" + _sentence_reveal(srow),
                                          parse_mode="HTML", reply_markup=BUILD_NEXT_KB)

    elif data == "pr_b_next":
        try:
            await q.message.delete()
        except Exception:
            pass
        await _build_next(context, q.message.chat_id)

    elif data == "pr_b_stop":
        db.kv_del(conn, "build_state")
        await q.edit_message_text("🏁 Nghỉ ghép câu. /luyen để chơi tiếp.")


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


async def _build_next(context, chat_id):
    conn = context.bot_data["conn"]
    await sentences.maybe_refill(conn)
    await sentences.enrich_one(conn)                 # tranh thủ tách từ 1 câu tồn đọng
    srow = sentences.pick(conn, need_words=True)
    if not srow:
        await context.bot.send_message(
            chat_id, "⚠️ Chưa có câu đã tách từ. Đặt Gemini API key trong /settings "
                     "để bot tự sinh/tách câu nhé.")
        return
    words = json.loads(srow["words_json"])
    perm = grading.shuffle_words(words, random.Random())
    st = {"sid": srow["id"], "words": words, "perm": perm, "chosen": [],
          "chat": chat_id, "msg": None}
    db.kv_set(conn, "build_state", st)
    sentences.mark_used(conn, srow["id"])
    await _build_render(context, st, srow)


def _build_kb(st):
    rows, row = [], []
    for i in st["perm"]:
        if i in st["chosen"]:
            continue
        row.append(Btn(st["words"][i], callback_data=f"pr_b_w:{i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Btn("↩️ Xóa từ cuối", callback_data="pr_b_undo"),
                 Btn("✅ Nộp", callback_data="pr_b_sub"),
                 Btn("⏭ Bỏ qua", callback_data="pr_b_skip")])
    return Markup(rows)


async def _build_render(context, st, srow):
    conn = context.bot_data["conn"]
    current = " ".join(st["words"][i] for i in st["chosen"]) or "…"
    text = (f"🧩 <b>Ghép các từ thành câu</b>\n"
            f"🇬🇧 {html.escape(srow['meaning']) if srow['meaning'] else '(không có gợi ý)'}\n\n"
            f"Câu của bạn: {html.escape(current)}")
    if st["msg"]:
        try:
            await context.bot.edit_message_text(text, chat_id=st["chat"],
                                                message_id=st["msg"],
                                                reply_markup=_build_kb(st),
                                                parse_mode="HTML")
            db.kv_set(conn, "build_state", st)
            return
        except Exception:
            pass
    m = await context.bot.send_message(st["chat"], text,
                                       reply_markup=_build_kb(st), parse_mode="HTML")
    st["msg"] = m.message_id
    db.kv_set(conn, "build_state", st)


BUILD_NEXT_KB = Markup([[Btn("▶️ Câu tiếp", callback_data="pr_b_next"),
                         Btn("🏁 Dừng", callback_data="pr_b_stop")]])


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
