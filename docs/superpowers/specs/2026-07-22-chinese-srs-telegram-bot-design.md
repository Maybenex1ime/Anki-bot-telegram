# Thiết kế: Bot Telegram học tiếng Trung kiểu Anki (SRS)

**Ngày:** 2026-07-22
**Trạng thái:** Đã duyệt

## 1. Mục tiêu

Hệ thống flashcard spaced-repetition (SRS) kiểu Anki cho một người dùng duy nhất, học **tiếng Trung**, chạy hoàn toàn qua **Telegram bot**:

- Nhắc học qua tin nhắn Telegram khi có thẻ đến hạn (iPhone của người dùng nhận thông báo qua Telegram; widget Telegram trên màn hình chính đóng vai trò badge).
- Ôn thẻ ngay trong chat Telegram bằng nút bấm inline (Lại/Khó/Tốt/Dễ) — không cần app/web riêng.
- Tạo thẻ bằng cách gõ chữ Hán (bot tự tra) hoặc nhập hàng loạt qua CSV.
- Thu âm giọng đọc của người dùng để tự so với giọng chuẩn; chừa sẵn khe cắm Azure Speech Pronunciation Assessment cho tương lai.

## 2. Quyết định kiến trúc

| Quyết định | Lựa chọn | Lý do |
|---|---|---|
| Ngôn ngữ | Python | Hệ sinh thái tiếng Trung mạnh: `pypinyin`, CC-CEDICT, `edge-tts` |
| Thư viện bot | `python-telegram-bot` | Chín muồi, hỗ trợ inline keyboard, JobQueue |
| Kết nối Telegram | Long-polling | Không cần domain/HTTPS/webhook; 1 người dùng nên hiệu năng không thành vấn đề |
| CSDL | SQLite (1 file) | Không cần server DB; backup = gửi file qua Telegram |
| Hosting | Fly.io free tier | Miễn phí, không "ngủ", volume lưu trữ bền vững |
| Lưu trữ file | Volume Fly.io | SQLite + mp3 + voice + ảnh sống sót qua restart |
| TTS | `edge-tts` (Microsoft) | Miễn phí, giọng zh-CN chất lượng cao |
| Từ điển | CC-CEDICT (Trung–Anh) | Mở, đầy đủ, chất lượng cao |
| Thuật toán SRS | SM-2 | Đơn giản, đã chứng minh, dễ hiểu; FSRS không đáng độ phức tạp cho bản đầu |
| Người dùng | Khóa theo 1 Telegram ID | Bot cá nhân, từ chối người lạ, không cần hệ thống tài khoản |
| Model AI khi triển khai | Opus cho task code, Fable cho planning | Yêu cầu của người dùng |

### Sơ đồ tổng thể

```
┌─────────────────────── Fly.io (VM miễn phí) ───────────────────────────┐
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────────────┐  │
│  │ Telegram Bot │   │  Scheduler   │   │  Dịch vụ tra cứu           │  │
│  │ (long-poll,  │   │ (giờ nhắc →  │   │  pypinyin → pinyin         │  │
│  │  inline      │   │  quét thẻ    │   │  CC-CEDICT → nghĩa Anh     │  │
│  │  buttons)    │   │  đến hạn)    │   │  edge-tts → mp3            │  │
│  └──────┬───────┘   └──────┬───────┘   └────────────┬───────────────┘  │
│         └──────────────────┴────────────────────────┘                  │
│                   ┌────────▼────────┐                                  │
│                   │ SQLite + media  │  ← volume Fly.io (bền vững)      │
│                   └─────────────────┘                                  │
└────────────────────────────────────────────────────────────────────────┘
```

- Âm thanh chuẩn tạo **một lần lúc tạo thẻ**; sau lần gửi đầu, lưu `file_id` Telegram để gửi lại tức thì.
- Lệnh `/backup`: bot gửi file SQLite qua Telegram.

## 3. Mô hình dữ liệu

### Thẻ (card)

| Trường | Bắt buộc | Nguồn |
|---|---|---|
| Chữ Hán | ✅ | Người dùng nhập |
| Pinyin | ✅ | Tự sinh (`pypinyin`), sửa được |
| Nghĩa tiếng Anh | ✅ | Tự tra CC-CEDICT, sửa được |
| Câu ví dụ | ⬜ | Người dùng nhập nếu muốn |
| Hình ảnh | ⬜ | Người dùng gửi nếu muốn |
| Âm thanh chuẩn (mp3) | ✅ | Tự sinh edge-tts |
| Bản thu của người dùng | ⬜ | Ghi đè mỗi lần thu mới |

Kèm trạng thái SRS mỗi thẻ: `due_date`, `interval`, `ease_factor`, `repetitions`, `lapses`.

### Bộ thẻ (deck)

- Thẻ thuộc về một bộ (VD "HSK 1"). Thao tác bản đầu: tạo, đổi tên, xóa, chuyển thẻ giữa bộ.

### Chiều ôn

- Một chiều: **Hán → nghĩa** (nhìn chữ Hán, đoán cách đọc + nghĩa). Cấu trúc cho phép thêm chiều ngược sau này nhưng bản đầu không làm.

### CSV nhập hàng loạt

```csv
hán,pinyin,nghĩa,ví_dụ
学习,,,我在学习中文
你好,nǐ hǎo,hello; hi,
```

Chỉ cột `hán` bắt buộc; cột trống thì tự sinh (pinyin, nghĩa) hoặc bỏ qua (ví dụ).

## 4. Thuật toán SRS: SM-2

- Thẻ mới: 1 ngày → 3 ngày → interval × ease_factor (mặc định 2.5).
- **Lại** (quên): về đầu (interval 1 ngày), tăng `lapses`, giảm ease.
- **Khó**: interval tăng chậm (×1.2), ease −0.15.
- **Tốt**: interval × ease.
- **Dễ**: interval × ease × 1.3, ease +0.15.
- Ease tối thiểu 1.3.
- Giới hạn: tối đa 20 thẻ mới/ngày (chỉnh được trong `/settings`); thẻ đến hạn không giới hạn.

## 5. Luồng ôn tập trong Telegram

```
Bot: 🀄 学习
     [🔊 Nghe] [👀 Xem đáp án]

(bấm Xem đáp án)

Bot: 🀄 学习
     📖 xuéxí
     🇬🇧 to learn; to study
     💬 我在学习中文        (nếu có; + ảnh nếu có; + audio)
     [🎤 Thu âm thử]
     [Lại] [Khó] [Tốt] [Dễ]
```

- Bot **sửa tin nhắn tại chỗ** khi chuyển thẻ — chat không trôi dài.
- 🔊 ở mặt trước = luyện nghe trước khi xem đáp án.
- 🎤: bot chờ voice message → gửi cặp "giọng chuẩn / giọng bạn" để tự so → quay lại nút chấm. Bản thu lưu đè vào thẻ. **Đây là khe cắm Azure Pronunciation Assessment sau này** (khi có API key qua cấu hình thì trả thêm điểm số).
- Trạng thái phiên ôn lưu trong SQLite — restart không mất phiên.

## 6. Lịch nhắc & thông báo

- Giờ nhắc cố định, người dùng tự đặt; mặc định **7:30, 12:30, 20:00** (Asia/Ho_Chi_Minh).
- Đến giờ: có thẻ đến hạn → `📚 Bạn có N thẻ đến hạn (M thẻ mới). [Ôn ngay ▶️]`; không có → im lặng.
- Chống nhắc trùng: đã ôn hết thì các giờ sau im.
- Nhắc cuối ngày 21:30 (tắt/chỉnh được) nếu cả ngày chưa ôn và còn thẻ đến hạn, kèm **streak** (chuỗi ngày liên tiếp).

## 7. Lệnh bot

| Lệnh | Chức năng |
|---|---|
| `/on` | Bắt đầu ôn ngay |
| *(gõ chữ Hán)* | Tạo thẻ — bot tra, hiện preview, Lưu/Sửa |
| `/csv` | Nhập hàng loạt từ file CSV |
| `/bo` | Quản lý bộ thẻ |
| `/tim <từ>` | Tìm/xem/sửa/xóa thẻ |
| `/thongke` | Thống kê: tổng thẻ, đến hạn, streak, tỉ lệ nhớ |
| `/settings` | Giờ nhắc, giới hạn thẻ mới/ngày, giọng đọc |
| `/backup` | Gửi file dữ liệu qua Telegram |

## 8. Xử lý lỗi

- **Từ không có trong CC-CEDICT**: vẫn tạo thẻ (pinyin tự sinh), nghĩa trống → hỏi người dùng nhập tay. Không bao giờ chặn tạo thẻ.
- **edge-tts lỗi**: thẻ vẫn lưu, đánh dấu thiếu audio, tự thử lại sau; nút 🔊 tạm ẩn.
- **Restart giữa phiên**: phiên ôn trong SQLite, tiếp tục được; scheduler tự tính lại giờ nhắc.
- **CSV lỗi**: báo rõ dòng lỗi, nhập dòng hợp lệ, liệt kê dòng bị bỏ.

## 9. Kiểm thử

- **Unit test bắt buộc**: lõi SM-2 (tính lịch) và parser CSV — sai âm thầm là hỏng cả hệ thống.
- Bot Telegram: test thủ công theo kịch bản (tạo thẻ, ôn, nhắc, backup, restart).

## 10. Ngoài phạm vi bản đầu (ghi nhận cho sau)

- Azure Speech Pronunciation Assessment (khe đã chừa — bật khi có API key).
- Chiều ôn ngược (nghĩa → Hán).
- FSRS thay SM-2.
- Nhiều người dùng.
