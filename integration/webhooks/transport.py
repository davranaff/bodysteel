from dataclasses import dataclass

import httpx


class WebhookTransportError(Exception):
    pass


@dataclass(frozen=True)
class WebhookTransportResponse:
    status_code: int
    retry_after: str | None = None


class HttpxWebhookTransport:
    def __init__(self):
        self.client = httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(5.0, connect=2.0),
            trust_env=False,
        )

    def send(self, url, body, headers):
        try:
            with self.client.stream(
                'POST',
                url,
                content=body.encode('utf-8'),
                headers=headers,
            ) as response:
                return WebhookTransportResponse(
                    status_code=response.status_code,
                    retry_after=response.headers.get('Retry-After'),
                )
        except httpx.HTTPError:
            raise WebhookTransportError('Webhook transport failed') from None

    def close(self):
        self.client.close()
