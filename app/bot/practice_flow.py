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
    where = "" if deck_id == 0 else "AND deck_id=? "
    args = ((deck_id,) if deck_id else ()) + (n,)
    return [r["id"] for r in conn.execute(
        f"SELECT id FROM cards WHERE meaning<>'' {where}"
        "ORDER BY RANDOM() LIMIT ?", args)]


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    # Ack once per path (pr_b_sub's unused-words guard needs its own toast text),
    # so no double-answer — mirror quiz_flow.on_callback.
    data = q.data

    if data.startswith("pr_quiz:"):
        await q.answer()
        mode = data.split(":")[1]
        decks = conn.execute(
            "SELECT d.id, d.name, COUNT(c.id) n FROM decks d "
            "LEFT JOIN cards c ON c.deck_id=d.id AND c.meaning<>'' "
            "GROUP BY d.id ORDER BY d.id").fetchall()
        kb = [[Btn("Tất cả các bộ", callback_data=f"pr_qd:{mode}:0")]]
        kb += [[Btn(f"{d['name']} ({d['n']})", callback_data=f"pr_qd:{mode}:{d['id']}")]
               for d in decks if d["n"]]
        await q.edit_message_text("Luyện bộ nào?", reply_markup=Markup(kb))

    elif data.startswith("pr_qd:"):
        await q.answer()
        _, mode, deck_id = data.split(":")
        if mode == "typed":
            await _start_quiz(context, q, "typed", "", int(deck_id))
        else:
            await q.edit_message_text(
                "Chọn mức:",
                reply_markup=review_flow.level_kb(lambda lv: f"pr_ql:{deck_id}:{lv}"))

    elif data.startswith("pr_ql:"):
        await q.answer()
        _, deck_id, level = data.split(":")
        await _start_quiz(context, q, "mc", level, int(deck_id))

    elif data == "pr_dict":
        await q.answer()
        try:
            await q.message.delete()
        except Exception:
            pass
        await _dict_next(context, q.message.chat_id)

    elif data == "pr_d_repeat":
        await q.answer()
        st = db.kv_get(conn, "dict_state")
        if st:
            srow = _sentence(conn, st["sid"])
            if srow:
                await sentences.send_audio(context, st["chat"], srow)

    elif data == "pr_d_next":
        await q.answer()
        _dict_teardown(conn)
        await _dict_next(context, q.message.chat_id)

    elif data == "pr_d_stop":
        await q.answer()
        _dict_teardown(conn)
        await q.edit_message_text("🏁 Nghỉ chính tả. /luyen để chơi tiếp.")

    elif data == "pr_build":
        await q.answer()
        try:
            await q.message.delete()
        except Exception:
            pass
        await _build_next(context, q.message.chat_id)

    elif data.startswith("pr_b_w:"):
        await q.answer()
        st = db.kv_get(conn, "build_state")
        if not st:
            return
        i = int(data.split(":")[1])
        if i in st["chosen"] or i not in st["perm"]:
            return
        st["chosen"].append(i)
        await _build_render(context, st)

    elif data == "pr_b_undo":
        await q.answer()
        st = db.kv_get(conn, "build_state")
        if not st or not st["chosen"]:
            return
        st["chosen"].pop()
        await _build_render(context, st)

    elif data == "pr_b_sub":
        st = db.kv_get(conn, "build_state")
        if not st:
            await q.answer()
            return
        srow = _sentence(conn, st["sid"])
        if len(st["chosen"]) < len(st["words"]):
            await q.answer("Dùng hết các từ đã rồi nộp nhé!", show_alert=False)
            return
        await q.answer()
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
        await q.answer()
        st = db.kv_get(conn, "build_state")
        db.kv_del(conn, "build_state")
        if st:
            srow = _sentence(conn, st["sid"])
            if srow:
                await q.edit_message_text("⏭ Bỏ qua.\n\n" + _sentence_reveal(srow),
                                          parse_mode="HTML", reply_markup=BUILD_NEXT_KB)

    elif data == "pr_b_next":
        await q.answer()
        try:
            await q.message.delete()
        except Exception:
            pass
        await _build_next(context, q.message.chat_id)

    elif data == "pr_b_stop":
        await q.answer()
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


def _sentence(conn, sid):
    return conn.execute("SELECT * FROM sentences WHERE id=?", (sid,)).fetchone()


def _dict_teardown(conn):
    db.kv_del(conn, "dict_state")
    db.clear_pending(conn, "dictation")


async def _dict_next(context, chat_id):
    conn = context.bot_data["conn"]
    _dict_teardown(conn)   # phiên cũ (nếu có) không được sống sót sang câu mới
    await sentences.maybe_refill(conn)              # nạp thêm nếu sắp cạn (Gemini có thì chạy)
    srow = sentences.pick(conn, need_words=False)
    if not srow:
        await context.bot.send_message(
            chat_id, "⚠️ Kho câu trống. Thêm câu ví dụ vào thẻ (cột ví_dụ/ví_dụ_thêm "
                     "trong CSV) hoặc đặt Gemini API key trong /settings.")
        return
    if await sentences.send_audio(context, chat_id, srow) is None:
        await context.bot.send_message(chat_id, "⚠️ Không tạo được audio (mạng?). Thử lại sau.")
        return
    kb = Markup([[Btn("🔁 Nghe lại", callback_data="pr_d_repeat"),
                  Btn("⏭ Bỏ qua", callback_data="pr_d_next"),
                  Btn("🏁 Dừng", callback_data="pr_d_stop")]])
    await context.bot.send_message(
        chat_id, "🎧 Nghe và gõ lại câu (chữ Hán):", reply_markup=kb)
    db.kv_set(conn, "dict_state", {"sid": srow["id"], "tries": 0, "chat": chat_id})
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
          "meaning": srow["meaning"], "chat": chat_id, "msg": None}
    sentences.mark_used(conn, srow["id"])
    await _build_render(context, st)   # _build_render lo phần lưu state


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


async def _build_render(context, st):
    conn = context.bot_data["conn"]
    current = " ".join(st["words"][i] for i in st["chosen"]) or "…"
    hint = html.escape(st["meaning"]) if st["meaning"] else "(không có gợi ý)"
    text = ("🧩 <b>Ghép các từ thành câu</b>\n"
            f"🇬🇧 {hint}\n\n"
            f"Câu của bạn: {html.escape(current)}")
    await review_flow._edit_or_send(context, st, text, _build_kb(st),
                                    kv_key="build_state")
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
    srow = _sentence(conn, st["sid"])
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
