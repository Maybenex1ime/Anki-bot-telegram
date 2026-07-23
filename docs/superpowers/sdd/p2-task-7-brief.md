### Task 7: Mode picker cho `/on` (`app/bot/review_flow.py`)

**Files:** Modify `app/bot/review_flow.py`

**Interfaces:**
- Consumes: setting `review_mode`
- Produces:
  - session kv `session` thêm khóa: `"mode"` (`"classic"|"mc"|"typed"`), `"level"` (`"easy"|"normal"|"hard"|""`), `"q"` (dict trạng thái câu hỏi hiện tại hoặc None), `"practice"` (bool), `"ok"` (đếm câu đúng — dùng ở /luyen)
  - callbacks mới dưới pattern `^rv_` có sẵn: `rv_mode:<classic|typed|mc:easy|mc:normal|mc:hard>`, `rv_mc_levels`
  - `start_session(context, chat_id, mode="classic", level="", practice=False, queue=None)` — chữ ký mở rộng; Task 8-10 gọi
  - `_show_front` rẽ nhánh: mode != "classic" → import cục bộ `from app.bot import quiz_flow; await quiz_flow.show_question(context)` (Task 8 tạo hàm này; TRONG task này để tạm stub thông báo — xem Step 2)
  - `advance(context)` — đổi tên public từ `_advance` (giữ alias `_advance = advance`); nhánh kết thúc: nếu `s.get("practice")` → tổng kết `"🏁 Luyện xong! Đúng {ok}/{done}."` không streak, không đụng review_mode

- [ ] **Step 1: Sửa `cmd_review` + thêm picker.** Trong `app/bot/review_flow.py`:

```python
MODE_LABEL = {"classic": "🃏 Lật thẻ", "typed": "⌨️ Tự luận",
              "mc:easy": "🔘 Trắc nghiệm 😌 Dễ",
              "mc:normal": "🔘 Trắc nghiệm 🙂 Thường",
              "mc:hard": "🔘 Trắc nghiệm 🔥 Khó"}


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
```

- [ ] **Step 2: Mở rộng `start_session` + `_show_front` + `advance`:**

```python
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
```

`_show_front`: sau guard `row is None`, thêm trước phần render cũ:

```python
    if s.get("mode", "classic") != "classic":
        from app.bot import quiz_flow
        await quiz_flow.show_question(context)
        return
```

(Task này `app/bot/quiz_flow.py` CHƯA tồn tại — tạo stub tối thiểu để import không vỡ:)

```python
# app/bot/quiz_flow.py (stub — Task 8 thay bằng bản đầy đủ)
async def show_question(context):
    from app.bot import review_flow
    conn = context.bot_data["conn"]
    s = review_flow.db.kv_get(conn, "session")
    await review_flow._edit_or_send(context, s, "⚠️ Chế độ này đang được xây.", None)
```

Đổi tên `_advance` → `advance` (giữ dòng `_advance = advance` ngay dưới để chỗ gọi cũ không vỡ), sửa nhánh kết thúc:

```python
    if s["pos"] >= len(s["queue"]):
        if s.get("practice"):
            await _edit_or_send(context, s,
                f"🏁 <b>Luyện xong!</b> Đúng {s.get('ok', 0)}/{s['done']} câu.", None)
        else:
            n = stats.streak(conn, config.today())
            await _edit_or_send(context, s,
                f"🎉 <b>Hoàn thành!</b> Đã ôn {s['done']} lượt.\n🔥 Chuỗi: {n} ngày liên tiếp.",
                None)
        db.kv_del(conn, "session")
        return
```

- [ ] **Step 3: Thêm nhánh callback trong `on_callback`** (sau nhánh `rv_start`; đổi luôn `rv_start` thành gọi `show_mode_picker(context, q.message.chat_id)`):

```python
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
```

Lưu ý: hai nhánh này đặt TRƯỚC đoạn `s = db.kv_get(conn, "session")` (chúng không cần session đang mở).

- [ ] **Step 4: Verify offline + suite** — `python -m pytest tests/ -v`; với env dummy: `python -c "from app.bot.main import build_app; build_app()"`; kiểm tra nhanh session mới có đủ khóa bằng REPL nhỏ nếu cần.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: /on mode picker + session mode plumbing (classic path intact)"`

---

