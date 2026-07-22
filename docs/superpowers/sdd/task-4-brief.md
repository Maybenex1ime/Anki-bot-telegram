### Task 4: TTS wrapper (`app/tts.py`)

**Files:** Create `app/tts.py`; Test `tests/test_tts.py`

**Interfaces:**
- Produces: `async tts.synthesize(text: str, voice: str, out_path: Path) -> bool` — True nếu file mp3 tồn tại và >0 byte; mọi exception nuốt vào và trả False (spec §8: TTS lỗi không được chặn tạo thẻ).

- [ ] **Step 1: Viết test (fail trước)** — mock edge_tts, không gọi mạng:

`tests/test_tts.py`:
```python
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
```

Thêm `pytest.ini` ở gốc repo:
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_tts.py -v`

- [ ] **Step 3: Viết `app/tts.py`**

```python
import edge_tts


async def synthesize(text, voice, out_path) -> bool:
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await edge_tts.Communicate(text, voice).save(str(out_path))
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        try:
            if out_path.exists():
                out_path.unlink()
        except OSError:
            pass
        return False
```

- [ ] **Step 4: Run PASS**, rồi kiểm tra thật 1 lần (cần mạng): `python -c "import asyncio,pathlib; from app import tts; print(asyncio.run(tts.synthesize('学习','zh-CN-XiaoxiaoNeural',pathlib.Path('data/media/smoke.mp3'))))"` — Expected: `True`, nghe thử file `data/media/smoke.mp3` rồi xóa.
- [ ] **Step 5: Commit** — `git commit -am "feat: edge-tts wrapper with graceful failure"`

---

