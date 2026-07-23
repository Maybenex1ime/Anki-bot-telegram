import random

from app import grading, srs


def test_variants_and_normalize():
    assert grading.meaning_variants("to learn; to study | learning") == \
        ["to learn", "to study", "learning"]
    assert grading.normalize_meaning("To Learn (a skill)!") == "learn"
    assert grading.normalize_meaning("AT&T [company]") == "at&t"


def test_grade_typed_offline():
    m = "to learn; to study"
    assert grading.grade_typed_offline(m, "study") == "correct"
    assert grading.grade_typed_offline(m, "To Learn") == "correct"
    assert grading.grade_typed_offline(m, "acquire knowledge") == "unsure"


def test_fallback_partial():
    m = "to learn; to study a subject"
    assert grading.fallback_partial(m, "study hard") == "partial"
    assert grading.fallback_partial(m, "the a of") == "wrong"
    assert grading.fallback_partial(m, "banana") == "wrong"


def test_time_to_rating():
    assert grading.time_to_rating(False, 1, "hard", 5, 15) == srs.AGAIN
    assert grading.time_to_rating(True, 20, "easy", 5, 15) == srs.HARD
    assert grading.time_to_rating(True, 10, "easy", 5, 15) == srs.GOOD
    assert grading.time_to_rating(True, 4, "hard", 5, 15) == srs.EASY
    assert grading.time_to_rating(True, 4, "easy", 5, 15) == srs.GOOD  # fast nhưng không phải hard
    assert grading.time_to_rating(True, 15, "hard", 5, 15) == srs.GOOD  # biên slow


def test_normalize_hanzi():
    assert grading.normalize_hanzi("我在 学习。中文！") == "我在学习中文"


def test_diff_chars_correct_and_wrong():
    html_out, ok, total = grading.diff_chars("我在学习", "我在学习")
    assert (ok, total) == (4, 4) and "<s>" not in html_out
    html_out, ok, total = grading.diff_chars("我在学习", "我再学习")
    assert (ok, total) == (3, 4)
    assert "<s>再</s>" in html_out and "<u>在</u>" in html_out
    html_out, ok, total = grading.diff_chars("我学习", "我的学习")   # thừa 的
    assert "<s>的</s>" in html_out and ok == 3
    html_out, ok, total = grading.diff_chars("我在学习", "我学习")   # thiếu 在
    assert "<u>在</u>" in html_out and ok == 3


def test_shuffle_words():
    rng = random.Random(42)
    words = ["我", "在", "学习", "中文"]
    perm = grading.shuffle_words(words, rng)
    assert sorted(perm) == [0, 1, 2, 3] and perm != [0, 1, 2, 3]
    assert grading.shuffle_words(["一"], rng) == [0]
