from datetime import timedelta


def bump_review(conn, day_iso, was_new):
    conn.execute(
        "INSERT INTO daily_log(day, reviews, new_introduced) VALUES(?, 1, ?) "
        "ON CONFLICT(day) DO UPDATE SET reviews=reviews+1, "
        "new_introduced=new_introduced+excluded.new_introduced",
        (day_iso, 1 if was_new else 0))
    conn.commit()


def reviews_today(conn, day_iso):
    row = conn.execute("SELECT reviews FROM daily_log WHERE day=?", (day_iso,)).fetchone()
    return row["reviews"] if row else 0


def new_used_today(conn, day_iso):
    row = conn.execute("SELECT new_introduced FROM daily_log WHERE day=?", (day_iso,)).fetchone()
    return row["new_introduced"] if row else 0


def streak(conn, today):
    days = {r["day"] for r in conn.execute("SELECT day FROM daily_log WHERE reviews>0")}
    d = today
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def overview(conn, today_iso):
    from datetime import date
    total = conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
    due = conn.execute(
        "SELECT COUNT(*) c FROM cards WHERE due_date<=? AND NOT(repetitions=0 AND lapses=0)",
        (today_iso,)).fetchone()["c"]
    new_waiting = conn.execute(
        "SELECT COUNT(*) c FROM cards WHERE repetitions=0 AND lapses=0 AND due_date<=?",
        (today_iso,)).fetchone()["c"]
    agg = conn.execute("SELECT COALESCE(SUM(repetitions),0) r, COALESCE(SUM(lapses),0) l FROM cards").fetchone()
    return {
        "total": total, "due": due, "new_waiting": new_waiting,
        "streak": streak(conn, date.fromisoformat(today_iso)),
        "total_reviews": agg["r"], "total_lapses": agg["l"],
    }
