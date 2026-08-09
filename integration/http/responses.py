import hashlib
import json
from urllib.parse import urlencode

from django.http import HttpResponse


def problem_response(problem, request_id):
    return json_response(
        {
            'type': 'about:blank',
            'title': problem.title,
            'status': problem.status,
            'detail': problem.detail,
            'requestId': request_id,
        },
        status=problem.status,
        content_type='application/problem+json',
        headers=problem.headers,
    )


def localized_entity_response(request, value, language, request_id):
    body = _json_bytes(value)
    representation = _representation_key(request, language).encode('utf-8') + b'\0' + body
    etag = '"sha256-{}"'.format(hashlib.sha256(representation).hexdigest())
    headers = _localized_headers(language, request_id)
    headers.update({'ETag': etag, 'Cache-Control': 'private, no-cache'})
    if _matches_etag(request.headers.get('If-None-Match'), etag):
        return HttpResponse(status=304, headers=headers)
    return HttpResponse(body, status=200, content_type='application/json', headers=headers)


def localized_json_response(value, language, request_id, status):
    headers = _localized_headers(language, request_id)
    headers['Cache-Control'] = 'no-store'
    return HttpResponse(
        _json_bytes(value),
        status=status,
        content_type='application/json',
        headers=headers,
    )


def json_response(value, status=200, content_type='application/json', headers=None):
    response_headers = {'Cache-Control': 'no-store', **(headers or {})}
    return HttpResponse(_json_bytes(value), status=status, content_type=content_type, headers=response_headers)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')


def _localized_headers(language, request_id):
    return {
        'Content-Language': language,
        'Vary': 'Accept-Language',
        'X-Request-Id': request_id,
    }


def _representation_key(request, language):
    query = urlencode(sorted(
        (name, item)
        for name, value in sorted(request.GET.lists())
        for item in sorted(value)
    ))
    return '{}:{}{}'.format(language, request.path, '?{}'.format(query) if query else '')


def _matches_etag(header, etag):
    if not header:
        return False
    expected = etag.removeprefix('W/')
    return any(
        candidate == '*' or candidate.removeprefix('W/') == expected
        for candidate in (part.strip() for part in header.split(','))
    )
