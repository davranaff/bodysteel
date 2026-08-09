import re


LANGUAGE_RANGE = re.compile(r'^(ru(?:-RU)?|uz(?:-UZ)?)$', re.IGNORECASE)
QUALITY = re.compile(r'^q=(0(?:\.\d{0,3})?|1(?:\.0{0,3})?)$', re.IGNORECASE)


def select_supported_language(header):
    if not isinstance(header, str) or not header or len(header) > 512:
        raise ValueError('unsupported language')
    candidates = []
    for order, raw_range in enumerate(header.split(',')):
        parsed = _parse_range(raw_range.strip(), order)
        if parsed is not None:
            candidates.append(parsed)
    if not candidates:
        raise ValueError('unsupported language')
    return max(candidates, key=lambda item: (item[0], -item[1]))[2]


def _parse_range(value, order):
    parts = [part.strip() for part in value.split(';')]
    if not parts or len(parts) > 2:
        return None
    match = LANGUAGE_RANGE.fullmatch(parts[0])
    if not match:
        return None
    quality = 1.0
    if len(parts) == 2:
        quality_match = QUALITY.fullmatch(parts[1])
        if not quality_match:
            return None
        quality = float(quality_match.group(1))
    if quality == 0:
        return None
    return quality, order, match.group(1)[:2].lower()
