import re
import unicodedata
from collections import defaultdict
from functools import lru_cache


_ENGLISH_KEYS = "qwertyuiop[]asdfghjkl;'zxcvbnm,."
_RUSSIAN_KEYS = 'йцукенгшщзхъфывапролджэячсмитьбю'
_ENGLISH_TO_RUSSIAN = str.maketrans(_ENGLISH_KEYS, _RUSSIAN_KEYS)
_RUSSIAN_TO_ENGLISH = str.maketrans(_RUSSIAN_KEYS, _ENGLISH_KEYS)
_CYRILLIC_TO_LATIN = str.maketrans({
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'қ': 'q', 'ғ': 'g', 'ҳ': 'h', 'ў': 'o',
})
_WHITESPACE = re.compile(r'\s+')


def smart_product_ids(queryset, query):
    """Return matching product IDs ordered by forgiving search relevance."""
    fields_by_product = defaultdict(list)
    rows = queryset.values(
        'pk', 'name_ru', 'name_uz', 'brand__name',
        'category__name_ru', 'category__name_uz',
    )
    for row in rows:
        fields_by_product[row['pk']].extend((
            row['name_ru'], row['name_uz'], row['brand__name'],
            row['category__name_ru'], row['category__name_uz'],
        ))

    ranked = []
    for product_id, fields in fields_by_product.items():
        score = smart_search_score(query, fields)
        if score:
            ranked.append((score, product_id))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [product_id for _, product_id in ranked]


def smart_search_score(query, fields):
    query_keys = _search_keys(query, keyboard_variants=True)
    if not query_keys:
        return 0

    best = 0
    for field in fields:
        for candidate in _search_keys(field):
            for query_key in query_keys:
                best = max(best, _pair_score(query_key, candidate))
                if best >= 108:
                    return best
    return best


@lru_cache(maxsize=32768)
def _search_keys(value, keyboard_variants=False):
    normalized = _normalize(value)
    if len(normalized) < 2:
        return frozenset()

    variants = {normalized, _transliterate(normalized)}
    if keyboard_variants:
        if re.search(r'[a-z]', normalized) and not re.search(r'[а-яё]', normalized):
            corrected = _normalize(normalized.translate(_ENGLISH_TO_RUSSIAN))
            variants.update((corrected, _transliterate(corrected)))
        elif re.search(r'[а-яё]', normalized) and not re.search(r'[a-z]', normalized):
            corrected = _normalize(normalized.translate(_RUSSIAN_TO_ENGLISH))
            variants.update((corrected, _transliterate(corrected)))
    return frozenset(variant for variant in variants if len(variant) >= 2)


def _normalize(value):
    if not isinstance(value, str):
        return ''
    decomposed = unicodedata.normalize('NFKD', value.casefold().replace('ё', 'е'))
    plain = ''.join(character for character in decomposed if not unicodedata.combining(character))
    safe = ''.join(character if character.isalnum() else ' ' for character in plain)
    return _WHITESPACE.sub(' ', safe).strip()


def _transliterate(value):
    return _WHITESPACE.sub(' ', value.translate(_CYRILLIC_TO_LATIN)).strip()


def _pair_score(query, candidate):
    if query == candidate:
        return 120
    if candidate.startswith(query):
        return 112
    if query in candidate.split():
        return 108
    if query in candidate:
        return max(94, 106 - candidate.index(query))

    query_tokens = query.split()
    candidate_tokens = candidate.split()
    token_scores = [
        max((_token_ratio(token, candidate_token) for candidate_token in candidate_tokens), default=0)
        for token in query_tokens
    ]
    threshold = _fuzzy_threshold(min(map(len, query_tokens)))
    if token_scores and min(token_scores) >= threshold:
        return round(70 + (sum(token_scores) / len(token_scores)) * 30)

    whole_ratio = _edit_ratio(query, candidate)
    return round(58 + whole_ratio * 30) if whole_ratio >= _fuzzy_threshold(len(query)) else 0


def _token_ratio(query, candidate):
    if query == candidate:
        return 1
    if candidate.startswith(query) or query.startswith(candidate):
        shorter = min(len(query), len(candidate))
        longer = max(len(query), len(candidate))
        return max(_edit_ratio(query, candidate), shorter / longer)
    return _edit_ratio(query, candidate)


def _edit_ratio(left, right):
    """Fast typo similarity with adjacent-letter transposition support."""
    if left == right:
        return 1
    longest = max(len(left), len(right))
    if not longest:
        return 1

    maximum_distance = max(1, round(longest * .36))
    if abs(len(left) - len(right)) > maximum_distance:
        return 0

    previous_previous = None
    previous = list(range(len(right) + 1))
    for row, left_character in enumerate(left, start=1):
        current = [row]
        for column, right_character in enumerate(right, start=1):
            substitution_cost = 0 if left_character == right_character else 1
            distance = min(
                current[column - 1] + 1,
                previous[column] + 1,
                previous[column - 1] + substitution_cost,
            )
            if (
                previous_previous is not None
                and column > 1
                and left_character == right[column - 2]
                and left[row - 2] == right_character
            ):
                distance = min(distance, previous_previous[column - 2] + 1)
            current.append(distance)
        if min(current) > maximum_distance:
            return 0
        previous_previous, previous = previous, current

    distance = previous[-1]
    return 0 if distance > maximum_distance else 1 - (distance / longest)


def _fuzzy_threshold(length):
    if length <= 3:
        return .84
    if length <= 5:
        return .76
    return .68
