### Task 16: CSV upload (`app/bot/csv_flow.py`)

**Files:** Create `app/bot/csv_flow.py`; Modify `app/bot/main.py`

**Interfaces:**
- Consumes: `csv_import.parse_csv`, `cards.create_card/exists_hanzi`, `db.kv_*`
- Produces: lệnh `/csv` (hướng dẫn); document handler nhận file `.csv` → hỏi bộ đích (callback `cs_deck:<id>`) → nhập. kv `pending_csv` = nội dung text file. Trùng chữ Hán → bỏ qua, đếm. Cứ 10 thẻ cập nhật message tiến độ.

- [ ] **Step 1: Viết `app/bot/csv_flow.py`**

```python
from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup
from telegram.error import BadRequest

from app import cards, db
from app.bot.auth import owner_only_callback

GUIDE = (
    "📄 <b>Nhập thẻ từ CSV</b>\n\n"
    "Soạn file .csv (UTF-8) với header:\n"
    "<code>hán,pinyin,nghĩa,ví_dụ</code>\n\n"
    "Chỉ cột <b>hán</b> bắt buộc — pinyin/nghĩa bỏ trống sẽ được tra tự động.\n"
    "VD:\n<code>hán,pinyin,nghĩa,ví_dụ\n学习,,,我在学习中文\n你好,nǐ hǎo,hello; hi,</code>\n\n"
    "Rồi gửi file vào đây."
)


async def cmd_csv(update, context):
    await update.message.reply_html(GUIDE)


async def on_document(update, context):
    conn = context.bot_data["conn"]
    doc = update.message.document
    if not (doc.file_name or "").lower().endswith(".csv"):
        return
    f = await doc.get_file()
    data = await f.download_as_bytearray()
    try:
        text = bytes(data).decode("utf-8-sig")
    except UnicodeDecodeError:
        await update.message.reply_text("⚠️ File không phải UTF-8. Lưu lại với encoding UTF-8 nhé.")
        return
    db.kv_set(conn, "pending_csv", text)
    decks = conn.execute("SELECT id, name FROM decks ORDER BY id").fetchall()
    kb = Markup([[Btn(d["name"], callback_data=f"cs_deck:{d['id']}")] for d in decks])
    await update.message.reply_text("Nhập các thẻ này vào bộ nào?", reply_markup=kb)


@owner_only_callback
async def on_callback(update, context):
    q = update.callback_query
    conn = context.bot_data["conn"]
    await q.answer()
    deck_id = int(q.data.split(":")[1])
    text = db.kv_get(conn, "pending_csv")
    if not text:
        await q.edit_message_text("Không còn file chờ nhập. Gửi lại file .csv nhé.")
        return
    db.kv_del(conn, "pending_csv")
    from app.csv_import import parse_csv
    result = parse_csv(text)
    total = len(result.rows)
    await q.edit_message_text(f"⏳ Đang nhập {total} thẻ...")
    created = skipped = 0
    for i, r in enumerate(result.rows, 1):
        if cards.exists_hanzi(conn, r.hanzi):
            skipped += 1
        else:
            await cards.create_card(conn, r.hanzi, deck_id=deck_id,
                                    pinyin_override=r.pinyin,
                                    meaning_override=r.meaning, example=r.example)
            created += 1
        if i % 10 == 0:
            try:
                await q.edit_message_text(f"⏳ Đang nhập... {i}/{total}")
            except BadRequest:
                pass
    lines = [f"✅ Nhập xong: {created} thẻ mới, {skipped} trùng (bỏ qua)."]
    if result.errors:
        lines.append("⚠️ Dòng lỗi (bỏ qua):")
        lines += [f"  • dòng {ln}: {reason}" for ln, reason in result.errors[:15]]
    await q.edit_message_text("\n".join(lines))
```

- [ ] **Step 2: Nối vào `main.py`**

```python
from app.bot import csv_flow
app.add_handler(CommandHandler("csv", csv_flow.cmd_csv, filters=owner_filter))
app.add_handler(CallbackQueryHandler(csv_flow.on_callback, pattern=r"^cs_deck:"))
app.add_handler(MessageHandler(
    owner_filter & filters.Document.FileExtension("csv"), csv_flow.on_document))
```

- [ ] **Step 3: Test thủ công** — `/csv` hiện hướng dẫn; gửi file 15 dòng (1 dòng thiếu hán, 1 dòng trùng thẻ có sẵn) → chọn bộ → tiến độ chạy → báo cáo đúng: N mới, 1 trùng, 1 dòng lỗi kèm số dòng; audio các thẻ mới nghe được khi ôn.

- [ ] **Step 4: Commit** — `git commit -am "feat: bulk CSV import with deck picker and progress"`

---

