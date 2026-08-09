import logging
import re
import uuid

from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from integration.errors import IntegrationProblem
from integration.http.authentication import authorize_request
from integration.http.responses import problem_response


logger = logging.getLogger(__name__)
REQUEST_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')


@method_decorator(csrf_exempt, name='dispatch')
class IntegrationView(View):
    http_method_names = ['get', 'post', 'options']
    required_scope = None

    def dispatch(self, request, *args, **kwargs):
        self.request_id = _request_id(request)
        try:
            if self.required_scope:
                authorize_request(request, self.required_scope)
            response = super().dispatch(request, *args, **kwargs)
        except IntegrationProblem as problem:
            response = problem_response(problem, self.request_id)
        except Exception:
            logger.exception('BodySteel Integration API request failed')
            response = problem_response(
                IntegrationProblem(503, 'Service unavailable', 'The commerce source is unavailable'),
                self.request_id,
            )
        response['X-Request-Id'] = self.request_id
        return response

    def http_method_not_allowed(self, request, *args, **kwargs):
        return problem_response(
            IntegrationProblem(405, 'Method not allowed', 'The HTTP method is not supported'),
            self.request_id,
        )


class PublicIntegrationView(IntegrationView):
    required_scope = None


def _request_id(request):
    requested = request.headers.get('X-Request-Id', '')
    return requested if REQUEST_ID.fullmatch(requested) else str(uuid.uuid4())
