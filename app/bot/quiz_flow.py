import html
import random
import time

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import cards, config, db, gemini, grading, quiz, srs, stats
from app.bot import review_flow
from app.bot.auth import owner_only_callback

LETTERS = ["A", "B", "C", "D"]


def _back_lines(row):
    lines = [f"🀄 <b>{html.escape(row['hanzi'])}</b>",
             f"📖 {html.escape(row['pinyin'])}",
             f"🇬🇧 {html.escape(row['meaning']) if row['meaning'] else '<i>(chưa có nghĩa)</i>'}"]
    if row["example"]:
        lines.append(f"💬 {html.escape(row['example'])}")
    return lines


async def _send_back_aux(context, s, row):
    if row["image_file_id"]:
        m = await context.bot.send_photo(s["chat"], row["image_file_id"])
        s["aux"].append(m.message_id)
    m = await review_flow.send_card_audio(context, s["chat"], row)
    if m:
        s["aux"].append(m.message_id)


async def _show_typed(context, s, row):
    conn = context.bot_data["conn"]
    s["q"] = {"kind": "typed", "asked_at": time.time()}
    db.kv_set(conn, "session", s)
    db.kv_set(conn, "pending_input", {"action": "quiz_typed", "cid": row["id"]})
    text = (f"🀄 <b>{html.escape(row['hanzi'])}</b>\n\n"
            f"⌨️ Gõ nghĩa tiếng Anh của từ này:\n\n({s['pos'] + 1}/{len(s['queue'])})")
    kb = Markup([[Btn("🔊 Nghe", callback_data=f"rv_listen:{row['id']}")]])
    await review_flow._edit_or_send(context, s, text, kb)


async def typed_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    cid = pending.get("cid")
    if (not s or s.get("mode") != "typed" or (s.get("q") or {}).get("kind") != "typed"
            or s["pos"] >= len(s["queue"]) or s["queue"][s["pos"]] != cid):
        return
    row = cards.get_card(conn, cid)
    if row is None:
        await review_flow.advance(context)
        return
    s["aux"].append(update.message.message_id)      # dọn tin trả lời khi sang câu
    verdict, note = grading.grade_typed_offline(row["meaning"], text), ""
    if verdict == "unsure":
        g = await gemini.judge_meaning(conn, row["hanzi"], row["meaning"], text)
        if g:
            verdict, note = g["verdict"], g["note"]
        else:
            verdict = grading.fallback_partial(row["meaning"], text)
    correct = verdict == "correct"
    s["done"] += 1
    extra = []
    if correct:
        s["ok"] += 1
        header, rating = "✅ Đúng!", srs.GOOD
        if not s["practice"]:
            extra = [Btn("😎 Dễ", callback_data=f"qz_easy:{cid}")]
    elif verdict == "partial":
        header, rating = "🟡 Đúng một phần.", srs.HARD
    else:
        header, rating = "❌ Chưa đúng.", srs.AGAIN
    if note:
        header += f"\n💡 {html.escape(note)}"
    if s["practice"]:
        stats.bump_practice(conn, config.today_iso(), "typed", correct)
        rating = None
    await _reveal(context, s, row, header, rating, extra_buttons=extra)


async def show_question(context):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    cid = s["queue"][s["pos"]]
    row = cards.get_card(conn, cid)
    if row is None:
        await review_flow.advance(context)
        return
    if s["mode"] == "typed":
        await _show_typed(context, s, row)
        return
    opts3 = await quiz.get_options(conn, row, s["level"]) if row["meaning"] else None
    if not opts3:                                   # không đủ nhiễu
        if s["practice"]:                           # /luyen: bỏ qua thẻ (không được rơi về rv_rate → SM-2)
            await review_flow.advance(context)
            return
        s["q"] = {"kind": "fallback"}               # /on: rơi về lật thẻ cổ điển
        db.kv_set(conn, "session", s)
        text = f"🀄 <b>{html.escape(row['hanzi'])}</b>\n\n({s['pos'] + 1}/{len(s['queue'])})"
        await review_flow._edit_or_send(context, s, text, review_flow._front_kb(cid))
        return
    options = opts3 + [row["meaning"]]
    rng = random.Random()
    order = grading.shuffle_words(options, rng)     # hoán vị 4 chỉ số
    options = [options[i] for i in order]
    correct = order.index(3)
    s["q"] = {"kind": "mc", "options": options, "correct": correct,
              "asked_at": time.time()}
    db.kv_set(conn, "session", s)
    lines = [f"🀄 <b>{html.escape(row['hanzi'])}</b> — nghĩa là gì?", ""]
    for i, o in enumerate(options):
        lines.append(f"<b>{LETTERS[i]}.</b> {html.escape(o)}")
    lines.append(f"\n({s['pos'] + 1}/{len(s['queue'])})")
    kb = Markup([[Btn(l, callback_data=f"qz_ans:{cid}:{i}")
                  for i, l in enumerate(LETTERS)]])
    await review_flow._edit_or_send(context, s, "\n".join(lines), kb)


def _thresholds(conn):
    return (float(db.get_setting(conn, "quiz_fast_sec")),
            float(db.get_setting(conn, "quiz_slow_sec")))


RATING_LABEL = {srs.AGAIN: "🔁 Lại", srs.HARD: "😓 Khó",
                srs.GOOD: "🙂 Tốt", srs.EASY: "😎 Dễ"}


async def _reveal(context, s, row, header, rating, extra_buttons=None):
    """Hiện mặt sau + lưu rating chờ áp ở qz_next."""
    conn = context.bot_data["conn"]
    s["q"] = {"kind": "reveal", "rating": rating}
    lines = [header, ""] + _back_lines(row)
    lines.append(f"\n({s['pos'] + 1}/{len(s['queue'])})")
    btns = (extra_buttons or []) + [Btn("▶️ Tiếp", callback_data=f"qz_next:{row['id']}")]
    await review_flow._edit_or_send(context, s, "\n".join(lines), Markup([btns]))
    await _send_back_aux(context, s, row)
    db.kv_set(conn, "session", s)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    # Ack once per path (qz_easy needs its own toast text), so no double-answer.
    s = db.kv_get(conn, "session")
    if not s:
        await q.answer()
        await q.edit_message_text("Phiên đã kết thúc. Gõ /on hoặc /luyen.")
        return
    parts = q.data.split(":")
    action, cid = parts[0], int(parts[1])
    if s["pos"] >= len(s["queue"]) or s["queue"][s["pos"]] != cid:
        await q.answer()
        return                                       # stale/double-tap
    row = cards.get_card(conn, cid)
    if row is None:
        await q.answer()
        await review_flow._clear_aux(context, s)
        db.kv_set(conn, "session", s)
        await review_flow.advance(context)
        return

    if action == "qz_ans":
        qst = s.get("q") or {}
        if qst.get("kind") != "mc":
            await q.answer()
            return
        await q.answer()
        idx = int(parts[2])
        correct = idx == qst["correct"]
        elapsed = time.time() - qst["asked_at"]
        fast, slow = _thresholds(conn)
        rating = grading.time_to_rating(correct, elapsed, s["level"], fast, slow)
        s["done"] += 1
        if correct:
            s["ok"] += 1
            header = f"✅ Đúng! ({elapsed:.0f}s → {RATING_LABEL[rating]})" \
                if not s["practice"] else "✅ Đúng!"
        else:
            right = html.escape(qst["options"][qst["correct"]])
            header = f"❌ Sai — đáp án: <b>{right}</b>"
        if s["practice"]:
            stats.bump_practice(conn, config.today_iso(), "mc", correct)
            rating = None
        await _reveal(context, s, row, header, rating)

    elif action == "qz_next":
        qst = s.get("q") or {}
        if qst.get("kind") != "reveal":
            await q.answer()
            return
        await q.answer()
        rating = qst.get("rating")
        if rating is not None and not s["practice"]:
            cards.apply_rating(conn, cid, rating, config.today())
            if rating == srs.AGAIN:
                s["queue"].append(cid)
        await review_flow._clear_aux(context, s)
        s["q"] = None
        db.kv_set(conn, "session", s)
        await review_flow.advance(context)

    elif action == "qz_easy":
        qst = s.get("q") or {}
        if qst.get("kind") != "reveal" or qst.get("rating") != srs.GOOD:
            await q.answer()
            return
        qst["rating"] = srs.EASY
        s["q"] = qst
        db.kv_set(conn, "session", s)
        await q.answer("😎 Sẽ tính là Dễ")
