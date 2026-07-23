### Task 6: CSV `ví_dụ_thêm` + ingest ví dụ vào kho câu

**Files:**
- Modify: `app/csv_import.py`, `app/bot/csv_flow.py`, `app/bot/create_flow.py`
- Test: `tests/test_csv_import.py` (thêm test)

**Interfaces:**
- Consumes: `sentences.ingest_examples`
- Produces: `CsvRow.extra_examples: str` (chuỗi thô còn nguyên `|`, mặc định `""`); alias header `ví_dụ_thêm|vi_du_them`

- [ ] **Step 1: Thêm test vào `tests/test_csv_import.py` (fail trước)**:

```python
def test_extra_examples_column():
    text = "hán,nghĩa,ví_dụ,ví_dụ_thêm\n学习,to study,我在学习,我们一起学习吧|他学习很努力\n"
    r = parse_csv(text)
    assert r.rows[0].extra_examples == "我们一起学习吧|他学习很努力"
    r2 = parse_csv("hán\n学\n")
    assert r2.rows[0].extra_examples == ""
```

- [ ] **Step 2: Run FAIL**, rồi sửa `app/csv_import.py`: thêm alias `"ví_dụ_thêm": "extra_examples", "vi_du_them": "extra_examples"` vào `_ALIASES`; thêm field `extra_examples: str = ""` vào `CsvRow`; trong vòng lặp append thêm `extra_examples=cell(row, "extra_examples")`.

- [ ] **Step 3: Run PASS** — `python -m pytest tests/test_csv_import.py -v`

- [ ] **Step 4: Nối vào flow.** Trong `app/bot/csv_flow.py`:
  - Sửa `GUIDE`: header mẫu thành `<code>hán,pinyin,nghĩa,ví_dụ,ví_dụ_thêm</code>` và thêm dòng `"Cột <b>ví_dụ_thêm</b>: nhiều câu cho kho luyện tập, ngăn cách bằng dấu |."`
  - Trong `on_callback`, sau nhánh tạo thẻ mới (cả nhánh created lẫn skipped), ingest ví dụ:

```python
    from app import sentences
    # ... trong vòng for, sau khi xử lý created/skipped:
        crow = conn.execute("SELECT id FROM cards WHERE hanzi=? LIMIT 1", (r.hanzi,)).fetchone()
        card_id = crow["id"] if crow else None
        n_sent = 0
        if r.example:
            n_sent += sentences.ingest_examples(conn, r.example, card_id)
        if r.extra_examples:
            n_sent += sentences.ingest_examples(conn, r.extra_examples, card_id)
```

  Cộng dồn `n_sent` vào biến `sent_added` khởi tạo 0 trước vòng lặp; thêm vào báo cáo cuối: `lines.append(f"📚 Thêm {sent_added} câu vào kho luyện tập.")` khi `sent_added > 0`.
  - Trong `app/bot/create_flow.py`, nhánh `pc_save` sau khi `cards.create_card(...)` thành công:

```python
        from app import sentences
        if row["example"]:
            sentences.ingest_examples(conn, row["example"], row["id"])
```

- [ ] **Step 5: Run toàn suite PASS + offline check** — `python -m pytest tests/ -v`; env `BOT_TOKEN=123:dummy OWNER_ID=1` rồi `python -c "from app.bot.main import build_app; build_app()"` không lỗi.
- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: CSV vi_du_them column + example ingestion into sentence bank"`

---

