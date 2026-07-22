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
