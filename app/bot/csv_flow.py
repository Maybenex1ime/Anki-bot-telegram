from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup
from telegram.error import BadRequest

from app import cards, db
from app.bot.auth import owner_only_callback

GUIDE = (
    "📄 <b>Nhập thẻ từ CSV</b>\n\n"
    "Soạn file .csv (UTF-8) với header:\n"
    "<code>hán,pinyin,nghĩa,ví_dụ,ví_dụ_thêm</code>\n\n"
    "Chỉ cột <b>hán</b> bắt buộc — pinyin/nghĩa bỏ trống sẽ được tra tự động.\n"
    "Cột <b>ví_dụ_thêm</b>: nhiều câu cho kho luyện tập, ngăn cách bằng dấu |.\n"
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
    from app import sentences
    result = parse_csv(text)
    total = len(result.rows)
    await q.edit_message_text(f"⏳ Đang nhập {total} thẻ...")
    created = skipped = 0
    sent_added = 0
    for i, r in enumerate(result.rows, 1):
        if cards.exists_hanzi(conn, r.hanzi):
            skipped += 1
        else:
            await cards.create_card(conn, r.hanzi, deck_id=deck_id,
                                    pinyin_override=r.pinyin,
                                    meaning_override=r.meaning, example=r.example)
            created += 1
        crow = conn.execute("SELECT id FROM cards WHERE hanzi=? LIMIT 1", (r.hanzi,)).fetchone()
        card_id = crow["id"] if crow else None
        if r.example:
            sent_added += sentences.ingest_examples(conn, r.example, card_id)
        if r.extra_examples:
            sent_added += sentences.ingest_examples(conn, r.extra_examples, card_id)
        if i % 10 == 0:
            try:
                await q.edit_message_text(f"⏳ Đang nhập... {i}/{total}")
            except BadRequest:
                pass
    lines = [f"✅ Nhập xong: {created} thẻ mới, {skipped} trùng (bỏ qua)."]
    if sent_added > 0:
        lines.append(f"📚 Thêm {sent_added} câu vào kho luyện tập.")
    if result.errors:
        lines.append("⚠️ Dòng lỗi (bỏ qua):")
        lines += [f"  • dòng {ln}: {reason}" for ln, reason in result.errors[:15]]
    await q.edit_message_text("\n".join(lines))
