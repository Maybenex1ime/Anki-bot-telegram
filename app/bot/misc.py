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
