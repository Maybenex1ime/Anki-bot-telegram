### Task 11: Chép chính tả (`practice_flow` phần 2)

**Files:** Modify `app/bot/practice_flow.py`, `app/bot/main.py`

**Interfaces:**
- Consumes: `sentences.pick/mark_used/send_audio/maybe_refill/enrich_one`, `grading.normalize_hanzi/diff_chars`, `stats.bump_practice`
- Produces: kv `dict_state` = `{"sid": int, "tries": int, "chat": int, "aux": [msg_ids], "first_ok": bool}`; text action `"dictation"`; callbacks `pr_d_repeat`, `pr_d_next`, `pr_d_stop` (+ thay stub `pr_dict`).

- [ ] **Step 1: Thay stub `pr_dict` và thêm hàm.** Trong `practice_flow.py` thêm import `html`, `from app import config, gemini, grading, sentences, stats`, rồi:

```python
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
```

Trong `on_callback` thay nhánh `pr_dict` và thêm:

```python
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
```

- [ ] **Step 2: Wiring `main.py`** — `register("dictation", practice_flow.dictation_input)`.
- [ ] **Step 3: Verify** — suite + offline build_app; REPL: `grading.diff_chars("我在学习","我再学习")` cho kết quả như test Task 2.
- [ ] **Step 4: Commit** — `git add -A && git commit -m "feat: dictation practice with char diff and one retry"`

---

