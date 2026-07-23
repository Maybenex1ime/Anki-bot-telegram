# app/bot/quiz_flow.py (stub — Task 8 thay bằng bản đầy đủ)
async def show_question(context):
    from app.bot import review_flow
    conn = context.bot_data["conn"]
    s = review_flow.db.kv_get(conn, "session")
    await review_flow._edit_or_send(context, s, "⚠️ Chế độ này đang được xây.", None)
