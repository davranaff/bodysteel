from rest_framework.response import Response

from users.auth.errors import AuthProblem


def success_response(data, status, language):
    return _response({'data': data}, status, language)


def problem_response(problem: AuthProblem, language=None):
    error = {'code': problem.code, 'message': problem.message}
    headers = {}
    if problem.retry_after is not None:
        error['retry_after'] = problem.retry_after
        headers['Retry-After'] = str(problem.retry_after)
    return _response({'error': error}, problem.status, language, headers)


def _response(payload, status, language, headers=None):
    response_headers = {'Cache-Control': 'no-store', **(headers or {})}
    if language:
        response_headers.update({'Content-Language': language, 'Vary': 'Accept-Language'})
    return Response(payload, status=status, headers=response_headers)
