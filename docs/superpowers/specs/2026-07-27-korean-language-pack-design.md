# Thiết kế: Language pack — thêm bot tiếng Hàn chạy song song

**Ngày:** 2026-07-27
**Trạng thái:** Đã duyệt
**Nền:** bot SRS tiếng Trung (`reminder-zh-bot`) đã deploy Fly.io, phase 1+2 đang chạy với dữ liệu thật.

## 1. Mục tiêu

Thêm một bot học **tiếng Hàn** chạy **song song** bot tiếng Trung hiện có: cùng một codebase Python, cùng nền Telegram, nhưng là con bot riêng (token riêng, dữ liệu riêng). Sửa lỗi / thêm tính năng ở codebase chung phải áp cho cả hai bot.

## 2. Quyết định kiến trúc

| Quyết định | Lựa chọn | Lý do |
|---|---|---|
| Fork vs config-drive | **Một codebase, chọn ngôn ngữ theo env `LANG`** | Cả hai bot còn phát triển tiếp → sửa một lần áp cả hai |
| Nơi gom khác biệt | **Một file `app/langpack.py`** (lớp mỏng) | Mọi đặc thù ngôn ngữ một chỗ; thêm ngôn ngữ = thêm 1 entry |
| Từ điển tiếng Hàn | **CC-KEDICT offline** (tải 1 lần vào DB) | Nhất quán CC-CEDICT; không cần key/mạng. Chấp nhận kho từ nhỏ hơn, tra rỗng thì nhập tay |
| Phiên âm | `korean-romanizer` (Revised Romanization) | Tương đương `pypinyin` bên tiếng Trung |
| TTS | edge-TTS giọng `ko-KR-SunHiNeural` | edge-TTS đã dùng sẵn, chỉ đổi voice |
| Deploy | **2 Fly app cùng image, khác `LANG` + token + volume** | Dữ liệu tách biệt, code chung |
| Phạm vi ngôn ngữ | Chỉ thay "ruột" ngôn ngữ; giữ nguyên mọi luồng | YAGNI — không làm framework đa ngôn ngữ tổng quát |

## 3. Language pack (`app/langpack.py`)

`LANGS: dict[str, LangPack]` — mỗi entry gồm đúng 6 thành phần:

| Thành phần | `zh` (rút từ code hiện tại) | `ko` (mới) |
|---|---|---|
| `display_name` (tiếng Việt) | "tiếng Trung" | "tiếng Hàn" |
| `romanize(text) -> str` | `pypinyin` tone marks | `korean-romanizer` RR |
| từ điển: `dict_url` + loader parse | CC-CEDICT | CC-KEDICT |
| `tts_voice` mặc định | `zh-CN-XiaoxiaoNeural` | `ko-KR-SunHiNeural` |
| `script_range` (khối ký tự chữ viết) | CJK `一-鿿` (U+4E00–U+9FFF) | Hangul `가-힣` (U+AC00–U+D7A3) |
| `gemini_name` (tên cho prompt) | "Chinese" | "Korean" |

`config.py` đọc `LANG` (mặc định `zh`) → nạp `LANGS[LANG]`; `LANG` không có trong `LANGS` → raise lỗi rõ ràng lúc khởi động (fail fast, không chạy sai âm thầm).

## 4. Các điểm sửa (5 chỗ hard-code tiếng Trung → gọi qua langpack)

- `app/lookup.py`: `gen_pinyin` → `langpack.romanize`; `ensure_cedict`/`lookup_meaning` dùng `dict_url` + loader của langpack (tên hàm giữ tổng quát, VD `ensure_dict`).
- `app/quiz.py`: `pinyin_key` → `langpack.phonetic_key` (bỏ dấu/khoảng trắng, ASCII lower). Đồng âm tiếng Hàn (동음이의어) vẫn hoạt động.
- `app/grading.py`: `normalize_hanzi` → `langpack.normalize_text` (lọc theo `script_range`, xóa khoảng trắng + dấu câu). **Giữ cách xóa hết khoảng trắng cho cả hai** — với tiếng Hàn nghĩa là không phạt lỗi spacing khi chép chính tả (thân thiện người mới học).
- `app/gemini.py`: prompt thay chuỗi cứng "tiếng Trung" bằng `langpack.gemini_name`.
- `app/config.py`: `CEDICT_URL`, `tts_voice` default → chuyển vào langpack.

Phần KHÔNG đụng: `srs.py`, `stats.py`, `sentences.py` (logic), `cards.py`, toàn bộ `bot/` flow (review/quiz/practice/reminders/csv/decks/manage/settings), schema DB. Chúng không phụ thuộc ngôn ngữ.

## 5. Đặc thù tiếng Hàn

- **Khoảng trắng giữa từ (띄어쓰기):** tiếng Hàn viết rời từ, tiếng Trung viết liền. `normalize_text` xóa hết khoảng trắng cho cả hai → chép chính tả không phạt lỗi spacing (cố ý, thân thiện). Ghép câu: Gemini trả `words[]` như tiếng Trung (dễ hơn vì có sẵn ranh giới từ), so đáp án ghép từ rồi normalize — logic hiện tại đã đúng.
- **Không thanh điệu:** `phonetic_key` chỉ cần Romanized bỏ khoảng trắng, không cần bước bỏ số thanh điệu như pinyin.
- Cấu trúc thẻ + mọi trải nghiệm người dùng: giống hệt bot tiếng Trung.

## 6. Refactor an toàn bot tiếng Trung (rủi ro chính)

Bot `reminder-zh-bot` đang chạy dữ liệu thật — refactor không được đổi hành vi, không được đụng dữ liệu.

1. **Test khóa hành vi `zh` viết TRƯỚC refactor** — `gen_pinyin("学习")=="xué xí"`, normalize xóa đúng ký tự, lookup CEDICT ra đúng nghĩa. Refactor xong test vẫn xanh = hành vi không đổi.
2. **DB không đụng** — schema/dữ liệu/tên bảng giữ nguyên; `LANG` chỉ ảnh hưởng code xử lý, không ảnh hưởng cách lưu.
3. **`LANG` mặc định `zh`** — quên set vẫn chạy như hiện tại; bot Trung chỉ thêm `LANG=zh` cho tường minh, không đổi secret khác.

**Thứ tự triển khai (bot Trung không bao giờ ở trạng thái hỏng):**
(a) tạo `langpack.py` gói `zh` + test khóa hành vi → (b) chuyển 5 file gọi qua langpack, test `zh` xanh → (c) **redeploy bot Trung, xác nhận chạy y như cũ** → (d) chỉ khi đó mới thêm gói `ko` + dựng app Fly mới. Bước (c) lỗi → lùi bản ngay, bot Hàn chưa tồn tại nên không ảnh hưởng.

## 7. Deploy bot tiếng Hàn

- BotFather tạo bot mới → token mới.
- Fly app mới `reminder-ko-bot`: cùng image, `fly secrets set BOT_TOKEN=<ko> OWNER_ID=<...>`, env `LANG=ko`, volume riêng (`fly volumes create`), region `sin`, `fly.toml` KHÔNG có `[http_service]` (bài học autostop).
- Boot đầu tự tải CC-KEDICT vào DB (như CC-CEDICT), tự tạo bảng.

## 8. Xử lý lỗi

- CC-KEDICT tra rỗng → thẻ vẫn tạo, nghĩa trống, nhắc nhập tay (cơ chế sẵn có).
- `korean-romanizer` gặp ký tự lạ (Hán tự lẫn, số, dấu) → trả nguyên văn phần không phiên âm được, không chặn tạo thẻ.
- `LANG` không hợp lệ → raise lúc khởi động, không chạy sai âm thầm.

## 9. Kiểm thử

- **Test khóa hành vi `zh`** (Phần 6) — điều kiện tiên quyết trước refactor.
- **Test gói `ko`**: `romanize("안녕") == "annyeong"`; `normalize_text` giữ đúng Hangul, xóa khoảng trắng + dấu câu; `phonetic_key` cho cặp đồng âm (VD 배 các nghĩa) ra cùng key.
- **Test chọn gói**: `LANG=zh`/`ko` nạp đúng gói; `LANG` lạ raise.
- CC-KEDICT loader: parse đúng định dạng file, tra simp/nghĩa (mock file nhỏ, không tải mạng trong test).
- Bot Hàn: test tay theo kịch bản sẵn có của bot Trung (không cần kịch bản mới — luồng giống hệt).

## 10. Ngoài phạm vi

- Học Hangul từ đầu (bảng chữ cái, ghép âm tiết).
- Phân tích trợ từ (조사), chia động từ.
- Gộp nhiều ngôn ngữ vào chung một bot / một DB.
- Ngôn ngữ thứ 3 (kiến trúc đã sẵn sàng: thêm 1 entry `LANGS`, nhưng chưa làm).
