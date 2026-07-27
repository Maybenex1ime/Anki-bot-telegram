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


async def test_prompt_uses_pack_language_name(conn, monkeypatch):
    seen = {}

    async def fake_ask(conn_, prompt):
        seen["p"] = prompt
        return {"options": ["a", "b", "c"]}

    monkeypatch.setattr(gemini, "ask_json", fake_ask)
    await gemini.make_distractors(conn, "学习", "to learn", "normal")
    assert "Chinese" in seen["p"]
