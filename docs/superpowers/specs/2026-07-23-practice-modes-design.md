# Thiết kế: Chế độ luyện tập — Trắc nghiệm, Tự luận, Chép chính tả, Ghép câu

**Ngày:** 2026-07-23
**Trạng thái:** Đã duyệt
**Nền:** mở rộng bot SRS hiện có (spec gốc: `2026-07-22-chinese-srs-telegram-bot-design.md`, đã deploy Fly.io app `reminder-zh-bot`)

## 1. Mục tiêu

Thêm 4 cách kiểm tra chủ động thay cho (và bên cạnh) lật thẻ + tự chấm:

1. **Trắc nghiệm nghĩa** — chọn 1/4 nghĩa tiếng Anh; 3 mức nhiễu (Dễ/Thường/Khó theo độ đồng âm/đồng nghĩa).
2. **Tự luận** — gõ nghĩa tiếng Anh, máy chấm.
3. **Chép chính tả** — nghe câu (TTS), gõ lại chữ Hán, chấm diff từng ký tự.
4. **Ghép từ thành câu** — xếp các từ xáo trộn thành câu đúng.

(1)(2) tích hợp vào phiên ôn `/on` và **tính vào lịch SM-2**; cả 4 chơi tự do qua lệnh mới `/luyen` (không ảnh hưởng SM-2).

## 2. Quyết định kiến trúc

| Quyết định | Lựa chọn |
|---|---|
| Bộ não chấm/ra đề | **Gemini API** (REST, model mặc định `gemini-2.5-flash`, free tier) + **fallback offline cho mọi đường** — không tính năng nào chết khi Gemini chết/thiếu key |
| Tích hợp SM-2 | `/on` chọn chế độ đầu phiên (nhớ lựa chọn gần nhất); kết quả tự quy ra rating. `/luyen` chỉ báo đúng/sai |
| Chấm theo thời gian | Có — đo từ lúc gửi câu hỏi đến lúc trả lời (timestamp trong session kv) |
| Nguồn câu (chính tả/ghép câu) | Kho câu `sentences`: Gemini sinh từ **từ vựng người dùng đã học** (+ từ chức năng cơ bản), câu trả về kèm **tách từ sẵn** (không cần jieba); câu ví dụ trên thẻ/CSV cũng nhập kho |
| API key | settings `gemini_api_key` (nhập qua /settings, hiển thị che) hoặc env `GEMINI_API_KEY`; không key → thuần offline |

## 3. Luồng `/on` và `/luyen`

```
/on → [🃏 Lật thẻ] [🔘 Trắc nghiệm] [⌨️ Tự luận]     (nhớ lựa chọn gần nhất)
      Trắc nghiệm hỏi thêm: [😌 Dễ] [🙂 Thường] [🔥 Khó]
/luyen → [🔘 Trắc nghiệm tự do (chọn bộ + mức)] [✍️ Chép chính tả] [🧩 Ghép câu]
```

Queue thẻ, sửa-tin-nhắn-tại-chỗ, dọn tin phụ: theo đúng cơ chế session hiện có của review_flow. Trắc nghiệm cần ≥4 thẻ trong phạm vi chọn; thiếu → tự chuyển lật thẻ và báo.

## 4. Trắc nghiệm nghĩa

Hiện chữ Hán + 4 nút nghĩa tiếng Anh (1 đúng + 3 nhiễu, thứ tự trộn).

**Nhiễu theo mức:**

| Mức | Online (Gemini) | Offline fallback |
|---|---|---|
| 😌 Dễ | — (không cần) | nghĩa ngẫu nhiên từ thẻ khác |
| 🙂 Thường | nghĩa cùng nhóm chủ đề (Gemini sinh) | nghĩa từ thẻ **cùng bộ**; thiếu thì ngẫu nhiên |
| 🔥 Khó | **đồng nghĩa giả** (nghĩa na ná nhưng sai, Gemini sinh) trộn với đồng âm | **đồng âm**: từ có pinyin trùng/gần (bỏ thanh điệu) trong kho thẻ, thiếu thì tra CEDICT |

Nhiễu cache vào bảng `distractors` (card_id, level, json) — sinh 1 lần/thẻ/mức. Nghĩa nhiễu không được trùng/chứa nghĩa đúng (so sau chuẩn hóa).

**Quy điểm trong `/on`** (ngưỡng chỉnh được: `quiz_fast_sec=5`, `quiz_slow_sec=15`):

| Kết quả | Rating |
|---|---|
| Sai | 🔁 Lại |
| Đúng, > slow | 😓 Khó |
| Đúng, ≤ slow | 🙂 Tốt |
| Đúng, ≤ fast **và** mức 🔥 Khó | 😎 Dễ |

Sau mỗi câu (đúng hay sai) hiện mặt sau đầy đủ: pinyin + nghĩa + ví dụ + audio; sai thì đánh dấu đáp án đúng.

## 5. Tự luận

Hiện chữ Hán → người dùng gõ nghĩa tiếng Anh (text message). Chấm 2 tầng:

1. **Offline** (luôn chạy trước): chuẩn hóa hai phía — lowercase, bỏ "to ", bỏ dấu câu/ngoặc, tách nghĩa thẻ thành biến thể theo `;`, `|`, `,` — trúng nguyên một biến thể → **Đúng**, không cần Gemini.
2. **Gemini** `judge_meaning`: trả `correct | partial | wrong` + giải thích 1 dòng. Không khả dụng → fallback: trùng ≥1 từ nội dung (không tính stopword a/the/of...) với biến thể nào đó = **partial**, còn lại wrong.

Quy điểm `/on`: wrong=🔁 Lại · partial=😓 Khó · correct=🙂 Tốt + nút "😎 Dễ?" tự nâng (chỉ đổi rating nếu bấm trước khi sang câu sau). Thời gian không tham gia chấm tự luận (gõ chậm không bị phạt).

## 6. Kho câu (`sentences`)

Bảng mới: `id, hanzi TEXT, words_json TEXT (mảng từ đã tách, '' nếu chưa tách), pinyin TEXT, meaning TEXT, source TEXT ('gemini'|'example'), card_id INTEGER NULL, times_used INTEGER, created_at TEXT`.

- **Nạp từ Gemini:** khi số câu chưa dùng < 10 → gọi `gen_sentences(vocab, n=10)` chạy ngầm: câu 4–10 từ, chỉ dùng từ trong bộ thẻ + từ chức năng (的/了/吗/在/是/我/你...), trả JSON gồm hanzi + words + pinyin + meaning. Kết quả lọc trùng (hanzi đã có trong kho thì bỏ).
- **Nạp từ ví dụ:** câu ở trường ví dụ của thẻ (tạo tay hoặc CSV) tự nhập kho với `source='example'`, `card_id` trỏ về thẻ; Gemini tách từ + dịch bổ sung ngầm (`words_json`/`pinyin`/`meaning` điền sau); chưa tách → vẫn dùng được cho chính tả, ghép câu bỏ qua.
- Audio câu: edge-tts + cache `file_id` (bảng sentences thêm cột `audio_path`, `audio_file_id`). **Tiết kiệm volume:** sau khi có `audio_file_id` (gửi lần đầu thành công), xóa file mp3 local và để `audio_path=''` — gửi lại bằng `file_id`; nếu `file_id` hỏng (Telegram trả lỗi) thì tái tạo bằng edge-tts. (Chỉ áp dụng audio câu; audio thẻ giữ hành vi cũ.)
- **Giới hạn kho:** setting `max_sentences=3000` — đạt mức này thì `gen_sentences` không được gọi nữa (câu `source='example'` từ thẻ/CSV vẫn luôn được nhận, không tính giới hạn chặn). Ước tính dung lượng: ~25 KB audio/câu → 3.000 câu ≈ 75 MB, cộng nền (DB+CEDICT+audio thẻ ~75 MB) vẫn <16% volume 1GB; với cơ chế xóa-mp3-sau-file_id, chiếm dụng dài hạn thực tế <10 MB.
- Chọn câu cho phiên: ưu tiên `times_used` thấp, ngẫu nhiên trong nhóm.

## 7. Chép chính tả (`/luyen`)

- Bot gửi voice câu + nút [🔁 Nghe lại (không giới hạn)] [⏭ Bỏ qua].
- Người dùng gõ chữ Hán. So sánh sau chuẩn hóa: bỏ khoảng trắng và dấu câu `。，！？、；：""''…·.,!?;:'"`.
- Đúng → ✅ + hiện hanzi + pinyin + nghĩa. Sai → diff từng ký tự (đúng vị trí nào, sai/thiếu/thừa chỗ nào, đếm "x/y ký tự đúng"), cho **thử lại 1 lần**, sai tiếp mới hiện đáp án.
- Diff: so ký tự bằng SequenceMatcher (difflib) trên chuỗi đã chuẩn hóa; render: ký tự sai/thiếu gạch (~~), phần đúng giữ nguyên, kèm dòng đáp án chuẩn.
- Ghi `practice_log`.

## 8. Ghép từ thành câu (`/luyen`)

- Lấy câu có `words_json` từ kho; hiện nghĩa tiếng Anh + các từ xáo trộn thành nút inline (mỗi từ 1 nút; từ trùng nhau đánh index riêng).
- Bấm từ → tin nhắn sửa tại chỗ: từ rời khỏi khay, nối vào "Câu của bạn". Nút [↩️ Xóa từ cuối] [✅ Nộp] [⏭ Bỏ qua]. Nộp khi khay còn từ → nhắc dùng hết từ.
- Chấm: khớp chuỗi câu gốc → ✅. Khác → `judge_word_order(original, attempt)` qua Gemini (chấp nhận trật tự thay thế đúng ngữ pháp cùng nghĩa → "✅ Cũng đúng!", kèm ghi chú); Gemini không có → chỉ chấp nhận khớp gốc. Sai → ❌ + câu gốc + pinyin + nghĩa.
- Ghi `practice_log`.

## 9. CSV mở rộng

Header mới (cột cũ giữ nguyên, cột mới tùy chọn):

```csv
hán,pinyin,nghĩa,ví_dụ,ví_dụ_thêm
学习,,,我在学习中文,我们一起学习吧|他学习很努力
```

- `ví_dụ`: như cũ — hiện trên thẻ, đồng thời nhập kho câu.
- `ví_dụ_thêm` (alias: `vi_du_them`): nhiều câu ngăn cách `|`, chỉ vào kho câu (không hiện trên thẻ). Câu rỗng sau tách `|` bị bỏ qua.
- Tạo thẻ thủ công: câu nhập ở nút "💬 Ví dụ" cũng tự vào kho câu.

## 10. Module Gemini (`app/gemini.py`)

- Lõi: `async ask_json(prompt: str, schema_hint: str) -> dict | None` — REST `generateContent`, model từ setting `gemini_model` (mặc định `gemini-2.5-flash`), key từ setting `gemini_api_key` hoặc env; timeout 20s, tối đa 1 retry; **mọi lỗi/timeout/không key → None**.
- 4 hàm mỏng dùng chung lõi: `make_distractors(hanzi, meaning, level) -> list[str] | None`; `judge_meaning(hanzi, meaning, user_answer) -> {"verdict": "correct|partial|wrong", "note": str} | None`; `gen_sentences(vocab: list[str], n) -> list[{hanzi, words, pinyin, meaning}] | None`; `judge_word_order(original, attempt, meaning) -> {"ok": bool, "note": str} | None`.
- Output Gemini là dữ liệu không tin cậy: validate cấu trúc, `html.escape` trước khi hiển thị, giới hạn độ dài.

## 11. Dữ liệu & cấu hình mới

- Bảng: `sentences`, `distractors`, `practice_log(day, mode, attempts, correct)`.
- Settings mới: `review_mode`, `quiz_fast_sec=5`, `quiz_slow_sec=15`, `gemini_api_key=''`, `gemini_model='gemini-2.5-flash'`, `max_sentences=3000`.
- `/settings` thêm mục sửa các key trên (API key nhập qua pending_input, hiển thị dạng `AIza...****`).
- `/thongke` thêm khối luyện tập (số câu đã luyện theo chế độ, tỉ lệ đúng 7 ngày).
- Session kv mở rộng: `mode`, `level`, `asked_at` (epoch giây, tính giờ trắc nghiệm), state riêng chính tả/ghép câu (câu hiện tại, số lần thử, từ đã chọn).

## 12. Xử lý lỗi

- Mọi đường Gemini có fallback offline như bảng §4–§8; timeout coi như None; không bao giờ chặn phiên.
- Restart giữa câu: câu đang dở hỏi lại từ đầu, đồng hồ tính lại (asked_at ghi trong kv).
- Kho câu cạn + không Gemini: chính tả/ghép câu báo rõ cách khắc phục (thêm ví dụ hoặc đặt API key).
- Text từ người dùng và từ Gemini đều `html.escape` khi render HTML.
- Thẻ bị xóa giữa phiên, double-tap nút: theo guard đã có từ final review cũ.

## 13. Kiểm thử

- **Unit test bắt buộc:** chuẩn hóa + chấm tự luận offline (biến thể nghĩa, stopword); diff chính tả (đúng/sai/thiếu/thừa, đếm ký tự); trộn từ + chấm khớp ghép câu (kể cả từ trùng nhau); quy đổi thời gian→rating (biên 5s/15s); chọn nhiễu offline (đồng âm bỏ thanh điệu, loại nhiễu trùng nghĩa đúng); parse cột `ví_dụ_thêm` (tách `|`, bỏ rỗng). Gemini mock toàn bộ.
- Bot flow: test tay theo kịch bản (sẽ ghi trong plan).

## 14. Ngoài phạm vi

- Luyện nói/chấm phát âm (khe Azure vẫn để dành).
- Chiều ôn ngược nghĩa→Hán, cloze, luyện viết tay.
- Nhắc lịch riêng cho luyện tập (dùng nhắc hiện có).
