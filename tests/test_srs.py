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
