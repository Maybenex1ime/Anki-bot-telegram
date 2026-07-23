### Task 9: Tự luận trong session (`quiz_flow` phần 2)

**Files:** Modify `app/bot/quiz_flow.py`, `app/bot/main.py`

**Interfaces:**
- Produces: `_show_typed` (đã gọi từ `show_question`); text action `"quiz_typed"` (`typed_input(update, context, pending, text)`); callback `qz_easy:<cid>` (nâng GOOD→EASY ở màn reveal); `s["q"]` typed: `{"kind":"typed","asked_at":float}`; pending_input `{"action":"quiz_typed","cid":cid}` đặt mỗi lần hiện câu.

- [ ] **Step 1: Thêm vào `app/bot/quiz_flow.py`:**

```python
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
```

Và trong `on_callback`, thêm nhánh (cùng cấp `qz_ans`/`qz_next`):

```python
    elif action == "qz_easy":
        qst = s.get("q") or {}
        if qst.get("kind") != "reveal" or qst.get("rating") != srs.GOOD:
            return
        qst["rating"] = srs.EASY
        s["q"] = qst
        db.kv_set(conn, "session", s)
        await q.answer("😎 Sẽ tính là Dễ")
```

(lưu ý: nhánh này gọi `q.answer(...)` lần nữa với text — chấp nhận được, PTB cho phép; hoặc chuyển `await q.answer()` đầu hàm xuống từng nhánh — chọn cách nào cũng được, miễn không lỗi.)

- [ ] **Step 2: Wiring `main.py`** — thêm `register("quiz_typed", quiz_flow.typed_input)` cạnh các register khác.

- [ ] **Step 3: Dọn pending_input khi phiên kết thúc** — trong `review_flow.advance`, nhánh kết thúc (trước `db.kv_del(conn, "session")`), thêm:

```python
        pi = db.kv_get(conn, "pending_input")
        if pi and pi.get("action") == "quiz_typed":
            db.kv_del(conn, "pending_input")
```

- [ ] **Step 4: Verify** — `python -m pytest tests/ -v`; offline build_app; kiểm tra `textrouter.TEXT_ACTIONS` chứa `quiz_typed` sau import main.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: typed-answer questions with two-tier grading and Easy upgrade"`

---

