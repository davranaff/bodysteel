from integration.catalog.inventory import read_inventory
from integration.catalog.products import get_product, list_products
from integration.http.language import require_language
from integration.http.request_parsing import (
    parse_inventory_ids,
    parse_product_id,
    parse_product_list_request,
)
from integration.http.responses import json_response, localized_entity_response
from integration.http.views import IntegrationView


class ProductsView(IntegrationView):
    required_scope = 'products:read'

    def get(self, request):
        language = require_language(request)
        cursor, updated_after, limit = parse_product_list_request(request)
        page = list_products(cursor, updated_after, limit, language)
        return localized_entity_response(request, page, language, self.request_id)


class ProductView(IntegrationView):
    required_scope = 'products:read'

    def get(self, request, product_id):
        language = require_language(request)
        product = get_product(parse_product_id(product_id), language)
        return localized_entity_response(request, product, language, self.request_id)


class InventoryView(IntegrationView):
    required_scope = 'inventory:read'

    def get(self, request):
        return json_response(read_inventory(parse_inventory_ids(request)))
