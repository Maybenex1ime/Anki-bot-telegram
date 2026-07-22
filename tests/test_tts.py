import pytest

from app import tts


class FakeCommOK:
    def __init__(self, text, voice):
        pass

    async def save(self, path):
        with open(path, "wb") as f:
            f.write(b"mp3data")


class FakeCommFail:
    def __init__(self, text, voice):
        pass

    async def save(self, path):
        raise RuntimeError("network down")


@pytest.mark.asyncio
async def test_synthesize_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.edge_tts, "Communicate", FakeCommOK)
    out = tmp_path / "m" / "1.mp3"
    assert await tts.synthesize("学习", "zh-CN-XiaoxiaoNeural", out) is True
    assert out.read_bytes() == b"mp3data"


@pytest.mark.asyncio
async def test_synthesize_failure_returns_false_and_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tts.edge_tts, "Communicate", FakeCommFail)
    out = tmp_path / "1.mp3"
    assert await tts.synthesize("学习", "voice", out) is False
    assert not out.exists()
