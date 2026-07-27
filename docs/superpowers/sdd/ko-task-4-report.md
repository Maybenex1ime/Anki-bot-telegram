# Task 4 (file portion) — Report

- **Status:** DONE (file changes only; deploy steps 2 & 5 skipped per scope).
- **Commit:** `948b0b5f378e5deaa75e6e429633a0bcdcc97dc4`
- **Files changed (3):**
  - `Dockerfile` — added `ENV BOT_LANG=zh` after WORKDIR, before COPY.
  - `docs/DEPLOY-ko.md` — created (Korean bot runbook, verbatim from brief).
  - `docs/superpowers/sdd/HANDOFF.md` — added langpack architecture section (BOT_LANG, 2 parallel Fly apps, "edit once deploy twice", CC-KEDICT note, pointer to DEPLOY-ko.md); updated docs list.
- **Tests:** `python -m pytest tests/ -q` → 64 passed (unchanged).
- **Fly commands:** NONE run. No flyctl deploy / apps create / secrets executed.

## Fix: final-review findings

**Commit:** `c38faebeb942163c231bf3dfda2ce47bdaa47d7c` — "fix: pack-driven script detection (Korean card creation) + boot-log/error-msg cues"

**Findings addressed:**

- **F1 (CRITICAL, launch-blocker):** Free-text card creation was hard-coded to CJK range (`_HAN = re.compile(r"[一-鿿]")` in `app/bot/textrouter.py`), so the Korean bot rejected every typed Hangul word — primary flow was dead. Root-cause fix (the missing `script_range` pack component):
  - `app/langpack.py`: added key `script_range` to both packs — zh `"一-鿿"`, ko `"가-힣"`.
  - `app/bot/textrouter.py`: removed module-level `_HAN`; added `looks_like_word(text)` helper that reads `config.PACK["script_range"]` at call time (`re.search(f"[{config.PACK['script_range']}]", text)`). `on_text` now calls it. Reject string made language-neutral: "Gõ một từ để tạo thẻ, hoặc /start để xem lệnh."

- **F2 (trivial):** `app/langpack.py` `get()` error said "LANG không hợp lệ" but the env var is `BOT_LANG` → changed to "BOT_LANG không hợp lệ".

- **F3 (log/runbook mismatch):** `app/bot/main.py` logged "Đã nạp CC-CEDICT: %d mục" for both bots while `docs/DEPLOY-ko.md` told operators to look for "CC-KEDICT". Genericized log to "Đã nạp từ điển: %d mục" and updated `docs/DEPLOY-ko.md` verification line to match.

**Tests:**
- `tests/test_langpack.py`: asserts both packs expose `script_range` (zh `"一-鿿"`, ko `"가-힣"`).
- `tests/test_textrouter.py` (new): proves detection is pack-driven. With zh pack `looks_like_word("学习")` True / `"hello"` False; monkeypatching `app.config.PACK` to the ko pack, `looks_like_word("안녕")` True / `"hello"` False.

**Verification:**
- `python -m pytest tests/ -v` → **66 passed, 2 warnings** (58 behavior-lock unchanged + langpack + 2 new textrouter). Chinese bot behavior-lock stays green.
- Offline build: `BOT_TOKEN=123:dummy OWNER_ID=1 python -c "from app.bot.main import build_app; build_app()"` → `BUILD OK`.
