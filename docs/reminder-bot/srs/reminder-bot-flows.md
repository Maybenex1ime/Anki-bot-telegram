---
type: srs-flows
feature: reminder-bot
updated: 2026-07-23
---

# Reminder Bot — Flows

## Flow: Tạo thẻ mới (Activity)

**Trigger**: Bạn gõ một từ tiếng Trung bất kỳ vào chat với bot.
**Related UC**: [[docs/superpowers/specs/2026-07-22-chinese-srs-telegram-bot-design.md|Spec bot SRS]]
**Related FR**: —
**Related E**: —

```mermaid
flowchart TB
    Start((Bắt đầu)) --> Input[Bạn gõ chữ Hán vào chat]
    Input --> Han{Có ký tự Hán?}
    Han -->|không| Hint[Bot gợi ý gõ /start để xem lệnh]
    Hint --> End((Kết thúc))
    Han -->|có| Lookup[Bot tự sinh pinyin và tra nghĩa tiếng Anh từ từ điển CC-CEDICT]
    Lookup --> Found{Từ điển có nghĩa?}
    Found -->|không| Blank[Để trống nghĩa và nhắc bạn nhập tay]
    Found -->|có| Preview[Bot hiện thẻ xem trước]
    Blank --> Preview
    Preview --> Dup{Đã có thẻ trùng chữ Hán?}
    Dup -->|có| Warn[Hiện cảnh báo trùng ngay trên thẻ xem trước]
    Dup -->|không| Choose{Bạn bấm nút nào?}
    Warn --> Choose
    Choose -->|Sửa pinyin, nghĩa hoặc ví dụ| Edit[Bạn nhập nội dung mới]
    Edit --> Preview
    Choose -->|Gửi ảnh| Img[Đính ảnh vào thẻ đang tạo]
    Img --> Preview
    Choose -->|Đổi bộ| Deck[Chọn bộ thẻ khác]
    Deck --> Preview
    Choose -->|Hủy| Cancel[Bỏ thẻ đang tạo]
    Cancel --> End
    Choose -->|Lưu| Save[Lưu thẻ với hạn ôn ngay hôm nay]
    Save --> Tts[Gọi edge-TTS sinh audio phát âm]
    Tts --> TtsOk{Tạo được audio?}
    TtsOk -->|không| NoAudio[Đánh dấu thiếu audio, tự thử lại khi ôn]
    TtsOk -->|có| Ex[Đổ câu ví dụ của thẻ vào kho luyện tập]
    NoAudio --> Ex
    Ex --> Done[Báo đã lưu thẻ]
    Done --> End
```

## Flow: Ôn tập theo lịch SM-2 (Activity)

**Trigger**: Bạn gõ `/on`, hoặc bấm nút Ôn ngay trong tin nhắn nhắc.
**Related UC**: [[docs/superpowers/specs/2026-07-23-practice-modes-design.md|Spec chế độ luyện tập]]
**Related FR**: —
**Related E**: —

```mermaid
flowchart TB
    Start((Bắt đầu)) --> Cmd[Bạn gõ /on hoặc bấm nút Ôn ngay]
    Cmd --> Due{Có thẻ đến hạn?}
    Due -->|không| Rest[Bot báo không có thẻ nào đến hạn]
    Rest --> End((Kết thúc))
    Due -->|có| Pick[Bạn chọn chế độ cho cả phiên: Lật thẻ, Trắc nghiệm kèm mức Dễ Thường Khó, hoặc Tự luận]
    Pick --> Ask{Hỏi thẻ theo chế độ nào?}
    Ask -->|Lật thẻ| Front[Hiện mặt trước chỉ có chữ Hán]
    Front --> Show[Bạn bấm Xem đáp án, bot hiện pinyin, nghĩa và audio]
    Show --> Self[Bạn tự chấm Lại, Khó, Tốt hoặc Dễ]
    Self --> Apply[Cập nhật lịch ôn kế tiếp theo thuật toán SM-2]
    Ask -->|Trắc nghiệm| Opts{Gom đủ 3 đáp án nhiễu?}
    Opts -->|không| Front
    Opts -->|có| Quiz[Hiện 4 lựa chọn nghĩa, bạn bấm A B C hoặc D]
    Quiz --> Right{Chọn đúng?}
    Right -->|không| Wrong[Máy chấm Lại và chỉ ra đáp án đúng]
    Wrong --> Reveal[Hiện mặt sau đầy đủ kèm audio và ảnh nếu có]
    Right -->|có| Fast{Trả lời nhanh cỡ nào?}
    Fast -->|dưới 5 giây và đang ở mức Khó| Easy[Máy chấm Dễ]
    Fast -->|trong vòng 15 giây| Good[Máy chấm Tốt]
    Fast -->|lâu hơn 15 giây| Hard[Máy chấm Khó]
    Easy --> Reveal
    Good --> Reveal
    Hard --> Reveal
    Ask -->|Tự luận| Type[Bạn gõ nghĩa tiếng Anh của từ]
    Type --> Grade[Máy so khớp nghĩa trên thẻ trước, chưa khớp thì nhờ Gemini chấm, Gemini lỗi thì so từ khóa chính]
    Grade --> Judge{Kết quả chấm}
    Judge -->|đúng| Good2[Máy chấm Tốt và cho nút tự nâng lên Dễ]
    Judge -->|đúng một phần| Hard2[Máy chấm Khó]
    Judge -->|sai| Again2[Máy chấm Lại]
    Good2 --> Reveal
    Hard2 --> Reveal
    Again2 --> Reveal
    Reveal --> Next[Bạn bấm Tiếp]
    Next --> Apply
    Apply --> Loop{Thẻ này bị chấm Lại?}
    Loop -->|có| Requeue[Đẩy thẻ về cuối phiên để hỏi lại]
    Loop -->|không| More{Còn thẻ trong phiên?}
    Requeue --> More
    More -->|có| Ask
    More -->|không| Summary[Báo hoàn thành kèm chuỗi ngày học liên tiếp]
    Summary --> End
```

## Flow: Luyện tự do (Activity)

**Trigger**: Bạn gõ `/luyen` — mọi kết quả ở đây không tác động tới lịch ôn SM-2.
**Related UC**: [[docs/superpowers/specs/2026-07-23-practice-modes-design.md|Spec chế độ luyện tập]]
**Related FR**: —
**Related E**: —

```mermaid
flowchart TB
    Start((Bắt đầu)) --> Cmd[Bạn gõ /luyen]
    Cmd --> Game{Chọn trò nào?}
    Game -->|Trắc nghiệm hoặc Tự luận| Deck[Chọn bộ thẻ, riêng trắc nghiệm chọn thêm mức]
    Deck --> Enough{Đủ thẻ có nghĩa trong phạm vi?}
    Enough -->|không| Warn[Bot báo chưa đủ thẻ]
    Warn --> End((Kết thúc))
    Enough -->|có| Quiz[Hỏi tối đa 10 thẻ ngẫu nhiên, báo đúng sai từng câu]
    Quiz --> NoSrs[Chỉ ghi thống kê luyện tập, giữ nguyên lịch ôn của thẻ]
    NoSrs --> End
    Game -->|Chép chính tả| Bank{Kho câu có câu nào?}
    Bank -->|không| Guide[Hướng dẫn thêm câu ví dụ vào thẻ hoặc đặt Gemini key]
    Guide --> End
    Bank -->|có| Play[Bot gửi audio một câu, bạn gõ lại bằng chữ Hán]
    Play --> Match{Gõ đúng chưa?}
    Match -->|đúng| Ok[Khen đúng và hiện pinyin cùng nghĩa]
    Ok --> NoSrs
    Match -->|sai lần đầu| Diff[Chỉ ra từng ký tự sai và cho thử lại một lần]
    Diff --> Play
    Match -->|sai lần hai| Answer[Hiện đáp án đầy đủ]
    Answer --> NoSrs
    Game -->|Ghép câu| Words{Kho có câu đã tách sẵn từ?}
    Words -->|không| Guide
    Words -->|có| Tap[Bạn bấm từng từ xếp thành câu rồi bấm Nộp]
    Tap --> Same{Khớp đúng câu gốc?}
    Same -->|có| Correct[Báo chính xác]
    Correct --> NoSrs
    Same -->|không| Alt{Gemini xác nhận trật tự vẫn hợp lệ?}
    Alt -->|có| AltOk[Báo cũng đúng kèm ghi chú]
    Alt -->|không| Nope[Báo chưa đúng và hiện câu gốc]
    AltOk --> NoSrs
    Nope --> NoSrs
```

## Flow: Nhắc học theo giờ (Activity)

**Trigger**: Đồng hồ trong bot chạy tới mốc giờ đã đặt trong `/settings`.
**Related UC**: [[docs/superpowers/specs/2026-07-22-chinese-srs-telegram-bot-design.md|Spec bot SRS]]
**Related FR**: —
**Related E**: —

```mermaid
flowchart TB
    Start((Đến mốc giờ đã đặt)) --> Which{Mốc giờ nào?}
    Which -->|Nhắc thường: 7:30, 12:30, 20:00| Due{Có thẻ đến hạn?}
    Due -->|không| Quiet[Im lặng, không nhắn gì cả]
    Quiet --> End((Kết thúc))
    Due -->|có| Ping[Nhắn số thẻ đến hạn kèm nút Ôn ngay]
    Ping --> Tap{Bạn bấm Ôn ngay?}
    Tap -->|có| Session[Mở phiên ôn tập]
    Session --> End
    Tap -->|không| End
    Which -->|Nhắc cuối ngày lúc 21:30| Did{Hôm nay đã ôn câu nào chưa?}
    Did -->|rồi| Quiet
    Did -->|chưa| Left{Còn thẻ đến hạn?}
    Left -->|không| Quiet
    Left -->|có| Streak[Nhắn cảnh báo sắp mất chuỗi ngày học liên tiếp]
    Streak --> Tap
```

## Flow: Nhập thẻ hàng loạt từ CSV (Activity)

**Trigger**: Bạn gửi file `.csv` vào chat với bot.
**Related UC**: [[docs/superpowers/specs/2026-07-23-practice-modes-design.md|Spec chế độ luyện tập]]
**Related FR**: —
**Related E**: —

```mermaid
flowchart TB
    Start((Bắt đầu)) --> Send[Bạn gửi file csv vào chat]
    Send --> Enc{File đọc được dạng UTF-8?}
    Enc -->|không| Err[Báo lỗi và nhắc lưu lại file bằng UTF-8]
    Err --> End((Kết thúc))
    Enc -->|có| Head{Dòng đầu có cột hán?}
    Head -->|không| Err2[Báo thiếu cột hán trong dòng tiêu đề]
    Err2 --> End
    Head -->|có| Deck[Bạn chọn bộ thẻ đích]
    Deck --> Row[Đọc từng dòng dữ liệu]
    Row --> Blank{Dòng có chữ Hán?}
    Blank -->|không| Skip[Ghi nhận dòng lỗi rồi bỏ qua]
    Skip --> Next{Còn dòng nào nữa?}
    Blank -->|có| Exist{Thẻ này đã có trong kho?}
    Exist -->|có| Dup[Bỏ qua vì trùng]
    Dup --> Ex[Đổ câu ở cột ví dụ và ví dụ thêm vào kho luyện tập]
    Exist -->|không| Create[Tạo thẻ mới, tự tra phần bỏ trống và sinh audio]
    Create --> Ex
    Ex --> Next
    Next -->|có| Row
    Next -->|không| Report[Báo cáo số thẻ mới, thẻ trùng, câu đã thêm và các dòng lỗi]
    Report --> End
```
