_CONNECTOR_WORDS = frozenset(('and', 'va', 'и'))


def _compact_keys(value):
    words = value.split()
    joined = ''.join(words)
    without_connectors = ''.join(word for word in words if word not in _CONNECTOR_WORDS)
    return frozenset(key for key in (joined, without_connectors) if key)


def has_compound_match(query_tokens, candidate_keys):
    query_keys = _compact_keys(' '.join(query_tokens))
    candidate_compounds = {
        compound
        for candidate in candidate_keys
        for compound in _compact_keys(candidate)
    }
    return any(
        len(query) >= 6 and any(query in candidate for candidate in candidate_compounds)
        for query in query_keys
    )


def compound_score(query, candidate):
    query_keys = _compact_keys(query)
    candidate_keys = _compact_keys(candidate)
    if any(len(query_key) >= 6 and query_key == candidate for query_key in query_keys for candidate in candidate_keys):
        return 107
    if any(len(query_key) >= 6 and query_key in candidate for query_key in query_keys for candidate in candidate_keys):
        return 101
    return 0
