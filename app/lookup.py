import gzip
import re
import urllib.request

from pypinyin import Style, pinyin

from app import config

_CEDICT_LINE = re.compile(r"^(\S+) (\S+) \[([^\]]+)\] /(.+)/\s*$")


def gen_pinyin(hanzi: str) -> str:
    return " ".join(p[0] for p in pinyin(hanzi, style=Style.TONE))


def parse_cedict_line(line):
    if line.startswith("#"):
        return None
    m = _CEDICT_LINE.match(line.strip())
    if not m:
        return None
    trad, simp, pin, meaning = m.groups()
    return simp, trad, pin, "; ".join(meaning.split("/"))


def ensure_cedict(conn) -> int:
    if conn.execute("SELECT COUNT(*) c FROM dict_entries").fetchone()["c"] > 0:
        return 0
    path = config.DATA_DIR / "cedict.txt.gz"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(config.CEDICT_URL, path)
    rows = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            parsed = parse_cedict_line(line)
            if parsed:
                rows.append(parsed)
    conn.executemany("INSERT INTO dict_entries VALUES(?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def lookup_meaning(conn, hanzi: str) -> str:
    rows = conn.execute(
        "SELECT meaning FROM dict_entries WHERE simplified=? OR traditional=? LIMIT 3",
        (hanzi, hanzi)).fetchall()
    return " | ".join(r["meaning"] for r in rows)
