import logging

from telegram import Update
from telegram.ext import Application, CommandHandler

from app import config, db, lookup
from app.bot import misc
from app.bot.auth import owner_filter

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def post_init(app):
    conn = db.connect()
    app.bot_data["conn"] = conn
    n = lookup.ensure_cedict(conn)
    if n:
        logging.info("Đã nạp CC-CEDICT: %d mục", n)


def build_app() -> Application:
    app = (Application.builder().token(config.BOT_TOKEN)
           .post_init(post_init).build())
    app.add_handler(CommandHandler("start", misc.cmd_start, filters=owner_filter))
    return app


def main():
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
