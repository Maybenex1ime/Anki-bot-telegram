### Task 8: MCQ trong session (`app/bot/quiz_flow.py` bản đầy đủ — phần 1)

**Files:** Rewrite `app/bot/quiz_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `quiz.get_options`, `grading.time_to_rating`, `cards.apply_rating/get_card`, `stats.bump_practice`, `review_flow._edit_or_send/_clear_aux/advance/send_card_audio/_front_kb`, session kv như Task 7
- Produces:
  - `quiz_flow.show_question(context)` — rẽ theo `s["mode"]`: `"mc"` → câu hỏi 4 lựa chọn (options trong text, nút `[A][B][C][D]` = `qz_ans:<cid>:<idx>`); `"typed"` → Task 9
  - `s["q"]` cho MCQ: `{"kind":"mc","options":[4 chuỗi],"correct":int,"asked_at":float}`
  - Callback `qz_ans` chấm + hiện mặt sau + nút `[▶️ Tiếp]` (`qz_next:<cid>`); rating áp khi bấm Tiếp (AGAIN → requeue)
  - Fallback: `get_options` trả None → thẻ đó hiển thị dạng lật thẻ cổ điển (`s["q"]={"kind":"fallback"}`)

- [ ] **Step 1: Viết `app/bot/quiz_flow.py`** (thay stub):

```python
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


async def show_question(context):
    conn = context.bot_data["conn"]
    s = db.kv_get(conn, "session")
    cid = s["queue"][s["pos"]]
    row = cards.get_card(conn, cid)
    if row is None:
        await review_flow.advance(context)
        return
    if s["mode"] == "typed":
        await _show_typed(context, s, row)          # Task 9 định nghĩa; Task 8 tạo stub tạm:
        # async def _show_typed(context, s, row):
        #     await review_flow._edit_or_send(context, s, "⚠️ Tự luận đang được xây.", None)
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
    await q.answer()
    s = db.kv_get(conn, "session")
    if not s:
        await q.edit_message_text("Phiên đã kết thúc. Gõ /on hoặc /luyen.")
        return
    parts = q.data.split(":")
    action, cid = parts[0], int(parts[1])
    if s["pos"] >= len(s["queue"]) or s["queue"][s["pos"]] != cid:
        return                                       # stale/double-tap
    row = cards.get_card(conn, cid)
    if row is None:
        await review_flow._clear_aux(context, s)
        db.kv_set(conn, "session", s)
        await review_flow.advance(context)
        return

    if action == "qz_ans":
        qst = s.get("q") or {}
        if qst.get("kind") != "mc":
            return
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
            return
        rating = qst.get("rating")
        if rating is not None and not s["practice"]:
            cards.apply_rating(conn, cid, rating, config.today())
            if rating == srs.AGAIN:
                s["queue"].append(cid)
        await review_flow._clear_aux(context, s)
        s["q"] = None
        db.kv_set(conn, "session", s)
        await review_flow.advance(context)
```

- [ ] **Step 2: Wiring `app/bot/main.py`** — thêm import `quiz_flow` vào khối import `app.bot`, và:

```python
app.add_handler(CallbackQueryHandler(quiz_flow.on_callback, pattern=r"^qz_"))
```

- [ ] **Step 3: Verify** — `python -m pytest tests/ -v`; offline build_app check (handler count tăng 1); REPL smoke: gọi `grading.shuffle_words(["a","b","c","d"], random.Random(1))` hợp lệ.
- [ ] **Step 4: Commit** — `git add -A && git commit -m "feat: MCQ questions in review session with timed auto-rating"`

---

