import json
import unicodedata

from app import gemini, grading


def pinyin_key(pinyin):
    s = unicodedata.normalize("NFD", pinyin.lower())
    return "".join(c for c in s if c.isascii() and c.isalpha())


def _ban_set(correct_meaning):
    return {grading.normalize_meaning(v)
            for v in grading.meaning_variants(correct_meaning)} | \
           {grading.normalize_meaning(correct_meaning)}


def _pick_valid(cands, correct_meaning, need=3):
    out, seen, ban = [], set(), _ban_set(correct_meaning)
    for m in cands:
        nm = grading.normalize_meaning(m)
        if not nm or nm in seen or nm in ban:
            continue
        if any(nm in b or b in nm for b in ban):
            continue
        seen.add(nm)
        out.append(m)
        if len(out) == need:
            break
    return out


def _random_meanings(conn, exclude_id, limit=25):
    return [r["meaning"] for r in conn.execute(
        "SELECT meaning FROM cards WHERE id<>? AND meaning<>'' "
        "ORDER BY RANDOM() LIMIT ?", (exclude_id, limit))]


def _same_deck_meanings(conn, row, limit=25):
    return [r["meaning"] for r in conn.execute(
        "SELECT meaning FROM cards WHERE id<>? AND deck_id=? AND meaning<>'' "
        "ORDER BY RANDOM() LIMIT ?", (row["id"], row["deck_id"], limit))]


def _homophone_meanings(conn, row, limit=10):
    key = pinyin_key(row["pinyin"])
    if not key:
        return []
    out = [r["meaning"] for r in conn.execute(
        "SELECT pinyin, meaning FROM cards WHERE id<>? AND meaning<>''",
        (row["id"],)) if pinyin_key(r["pinyin"]) == key][:limit]
    if len(out) < limit:
        cur = conn.execute(
            "SELECT pinyin, meaning FROM dict_entries WHERE simplified<>?",
            (row["hanzi"],))
        for r in cur:
            if pinyin_key(r["pinyin"]) == key:
                out.append(r["meaning"])
                if len(out) >= limit:
                    break
    return out


async def get_options(conn, row, level):
    cached = conn.execute(
        "SELECT options_json FROM distractors WHERE card_id=? AND level=?",
        (row["id"], level)).fetchone()
    if cached:
        return json.loads(cached["options_json"])
    correct = row["meaning"]
    cands = []
    if level == "normal":
        g = await gemini.make_distractors(conn, row["hanzi"], correct, level)
        if g:
            cands += g
        cands += _same_deck_meanings(conn, row)
    elif level == "hard":
        homo = _homophone_meanings(conn, row)
        g = await gemini.make_distractors(conn, row["hanzi"], correct, level)
        # ưu tiên trộn: đồng âm trước, rồi đồng nghĩa giả
        cands += homo[:2] + (g or []) + homo[2:]
    cands += _random_meanings(conn, row["id"])
    opts = _pick_valid(cands, correct)
    if len(opts) < 3:
        return None
    conn.execute("INSERT OR REPLACE INTO distractors VALUES(?, ?, ?)",
                 (row["id"], level, json.dumps(opts, ensure_ascii=False)))
    conn.commit()
    return opts
