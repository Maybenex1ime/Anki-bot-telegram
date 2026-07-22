### Task 6: Stats & streak (`app/stats.py`)

**Files:** Create `app/stats.py`; Test `tests/test_stats.py`

**Interfaces:**
- Consumes: bảng `daily_log`, `cards`
- Produces: `stats.bump_review(conn, day_iso: str, was_new: bool)`; `stats.reviews_today(conn, day_iso) -> int`; `stats.new_used_today(conn, day_iso) -> int`; `stats.streak(conn, today: date) -> int` (hôm nay chưa ôn thì tính chuỗi kết thúc hôm qua); `stats.overview(conn, today_iso) -> dict` với khóa `total, due, new_waiting, streak, total_reviews, total_lapses`

- [ ] **Step 1: Viết test (fail trước)**

`tests/test_stats.py`:
```python
from datetime import date

from app import db, stats


def make(tmp_path):
    return db.connect(tmp_path / "t.db")


def test_bump_and_counts(tmp_path):
    conn = make(tmp_path)
    stats.bump_review(conn, "2026-07-22", was_new=True)
    stats.bump_review(conn, "2026-07-22", was_new=False)
    assert stats.reviews_today(conn, "2026-07-22") == 2
    assert stats.new_used_today(conn, "2026-07-22") == 1
    assert stats.reviews_today(conn, "2026-07-23") == 0


def test_streak_counts_consecutive_days(tmp_path):
    conn = make(tmp_path)
    for d in ["2026-07-19", "2026-07-20", "2026-07-21"]:
        stats.bump_review(conn, d, was_new=False)
    # hôm nay 22 chưa ôn -> chuỗi kết thúc hôm qua vẫn là 3
    assert stats.streak(conn, date(2026, 7, 22)) == 3
    stats.bump_review(conn, "2026-07-22", was_new=False)
    assert stats.streak(conn, date(2026, 7, 22)) == 4


def test_streak_broken(tmp_path):
    conn = make(tmp_path)
    stats.bump_review(conn, "2026-07-15", was_new=False)
    assert stats.streak(conn, date(2026, 7, 22)) == 0
```

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_stats.py -v`

- [ ] **Step 3: Viết `app/stats.py`**

```python
from datetime import timedelta


def bump_review(conn, day_iso, was_new):
    conn.execute(
        "INSERT INTO daily_log(day, reviews, new_introduced) VALUES(?, 1, ?) "
        "ON CONFLICT(day) DO UPDATE SET reviews=reviews+1, "
        "new_introduced=new_introduced+excluded.new_introduced",
        (day_iso, 1 if was_new else 0))
    conn.commit()


def reviews_today(conn, day_iso):
    row = conn.execute("SELECT reviews FROM daily_log WHERE day=?", (day_iso,)).fetchone()
    return row["reviews"] if row else 0


def new_used_today(conn, day_iso):
    row = conn.execute("SELECT new_introduced FROM daily_log WHERE day=?", (day_iso,)).fetchone()
    return row["new_introduced"] if row else 0


def streak(conn, today):
    days = {r["day"] for r in conn.execute("SELECT day FROM daily_log WHERE reviews>0")}
    d = today
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def overview(conn, today_iso):
    from datetime import date
    total = conn.execute("SELECT COUNT(*) c FROM cards").fetchone()["c"]
    due = conn.execute(
        "SELECT COUNT(*) c FROM cards WHERE due_date<=? AND NOT(repetitions=0 AND lapses=0)",
        (today_iso,)).fetchone()["c"]
    new_waiting = conn.execute(
        "SELECT COUNT(*) c FROM cards WHERE repetitions=0 AND lapses=0 AND due_date<=?",
        (today_iso,)).fetchone()["c"]
    agg = conn.execute("SELECT COALESCE(SUM(repetitions),0) r, COALESCE(SUM(lapses),0) l FROM cards").fetchone()
    return {
        "total": total, "due": due, "new_waiting": new_waiting,
        "streak": streak(conn, date.fromisoformat(today_iso)),
        "total_reviews": agg["r"], "total_lapses": agg["l"],
    }
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_stats.py -v`
- [ ] **Step 5: Commit** — `git commit -am "feat: daily log, streak, stats overview"`

---

