import json

from app import config, gemini, grading


def pinyin_key(pinyin):
    return config.PACK["phonetic_key"](pinyin)


def _ban_set(correct_meaning):
    ban = {grading.normalize_meaning(v)
           for v in grading.meaning_variants(correct_meaning)} | \
          {grading.normalize_meaning(correct_meaning)}
    return {b for b in ban if b}


def _pick_valid(cands, correct_meaning, need=3):
    out, seen, ban = [], set(), _ban_set(correct_meaning)
    for m in cands:
        nm = grading.normalize_meaning(m)
        if not nm or nm in seen:
            continue
        if any(nm in b or b in nm for b in ban):
            continue
        seen.add(nm)
        out.append(m)
        if len(out) == need:
            break
    return out


def _other_meanings(conn, exclude_id, deck_id=None, limit=25):
    deck_clause = "AND deck_id=? " if deck_id is not None else ""
    args = (exclude_id,) + ((deck_id,) if deck_id is not None else ()) + (limit,)
    return [r["meaning"] for r in conn.execute(
        f"SELECT meaning FROM cards WHERE id<>? {deck_clause}AND meaning<>'' "
        "ORDER BY RANDOM() LIMIT ?", args)]


def _homophone_meanings(conn, row, limit=10):
    key = pinyin_key(row["pinyin"])
    if not key:
        return []
    out = [r["meaning"] for r in conn.execute(
        "SELECT pinyin, meaning FROM cards WHERE id<>? AND meaning<>''",
        (row["id"],)) if pinyin_key(r["pinyin"]) == key][:limit]
    if len(out) < limit:
        syllables = row["pinyin"].split()
        prefix = pinyin_key(syllables[0]) if syllables else ""
        if prefix:
            cur = conn.execute(
                "SELECT pinyin, meaning FROM dict_entries "
                "WHERE simplified<>? AND pinyin LIKE ?",
                (row["hanzi"], prefix + "%"))
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
        return json.loads(cached["options_json"]) or None
    correct = row["meaning"]
    cands = []
    if level == "normal":
        g = await gemini.make_distractors(conn, row["hanzi"], correct, level)
        if g:
            cands += g
        cands += _other_meanings(conn, row["id"], deck_id=row["deck_id"])
    elif level == "hard":
        homo = _homophone_meanings(conn, row)
        g = await gemini.make_distractors(conn, row["hanzi"], correct, level)
        # ưu tiên trộn: đồng âm trước, rồi đồng nghĩa giả
        cands += homo[:2] + (g or []) + homo[2:]
    opts = _pick_valid(cands, correct)
    if len(opts) < 3:   # chỉ quét toàn kho khi các nguồn rẻ chưa đủ
        opts = _pick_valid(cands + _other_meanings(conn, row["id"]), correct)
    stored = json.dumps(opts, ensure_ascii=False) if len(opts) == 3 else "[]"
    conn.execute("INSERT OR REPLACE INTO distractors VALUES(?, ?, ?)",
                 (row["id"], level, stored))
    conn.commit()
    return opts if len(opts) == 3 else None
