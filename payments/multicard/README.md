# Multicard payment gateway

Online card payment for storefront orders through Multicard's hosted checkout
page ("Оплата на платежной странице Multicard", https://docs.multicard.uz/).
Credentials are server-only; the web storefront and the app talk to Django
only through the Next.js gateway.

## Flow

1. The shopper creates an order as before (`POST /api/v1/users/orders/`).
2. If they chose online payment, the client calls
   `POST /api/v1/payments/orders/{order_id}/multicard/` with
   `{"channel": "web"|"app", "order_key": "<the order's Idempotency-Key>"}`.
   The gateway fixes `channel` by route. A signed-in owner may omit `order_key`.
   Django creates a Multicard invoice (`POST /payment/invoice`, amount in tiyin,
   `invoice_id = BS-{payment.pk}`, OFD receipt lines) and returns
   `checkout_url` + `status_token`.
3. The client opens `checkout_url` (browser redirect on web, the system
   browser in the app). Multicard sends the shopper back to
   `{MULTICARD_WEB_RETURN_URL|MULTICARD_APP_RETURN_URL}/{status_token}`;
   the app URL is an HTTPS App Link / Universal Link.
4. Multicard calls `POST /api/v1/payments/multicard/callback/` after a
   successful charge. The `sign` field is `md5(store_id + invoice_id + amount + secret)`.
   Only `200 {"success": true}` keeps the money; any other answer makes
   Multicard refund it.
5. `GET /api/v1/payments/multicard/status/{status_token}/` returns the state.
   While pending it also asks Multicard (`GET /payment/invoice/{uuid}`, at most
   every 4 s per payment), so a delayed or lost callback still resolves.

Optional per-status webhooks go to `POST /api/v1/payments/multicard/webhook/`
(`md5(uuid + amount + secret)` or `sha1(uuid + invoice_id + amount + secret)`;
the docs show both, so both are accepted).

## States and idempotency

`Payment`: `created → pending → succeeded | failed`, `succeeded → refunded`.
`Order.payment_status` mirrors it: `unpaid → pending → paid | failed | refunded`.

* A repeated start for the same order and channel returns the stored, unexpired
  invoice (`200`, `replayed: true`). A concurrent start gets `409 start_in_progress`.
  Switching channel or retrying after a failure creates a new invoice and
  best-effort cancels the old one.
* Callbacks lock the payment row. A replay of the same transaction `uuid`
  answers success again without new side effects. A second, different
  transaction for an already paid order, a wrong amount, a wrong `store_id`
  or a cancelled order is refused, so Multicard returns that money.
* A `failed` payment can still be completed by a late success callback.

## Configuration

All keys are environment variables (see `back/.env.example`). Locally they can
live in the gitignored `back/.env`; `config/env_file.py` reads only `MULTICARD_*`
keys from it and never overrides real environment variables. On servers put the
same keys into the systemd `EnvironmentFile`.

| Key | Notes |
| --- | --- |
| `MULTICARD_ENABLED` | `1` to offer online payment. Off → the option is hidden and starts return `503`. |
| `MULTICARD_BASE_URL` | `https://dev-mesh.multicard.uz` (sandbox) or `https://mesh.multicard.uz` (production). |
| `MULTICARD_APPLICATION_ID`, `MULTICARD_SECRET`, `MULTICARD_STORE_ID` | Issued by Multicard. Never commit or log them. |
| `MULTICARD_CALLBACK_URL` | Public HTTPS URL of the callback view. Required by Multicard. |
| `MULTICARD_WEB_RETURN_URL`, `MULTICARD_APP_RETURN_URL` | Return pages; the token is appended as a path segment. |
| `MULTICARD_DEFAULT_IKPU`, `MULTICARD_DEFAULT_PACKAGE_CODE` | Fallback fiscal codes; `Product.ikpu_code` / `package_code` win. |
| `MULTICARD_DELIVERY_IKPU`, `MULTICARD_DELIVERY_PACKAGE_CODE` | Required when an order has a delivery fee. |
| `MULTICARD_VAT_PERCENT`, `MULTICARD_TIN` | Optional receipt fields. |
| `MULTICARD_CALLBACK_ALLOWED_IPS` | Optional exact client IPs (Multicard: `195.158.26.90`); needs `AUTH_TRUSTED_PROXY_NETWORKS` behind a proxy. |

Switching to production is only an environment change: production base URL,
production credentials and store, production callback URL. Do it only after
Multicard approves the sandbox integration.

## Sandbox testing

Test card `8600 5333 6409 8829`, expiry `06/28`, SMS code `111111`.
Multicard must reach `MULTICARD_CALLBACK_URL` over public HTTPS, so a local
backend needs a tunnel (or a staging host). Without the callback the status
endpoint still reconciles by polling the invoice.
