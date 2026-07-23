import json
import os

import httpx

from app import db

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
    kind = ("nghĩa tiếng Anh cùng nhóm chủ đề nhưng SAI"
            if level == "normal"
            else "nghĩa tiếng Anh RẤT GIỐNG nghĩa đúng nhưng SAI (bẫy gần-đồng-nghĩa)")
    data = await ask_json(conn, (
        f"Từ tiếng Trung: {hanzi}\nNghĩa đúng (tiếng Anh): {meaning}\n"
        f"Sinh đúng 3 {kind}, ngắn gọn kiểu từ điển.\n"
        'Trả JSON: {"options": ["...", "...", "..."]}'))
    if not isinstance(data, dict) or not isinstance(data.get("options"), list):
        return None
    opts = [str(o).strip()[:80] for o in data["options"] if str(o).strip()][:3]
    return opts if len(opts) == 3 else None


async def judge_meaning(conn, hanzi, meaning, answer):
    data = await ask_json(conn, (
        f'Từ tiếng Trung: {hanzi}. Nghĩa chuẩn (tiếng Anh): "{meaning}". '
        f'Người học trả lời: "{answer}".\n'
        "Chấm verdict: correct (đúng hoặc tương đương), partial (đúng một phần), wrong.\n"
        'Trả JSON: {"verdict": "...", "note": "giải thích 1 câu tiếng Việt"}'))
    if not isinstance(data, dict) or data.get("verdict") not in ("correct", "partial", "wrong"):
        return None
    return {"verdict": data["verdict"], "note": str(data.get("note", ""))[:200]}


async def gen_sentences(conn, vocab, n=10):
    data = await ask_json(conn, (
        f"Sinh {n} câu tiếng Trung giản thể ngắn (4-10 từ), CHỈ dùng các từ sau "
        "cộng từ chức năng cơ bản (的了吗在是我你他她们不很和有个这那):\n"
        + "、".join(vocab[:300]) + "\n"
        'Trả JSON: {"sentences": [{"hanzi": "...", "words": ["từ", "đã", "tách"], '
        '"pinyin": "...", "meaning": "bản dịch tiếng Anh"}]}'))
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
    data = await ask_json(conn, (
        f"Câu tiếng Trung: {hanzi}\nTách từ và dịch sang tiếng Anh.\n"
        'Trả JSON: {"words": ["từ", "đã", "tách"], "pinyin": "...", "meaning": "..."}'))
    if not isinstance(data, dict) or not isinstance(data.get("words"), list) or not data["words"]:
        return None
    return {"words": [str(w)[:20] for w in data["words"]][:20],
            "pinyin": str(data.get("pinyin", ""))[:200],
            "meaning": str(data.get("meaning", ""))[:200]}


async def judge_word_order(conn, original, attempt, meaning):
    data = await ask_json(conn, (
        f"Câu gốc: {original}\nNghĩa: {meaning}\nHọc viên xếp lại thành: {attempt}\n"
        "Câu xếp lại có đúng ngữ pháp tiếng Trung và giữ nguyên nghĩa không?\n"
        'Trả JSON: {"ok": true/false, "note": "1 câu tiếng Việt"}'))
    if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
        return None
    return {"ok": data["ok"], "note": str(data.get("note", ""))[:200]}
