import html
import re
from difflib import SequenceMatcher

from app import srs

STOPWORDS = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "and",
             "or", "is", "are", "be", "it", "its", "sth", "sb", "one", "ones",
             "something", "somebody", "someone"}
_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_PUNCT = re.compile(r"[^\w\s&']", re.UNICODE)
_HANZI_PUNCT = "。，！？、；：“”‘’…·.,!?;:'\"()（）"


def meaning_variants(meaning):
    parts = re.split(r"[;|,]", meaning)
    return [p.strip() for p in parts if p.strip()]


def normalize_meaning(s):
    s = _PAREN.sub(" ", s.lower())
    s = _PUNCT.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("to "):
        s = s[3:]
    return s


def _content_words(s):
    return {w for w in normalize_meaning(s).split() if w not in STOPWORDS}


def grade_typed_offline(card_meaning, answer):
    ans = normalize_meaning(answer)
    if not ans:
        return "unsure"
    for v in meaning_variants(card_meaning):
        if normalize_meaning(v) == ans:
            return "correct"
    return "unsure"


def fallback_partial(card_meaning, answer):
    ans_words = _content_words(answer)
    if not ans_words:
        return "wrong"
    for v in meaning_variants(card_meaning):
        if ans_words & _content_words(v):
            return "partial"
    return "wrong"


def time_to_rating(correct, elapsed, level, fast, slow):
    if not correct:
        return srs.AGAIN
    if elapsed <= fast and level == "hard":
        return srs.EASY
    if elapsed <= slow:
        return srs.GOOD
    return srs.HARD


def normalize_hanzi(s):
    return "".join(c for c in s if not c.isspace() and c not in _HANZI_PUNCT)


def diff_chars(expected, got):
    out, ok = [], 0
    for op, i1, i2, j1, j2 in SequenceMatcher(None, expected, got).get_opcodes():
        if op == "equal":
            out.append(html.escape(expected[i1:i2]))
            ok += i2 - i1
        elif op == "delete":      # thiếu ký tự
            out.append(f"<u>{html.escape(expected[i1:i2])}</u>")
        elif op == "insert":      # thừa ký tự
            out.append(f"<s>{html.escape(got[j1:j2])}</s>")
        else:                     # replace: sai — hiện cả hai
            out.append(f"<s>{html.escape(got[j1:j2])}</s><u>{html.escape(expected[i1:i2])}</u>")
    return "".join(out), ok, len(expected)


def shuffle_words(words, rng):
    idx = list(range(len(words)))
    if len(idx) < 2:
        return idx
    for _ in range(10):
        perm = rng.sample(idx, len(idx))
        if perm != idx:
            return perm
    return list(reversed(idx))
