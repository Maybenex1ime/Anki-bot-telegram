import logging

from telegram import Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          MessageHandler, filters)

from app import config, db, lookup
from app.bot import (create_flow, misc, reminders, review_flow, textrouter,
                     voice_flow)
from app.bot.auth import owner_filter
from app.bot.textrouter import register

register("pc_field", create_flow.field_input)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def post_init(app):
    conn = db.connect()
    app.bot_data["conn"] = conn
    n = lookup.ensure_cedict(conn)
    if n:
        logging.info("Đã nạp CC-CEDICT: %d mục", n)
    reminders.schedule_jobs(app)


def build_app() -> Application:
    app = (Application.builder().token(config.BOT_TOKEN)
           .post_init(post_init).build())
    app.add_handler(CommandHandler("start", misc.cmd_start, filters=owner_filter))
    app.add_handler(CommandHandler("on", review_flow.cmd_review, filters=owner_filter))
    app.add_handler(CallbackQueryHandler(create_flow.on_callback, pattern=r"^pc_"))
    app.add_handler(CallbackQueryHandler(review_flow.on_callback, pattern=r"^rv_"))
    app.add_handler(CallbackQueryHandler(voice_flow.on_rec_callback, pattern=r"^vc_rec:"))
    app.add_handler(MessageHandler(owner_filter & filters.TEXT & ~filters.COMMAND, textrouter.on_text))
    app.add_handler(MessageHandler(owner_filter & filters.PHOTO, textrouter.on_photo))
    app.add_handler(MessageHandler(owner_filter & filters.VOICE, voice_flow.on_voice))
    return app


def main():
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
