from app import db


def test_connect_creates_schema_and_defaults(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"decks", "cards", "settings", "daily_log", "dict_entries", "kv"} <= tables
    assert conn.execute("SELECT name FROM decks WHERE id=1").fetchone()["name"] == "Mặc định"
    assert db.get_setting(conn, "new_per_day") == "20"


def test_settings_roundtrip(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.set_setting(conn, "new_per_day", "5")
    assert db.get_setting(conn, "new_per_day") == "5"


def test_kv_roundtrip(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    assert db.kv_get(conn, "x") is None
    db.kv_set(conn, "x", {"a": [1, 2]})
    assert db.kv_get(conn, "x") == {"a": [1, 2]}
    db.kv_del(conn, "x")
    assert db.kv_get(conn, "x", "gone") == "gone"
