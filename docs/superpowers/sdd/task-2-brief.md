### Task 2: SM-2 (`app/srs.py`)

**Files:** Create `app/srs.py`; Test `tests/test_srs.py`

**Interfaces:**
- Produces: hằng `srs.AGAIN=1, HARD=2, GOOD=3, EASY=4`; `@dataclass SrsState(interval: float=0.0, ease: float=2.5, repetitions: int=0, lapses: int=0)`; `srs.review(state: SrsState, rating: int, today: date) -> tuple[SrsState, date]` (trả state MỚI, không sửa state cũ; date = due mới).

- [ ] **Step 1: Viết test (fail trước)**

`tests/test_srs.py`:
```python
from datetime import date, timedelta

import pytest

from app.srs import AGAIN, EASY, GOOD, HARD, SrsState, review

TODAY = date(2026, 7, 22)


def test_new_card_good_gives_1_day():
    s, due = review(SrsState(), GOOD, TODAY)
    assert (s.interval, s.repetitions) == (1.0, 1)
    assert due == TODAY + timedelta(days=1)


def test_second_good_gives_3_days():
    s1, _ = review(SrsState(), GOOD, TODAY)
    s2, due = review(s1, GOOD, TODAY)
    assert s2.interval == 3.0
    assert due == TODAY + timedelta(days=3)


def test_third_good_multiplies_by_ease():
    s = SrsState(interval=3.0, ease=2.5, repetitions=2)
    s2, due = review(s, GOOD, TODAY)
    assert s2.interval == pytest.approx(7.5)
    assert due == TODAY + timedelta(days=8)  # 7.5 làm tròn nửa-lên = 8 (xem note làm tròn dưới)


def test_again_resets_and_stays_today():
    s = SrsState(interval=20.0, ease=2.5, repetitions=5)
    s2, due = review(s, AGAIN, TODAY)
    assert (s2.interval, s2.repetitions, s2.lapses) == (1.0, 0, 1)
    assert s2.ease == pytest.approx(2.3)
    assert due == TODAY  # lặp lại ngay trong phiên hôm nay


def test_hard_grows_slow_and_drops_ease():
    s = SrsState(interval=10.0, ease=2.5, repetitions=3)
    s2, due = review(s, HARD, TODAY)
    assert s2.interval == pytest.approx(12.0)
    assert s2.ease == pytest.approx(2.35)
    assert due == TODAY + timedelta(days=12)


def test_easy_boosts():
    s = SrsState(interval=3.0, ease=2.5, repetitions=2)
    s2, _ = review(s, EASY, TODAY)
    assert s2.ease == pytest.approx(2.65)
    assert s2.interval == pytest.approx(3.0 * 2.65 * 1.3)


def test_ease_floor():
    s = SrsState(interval=5.0, ease=1.3, repetitions=3)
    s2, _ = review(s, AGAIN, TODAY)
    assert s2.ease == 1.3


def test_input_state_not_mutated():
    s = SrsState(interval=5.0, ease=2.0, repetitions=2)
    review(s, GOOD, TODAY)
    assert (s.interval, s.ease, s.repetitions) == (5.0, 2.0, 2)
```

**Lưu ý làm tròn:** dùng `int(x + 0.5)` (làm tròn nửa-lên), KHÔNG dùng `round()` (banker's rounding của Python cho `round(7.5) == 8` nhưng `round(8.5) == 8`). Test số 3 kỳ vọng 7.5 → 8 ngày.

- [ ] **Step 2: Run FAIL** — `python -m pytest tests/test_srs.py -v`

- [ ] **Step 3: Viết `app/srs.py`**

```python
from dataclasses import dataclass, replace
from datetime import date, timedelta

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
MIN_EASE = 1.3


@dataclass(frozen=True)
class SrsState:
    interval: float = 0.0
    ease: float = 2.5
    repetitions: int = 0
    lapses: int = 0


def review(state: SrsState, rating: int, today: date) -> tuple[SrsState, date]:
    if rating == AGAIN:
        s = replace(state, interval=1.0, repetitions=0,
                    lapses=state.lapses + 1,
                    ease=max(MIN_EASE, state.ease - 0.20))
        return s, today  # lặp lại ngay trong phiên hôm nay
    if rating == HARD:
        interval = 1.0 if state.repetitions == 0 else max(state.interval * 1.2, state.interval + 1)
        s = replace(state, interval=interval, repetitions=state.repetitions + 1,
                    ease=max(MIN_EASE, state.ease - 0.15))
    elif rating == GOOD:
        if state.repetitions == 0:
            interval = 1.0
        elif state.repetitions == 1:
            interval = 3.0
        else:
            interval = state.interval * state.ease
        s = replace(state, interval=interval, repetitions=state.repetitions + 1)
    elif rating == EASY:
        ease = state.ease + 0.15
        interval = 4.0 if state.repetitions == 0 else state.interval * ease * 1.3
        s = replace(state, interval=interval, repetitions=state.repetitions + 1, ease=ease)
    else:
        raise ValueError(f"rating không hợp lệ: {rating}")
    days = max(1, int(s.interval + 0.5))
    return s, today + timedelta(days=days)
```

- [ ] **Step 4: Run PASS** — `python -m pytest tests/test_srs.py -v`
- [ ] **Step 5: Commit** — `git commit -am "feat: SM-2 scheduler (pure functions)"`

---

