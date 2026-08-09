from config.http_language import select_supported_language
from users.auth.errors import AuthProblem


def require_language(request):
    try:
        return select_supported_language(request.headers.get('Accept-Language', ''))
    except ValueError:
        raise AuthProblem(406, 'language_not_acceptable', 'Language not acceptable') from None
