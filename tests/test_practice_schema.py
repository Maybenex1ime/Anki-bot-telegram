from app import db, stats


def test_new_tables_and_settings(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sentences", "distractors", "practice_log"} <= tables
    assert db.get_setting(conn, "quiz_fast_sec") == "5"
    assert db.get_setting(conn, "quiz_slow_sec") == "15"
    assert db.get_setting(conn, "gemini_model") == "gemini-2.5-flash"
    assert db.get_setting(conn, "max_sentences") == "3000"
    assert db.get_setting(conn, "gemini_api_key") == ""
    assert db.get_setting(conn, "review_mode") == ""


def test_bump_practice_and_summary(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    stats.bump_practice(conn, "2026-07-23", "mc", True)
    stats.bump_practice(conn, "2026-07-23", "mc", False)
    stats.bump_practice(conn, "2026-07-23", "dict", True)
    stats.bump_practice(conn, "2026-07-20", "mc", True)
    s = stats.practice_summary(conn, "2026-07-21")
    assert s == {"mc": (2, 1), "dict": (1, 1)}
