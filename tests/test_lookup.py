from app import db, lookup


def test_gen_pinyin_with_tones():
    assert lookup.gen_pinyin("学习") == "xué xí"
    assert lookup.gen_pinyin("你好") == "nǐ hǎo"


def test_parse_cedict_line():
    line = "學習 学习 [xue2 xi2] /to learn/to study/"
    assert lookup.parse_cedict_line(line) == (
        "学习", "學習", "xue2 xi2", "to learn; to study")


def test_parse_cedict_skips_comments_and_garbage():
    assert lookup.parse_cedict_line("# CC-CEDICT") is None
    assert lookup.parse_cedict_line("not a dict line") is None


def test_lookup_meaning_by_simplified_and_traditional(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO dict_entries VALUES(?,?,?,?)",
                 ("学习", "學習", "xue2 xi2", "to learn; to study"))
    conn.commit()
    assert lookup.lookup_meaning(conn, "学习") == "to learn; to study"
    assert lookup.lookup_meaning(conn, "學習") == "to learn; to study"
    assert lookup.lookup_meaning(conn, "不存在的词") == ""
