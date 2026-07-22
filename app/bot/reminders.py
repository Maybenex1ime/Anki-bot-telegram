import logging
from datetime import time as dtime

from telegram import InlineKeyboardButton as Btn
from telegram import InlineKeyboardMarkup as Markup

from app import cards, config, db, stats

START_KB = Markup([[Btn("▶️ Ôn ngay", callback_data="rv_start")]])


def _parse_hhmm(s):
    h, m = s.strip().split(":")
    return dtime(int(h), int(m), tzinfo=config.TZ)


def schedule_jobs(app):
    conn = app.bot_data["conn"]
    for job in app.job_queue.jobs():
        if job.name and job.name.startswith("rem:"):
            job.schedule_removal()
    for t in db.get_setting(conn, "reminder_times").split(","):
        t = t.strip()
        if t:
            app.job_queue.run_daily(reminder_job, _parse_hhmm(t), name=f"rem:{t}")
    ev = db.get_setting(conn, "evening_nudge").strip()
    if ev and ev.lower() != "off":
        app.job_queue.run_daily(evening_job, _parse_hhmm(ev), name="rem:evening")
    logging.info("Đã đặt lịch nhắc: %s / nudge: %s",
                 db.get_setting(conn, "reminder_times"), ev)


async def reminder_job(context):
    conn = context.application.bot_data["conn"]
    queue = cards.build_queue(conn, config.today_iso())
    if not queue:
        return  # đã ôn hết / không có gì -> im lặng (spec §6)
    n_new = sum(1 for cid in queue
                if (r := cards.get_card(conn, cid)) and cards.is_new(r))
    await context.bot.send_message(
        config.OWNER_ID,
        f"📚 Bạn có <b>{len(queue)}</b> thẻ đến hạn ({n_new} thẻ mới).",
        reply_markup=START_KB, parse_mode="HTML")


async def evening_job(context):
    conn = context.application.bot_data["conn"]
    if stats.reviews_today(conn, config.today_iso()) > 0:
        return
    queue = cards.build_queue(conn, config.today_iso())
    if not queue:
        return
    n = stats.streak(conn, config.today())
    flame = f"🔥 Chuỗi {n} ngày của bạn sắp mất! " if n > 0 else ""
    await context.bot.send_message(
        config.OWNER_ID,
        f"🌙 {flame}Hôm nay bạn chưa ôn — còn {len(queue)} thẻ chờ.",
        reply_markup=START_KB)
