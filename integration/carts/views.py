from integration.carts.service import create_cart, restore_cart
from integration.carts.validation import validate_cart_payload
from integration.http.language import require_language
from integration.http.request_parsing import (
    parse_json_body,
    require_idempotency_key,
)
from integration.http.responses import json_response, localized_json_response
from integration.http.views import IntegrationView, PublicIntegrationView


class CartsView(IntegrationView):
    required_scope = 'carts:write'

    def post(self, request):
        language = require_language(request)
        idempotency_key = require_idempotency_key(request)
        payload = validate_cart_payload(parse_json_body(request))
        cart = create_cart(language, idempotency_key, payload)
        return localized_json_response(cart, language, self.request_id, status=201)


class CartRestoreView(PublicIntegrationView):
    def post(self, request):
        body = parse_json_body(request)
        token = body.get('token') if isinstance(body, dict) and set(body) == {'token'} else None
        return json_response(restore_cart(token))
