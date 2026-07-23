import json

from telegram.error import TelegramError

from app import config, db, gemini, grading, tts


def add_sentence(conn, hanzi, words=None, pinyin="", meaning="",
                 source="gemini", card_id=None):
    hanzi = hanzi.strip()
    norm = grading.normalize_hanzi(hanzi)
    if not norm:
        return None
    cur = conn.execute(   # OR IGNORE: câu trùng (UNIQUE norm) → rowcount 0
        "INSERT OR IGNORE INTO sentences(hanzi, norm, words_json, pinyin, "
        "meaning, source, card_id, created_at) VALUES(?,?,?,?,?,?,?,?)",
        (hanzi, norm,
         json.dumps(words, ensure_ascii=False) if words else "",
         pinyin, meaning, source, card_id, config.today_iso()))
    conn.commit()
    return cur.lastrowid if cur.rowcount else None


def ingest_examples(conn, raw, card_id):
    n = 0
    for part in raw.split("|"):
        if part.strip() and add_sentence(conn, part, source="example",
                                         card_id=card_id) is not None:
            n += 1
    return n


async def maybe_refill(conn):
    unused = conn.execute(
        "SELECT COUNT(*) c FROM sentences WHERE times_used=0").fetchone()["c"]
    if unused >= 10:
        return 0
    gen_total = conn.execute(
        "SELECT COUNT(*) c FROM sentences WHERE source='gemini'").fetchone()["c"]
    if gen_total >= int(db.get_setting(conn, "max_sentences")):
        return 0
    vocab = [r["hanzi"] for r in conn.execute("SELECT hanzi FROM cards")]
    if len(vocab) < 5:
        return 0
    items = await gemini.gen_sentences(conn, vocab)
    if not items:
        return 0
    n = 0
    for it in items:
        if add_sentence(conn, it["hanzi"], words=it["words"],
                        pinyin=it["pinyin"], meaning=it["meaning"]) is not None:
            n += 1
    return n


async def enrich_one(conn):
    row = conn.execute(
        "SELECT * FROM sentences WHERE words_json='' LIMIT 1").fetchone()
    if not row:
        return False
    data = await gemini.segment_translate(conn, row["hanzi"])
    if not data:
        return False
    conn.execute(
        "UPDATE sentences SET words_json=?, pinyin=COALESCE(NULLIF(pinyin,''),?), "
        "meaning=COALESCE(NULLIF(meaning,''),?) WHERE id=?",
        (json.dumps(data["words"], ensure_ascii=False),
         data["pinyin"], data["meaning"], row["id"]))
    conn.commit()
    return True


def pick(conn, need_words):
    where = "WHERE words_json<>''" if need_words else ""
    return conn.execute(
        f"SELECT * FROM sentences {where} "
        "ORDER BY times_used, RANDOM() LIMIT 1").fetchone()


def mark_used(conn, sid):
    conn.execute("UPDATE sentences SET times_used=times_used+1 WHERE id=?", (sid,))
    conn.commit()


async def send_audio(context, chat_id, srow):
    conn = context.bot_data["conn"]
    if srow["audio_file_id"]:
        try:
            return await context.bot.send_voice(chat_id, srow["audio_file_id"])
        except TelegramError:   # file_id hỏng — synth lại bên dưới
            pass
    out = config.MEDIA_DIR / f"sent_{srow['id']}.mp3"
    voice = db.get_setting(conn, "tts_voice")
    if not await tts.synthesize(srow["hanzi"], voice, out):
        return None
    with open(out, "rb") as f:
        m = await context.bot.send_voice(chat_id, f)
    conn.execute("UPDATE sentences SET audio_file_id=?, audio_path='' WHERE id=?",
                 (m.voice.file_id, srow["id"]))
    conn.commit()
    try:
        out.unlink()            # chính sách volume: xóa mp3 sau khi có file_id
    except OSError:
        pass
    return m
