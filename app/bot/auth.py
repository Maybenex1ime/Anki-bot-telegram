from functools import wraps

from telegram.ext import filters

from app import config

owner_filter = filters.User(user_id=config.OWNER_ID)


def owner_only_callback(fn):
    @wraps(fn)
    async def wrapper(update, context):
        if not update.effective_user or update.effective_user.id != config.OWNER_ID:
            if update.callback_query:
                await update.callback_query.answer()
            return
        return await fn(update, context)
    return wrapper
