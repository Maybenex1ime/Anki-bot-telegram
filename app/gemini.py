import json
import os

import httpx

from app import config, db

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _key(conn):
    return db.get_setting(conn, "gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")


def available(conn):
    return bool(_key(conn))


async def ask_json(conn, prompt):
    key = _key(conn)
    if not key:
        return None
    model = db.get_setting(conn, "gemini_model")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}}
    for _ in range(2):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(API_URL.format(model=model),
                                      params={"key": key}, json=body)
            if r.status_code != 200:
                continue
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception:
            continue
    return None


async def make_distractors(conn, hanzi, meaning, level):
    lang = config.PACK["gemini_name"]
    kind = (f"an English meaning in the same topic but WRONG"
            if level == "normal"
            else "an English meaning VERY CLOSE to the correct one but WRONG (near-synonym trap)")
    data = await ask_json(conn, (
        f"{lang} word: {hanzi}\nCorrect English meaning: {meaning}\n"
        f"Generate exactly 3 distractors, each {kind}, short dictionary style.\n"
        'Return JSON: {"options": ["...", "...", "..."]}'))
    if not isinstance(data, dict) or not isinstance(data.get("options"), list):
        return None
    opts = [str(o).strip()[:80] for o in data["options"] if str(o).strip()][:3]
    return opts if len(opts) == 3 else None


async def judge_meaning(conn, hanzi, meaning, answer):
    lang = config.PACK["gemini_name"]
    data = await ask_json(conn, (
        f'{lang} word: {hanzi}. Correct English meaning: "{meaning}". '
        f'Learner answered: "{answer}".\n'
        "Grade verdict: correct (right or equivalent), partial, wrong.\n"
        'Return JSON: {"verdict": "...", "note": "one short note in Vietnamese"}'))
    if not isinstance(data, dict) or data.get("verdict") not in ("correct", "partial", "wrong"):
        return None
    return {"verdict": data["verdict"], "note": str(data.get("note", ""))[:200]}


async def gen_sentences(conn, vocab, n=10):
    lang = config.PACK["gemini_name"]
    fw = config.PACK["function_words"]
    data = await ask_json(conn, (
        f"Generate {n} short {lang} sentences (4-10 words), using ONLY the words below "
        f"plus basic function words ({fw}):\n"
        + "、".join(vocab[:300]) + "\n"
        'Return JSON: {"sentences": [{"hanzi": "...", "words": ["tokenized"], '
        '"pinyin": "romanization", "meaning": "English translation"}]}'))
    if not isinstance(data, dict) or not isinstance(data.get("sentences"), list):
        return None
    out = []
    for it in data["sentences"]:
        if (isinstance(it, dict) and str(it.get("hanzi", "")).strip()
                and isinstance(it.get("words"), list) and it["words"]):
            out.append({"hanzi": str(it["hanzi"]).strip()[:100],
                        "words": [str(w)[:20] for w in it["words"]][:20],
                        "pinyin": str(it.get("pinyin", ""))[:200],
                        "meaning": str(it.get("meaning", ""))[:200]})
    return out or None


async def segment_translate(conn, hanzi):
    lang = config.PACK["gemini_name"]
    data = await ask_json(conn, (
        f"{lang} sentence: {hanzi}\nTokenize into words and translate to English.\n"
        'Return JSON: {"words": ["tokenized"], "pinyin": "romanization", "meaning": "..."}'))
    if not isinstance(data, dict) or not isinstance(data.get("words"), list) or not data["words"]:
        return None
    return {"words": [str(w)[:20] for w in data["words"]][:20],
            "pinyin": str(data.get("pinyin", ""))[:200],
            "meaning": str(data.get("meaning", ""))[:200]}


async def judge_word_order(conn, original, attempt, meaning):
    lang = config.PACK["gemini_name"]
    data = await ask_json(conn, (
        f"Original sentence: {original}\nMeaning: {meaning}\nLearner arranged: {attempt}\n"
        f"Is the arrangement grammatical {lang} with the same meaning?\n"
        'Return JSON: {"ok": true/false, "note": "one short note in Vietnamese"}'))
    if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
        return None
    return {"ok": data["ok"], "note": str(data.get("note", ""))[:200]}
