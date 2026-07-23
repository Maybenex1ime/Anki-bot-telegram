### Task 13: Settings + /thongke + HELP + hoàn thiện

**Files:** Modify `app/bot/settings_flow.py`, `app/bot/misc.py`; docs `docs/superpowers/sdd/HANDOFF.md`

**Interfaces:**
- Produces: settings UI cho `gemini_api_key` (hiển thị che `AIza...****`), `gemini_model`, `quiz_fast_sec`/`quiz_slow_sec` (nhập "5,15"); text actions `set_gemkey`, `set_gmodel`, `set_quiztime`; `/thongke` thêm khối luyện tập 7 ngày; HELP thêm `/luyen`.

- [ ] **Step 1: `settings_flow.py`.** Trong `_view`, thêm 2 dòng hiển thị + 1 hàng nút:

```python
    key = db.get_setting(conn, "gemini_api_key")
    masked = (key[:4] + "..." + "*" * 4) if key else "(chưa đặt — chế độ offline)"
    # thêm vào chuỗi text:
    #  f"\n🤖 Gemini: {html.escape(masked)} · model {e('gemini_model')}\n"
    #  f"⏱ Ngưỡng trắc nghiệm: {e('quiz_fast_sec')}s / {e('quiz_slow_sec')}s"
    # thêm hàng nút:
    #  [Btn("🤖 Gemini key", callback_data="st_gemkey"), Btn("🧠 Model", callback_data="st_gmodel")],
    #  [Btn("⏱ Ngưỡng giờ quiz", callback_data="st_quiztime")],
```

Trong `on_callback` thêm 3 nhánh đặt `pending_input` với prompt:
- `st_gemkey` → `{"action": "set_gemkey"}`, prompt: `"Dán Gemini API key (tạo miễn phí tại aistudio.google.com), hoặc gõ off để xóa:"`
- `st_gmodel` → `{"action": "set_gmodel"}`, prompt: `"Nhập tên model (mặc định gemini-2.5-flash):"`
- `st_quiztime` → `{"action": "set_quiztime"}`, prompt: `"Nhập 2 số giây fast,slow (VD: 5,15):"`

Và 3 input handler:

```python
async def gemkey_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    v = text.strip()
    db.set_setting(conn, "gemini_api_key", "" if v.lower() == "off" else v)
    try:
        await update.message.delete()       # không để key nằm lại trong chat
    except Exception:
        pass
    await update.message.chat.send_message(
        "✅ Đã cập nhật Gemini API key." if v.lower() != "off" else "✅ Đã xóa key — chạy offline.")


async def gmodel_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    db.set_setting(conn, "gemini_model", text.strip() or "gemini-2.5-flash")
    await update.message.reply_text(f"✅ Model: {text.strip() or 'gemini-2.5-flash'}")


async def quiztime_input(update, context, pending, text):
    conn = context.bot_data["conn"]
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 2 or not all(p.isdigit() for p in parts) \
            or not (0 < int(parts[0]) < int(parts[1]) <= 120):
        await update.message.reply_text("⚠️ Nhập dạng fast,slow (0 < fast < slow ≤ 120). VD: 5,15")
        return
    db.set_setting(conn, "quiz_fast_sec", parts[0])
    db.set_setting(conn, "quiz_slow_sec", parts[1])
    await update.message.reply_text(f"✅ Ngưỡng: {parts[0]}s / {parts[1]}s")
```

- [ ] **Step 2: `misc.py`.** HELP thêm dòng `"• /luyen — trắc nghiệm, chính tả, ghép câu (không tính lịch ôn)\n"`. `cmd_stats` thêm sau dòng tỉ lệ nhớ:

```python
    from datetime import timedelta
    since = (config.today() - timedelta(days=6)).isoformat()
    p = stats.practice_summary(conn, since)
    if p:
        label = {"mc": "🔘 Trắc nghiệm", "typed": "⌨️ Tự luận",
                 "dict": "✍️ Chính tả", "build": "🧩 Ghép câu"}
        extra = "\n🏋️ <b>Luyện tập 7 ngày:</b>\n" + "\n".join(
            f"  {label.get(m, m)}: {c}/{a} đúng" for m, (a, c) in sorted(p.items()))
        # nối extra vào chuỗi reply
```

- [ ] **Step 3: Wiring `main.py`** — `register("set_gemkey", settings_flow.gemkey_input)`, `register("set_gmodel", settings_flow.gmodel_input)`, `register("set_quiztime", settings_flow.quiztime_input)`.

- [ ] **Step 4: Verify tổng** — `python -m pytest tests/ -v` toàn xanh; offline build_app đếm handler; cập nhật `docs/superpowers/sdd/HANDOFF.md` (trạng thái: practice modes đã code xong, chờ test tay + `fly deploy`).

- [ ] **Step 5: Kịch bản test tay (chạy sau khi deploy, cần chủ dự án):**
1. `/settings` → đặt Gemini key → hiển thị che key.
2. `/on` → picker 3 chế độ; chọn Trắc nghiệm Khó → 4 đáp án có bẫy; trả lời nhanh <5s → reveal ghi 😎 Dễ; bấm Tiếp.
3. `/on` → Tự luận → gõ đúng lời khác ("study hard") → Gemini chấm partial/correct kèm note; nút 😎 Dễ hoạt động.
4. Sai ở MCQ → thẻ quay lại cuối phiên (AGAIN requeue).
5. `/luyen` → Trắc nghiệm tự do → kết thúc hiện "Đúng x/y", `/thongke` có khối luyện tập; lịch SM-2 của thẻ KHÔNG đổi (check /tim).
6. `/luyen` → Chính tả: nghe lại nhiều lần, gõ sai 1 ký tự → diff + thử lại; câu do Gemini sinh chỉ dùng từ đã học.
7. `/luyen` → Ghép câu: bấm từ, undo, nộp thiếu từ bị nhắc, nộp trật tự khác được Gemini phán "Cũng đúng!" khi hợp lệ.
8. Xóa Gemini key (`off`) → mọi thứ vẫn chạy: MCQ dễ/khó (đồng âm), tự luận fallback, chính tả từ câu ví dụ; ghép câu báo thiếu câu tách từ nếu kho chưa có.
9. Restart bot giữa câu hỏi → /on tiếp tục, câu hiện lại, đồng hồ tính lại.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: settings for gemini/thresholds, practice stats, help; handoff update"`

---

## Self-Review Notes

- Spec coverage: §3 modes+/luyen (T7,8,9,10), §4 MCQ+nhiễu 3 mức+cache (T4,8), §5 tự luận 2 tầng (T2,3,9), §6 kho câu+cap+audio cleanup (T5), §7 chính tả (T11), §8 ghép câu (T12), §9 CSV (T6), §10 gemini module (T3), §11 bảng/settings/thongke (T1,13), §12 lỗi (fallback mọi task, guard theo pattern cũ), §13 test (T1-6 unit, T13 kịch bản tay).
- Callback prefix: `qz_`, `pr_` mới; `rv_mode`/`rv_mc_levels` dưới `^rv_` sẵn có — không cần thêm handler.
- Type-consistency đã rà: `grading.shuffle_words` dùng cho cả MCQ (4 options) lẫn builder; `sentences.pick(need_words)` bool; `stats.bump_practice(mode)` nhận `"mc"|"typed"|"dict"|"build"`.
- Lưu ý cho implementer T8: `quiz_flow` import `review_flow` (một chiều — `review_flow` chỉ import `quiz_flow` cục bộ trong `_show_front`), tránh vòng import.
- Stub `pr_dict`/`pr_build` ở T10 bị thay ở T11/T12 — reviewer T10 đừng coi stub là thiếu sót (plan chủ đích).
```
