from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from config.http_language import select_supported_language
from store.geocoding.bounds import inside_uzbekistan, parse_coordinate
from store.geocoding.service import normalize_query, reverse_place, search_places, throttle_client
from users.auth.client_ip import client_ip
from users.auth.errors import AuthProblem
from users.auth.responses import problem_response, success_response


QUERY_MIN_LENGTH = 2
QUERY_MAX_LENGTH = 120
PLACE_EXAMPLE = {'label': 'Ляби-Хауз', 'address': 'улица Накшбанди, 5, Бухара'}


class GeocodeReverseView(APIView):
    """Public: turn a map point inside Uzbekistan into a short place name and address."""

    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ['get']

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('lat', openapi.IN_QUERY, type=openapi.TYPE_NUMBER, required=True),
            openapi.Parameter('lng', openapi.IN_QUERY, type=openapi.TYPE_NUMBER, required=True),
        ],
        responses={200: openapi.Response('Place', examples={'application/json': {'data': PLACE_EXAMPLE}})},
    )
    def get(self, request):
        language = _language(request)
        try:
            params = _query(request, {'lat', 'lng'})
            latitude, longitude = _point(params['lat'], params['lng'])
            throttle_client(client_ip(request))
            place = reverse_place(latitude, longitude, language)
        except AuthProblem as problem:
            return problem_response(problem, language)
        return success_response({'label': place['label'], 'address': place['address']}, 200, language)


class GeocodeSearchView(APIView):
    """Public: up to five places in Uzbekistan matching a free-text query."""

    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ['get']

    @swagger_auto_schema(
        manual_parameters=[openapi.Parameter('q', openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True)],
        responses={200: openapi.Response('Places', examples={'application/json': {
            'data': [{**PLACE_EXAMPLE, 'lat': 39.774, 'lng': 64.4198}],
        }})},
    )
    def get(self, request):
        language = _language(request)
        try:
            query = normalize_query(_query(request, {'q'})['q'])
            if not QUERY_MIN_LENGTH <= len(query) <= QUERY_MAX_LENGTH:
                raise AuthProblem(400, 'invalid_request', 'Query must be 2 to 120 characters')
            throttle_client(client_ip(request))
            places = search_places(query, language)
        except AuthProblem as problem:
            return problem_response(problem, language)
        return success_response(places, 200, language)


def _language(request):
    try:
        return select_supported_language(request.headers.get('Accept-Language', ''))
    except ValueError:
        return 'ru'


def _query(request, names):
    params = request.query_params
    if set(params) != names or any(len(params.getlist(name)) != 1 for name in names):
        raise AuthProblem(400, 'invalid_request', 'Invalid query parameters')
    return {name: params[name] for name in names}


def _point(raw_latitude, raw_longitude):
    try:
        if max(len(raw_latitude), len(raw_longitude)) > 32:
            raise ValueError('coordinate')
        latitude = parse_coordinate(raw_latitude, 90)
        longitude = parse_coordinate(raw_longitude, 180)
    except (TypeError, ValueError, OverflowError):
        raise AuthProblem(400, 'invalid_request', 'Invalid coordinates') from None
    if not inside_uzbekistan(latitude, longitude):
        raise AuthProblem(400, 'outside_service_area', 'Coordinates are outside Uzbekistan')
    return latitude, longitude
