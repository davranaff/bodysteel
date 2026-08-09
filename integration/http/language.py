from config.http_language import select_supported_language
from integration.errors import IntegrationProblem


def require_language(request):
    try:
        return select_supported_language(request.headers.get('Accept-Language', ''))
    except ValueError:
        raise _not_acceptable()


def _not_acceptable():
    return IntegrationProblem(
        406,
        'Language not acceptable',
        'Accept-Language must select Russian or Uzbek',
    )
