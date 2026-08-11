import base64
from unittest.mock import Mock, patch

from django.test import override_settings

from integration.models import RegosWebhookEvent
from integration.regos.config import RegosSyncError
from integration.regos.queue import process_pending_events
from integration.regos.sync import (
    SyncResult,
    apply_records,
    archive_regos_item,
    record_from_regos,
    sync_from_regos,
)
from integration.tests.fixtures import IntegrationAPITestCase
from store.models import Product


REGOS_SETTINGS = {
    'REGOS_INTEGRATION_KEY': 'regos-integration-key-example',
    'REGOS_API_ENDPOINT': '',
    'REGOS_STOCK_IDS': ('3',),
    'REGOS_API_TIMEOUT_SECONDS': 15,
    'REGOS_TO_SERVER_USERNAME': 'regos-to-server-user',
    'REGOS_TO_SERVER_PASSWORD': 'regos-to-server-password',
    'REGOS_CONNECTED_INTEGRATION_ID': 'connected-integration-id-example',
}


@override_settings(**REGOS_SETTINGS)
class RegosInventoryTests(IntegrationAPITestCase):
    def test_direct_sync_links_by_name_and_uses_allowed_quantity(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'ok': True,
            'result': [
                {
                    'item': {'id': 9001, 'code': 101, 'articul': 'CRE-1', 'name': 'Креатин 1'},
                    'quantity': {'common': 12, 'booked': 3, 'allowed': 9},
                }
            ],
            'next_offset': 1,
            'total': 1,
        }
        session = Mock()
        session.post.return_value = response
        with patch('integration.regos.sync.requests.Session', return_value=session):
            result = sync_from_regos()

        product = Product.objects.get(pk=self.products[0].pk)
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.linked, 1)
        self.assertEqual(product.quantity, 9)
        self.assertEqual(product.regos_item_id, 9001)
        self.assertEqual(product.regos_item_code, '101')
        self.assertEqual(product.regos_item_articul, 'CRE-1')
        url = session.post.call_args.args[0]
        self.assertEqual(url, 'https://integration.regos.uz/gateway/out/regos-integration-key-example/v1/item/getext')
        self.assertEqual(session.post.call_args.kwargs['json']['filters'][0]['Value'], '3')

    def test_ambiguous_or_fractional_records_are_not_written(self):
        result = apply_records([
            record_from_regos({
                'item': {'id': 9002, 'code': 102, 'name': 'Неизвестный'},
                'quantity': {'allowed': 1},
            }),
            record_from_regos({
                'item': {'id': 9003, 'code': 103, 'name': 'Креатин 2'},
                'quantity': {'allowed': '1.5'},
            }),
        ], source='test')

        self.assertEqual(result.unmatched, 1)
        self.assertEqual(result.invalid, 1)
        self.assertEqual(Product.objects.get(pk=self.products[1].pk).quantity, 2)

    def test_item_added_creates_hidden_regos_draft_only_when_requested(self):
        record = record_from_regos({
            'item': {'id': 9010, 'code': '010230', 'articul': 'ARG-1', 'name': 'REGOS arginine', 'price': 350000},
            'quantity': {'allowed': 2},
        })

        result = apply_records([record], source='item-added', create_drafts=True, update_catalog=True)

        product = Product.objects.get(regos_item_id=9010)
        self.assertEqual(result.created, 1)
        self.assertEqual(product.regos_catalog_status, Product.REGOS_STATUS_DRAFT)
        self.assertEqual(product.price, 350000)
        self.assertEqual(product.quantity, 2)
        self.assertFalse(Product.objects.visible_on_storefront().filter(pk=product.pk).exists())

    def test_deleted_regos_item_is_archived_not_physically_deleted(self):
        Product.objects.filter(pk=self.products[0].pk).update(regos_item_id=9001, quantity=8)

        result = archive_regos_item(9001)

        product = Product.objects.get(pk=self.products[0].pk)
        self.assertEqual(result.archived, 1)
        self.assertEqual(product.regos_catalog_status, Product.REGOS_STATUS_ARCHIVED)
        self.assertEqual(product.quantity, 0)
        self.assertFalse(Product.objects.visible_on_storefront().filter(pk=product.pk).exists())

    def test_to_server_receiver_updates_matching_item_with_basic_auth(self):
        credentials = base64.b64encode(b'regos-to-server-user:regos-to-server-password').decode('ascii')
        response = self.client.post(
            '/integration/v1/regos/to-server',
            data={
                'jsonrpc': '2.0',
                'id': 'sync-7',
                'method': 'upload',
                'params': {
                    'items': [{
                        'code': 101,
                        'articul': 'CRE-1',
                        'name': 'Креатин 1',
                        'stock_quantities': [{'allowed': 4}, {'allowed': 3}],
                    }]
                },
            },
            content_type='application/json',
            HTTP_AUTHORIZATION='Basic {}'.format(credentials),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['updated'], 1)
        product = Product.objects.get(pk=self.products[0].pk)
        self.assertEqual(product.quantity, 7)
        self.assertEqual(product.regos_item_code, '101')
        self.assertEqual(product.regos_item_articul, 'CRE-1')

    def test_offline_regos_sale_decreases_site_stock(self):
        """A later REGOS export after an offline POS sale is authoritative."""
        credentials = base64.b64encode(b'regos-to-server-user:regos-to-server-password').decode('ascii')
        Product.objects.filter(pk=self.products[0].pk).update(
            quantity=5,
            regos_item_id=9001,
            regos_item_code='101',
        )

        response = self.client.post(
            '/integration/v1/regos/to-server',
            data={
                'jsonrpc': '2.0',
                'id': 'offline-sale-8',
                'method': 'upload',
                'params': {
                    'items': [{
                        'id': 9001,
                        'code': 101,
                        'name': 'Креатин 1',
                        # REGOS reports 4 available pieces after one offline sale.
                        'quantity': [{'common': 5, 'booked': 1, 'allowed': 4}],
                    }]
                },
            },
            content_type='application/json',
            HTTP_AUTHORIZATION='Basic {}'.format(credentials),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['updated'], 1)
        self.assertEqual(Product.objects.get(pk=self.products[0].pk).quantity, 4)

    def test_offline_regos_return_restores_site_stock(self):
        """A completed return in REGOS raises the quantity displayed on the site."""
        credentials = base64.b64encode(b'regos-to-server-user:regos-to-server-password').decode('ascii')
        Product.objects.filter(pk=self.products[0].pk).update(
            quantity=4,
            regos_item_id=9001,
            regos_item_code='101',
        )

        response = self.client.post(
            '/integration/v1/regos/to-server',
            data={
                'jsonrpc': '2.0',
                'id': 'offline-return-9',
                'method': 'upload',
                'params': {
                    'items': [{
                        'id': 9001,
                        'code': 101,
                        'name': 'Креатин 1',
                        # REGOS reports 5 available pieces after accepting a return.
                        'quantity': [{'common': 6, 'booked': 1, 'allowed': 5}],
                    }]
                },
            },
            content_type='application/json',
            HTTP_AUTHORIZATION='Basic {}'.format(credentials),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['updated'], 1)
        self.assertEqual(Product.objects.get(pk=self.products[0].pk).quantity, 5)

    def test_to_server_receiver_rejects_missing_authentication(self):
        response = self.client.post('/integration/v1/regos/to-server', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_local_webhook_refreshes_inventory_after_offline_event(self):
        response = self.client.post(
            '/integration/v1/regos/webhook',
            data={
                'action': 'HandleWebhook',
                'event_id': 'event-10',
                'connected_integration_id': 'connected-integration-id-example',
                'data': {'action': 'DocChequeClosed', 'data': {'uuid': 'cheque-10'}},
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['result']['accepted'])
        event = RegosWebhookEvent.objects.get(event_id='event-10')
        self.assertEqual(event.status, RegosWebhookEvent.STATUS_PENDING)
        self.assertEqual(event.event_type, 'DocChequeClosed')

    def test_item_added_webhook_uses_targeted_draft_sync(self):
        response = self.client.post(
            '/integration/v1/regos/webhook',
            data={
                'action': 'HandleWebhook',
                'event_id': 'item-added-12',
                'connected_integration_id': 'connected-integration-id-example',
                'data': {'action': 'ItemAdded', 'data': {'id': 9010}},
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        with patch('integration.regos.queue.sync_item_from_regos') as sync:
            processed, retried = process_pending_events()
        self.assertEqual((processed, retried), (1, 0))
        sync.assert_called_once_with(9010, create_draft=True)
        self.assertEqual(
            RegosWebhookEvent.objects.get(event_id='item-added-12').status,
            RegosWebhookEvent.STATUS_DONE,
        )

    def test_item_deleted_webhook_archives_linked_product(self):
        response = self.client.post(
            '/integration/v1/regos/webhook',
            data={
                'action': 'HandleWebhook',
                'event_id': 'item-deleted-13',
                'connected_integration_id': 'connected-integration-id-example',
                'data': {'action': 'ItemDeleted', 'data': {'id': 9010}},
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        with patch('integration.regos.queue.archive_regos_item') as archive:
            processed, retried = process_pending_events()
        self.assertEqual((processed, retried), (1, 0))
        archive.assert_called_once_with(9010)

    def test_regos_queue_retries_a_temporary_api_failure(self):
        RegosWebhookEvent.objects.create(
            event_id='retry-14',
            event_type='ItemEdited',
            item_id=9010,
            payload={},
        )
        with patch(
            'integration.regos.queue.sync_item_from_regos',
            side_effect=RegosSyncError('REGOS item request failed'),
        ):
            processed, retried = process_pending_events()
        event = RegosWebhookEvent.objects.get(event_id='retry-14')
        self.assertEqual((processed, retried), (0, 1))
        self.assertEqual(event.status, RegosWebhookEvent.STATUS_RETRY)
        self.assertEqual(event.attempt_count, 1)

    def test_local_webhook_rejects_unknown_integration(self):
        response = self.client.post(
            '/integration/v1/regos/webhook',
            data={
                'action': 'HandleWebhook',
                'event_id': 'webhook-11',
                'connected_integration_id': 'wrong-integration',
                'data': {},
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_to_server_receiver_validates_json_boundary(self):
        credentials = base64.b64encode(b'regos-to-server-user:regos-to-server-password').decode('ascii')
        headers = {'HTTP_AUTHORIZATION': 'Basic {}'.format(credentials)}

        unsupported = self.client.post(
            '/integration/v1/regos/to-server', data='{}', content_type='text/plain', **headers
        )
        self.assertEqual(unsupported.status_code, 415)

        malformed = self.client.post(
            '/integration/v1/regos/to-server', data='{"id":', content_type='application/json', **headers
        )
        self.assertEqual(malformed.status_code, 400)

        invalid_params = self.client.post(
            '/integration/v1/regos/to-server',
            data='{"id":"bad-params","params":"items"}',
            content_type='application/json',
            **headers,
        )
        self.assertEqual(invalid_params.status_code, 400)
