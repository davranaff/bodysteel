# SAVDOQ Integration API for BodySteel

Этот Django app — production store-side boundary между BodySteel и SAVDOQ. Он читает только модели
магазина и никогда не предоставляет SaaS доступ к базе или её схеме.

## Routes

```text
GET  /integration/v1/products
GET  /integration/v1/products/{productId}
GET  /integration/v1/inventory?ids=1,2
POST /integration/v1/carts
POST /integration/v1/cart-restores   # public capability exchange for the storefront proxy
```

Первые четыре routes реализуют канонический SAVDOQ contract. Последний route не вызывается SaaS:
Next.js storefront обменивает через него capability token из cart URL на существующий browser cart
shape.

## Required environment

```dotenv
SECRET_KEY=<random Django signing key>
ALLOWED_HOSTS=api.bodysteel.uz
DATABASE_PASSWORD=<server-only database password>
BOT_TOKEN=<rotated token when the legacy bot is enabled>
SAVDOQ_INTEGRATION_FULL_TOKEN=<random token, at least 32 characters>
SAVDOQ_INTEGRATION_READ_TOKEN=<different random token, at least 32 characters>
SAVDOQ_STOREFRONT_ORIGIN=https://bodysteel.uz
SAVDOQ_MEDIA_ORIGIN=https://api.bodysteel.uz
SAVDOQ_CART_TTL_SECONDS=3600
SAVDOQ_WEBHOOK_URL=https://<savdoq-host>/api/v1/webhooks/connections/<connection-id>
SAVDOQ_WEBHOOK_SECRET=<different random HMAC secret, 32-512 characters>
```

Full token получает `products:read`, `inventory:read`, `carts:write`; read token — только два read
scope. Tokens нельзя хранить в Git, передавать в query string или логировать. При rotation временно
задайте новые values в deployment secrets, замените credentials в SAVDOQ и отзовите старые.

Storefront server использует только backend origin, не Integration bearer token:

```dotenv
BODYSTEEL_API_ORIGIN=https://api.bodysteel.uz
BODYSTEEL_PUBLIC_ORIGIN=https://bodysteel.uz
```

## Data mapping

- Internal `name_ru/name_uz`, descriptions, country and composition flatten to canonical names
  according to `Accept-Language`.
- `Product.id` becomes a stable string ID; price is UZS minor units.
- `discounted_price` is interpreted as discount amount, so `salePrice = price - discounted_price`.
- `updated_at` plus related category/brand/image signals drives strict delta sync.
- Catalog descriptions and composition are exported as plain text, not raw HTML.
- Store-authored HTML is sanitized at persistence and again at serializer output with a versioned
  allowlist before any storefront `dangerouslySetInnerHTML` sink can receive it. Admin editing uses
  Django's built-in `Textarea` and no executable third-party editor bundle.
- Inventory is read live; cart creation locks product rows and rechecks requested quantity.

Hard product deletions are emitted through the signed `product.deleted` outbox event. Keep SAVDOQ
daily full reconcile enabled as a repair path for deployment outages or exhausted retries.

Cursor values are signed and bind the delta watermark/snapshot. ETags include locale, route/query and
exact JSON representation. A cart idempotency key is stored only as SHA-256; exact replay returns the
same database-backed receipt and a conflicting payload returns `409`.

Cart handoff uses `https://bodysteel.uz/cart/restore#<capability>`. URL fragments are not sent in HTTP
request paths or referrers. The page immediately removes the fragment, then sends the token in a
same-origin POST body to a bounded Next.js proxy; access logs therefore do not contain the token.
The storefront keeps the capability only in tab-scoped `sessionStorage` until checkout. Django then
links the order to `IntegrationCart` server-side; the browser never receives `aiSessionId` or
channel metadata.

Checkout POSTs carry a 16–128 character `Idempotency-Key` from browser to Next.js and then Django.
The browser stores only the random key plus SHA-256 of the normalized attempt in tab-scoped
`sessionStorage`; Django persists only SHA-256 digests. An exact replay returns the original
`orderId` with `Idempotency-Replayed: true` and skips stock, coupon, bonus and notification side
effects. Reusing the key for another normalized request returns `409`.

The storefront exposes only explicit `/api/*` adapters. All eight browser mutation routes require
the exact configured storefront origin; there is no wildcard CORS or generic `/api/:path*` backend
rewrite. Each adapter owns a fixed upstream path, method, allowlisted JSON projection, timeout,
manual redirect policy and bounded response. The public `/integration/:path*` rewrite is the only
external rewrite and does not expose store credentials to browser code.

## Webhook outbox

Product create/update/delete, live inventory changes and the first transition of an order to
`purchased` create durable events. `order.completed` contains only order ID, UZS amount, product
IDs and optional `channel`/`aiSessionId`; shopper PII is structurally excluded.

Run the one-shot worker continuously through systemd, Supervisor or another scheduler:

```bash
python manage.py deliver_integration_webhooks --limit 100
```

Any `2xx` is terminal success. Network errors and `408/425/429/500/502/503/504` retry after roughly
1 minute, 5 minutes, 30 minutes, 2 hours and 24 hours with bounded jitter; `Retry-After` is honored.
Redirects and other HTTP failures become explicit permanent failures, and the command exits nonzero
so monitoring can alert. A stale five-minute lease is recoverable after worker restart.

For signing-secret rotation, pause delivery, update the connection secret in SAVDOQ, inject the same
new secret into BodySteel, restart Django/worker, then resume. Pending bodies and event IDs remain
stable and are signed with the current secret at delivery time.

## Verification

```bash
./venv/bin/python -m pip install -r requirements-dev.txt
DEBUG=1 ./venv/bin/python manage.py makemigrations --check --dry-run
DEBUG=1 ./venv/bin/python manage.py test integration.tests users.orders.test_idempotency store.content.test_html
./venv/bin/python -m pip_audit -r requirements.txt
```

The focused suite covers auth/scopes, weighted RU/UZ, strict query/body validation, cursor/delta,
ETag/304, inventory, idempotent carts, restore expiry, transactional checkout attribution, PII-free
events, checkout replay/conflict, fixed-vector HMAC, retry classification, `Retry-After`, stale
leases, terminal retention and stored-HTML XSS sanitation. It applies all migrations to a clean
test database. The concurrent checkout test is explicitly skipped on SQLite and runs against
PostgreSQL, where two simultaneous
requests must return one receipt and produce one set of business side effects. Runtime dependencies
are pinned to Django 5.2 LTS-compatible releases and the audit must report no known vulnerabilities.

Run the complete suite against a dedicated PostgreSQL database as a separate required gate:

```bash
export DJANGO_SETTINGS_MODULE=config.settings_test_postgres
export DEBUG=1
export TEST_DATABASE_NAME=bodysteel_test
export TEST_DATABASE_USER=bodysteel_test_runner
export TEST_DATABASE_HOST=127.0.0.1
export TEST_DATABASE_PORT=5432
read -r -s TEST_DATABASE_PASSWORD
export TEST_DATABASE_PASSWORD
./venv/bin/python manage.py test
unset TEST_DATABASE_PASSWORD
```

The role must have permission to create a disposable test database and must never point at
production. PostgreSQL runs all 35 tests, including the real concurrent checkout case. This gate
also protects the cart query rule:
`select_for_update()` locks only `Product` rows and must not be combined with nullable outer joins
for brand or media data.

After backend and storefront deployment, run the real external preflight from the SAVDOQ repository:

```bash
export CONFORMANCE_BASE_URL=https://bodysteel.uz/integration/v1
read -r -s CONFORMANCE_TOKEN
export CONFORMANCE_TOKEN
pnpm connector:conformance
unset CONFORMANCE_TOKEN
```

For `CONFORMANCE_PROFILE=full`, also provide the distinct read-only token. Full profile creates a
test restorable cart, so run it in staging or an agreed production window.

## Deployment order

1. Back up the BodySteel database, then run `python manage.py audit_rich_html` before migration. It
   reports only per-field counts and never prints stored HTML. Review the affected formatting on a
   restored staging copy, then apply `store.0032`–`0037` plus `integration.0001`–`0004`.
2. Configure server-only `SECRET_KEY`, `BOT_TOKEN`, SAVDOQ tokens, origins, webhook URL and separate
   webhook secret, then deploy Django.
   If either legacy secret was ever used outside local development, rotate it before rollout.
3. Run `python manage.py collectstatic --clear --noinput` so a previous CKEditor 4 bundle cannot
   survive in `STATIC_ROOT`, then deploy the hardened storefront adapters, the Integration-only
   rewrite and `/cart/restore` attribution flow. Run all 37 storefront boundary tests first.
4. Start the webhook delivery worker and alert on a nonzero exit or growing pending lag.
5. Run read-only, then full conformance against `https://bodysteel.uz/integration/v1`, followed by
   signed product-delete and test-order webhook smoke checks.
6. Only after both verdicts pass, start initial sync and keep daily reconcile enabled.

Run retention from cron after deployment:

```bash
python manage.py purge_expired_integration_carts --retention-hours 24
python manage.py purge_integration_webhooks --delivered-retention-days 30 --failed-retention-days 90
```

Schedule it at least hourly; it deletes only carts whose expiry is older than the retention window.

Apply an infrastructure rate limit to `/integration/v1/*` and the public restore exchange. Do not
consider the endpoint production-ready until TLS, migration backup/rollback, rate limit and external
conformance are verified in the deployed environment.

For local development, copy `config/settings_dev.py.example` to the ignored
`config/settings_dev.py` and provide secrets only through environment variables. If that ignored
file is absent, `DEBUG=1` intentionally falls back to SQLite so a clean clone can run checks; the
dedicated PostgreSQL gate above remains mandatory before release. Never commit bot, email, database
or SAVDOQ credentials. Production uses the same pattern: copy
`config/settings_prod.py.example` to the ignored `config/settings_prod.py`, then inject its required
values from the deployment secret store. The pinned `psycopg[binary]` dependency provides the
PostgreSQL driver used by that configuration. The pinned `nh3` dependency provides the server-side
HTML allowlist sanitizer; CKEditor is not a runtime dependency.
