### Task 11: Thu âm & tự so giọng (`app/bot/voice_flow.py`)

**Files:** Create `app/bot/voice_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `review_flow.send_card_audio`, `db.kv_*`, `cards.get_card`
- Produces: kv `awaiting_voice` = card id; callback `vc_rec:<cid>` (đã được `_answer_kb` trong Task 10 phát ra); `voice_flow.on_voice(update, context)` cho MessageHandler VOICE. **Khe cắm Azure (spec §10):** sau khi lưu voice, nếu setting `azure_speech_key` không rỗng thì (tương lai) gọi chấm điểm — bản này chỉ để comment đánh dấu chỗ cắm.

- [ ] **Step 1: Viết `app/bot/voice_flow.py`**

```python
from app import cards, db
from app.bot import review_flow
from app.bot.auth import owner_only_callback


@owner_only_callback
async def on_rec_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    cid = int(q.data.split(":")[1])
    db.kv_set(conn, "awaiting_voice", cid)
    await q.answer("Gửi tin nhắn thoại 🎙 ngay bây giờ")
    m = await context.bot.send_message(
        q.message.chat_id, "🎙 Nhấn giữ nút mic của Telegram, đọc từ này rồi gửi nhé.")
    s = db.kv_get(conn, "session")
    if s:
        s["aux"].append(m.message_id)
        db.kv_set(conn, "session", s)


async def on_voice(update, context):
    conn = context.bot_data["conn"]
    cid = db.kv_get(conn, "awaiting_voice")
    if cid is None:
        return
    db.kv_del(conn, "awaiting_voice")
    row = cards.get_card(conn, cid)
    if row is None:
        return
    file_id = update.message.voice.file_id
    conn.execute("UPDATE cards SET voice_file_id=? WHERE id=?", (file_id, cid))
    conn.commit()
    chat_id = update.effective_chat.id
    aux = [update.message.message_id]
    m1 = await review_flow.send_card_audio(context, chat_id, row)
    if m1:
        aux.append(m1.message_id)
    m2 = await context.bot.send_voice(chat_id, file_id)
    m3 = await context.bot.send_message(chat_id, "👂 Giọng chuẩn ở trên, giọng bạn ở dưới — nghe lại và tự so nhé.")
    aux += [m2.message_id, m3.message_id]
    # AZURE-SLOT: nếu db.get_setting(conn, "azure_speech_key") != "" thì gọi
    # Pronunciation Assessment ở đây và gửi kèm điểm số (spec §10, ngoài phạm vi bản đầu).
    s = db.kv_get(conn, "session")
    if s:
        s["aux"] += aux
        db.kv_set(conn, "session", s)
```

- [ ] **Step 2: Nối vào `main.py`**

```python
from app.bot import voice_flow
app.add_handler(CallbackQueryHandler(voice_flow.on_rec_callback, pattern=r"^vc_rec:"))
app.add_handler(MessageHandler(owner_filter & filters.VOICE, voice_flow.on_voice))
```

- [ ] **Step 3: Test thủ công** — trong phiên ôn, mở đáp án → 🎤 → gửi voice → nhận cặp audio chuẩn/của mình + lời nhắc; chấm điểm thẻ → mọi tin phụ (kể cả voice mình gửi) bị dọn. Gửi voice khi KHÔNG bấm 🎤 → bot im lặng.

- [ ] **Step 4: Commit** — `git commit -am "feat: voice self-comparison with Azure slot marker"`

---

