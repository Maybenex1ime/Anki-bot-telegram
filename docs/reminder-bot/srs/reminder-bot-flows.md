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
    TtsOk -->|có| HasEx{Thẻ có câu ví dụ?}
    NoAudio --> HasEx
    HasEx -->|có| Ex[Đổ câu ví dụ vào kho luyện tập]
    HasEx -->|không| Done[Báo đã lưu thẻ]
    Ex --> Done
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
    Due -->|có| Pick[Chọn chế độ cho cả phiên: Lật thẻ, Trắc nghiệm kèm mức Dễ Thường Khó, Tự luận, hoặc bấm lối tắt Như lần trước]
    Pick --> Ask{Hỏi thẻ theo chế độ nào?}
    Ask -->|Lật thẻ| Front[Hiện mặt trước chỉ có chữ Hán]
    Front -->|Bấm nút Nghe| Sound[Phát audio phát âm, thẻ chưa có audio thì báo chưa có]
    Sound --> Front
    Front -->|Bấm Xem đáp án| Show[Hiện pinyin, nghĩa, audio và ảnh nếu có]
    Show -->|Bấm Thu âm thử| Rec[Bạn gửi tin nhắn thoại, bot phát lại giọng chuẩn và giọng bạn để tự so]
    Rec --> Show
    Show -->|Tự chấm| Self[Bạn chọn Lại, Khó, Tốt hoặc Dễ]
    Self --> Apply[Cập nhật lịch ôn kế tiếp theo thuật toán SM-2]
    Ask -->|Trắc nghiệm| Opts{Gom đủ 3 đáp án nhiễu?}
    Opts -->|không| Front
    Opts -->|có| Quiz[Hiện 4 lựa chọn nghĩa, bạn bấm A B C hoặc D]
    Quiz --> Right{Chọn đúng?}
    Right -->|không| Wrong[Máy chấm Lại và chỉ ra đáp án đúng]
    Wrong --> Reveal[Hiện mặt sau đầy đủ kèm audio và ảnh nếu có]
    Right -->|có| Fast{Trả lời nhanh cỡ nào? Ngưỡng cấu hình được, mặc định 5 và 15 giây}
    Fast -->|trong 5 giây và đang ở mức Khó| Easy[Máy chấm Dễ]
    Fast -->|trong 15 giây| Good[Máy chấm Tốt]
    Fast -->|trên 15 giây| Hard[Máy chấm Khó]
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
    Deck --> Enough{Đủ thẻ có nghĩa? Trắc nghiệm cần ít nhất 4 thẻ, tự luận cần 1}
    Enough -->|không| Warn[Bot báo chưa đủ thẻ]
    Warn --> End((Kết thúc))
    Enough -->|có| Quiz[Hỏi tối đa 10 thẻ ngẫu nhiên, chấm đúng sai từng câu, thẻ nào không gom đủ đáp án nhiễu thì bỏ qua]
    Quiz --> NoSrs[Chỉ ghi thống kê luyện tập, giữ nguyên lịch ôn của thẻ]
    NoSrs --> End
    Game -->|Chép chính tả| Bank{Kho câu có câu nào?}
    Bank -->|không| Guide[Hướng dẫn thêm câu ví dụ vào thẻ hoặc đặt Gemini key]
    Guide --> End
    Bank -->|có| Snd{Tạo được audio cho câu?}
    Snd -->|không| SndErr[Báo lỗi mạng và dừng lượt này]
    SndErr --> End
    Snd -->|có| Play[Bot gửi audio, bạn gõ lại bằng chữ Hán]
    Play -->|Bấm Nghe lại| Play
    Play -->|Bấm Bỏ qua| Bank
    Play -->|Gõ câu trả lời| Match{Gõ đúng chưa?}
    Match -->|đúng| Ok[Khen đúng và hiện pinyin cùng nghĩa]
    Ok --> DStat[Ghi thống kê chính tả]
    Match -->|sai lần đầu| Diff[Chỉ ra từng ký tự sai và cho thử lại một lần]
    Diff --> Play
    Match -->|sai lần hai| Answer[Hiện đáp án đầy đủ]
    Answer --> DStat
    DStat --> DNext{Bấm Câu tiếp hay Dừng?}
    DNext -->|Câu tiếp| Bank
    DNext -->|Dừng| End
    Game -->|Ghép câu| Words{Kho có câu đã tách sẵn từ?}
    Words -->|không| Guide
    Words -->|có| Tap[Bấm từng từ để xếp thành câu]
    Tap -->|Bấm Xóa từ cuối| Tap
    Tap -->|Bấm Nộp khi chưa dùng hết từ| Toast[Nhắc dùng hết các từ rồi mới nộp]
    Toast --> Tap
    Tap -->|Bấm Bỏ qua| Reveal[Hiện câu gốc kèm pinyin và nghĩa]
    Tap -->|Bấm Nộp| Same{Khớp đúng câu gốc?}
    Same -->|có| Correct[Báo chính xác]
    Correct --> BStat[Ghi thống kê ghép câu]
    Same -->|không| Alt{Gemini xác nhận trật tự vẫn hợp lệ?}
    Alt -->|có| AltOk[Báo cũng đúng kèm ghi chú]
    Alt -->|không| Nope[Báo chưa đúng và hiện câu gốc]
    AltOk --> BStat
    Nope --> BStat
    Reveal --> BNext
    BStat --> BNext{Bấm Câu tiếp hay Dừng?}
    BNext -->|Câu tiếp| Words
    BNext -->|Dừng| End
```

## Flow: Nhắc học theo giờ (Activity)

**Trigger**: Đồng hồ trong bot chạy tới mốc giờ đã đặt trong `/settings`.
**Related UC**: [[docs/superpowers/specs/2026-07-22-chinese-srs-telegram-bot-design.md|Spec bot SRS]]
**Related FR**: —
**Related E**: —

```mermaid
flowchart TB
    Start((Đến mốc giờ đã đặt)) --> Which{Mốc giờ nào?}
    Which -->|Nhắc trong ngày, mặc định 7:30 12:30 20:00| Due{Có thẻ đến hạn?}
    Due -->|không| Quiet[Im lặng, không nhắn gì cả]
    Quiet --> End((Kết thúc))
    Due -->|có| Ping[Nhắn số thẻ đến hạn kèm số thẻ mới và nút Ôn ngay]
    Ping --> Tap{Bạn bấm Ôn ngay?}
    Tap -->|có| Session[Mở phiên ôn tập]
    Session --> End
    Tap -->|không| End
    Which -->|Nhắc cuối ngày, mặc định 21:30, tắt được trong settings| Did{Hôm nay đã ôn câu nào chưa?}
    Did -->|rồi| Quiet
    Did -->|chưa| Left{Còn thẻ đến hạn?}
    Left -->|không| Quiet
    Left -->|có| Streak{Đang có chuỗi ngày học?}
    Streak -->|có| Flame[Nhắn cảnh báo sắp mất chuỗi kèm số thẻ còn chờ]
    Streak -->|chưa có| Plain[Nhắn nhắc nhẹ kèm số thẻ còn chờ]
    Flame --> Tap
    Plain --> Tap
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
    Enc -->|có| Deck[Bạn chọn bộ thẻ đích]
    Deck --> Head{Dòng đầu có cột hán?}
    Head -->|không| Report[Báo cáo số thẻ mới, thẻ trùng, câu đã thêm và các dòng lỗi]
    Head -->|có| Row[Đọc từng dòng dữ liệu]
    Row --> Blank{Dòng có dữ liệu?}
    Blank -->|không| Empty[Bỏ qua lặng lẽ, không tính là dòng lỗi]
    Empty --> Next{Còn dòng nào nữa?}
    Blank -->|có| HasHan{Ô chữ Hán có nội dung?}
    HasHan -->|không| BadRow[Ghi nhận dòng lỗi để báo cáo cuối]
    BadRow --> Next
    HasHan -->|có| Exist{Thẻ này đã có trong kho?}
    Exist -->|có| Dup[Bỏ qua vì trùng]
    Dup --> Ex[Đổ câu ở cột ví dụ và ví dụ thêm vào kho luyện tập]
    Exist -->|không| Create[Tạo thẻ mới, tự tra phần bỏ trống và sinh audio]
    Create --> Ex
    Ex --> Next
    Next -->|có| Row
    Next -->|không| Report
    Report --> End
```
