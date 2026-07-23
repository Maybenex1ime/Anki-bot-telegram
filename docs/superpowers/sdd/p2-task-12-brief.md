### Task 12: Ghép từ thành câu (`practice_flow` phần 3)

**Files:** Modify `app/bot/practice_flow.py`

**Interfaces:**
- Consumes: `sentences.pick(need_words=True)/mark_used/enrich_one/maybe_refill`, `grading.shuffle_words/normalize_hanzi`, `gemini.judge_word_order`, `stats.bump_practice`
- Produces: kv `build_state` = `{"sid": int, "words": [str], "perm": [int], "chosen": [int], "chat": int, "msg": int}`; callbacks `pr_build`, `pr_b_w:<i>`, `pr_b_undo`, `pr_b_sub`, `pr_b_skip`, `pr_b_next`, `pr_b_stop`.

- [ ] **Step 1: Thêm vào `practice_flow.py`** (import thêm `json`):

```python
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
```

Và trong `on_callback` thay stub `pr_build` + thêm các nhánh:

```python
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
```

- [ ] **Step 2: Verify** — suite + offline build_app.
- [ ] **Step 3: Commit** — `git add -A && git commit -m "feat: sentence-builder practice with tap-to-arrange and alt-order judging"`

---

