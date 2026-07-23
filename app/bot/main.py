import logging

from telegram import Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          MessageHandler, filters)

from app import config, db, lookup
from app.bot import (create_flow, csv_flow, decks_flow, manage_flow, misc,
                     practice_flow, quiz_flow, reminders, review_flow,
                     settings_flow, textrouter, voice_flow)
from app.bot.auth import owner_filter
from app.bot.textrouter import register

register("pc_field", create_flow.field_input)
register("deck_new", decks_flow.deck_new_input)
register("deck_rename", decks_flow.deck_rename_input)
register("card_edit", manage_flow.card_edit_input)
register("set_times", settings_flow.times_input)
register("set_nudge", settings_flow.nudge_input)
register("set_newlimit", settings_flow.newlimit_input)
register("quiz_typed", quiz_flow.typed_input)

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
    app.add_handler(CommandHandler("bo", decks_flow.cmd_decks, filters=owner_filter))
    app.add_handler(CommandHandler("tim", manage_flow.cmd_search, filters=owner_filter))
    app.add_handler(CommandHandler("settings", settings_flow.cmd_settings, filters=owner_filter))
    app.add_handler(CommandHandler("csv", csv_flow.cmd_csv, filters=owner_filter))
    app.add_handler(CommandHandler("thongke", misc.cmd_stats, filters=owner_filter))
    app.add_handler(CommandHandler("backup", misc.cmd_backup, filters=owner_filter))
    app.add_handler(CommandHandler("luyen", practice_flow.cmd_practice, filters=owner_filter))
    app.add_handler(CallbackQueryHandler(practice_flow.on_callback, pattern=r"^pr_"))
    app.add_handler(CallbackQueryHandler(create_flow.on_callback, pattern=r"^pc_"))
    app.add_handler(CallbackQueryHandler(review_flow.on_callback, pattern=r"^rv_"))
    app.add_handler(CallbackQueryHandler(quiz_flow.on_callback, pattern=r"^qz_"))
    app.add_handler(CallbackQueryHandler(voice_flow.on_rec_callback, pattern=r"^vc_rec:"))
    app.add_handler(CallbackQueryHandler(decks_flow.on_callback, pattern=r"^dk_"))
    app.add_handler(CallbackQueryHandler(manage_flow.on_callback, pattern=r"^cd_"))
    app.add_handler(CallbackQueryHandler(settings_flow.on_callback, pattern=r"^st_"))
    app.add_handler(CallbackQueryHandler(csv_flow.on_callback, pattern=r"^cs_deck:"))
    app.add_handler(MessageHandler(owner_filter & filters.TEXT & ~filters.COMMAND, textrouter.on_text))
    app.add_handler(MessageHandler(owner_filter & filters.PHOTO, textrouter.on_photo))
    app.add_handler(MessageHandler(owner_filter & filters.VOICE, voice_flow.on_voice))
    app.add_handler(MessageHandler(
        owner_filter & filters.Document.FileExtension("csv"), csv_flow.on_document))
    return app


def main():
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
