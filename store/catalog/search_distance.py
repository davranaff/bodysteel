"""Typo similarity between search words.

Ratios run from 0 (unrelated) to 1 (equal). ``fuzzy_threshold`` is the ratio a
single word needs; ``phrase_score`` accepts weaker words when several of them
line up with neighbouring words of a product name, as in a brand typed by ear
("кеатн ливрн" for "Кевин Леврон").
"""
from functools import lru_cache

from rapidfuzz.distance import DamerauLevenshtein


# A word in a phrase may be this far off when its neighbours confirm it.
_PHRASE_WORD_RATIO = .55
_PHRASE_RATIO = .6


@lru_cache(maxsize=1 << 17)
def token_ratio(query, candidate):
    if query == candidate:
        return 1
    if candidate.startswith(query) or query.startswith(candidate):
        shorter = min(len(query), len(candidate))
        longer = max(len(query), len(candidate))
        return max(edit_ratio(query, candidate), shorter / longer)
    return edit_ratio(query, candidate)


def edit_ratio(left, right):
    """Fast typo similarity with adjacent-letter transposition support."""
    if left == right:
        return 1
    longest = max(len(left), len(right))
    if not longest:
        return 1

    maximum_distance = max(1, round(longest * .36))
    if abs(len(left) - len(right)) > maximum_distance:
        return 0
    # Word pairs repeat across products and spellings, so token_ratio is cached;
    # rapidfuzz stops early once the distance passes the cutoff.
    distance = DamerauLevenshtein.distance(left, right, score_cutoff=maximum_distance)
    return 0 if distance > maximum_distance else 1 - (distance / longest)


def fuzzy_threshold(length):
    if length <= 3:
        return .84
    if length == 4:
        return .75
    if length <= 5:
        return .76
    return .68


def phrase_score(query_tokens, candidate_tokens):
    """Score two or more misspelt words that match neighbouring words in order.

    A short word (three letters or fewer) must start its partner; a longer one must
    share its first letter. Scores stay below the per-word fuzzy matches (70+).
    """
    count = len(query_tokens)
    if count < 2 or count > len(candidate_tokens):
        return 0
    letters = sum(len(token) for token in query_tokens)
    best = 0
    for start in range(len(candidate_tokens) - count + 1):
        window = candidate_tokens[start:start + count]
        ratios = [_phrase_word_ratio(query, candidate) for query, candidate in zip(query_tokens, window)]
        if min(ratios) < _PHRASE_WORD_RATIO:
            continue
        ratio = sum(value * len(token) for value, token in zip(ratios, query_tokens)) / letters
        if ratio >= _PHRASE_RATIO:
            best = max(best, round(60 + ratio * 30))
    return best


def _phrase_word_ratio(query, candidate):
    if len(query) <= 3:
        return 1 if candidate.startswith(query) else 0
    if query[0] != candidate[0]:
        return 0
    return token_ratio(query, candidate)
