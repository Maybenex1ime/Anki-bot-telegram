# Phase 2 (practice modes) — Final whole-branch review

**Phạm vi:** 3c9df78..7628f86 (16 commits) · **Ngày:** 2026-07-23

## Verdict: ✅ Ready to merge/deploy

- Bất biến quan trọng nhất được xác nhận giữ vững xuyên suốt: **SM-2 chỉ bị ghi từ `/on`, không bao giờ từ `/luyen`** (3 lớp guard độc lập).
- Gemini có fallback offline ở cả 5 điểm gọi; mọi text từ Gemini/người dùng đều html.escape; migration lên DB Fly đang chạy an toàn (CREATE IF NOT EXISTS + INSERT OR IGNORE); chính sách audio/volume đúng spec.
- Không có finding Critical/Important. Toàn bộ Minor (danh sách trong `progress.md`) được triage **defer** — 2 mục rẻ nhất nếu muốn polish: dòng VD trong `/csv` GUIDE còn 4 cột, và `except Exception` quá rộng trong `add_sentence`.

## Khe hở spec ghi nhận (Minor)
- §12 "restart giữa câu → đồng hồ tính lại": `asked_at` sống qua restart nhưng không có cơ chế re-ask khi boot — trả lời câu MCQ cũ sau restart có thể bị chấm Khó thay vì Tốt (1 thẻ, chỉ ảnh hưởng timing, không bao giờ chấm hào phóng sai).

## 8 kịch bản test tay BỔ SUNG (ngoài 9 bước trong plan Task 13)
1. Đan xen chế độ giữa chừng: `/on` tự luận bỏ dở → `/luyen` chính tả → quay lại tin `/on` cũ.
2. `pending_input` mồ côi: bỏ dở chính tả (không bấm nút) rồi gõ chữ Hán — sẽ bị chấm như chính tả (hành vi biết trước), xác nhận `/luyen` sau đó vẫn chạy.
3. `/on` MCQ: thẻ không đủ nhiễu rơi về lật thẻ và nút chấm vẫn ăn SM-2; thẻ đủ nhiễu vẫn MCQ.
4. Negative-cache: vocab nhỏ khiến thẻ bị cache "[]" — thêm thẻ mới rồi thử lại, ghi nhận thẻ đó vẫn bị bỏ qua ở mức cũ (hạn chế đã biết).
5. Độ trễ khi kho câu cạn + có Gemini key (chờ tối đa ~40s khi bấm "Câu tiếp").
6. `file_id` audio hỏng → tự re-synth.
7. Kho trống + không key → 2 thông báo hướng dẫn hiện đúng.
8. Diff chính tả với câu chứa `&`/dấu latin — không lỗi parse HTML.
