from app import config, db, lookup, srs, stats, tts


async def create_card(conn, hanzi, deck_id=1, pinyin_override="",
                      meaning_override="", example="", image_file_id=""):
    pin = pinyin_override or lookup.gen_pinyin(hanzi)
    meaning = meaning_override if meaning_override else lookup.lookup_meaning(conn, hanzi)
    today = config.today_iso()
    cur = conn.execute(
        "INSERT INTO cards(deck_id,hanzi,pinyin,meaning,example,image_file_id,"
        "created_at,due_date) VALUES(?,?,?,?,?,?,?,?)",
        (deck_id, hanzi, pin, meaning, example, image_file_id, today, today))
    cid = cur.lastrowid
    conn.commit()
    await retry_audio(conn, cid)
    return get_card(conn, cid)


async def retry_audio(conn, cid) -> bool:
    row = get_card(conn, cid)
    if not row or row["audio_path"]:
        return bool(row and row["audio_path"])
    out = config.MEDIA_DIR / f"{cid}.mp3"
    voice = db.get_setting(conn, "tts_voice")
    if await tts.synthesize(row["hanzi"], voice, out):
        conn.execute("UPDATE cards SET audio_path=? WHERE id=?", (str(out), cid))
        conn.commit()
        return True
    return False


def get_card(conn, cid):
    return conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()


def is_new(row) -> bool:
    return row["repetitions"] == 0 and row["lapses"] == 0


def exists_hanzi(conn, hanzi) -> bool:
    return conn.execute("SELECT 1 FROM cards WHERE hanzi=? LIMIT 1", (hanzi,)).fetchone() is not None


def build_queue(conn, today_iso):
    reviews = [r["id"] for r in conn.execute(
        "SELECT id FROM cards WHERE due_date<=? AND NOT(repetitions=0 AND lapses=0) "
        "ORDER BY due_date, id", (today_iso,))]
    limit = max(0, int(db.get_setting(conn, "new_per_day")) - stats.new_used_today(conn, today_iso))
    news = [r["id"] for r in conn.execute(
        "SELECT id FROM cards WHERE repetitions=0 AND lapses=0 AND due_date<=? "
        "ORDER BY id LIMIT ?", (today_iso, limit))]
    return reviews + news


def apply_rating(conn, cid, rating, today):
    row = get_card(conn, cid)
    state = srs.SrsState(row["interval"], row["ease"], row["repetitions"], row["lapses"])
    was_new = is_new(row)
    new_state, due = srs.review(state, rating, today)
    conn.execute(
        "UPDATE cards SET interval=?, ease=?, repetitions=?, lapses=?, due_date=? WHERE id=?",
        (new_state.interval, new_state.ease, new_state.repetitions,
         new_state.lapses, due.isoformat(), cid))
    conn.commit()
    stats.bump_review(conn, today.isoformat(), was_new)
