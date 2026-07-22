from datetime import date

from app import db, stats


def make(tmp_path):
    return db.connect(tmp_path / "t.db")


def test_bump_and_counts(tmp_path):
    conn = make(tmp_path)
    stats.bump_review(conn, "2026-07-22", was_new=True)
    stats.bump_review(conn, "2026-07-22", was_new=False)
    assert stats.reviews_today(conn, "2026-07-22") == 2
    assert stats.new_used_today(conn, "2026-07-22") == 1
    assert stats.reviews_today(conn, "2026-07-23") == 0


def test_streak_counts_consecutive_days(tmp_path):
    conn = make(tmp_path)
    for d in ["2026-07-19", "2026-07-20", "2026-07-21"]:
        stats.bump_review(conn, d, was_new=False)
    # hôm nay 22 chưa ôn -> chuỗi kết thúc hôm qua vẫn là 3
    assert stats.streak(conn, date(2026, 7, 22)) == 3
    stats.bump_review(conn, "2026-07-22", was_new=False)
    assert stats.streak(conn, date(2026, 7, 22)) == 4


def test_streak_broken(tmp_path):
    conn = make(tmp_path)
    stats.bump_review(conn, "2026-07-15", was_new=False)
    assert stats.streak(conn, date(2026, 7, 22)) == 0


def test_total_reviews_counts_reviews_after_again(tmp_path):
    # A card reviewed then rated AGAIN resets cards.repetitions to 0, but the
    # reviews still happened — total_reviews (from daily_log) must keep counting.
    from app import cards
    conn = make(tmp_path)
    cur = conn.execute(
        "INSERT INTO cards(deck_id,hanzi,pinyin,created_at,due_date) "
        "VALUES(1,'好','hǎo','2026-07-22','2026-07-22')")
    conn.commit()
    cid = cur.lastrowid
    today = date(2026, 7, 22)
    cards.apply_rating(conn, cid, 3, today)  # Tốt -> repetitions=1
    cards.apply_rating(conn, cid, 1, today)  # Lại (AGAIN) -> repetitions back to 0
    ov = stats.overview(conn, today.isoformat())
    assert ov["total_reviews"] == 2  # both reviews counted despite reset
    assert conn.execute("SELECT repetitions FROM cards WHERE id=?", (cid,)).fetchone()["repetitions"] == 0
