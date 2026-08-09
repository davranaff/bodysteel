from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from users.auth.client_ip import client_ip


class ClientIpTests(SimpleTestCase):
    @override_settings(AUTH_TRUSTED_PROXY_NETWORKS=('10.0.0.0/8', '192.0.2.10/32'))
    def test_walks_trusted_proxy_chain_from_the_right(self):
        request = SimpleNamespace(META={
            'REMOTE_ADDR': '10.0.0.5',
            'HTTP_X_FORWARDED_FOR': '198.51.100.7, 192.0.2.10',
        })
        self.assertEqual(client_ip(request), '198.51.100.7')

    @override_settings(AUTH_TRUSTED_PROXY_NETWORKS=('10.0.0.0/8',))
    def test_ignores_forwarded_header_from_untrusted_peer(self):
        request = SimpleNamespace(META={
            'REMOTE_ADDR': '198.51.100.9',
            'HTTP_X_FORWARDED_FOR': '203.0.113.8',
        })
        self.assertEqual(client_ip(request), '198.51.100.9')
