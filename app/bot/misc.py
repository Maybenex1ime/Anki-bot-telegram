from app import config, stats

HELP = (
    "🀄 <b>Bot học tiếng Trung SRS</b>\n\n"
    "• Gõ chữ Hán bất kỳ (VD: 学习) → tạo thẻ mới\n"
    "• /on — ôn thẻ đến hạn ngay\n"
    "• /csv — nhập hàng loạt từ file CSV\n"
    "• /bo — quản lý bộ thẻ\n"
    "• /tim &lt;từ&gt; — tìm thẻ\n"
    "• /thongke — thống kê & streak\n"
    "• /settings — giờ nhắc, giới hạn thẻ mới, giọng đọc\n"
    "• /backup — nhận file dữ liệu"
)


async def cmd_start(update, context):
    await update.message.reply_html(HELP)


async def cmd_stats(update, context):
    conn = context.bot_data["conn"]
    o = stats.overview(conn, config.today_iso())
    total_r = o["total_reviews"]
    rate = 100 * (1 - o["total_lapses"] / total_r) if total_r else 100.0
    await update.message.reply_html(
        "📊 <b>Thống kê</b>\n"
        f"🗂 Tổng số thẻ: {o['total']}\n"
        f"📚 Đến hạn hôm nay: {o['due']} (+{o['new_waiting']} thẻ mới chờ)\n"
        f"🔥 Chuỗi: {o['streak']} ngày\n"
        f"✅ Tỉ lệ nhớ: {rate:.0f}% ({total_r} lượt ôn, {o['total_lapses']} lần quên)")


async def cmd_backup(update, context):
    with open(config.DB_PATH, "rb") as f:
        await update.message.reply_document(
            f, filename=f"reminder-backup-{config.today_iso()}.db",
            caption="💾 Bản sao lưu dữ liệu (SQLite). Cất giữ cẩn thận nhé.")
