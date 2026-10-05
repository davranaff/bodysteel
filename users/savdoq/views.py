import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from users.auth.errors import AuthProblem
from users.auth.http_boundary import require_storefront_proxy
from users.auth.language import require_language
from users.auth.responses import problem_response, success_response
from users.savdoq.client import SavdoqRefused, SavdoqUnavailable
from users.savdoq.configuration import SavdoqShopperConfigurationError
from users.savdoq.sessions import session_payload, shopper_session_service


logger = logging.getLogger('bodysteel.savdoq')
SESSION_MODES = {None: False, 'new': True}


class ShopperChatSessionView(APIView):
    """Issues the SAVDOQ widget session for the signed-in customer.

    Server-to-server boundary: the storefront calls it with its proxy token and
    the customer's DRF token; SAVDOQ credentials never leave this service.
    """

    http_method_names = ['post']
    permission_classes = [IsAuthenticated]

    def post(self, request):
        language = None
        try:
            require_storefront_proxy(request)
            language = require_language(request)
            fresh = self._session_mode(request)
            service = shopper_session_service()
            issued = service.issue(request.user, request.auth, language, fresh=fresh)
        except AuthProblem as problem:
            return problem_response(problem, language)
        except SavdoqRefused as refused:
            logger.info(
                'savdoq_shopper_event=issue outcome=refused status=%s user_id=%s',
                refused.status, request.user.pk,
            )
            return problem_response(_refusal_problem(refused), language)
        except (SavdoqShopperConfigurationError, SavdoqUnavailable):
            logger.warning(
                'savdoq_shopper_event=issue outcome=unavailable user_id=%s', request.user.pk,
            )
            return problem_response(
                AuthProblem(503, 'chat_unavailable', 'Chat service unavailable'), language,
            )
        # The site values are public; the storefront uses them for its own
        # conversation-history adapter instead of duplicating SAVDOQ config.
        return success_response({
            'session': session_payload(issued),
            'site': {
                'apiOrigin': service.configuration.api_origin,
                'publicKey': service.configuration.public_key,
            },
        }, 200, language)

    @staticmethod
    def _session_mode(request):
        if request.data:
            raise AuthProblem(400, 'invalid_request', 'Request must not contain a shopper identity')
        mode = request.headers.get('X-Savdoq-Session')
        if mode not in SESSION_MODES:
            raise AuthProblem(400, 'invalid_request', 'Unsupported shopper session mode')
        return SESSION_MODES[mode]


def _refusal_problem(refused):
    if refused.status == 429:
        return AuthProblem(
            429, 'chat_rate_limited', 'Too many chat requests', retry_after=refused.retry_after,
        )
    return AuthProblem(403, 'chat_refused', 'Chat session refused')
