import hmac

from users.auth.configuration import storefront_proxy_token
from users.auth.errors import AuthProblem


def require_storefront_proxy(request):
    expected = storefront_proxy_token()
    supplied = request.META.get('HTTP_X_STOREFRONT_PROXY_TOKEN', '')
    if not isinstance(supplied, str) or not hmac.compare_digest(supplied, expected):
        raise AuthProblem(403, 'forbidden', 'Forbidden')
