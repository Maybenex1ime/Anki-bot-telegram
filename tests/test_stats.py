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
