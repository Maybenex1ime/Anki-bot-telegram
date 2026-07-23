from app.csv_import import parse_csv


def test_parse_full_and_partial_rows():
    text = "hán,pinyin,nghĩa,ví_dụ\n学习,,to learn,我在学习\n你好,nǐ hǎo,,\n"
    r = parse_csv(text)
    assert not r.errors
    assert [row.hanzi for row in r.rows] == ["学习", "你好"]
    assert r.rows[0].meaning == "to learn"
    assert r.rows[0].example == "我在学习"
    assert r.rows[1].pinyin == "nǐ hǎo"


def test_missing_hanzi_cell_is_error_with_line_number():
    text = "hán,pinyin,nghĩa,ví_dụ\n,,x,\n好,,,\n"
    r = parse_csv(text)
    assert len(r.rows) == 1
    assert r.errors == [(2, "thiếu chữ Hán")]


def test_header_aliases_and_bom():
    text = "﻿hanzi,meaning\n学,to study\n"
    r = parse_csv(text)
    assert r.rows[0].hanzi == "学"
    assert r.rows[0].meaning == "to study"


def test_missing_hanzi_column():
    r = parse_csv("pinyin,nghĩa\nxue,to learn\n")
    assert r.rows == []
    assert r.errors == [(1, "thiếu cột 'hán' trong header")]


def test_blank_lines_skipped():
    r = parse_csv("hán\n学\n\n习\n")
    assert [row.hanzi for row in r.rows] == ["学", "习"]
    assert not r.errors


def test_extra_examples_column():
    text = "hán,nghĩa,ví_dụ,ví_dụ_thêm\n学习,to study,我在学习,我们一起学习吧|他学习很努力\n"
    r = parse_csv(text)
    assert r.rows[0].extra_examples == "我们一起学习吧|他学习很努力"
    r2 = parse_csv("hán\n学\n")
    assert r2.rows[0].extra_examples == ""
