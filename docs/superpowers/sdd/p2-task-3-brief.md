### Task 3: Gemini client (`app/gemini.py`)

**Files:** Create `app/gemini.py`; Test `tests/test_gemini.py`

**Interfaces:**
- Consumes: `db.get_setting` (`gemini_api_key`, `gemini_model`), env `GEMINI_API_KEY`, `httpx`
- Produces:
  - `available(conn) -> bool`
  - `async ask_json(conn, prompt: str) -> dict | list | None` — POST `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=...`, body `{"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"response_mime_type":"application/json"}}`, timeout 20s, tối đa 2 lần thử; parse `candidates[0].content.parts[0].text` là JSON; **mọi lỗi → None**
  - `async make_distractors(conn, hanzi, meaning, level) -> list[str] | None` (đúng 3 chuỗi, mỗi chuỗi cắt 80 ký tự)
  - `async judge_meaning(conn, hanzi, meaning, answer) -> {"verdict": "correct|partial|wrong", "note": str} | None`
  - `async gen_sentences(conn, vocab: list[str], n=10) -> list[{"hanzi","words","pinyin","meaning"}] | None` (lọc item thiếu hanzi/words)
  - `async segment_translate(conn, hanzi) -> {"words": list[str], "pinyin": str, "meaning": str} | None`
  - `async judge_word_order(conn, original, attempt, meaning) -> {"ok": bool, "note": str} | None`

- [ ] **Step 1: Viết test (fail trước)** — `tests/test_gemini.py` (mock `httpx.AsyncClient`):

```python
import json

import pytest

from app import db, gemini


class FakeResp:
    def __init__(self, status_code=200, payload_text=""):
        self.status_code = status_code
        self._t = payload_text

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._t}]}}]}


class FakeClient:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc = resp, exc

    def __call__(self, *a, **k):  # đóng vai httpx.AsyncClient(...)
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        if self.exc:
            raise self.exc
        return self.resp


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.set_setting(c, "gemini_api_key", "test-key")
    return c


async def test_ask_json_ok(conn, monkeypatch):
    monkeypatch.setattr(gemini.httpx, "AsyncClient",
                        FakeClient(FakeResp(200, json.dumps({"x": 1}))))
    assert await gemini.ask_json(conn, "p") == {"x": 1}


async def test_ask_json_no_key_http_error_and_garbage(tmp_path, conn, monkeypatch):
    bare = db.connect(tmp_path / "nokey.db")
    assert await gemini.ask_json(bare, "p") is None          # không key
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(429, "{}")))
    assert await gemini.ask_json(conn, "p") is None          # HTTP lỗi
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, "not json")))
    assert await gemini.ask_json(conn, "p") is None          # JSON hỏng
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(exc=RuntimeError("net")))
    assert await gemini.ask_json(conn, "p") is None          # exception


async def test_make_distractors_validates(conn, monkeypatch):
    good = json.dumps({"options": ["to teach", "to read", "to test"]})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, good)))
    assert await gemini.make_distractors(conn, "学", "to learn", "normal") == \
        ["to teach", "to read", "to test"]
    bad = json.dumps({"options": ["one", "two"]})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, bad)))
    assert await gemini.make_distractors(conn, "学", "to learn", "normal") is None


async def test_judge_meaning_validates(conn, monkeypatch):
    ok = json.dumps({"verdict": "partial", "note": "thiếu ý"})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, ok)))
    assert (await gemini.judge_meaning(conn, "学", "to learn", "study"))["verdict"] == "partial"
    bad = json.dumps({"verdict": "maybe"})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, bad)))
    assert await gemini.judge_meaning(conn, "学", "to learn", "x") is None


async def test_gen_sentences_filters(conn, monkeypatch):
    payload = json.dumps({"sentences": [
        {"hanzi": "我学习", "words": ["我", "学习"], "pinyin": "wǒ xuéxí", "meaning": "I study"},
        {"hanzi": "", "words": []},
    ]})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, payload)))
    out = await gemini.gen_sentences(conn, ["我", "学习"])
    assert len(out) == 1 and out[0]["hanzi"] == "我学习"


async def test_judge_word_order_validates(conn, monkeypatch):
    ok = json.dumps({"ok": True, "note": "đảo trạng ngữ hợp lệ"})
    monkeypatch.setattr(gemini.httpx, "AsyncClient", FakeClient(FakeResp(200, ok)))
    assert (await gemini.judge_word_order(conn, "昨天我去", "我昨天去", "x"))["ok"] is True
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_gemini.py -v`

- [ ] **Step 3: Implement** — `app/gemini.py`:

```python
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
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/ -v`
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: gemini client with JSON mode, validation, None-on-error"`

---

