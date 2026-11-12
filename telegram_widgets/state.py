"""Widget chat state and request answers: compact JSON of at most 1024 UTF-8 bytes."""
import json


MAXIMUM_STATE_BYTES = 1024
MAXIMUM_REQUEST_BYTES = 64


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def size(value):
    return len(encode(value).encode('utf-8'))


def fits(value):
    return size(value) <= MAXIMUM_STATE_BYTES


def clip(text, maximum_bytes):
    """Cut ``text`` to at most ``maximum_bytes`` of UTF-8 without splitting a character."""
    value = ' '.join(str(text or '').split())
    if len(value.encode('utf-8')) <= maximum_bytes:
        return value
    cut = value.encode('utf-8')[:max(0, maximum_bytes - 3)].decode('utf-8', 'ignore').rstrip()
    return cut + '…'


def fit_rows(state, key, rows, title=1, budgets=(96, 64, 44, 24)):
    """Put as many ``rows`` into ``state[key]`` as fit, shortening row titles first.

    ``title`` is the index of each row's title. Returns how many rows were left out so
    the widget can say "+N".
    """
    best_count, best_rows = -1, []
    for budget in budgets:
        shortened = [
            [clip(value, budget) if index == title else value for index, value in enumerate(row)]
            for row in rows
        ]
        count = len(shortened)
        while count and not fits({**state, key: shortened[:count]}):
            count -= 1
        if count > best_count:
            best_count, best_rows = count, shortened[:count]
        if count == len(rows):
            break
    state[key] = best_rows
    return len(rows) - max(best_count, 0)


def valid_request(data):
    return isinstance(data, str) and 0 < len(data.encode('utf-8')) <= MAXIMUM_REQUEST_BYTES
