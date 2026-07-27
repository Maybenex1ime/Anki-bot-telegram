import urllib.request

from app import config, langpack


def gen_pinyin(text: str) -> str:
    return config.PACK["romanize"](text)


def parse_cedict_line(line):
    # Giữ cho test_lookup — là parser dòng CC-CEDICT (zh). Ủy cho langpack regex.
    if line.startswith("#"):
        return None
    m = langpack._CEDICT_LINE.match(line.strip())
    if not m:
        return None
    trad, simp, pin, meaning = m.groups()
    return simp, trad, pin, "; ".join(meaning.split("/"))


def ensure_cedict(conn) -> int:
    if conn.execute("SELECT COUNT(*) c FROM dict_entries").fetchone()["c"] > 0:
        return 0
    pack = config.PACK
    path = config.DATA_DIR / pack["dict_file"]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(pack["dict_url"], path)
    rows = pack["parse_dict"](path)
    conn.executemany("INSERT INTO dict_entries VALUES(?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def lookup_meaning(conn, hanzi: str) -> str:
    rows = conn.execute(
        "SELECT meaning FROM dict_entries WHERE simplified=? OR traditional=? LIMIT 3",
        (hanzi, hanzi)).fetchall()
    return " | ".join(r["meaning"] for r in rows)
