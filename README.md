# BodySteel Django backend

Store-owned commerce backend for `api.bodysteel.uz`. It owns catalog, inventory, orders, customer
accounts and the SAVDOQ Integration API; it never connects to a SAVDOQ database.

## Repository map

```text
config/                 Django composition and deployment settings
integration/            SAVDOQ catalog, inventory, carts and webhook outbox
store/models.py         Stable model facade and historical migration callbacks
store/views.py          Backward-compatible HTTP facade
store/catalog/          Product/category models and storefront read adapters
store/commerce/         Basket/favorite/order/coupon models
store/content/          Menu/blog/brand/location models, HTML policy and content adapters
store/locations/        Filial administration transport
store/serializers/      Legacy storefront response serializers
users/auth/             OTP registration, sign-in, rate limits and Eskiz adapter
users/orders/           Transactional checkout and idempotency
users/profile/          Authenticated account transport
users/savdoq/           SAVDOQ shopper chat sessions for signed-in customers
users/management/       Auth retention commands
```

`store.models` и `store.views` остаются публичными compatibility facades: старые imports и
`store.models.*` upload callbacks из применённых migrations не меняются. Новая реализация находится
в feature modules; каждый production file остаётся меньше 250 строк.

Auth deployment and API contracts are documented in [`users/auth/README.md`](users/auth/README.md).
The store connector contract and rollout are documented in [`integration/README.md`](integration/README.md).
Shopper AI-chat sessions and their rollout are documented in
[`users/savdoq/README.md`](users/savdoq/README.md).
The isolated customer bot, campaigns and rollout are documented in
[`customer_telegram/README.md`](customer_telegram/README.md).

## Verification

```bash
DEBUG=1 ./venv/bin/python manage.py makemigrations --check --dry-run
DEBUG=1 ./venv/bin/python manage.py check
DEBUG=1 ./venv/bin/python manage.py test
./venv/bin/pip-audit -r requirements.txt
```

Concurrency-sensitive checkout and auth tests must also run against PostgreSQL through
`config.settings_test_postgres`.

GitHub Actions повторяет SQLite test/migration gate и `pip-audit` на каждом push и pull request;
production release дополнительно обязан пройти `check_integration_release` на целевой БД.
Gunicorn не содержит release-specific paths или public IP: задайте `GUNICORN_COMMAND`,
`GUNICORN_PYTHONPATH`, `GUNICORN_BIND` и bounded `GUNICORN_WORKERS` через systemd environment.

## Native push notifications

`notifications/` owns encrypted installation tokens, campaign segmentation and a durable delivery
queue. It adds no demographic/profile fields to `User`: age, birth date and weight are not available.
The admin supports RU/UZ content, scheduling, preview/confirmation, an own-device test and cancellation.
Filters combine with AND; lists combine with OR. Product/category/brand criteria must match one basket
position. Recent-purchase filters use the last order in the selected purchase scope, not any old order.
Cancelled/refunded orders are excluded by default; staff inclusion and one matching device per user
are explicit options. Only active, recently seen installations with OS permission and explicit
marketing consent participate. Device metadata is reported by the app, not hardware-attested.

Before rollout:

1. Apply `python manage.py migrate notifications` in the normal release workflow.
2. Configure server-only `PUSH_TOKEN_ENCRYPTION_KEYS` (comma-separated Fernet keys, newest first),
   `PUSH_FIREBASE_PROJECT_ID` and Application Default Credentials for that Firebase project.
   `GOOGLE_APPLICATION_CREDENTIALS` may point to a service-account file outside the repository;
   prefer workload identity where supported. Keep old encryption keys during rotation.
3. Set `PUSH_ENABLED=true` only after the mobile Firebase apps and APNs are configured. With it off,
   drafts/preview remain available and sending fails closed; missing encryption keys reject registration.
4. Grant trusted staff `view/add/change_pushcampaign` plus the separate
   `publish_pushcampaign`, `test_pushcampaign` and/or `cancel_pushcampaign` permissions.
5. Schedule `python manage.py deliver_push_notifications --limit 100` using the existing worker
   infrastructure (for example once a minute). Publishing never performs HTTP delivery in a DB
   transaction or in an admin request. Leases expire after 300 seconds; provider retries stop after
   five attempts. A network-uncertain send can be repeated: delivery IDs/collapse tags are stable,
   but exactly-once delivery and proof of reading are not claimed.

The cookie-authenticated Next.js gateway must implement `GET/PUT/DELETE
/api/push-devices/{installation_id}`. Forward only to
`/api/v1/users/push/devices/{installation_id}/` with the current customer's server-held Django
token, independent storefront proxy token and RU/UZ language. Require the existing exact-Origin
mutation checks; never trust a caller-supplied user ID, bearer/proxy header or upstream URL. PUT accepts
bounded JSON (16 KiB); GET/DELETE accept no query/body. Return the existing problem/data envelope,
`Cache-Control: no-store`, and never return/log an FCM token. The generated mobile contract lives in
`openapi/auth-proxy.yaml`; deployment of this new Next route is a prerequisite, not included in this
Django repository. Sign-out/token rotation deactivate devices; already queued OS alerts cannot be
recalled. Campaign content must not contain private account data.
