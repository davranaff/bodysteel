from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from moderation.serializers import ContentReportInputSerializer
from moderation.services import create_report
from users.auth.errors import AuthProblem
from users.auth.language import require_language
from users.auth.responses import problem_response, success_response


class ContentReportView(APIView):
    """Customer reports about reviews and AI answers (App Store 1.2 / Play UGC policy).

    Like the other signed-in customer endpoints (favorites, basket, profile) it is
    called directly by the mobile app with the customer's token; it requires
    ``Accept-Language: ru|uz`` like the rest of the customer account API.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    http_method_names = ['post']

    @swagger_auto_schema(
        request_body=ContentReportInputSerializer,
        responses={201: openapi.Response('Report accepted', examples={'application/json': {'data': {'id': 1}}})},
    )
    def post(self, request):
        language = None
        try:
            language = require_language(request)
            serializer = ContentReportInputSerializer(data=_body(request))
            if not serializer.is_valid():
                raise AuthProblem(400, 'invalid_request', 'Invalid request')
            report = create_report(request.user, serializer.validated_data)
        except AuthProblem as problem:
            return problem_response(problem, language)
        return success_response({'id': report.pk}, 201, language)


def _body(request):
    try:
        return request.data
    except UnsupportedMediaType:
        raise AuthProblem(415, 'unsupported_media_type', 'Unsupported media type') from None
    except ParseError:
        raise AuthProblem(400, 'invalid_request', 'Invalid request') from None
