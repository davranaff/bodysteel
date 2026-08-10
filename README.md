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
users/management/       Auth retention commands
```

`store.models` и `store.views` остаются публичными compatibility facades: старые imports и
`store.models.*` upload callbacks из применённых migrations не меняются. Новая реализация находится
в feature modules; каждый production file остаётся меньше 250 строк.

Auth deployment and API contracts are documented in [`users/auth/README.md`](users/auth/README.md).
The store connector contract and rollout are documented in [`integration/README.md`](integration/README.md).

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
