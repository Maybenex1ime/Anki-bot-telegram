### Task 9: Text router + luồng tạo thẻ

**Files:** Create `app/bot/textrouter.py`, `app/bot/create_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `cards.create_card/exists_hanzi`, `lookup.gen_pinyin/lookup_meaning`, `db.kv_*`
- Produces:
  - kv `pending_input`: dict `{"action": str, ...}` — hợp đồng chung mọi flow. Actions của task này: `pc_field` (`{"field": "pinyin"|"meaning"|"example"}`). Task sau thêm action mới vào `textrouter.TEXT_ACTIONS` bằng `textrouter.register(action, async_fn(update, context, pending, text))`.
  - kv `pending_card`: `{"hanzi","pinyin","meaning","example","image_file_id","deck_id"}`
  - `textrouter.on_text(update, context)` — nếu có `pending_input` → dispatch; elif text chứa ký tự CJK (`[一-鿿]`) → `create_flow.start_pending(update, context, text)`; else gợi ý dùng /start.
  - `textrouter.on_photo(update, context)` — nếu có `pending_card` → gắn ảnh (photo lớn nhất: `update.message.photo[-1].file_id`), render lại preview.
  - `create_flow.render_preview(context, chat_id) -> None` (gửi/sửa message preview, msg id lưu kv `pending_msg`)
  - Callback data: `pc_save`, `pc_cancel`, `pc_edit:pinyin`, `pc_edit:meaning`, `pc_edit:example`, `pc_deck`, `pc_deck_set:<id>`

- [ ] **Step 1: Viết `app/bot/textrouter.py`**

```python
import re

from app import db
from app.bot import create_flow

_HAN = re.compile(r"[一-鿿]")
TEXT_ACTIONS = {}


def register(action, fn):
    TEXT_ACTIONS[action] = fn


async def on_text(update, context):
    conn = context.bot_data["conn"]
    text = update.message.text.strip()
    pending = db.kv_get(conn, "pending_input")
    if pending:
        fn = TEXT_ACTIONS.get(pending.get("action"))
        if fn:
            db.kv_del(conn, "pending_input")
            await fn(update, context, pending, text)
            return
    if _HAN.search(text):
        await create_flow.start_pending(update, context, text)
    else:
        await update.message.reply_text(
            "Gõ chữ Hán để tạo thẻ (VD: 学习), hoặc /start để xem lệnh.")


async def on_photo(update, context):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if not pc:
        return
    pc["image_file_id"] = update.message.photo[-1].file_id
    db.kv_set(conn, "pending_card", pc)
    await update.message.reply_text("🖼 Đã đính kèm ảnh vào thẻ đang tạo.")
    await create_flow.render_preview(context, update.effective_chat.id)
```

- [ ] **Step 2: Viết `app/bot/create_flow.py`**

```python
from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup
from telegram.error import BadRequest

from app import cards, db, lookup
from app.bot.auth import owner_only_callback

FIELD_LABEL = {"pinyin": "pinyin", "meaning": "nghĩa tiếng Anh", "example": "câu ví dụ"}


async def start_pending(update, context, hanzi):
    conn = context.bot_data["conn"]
    pc = {
        "hanzi": hanzi,
        "pinyin": lookup.gen_pinyin(hanzi),
        "meaning": lookup.lookup_meaning(conn, hanzi),
        "example": "", "image_file_id": "", "deck_id": 1,
    }
    db.kv_set(conn, "pending_card", pc)
    db.kv_del(conn, "pending_msg")
    await render_preview(context, update.effective_chat.id)


def _preview(conn, pc):
    deck = conn.execute("SELECT name FROM decks WHERE id=?", (pc["deck_id"],)).fetchone()
    lines = [f"🀄 <b>{pc['hanzi']}</b>", f"📖 {pc['pinyin']}",
             f"🇬🇧 {pc['meaning'] or '<i>(chưa có nghĩa — bấm Sửa nghĩa)</i>'}"]
    if pc["example"]:
        lines.append(f"💬 {pc['example']}")
    if pc["image_file_id"]:
        lines.append("🖼 Có ảnh đính kèm")
    if cards.exists_hanzi(conn, pc["hanzi"]):
        lines.append("⚠️ <b>Đã có thẻ trùng chữ Hán này</b>")
    lines.append(f"📦 Bộ: {deck['name'] if deck else '?'}")
    lines.append("\nXem lại rồi bấm Lưu nhé:")
    kb = Markup([
        [Btn("💾 Lưu", callback_data="pc_save"), Btn("❌ Hủy", callback_data="pc_cancel")],
        [Btn("✏️ Pinyin", callback_data="pc_edit:pinyin"),
         Btn("✏️ Nghĩa", callback_data="pc_edit:meaning")],
        [Btn("💬 Ví dụ", callback_data="pc_edit:example"),
         Btn("📦 Đổi bộ", callback_data="pc_deck")],
    ])
    return "\n".join(lines), kb


async def render_preview(context, chat_id):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if not pc:
        return
    text, kb = _preview(conn, pc)
    msg_id = db.kv_get(conn, "pending_msg")
    if msg_id:
        try:
            await context.bot.edit_message_text(
                text, chat_id=chat_id, message_id=msg_id,
                reply_markup=kb, parse_mode="HTML")
            return
        except BadRequest:
            pass
    m = await context.bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
    db.kv_set(conn, "pending_msg", m.message_id)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    await q.answer()
    if not pc:
        await q.edit_message_text("Phiên tạo thẻ đã kết thúc.")
        return
    data = q.data
    if data == "pc_cancel":
        db.kv_del(conn, "pending_card")
        db.kv_del(conn, "pending_msg")
        await q.edit_message_text("❌ Đã hủy tạo thẻ.")
    elif data == "pc_save":
        row = await cards.create_card(
            conn, pc["hanzi"], deck_id=pc["deck_id"],
            pinyin_override=pc["pinyin"], meaning_override=pc["meaning"],
            example=pc["example"], image_file_id=pc["image_file_id"])
        db.kv_del(conn, "pending_card")
        db.kv_del(conn, "pending_msg")
        note = "" if row["audio_path"] else "\n⚠️ Chưa tạo được audio, sẽ thử lại khi ôn."
        await q.edit_message_text(
            f"✅ Đã lưu thẻ <b>{row['hanzi']}</b> ({row['pinyin']}){note}",
            parse_mode="HTML")
    elif data.startswith("pc_edit:"):
        field = data.split(":", 1)[1]
        db.kv_set(conn, "pending_input", {"action": "pc_field", "field": field})
        await context.bot.send_message(
            q.message.chat_id, f"Nhập {FIELD_LABEL[field]} mới:")
    elif data == "pc_deck":
        decks = conn.execute("SELECT id, name FROM decks ORDER BY id").fetchall()
        kb = Markup([[Btn(d["name"], callback_data=f"pc_deck_set:{d['id']}")] for d in decks])
        await context.bot.send_message(q.message.chat_id, "Chọn bộ thẻ:", reply_markup=kb)
    elif data.startswith("pc_deck_set:"):
        pc["deck_id"] = int(data.split(":")[1])
        db.kv_set(conn, "pending_card", pc)
        await q.message.delete()
        await render_preview(context, q.message.chat_id)


async def field_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    pc = db.kv_get(conn, "pending_card")
    if not pc:
        return
    pc[pending["field"]] = text
    db.kv_set(conn, "pending_card", pc)
    await render_preview(context, update.effective_chat.id)
```

- [ ] **Step 3: Nối vào `main.py` và `textrouter`**

Trong `app/bot/main.py` thêm import và handler (trong `build_app`, sau handler /start):
```python
from telegram.ext import CallbackQueryHandler, MessageHandler, filters
from app.bot import create_flow, textrouter
from app.bot.textrouter import register

register("pc_field", create_flow.field_input)
app.add_handler(CallbackQueryHandler(create_flow.on_callback, pattern=r"^pc_"))
app.add_handler(MessageHandler(owner_filter & filters.TEXT & ~filters.COMMAND, textrouter.on_text))
app.add_handler(MessageHandler(owner_filter & filters.PHOTO, textrouter.on_photo))
```
(`register(...)` đặt ở mức module của `main.py`, ngay sau các import.)

- [ ] **Step 4: Test thủ công**

Chạy bot local. Kịch bản: (1) gõ `学习` → preview có pinyin `xué xí` + nghĩa Anh; (2) bấm ✏️ Nghĩa → gõ nghĩa mới → preview cập nhật; (3) gửi 1 ảnh → preview hiện "Có ảnh"; (4) 💾 Lưu → "✅ Đã lưu"; (5) gõ lại `学习` → preview cảnh báo trùng; (6) ❌ Hủy hoạt động; (7) gõ `hello` không CJK → nhận gợi ý.

- [ ] **Step 5: Commit** — `git commit -am "feat: card creation flow with auto-lookup preview"`

---

