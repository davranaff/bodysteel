# BodySteel customer Telegram bot

## Two isolated bots

`BOT_TOKEN` remains the staff/order bot used by `teleg`. The customer bot uses only
`CUSTOMER_TELEGRAM_BOT_TOKEN`, has its own webhook, update table, handlers and campaign queue, and
must be a different BotFather bot. Never substitute one token for the other.

The customer bot supports RU/UZ, registration and password-reset OTP, authenticated account
link/unlink, User-owned order history, and explicit opt-in discount notifications. Guest orders are
not visible because ownership is resolved only through `Order.user`.

Official references: [Bots](https://core.telegram.org/bots),
[deep links](https://core.telegram.org/bots/features#deep-linking),
[setWebhook](https://core.telegram.org/bots/api#setwebhook),
[contact keyboard](https://core.telegram.org/bots/api#keyboardbutton), and
[broadcast limits](https://core.telegram.org/bots/faq#broadcasting-to-users).

## BotFather and secrets

1. Open `@BotFather`, run `/newbot`, choose the approved customer-facing name and a unique username
   ending in `bot`.
2. Store the returned token only in the production secret store. Do not paste it into Git, tickets,
   logs, browser env or command history.
3. Generate independent random values of at least 32 bytes for the webhook secret and link hash key.
4. Keep the staff `BOT_TOKEN` unchanged.

Backend environment:

```dotenv
CUSTOMER_TELEGRAM_ENABLED=0
CUSTOMER_TELEGRAM_CAMPAIGNS_ENABLED=0
CUSTOMER_TELEGRAM_BOT_TOKEN=<new-BotFather-token>
CUSTOMER_TELEGRAM_BOT_USERNAME=<new-public-username>
CUSTOMER_TELEGRAM_WEBHOOK_SECRET=<independent-url-safe-secret>
CUSTOMER_TELEGRAM_LINK_HASH_KEY=<independent-random-secret>
CUSTOMER_TELEGRAM_PUBLIC_ORIGIN=https://api.bodysteel.uz
CUSTOMER_TELEGRAM_WEBHOOK_URL=https://api.bodysteel.uz/telegram/customer/webhook/
CUSTOMER_TELEGRAM_STORE_ORIGIN=https://bodysteel.uz
CUSTOMER_TELEGRAM_LINK_TTL_SECONDS=300
CUSTOMER_TELEGRAM_CONTACT_MAX_ATTEMPTS=3
```

The storefront needs only the public username and rollout flag:

```dotenv
BODYSTEEL_CUSTOMER_TELEGRAM_BOT_USERNAME=<same-public-username>
NEXT_PUBLIC_CUSTOMER_TELEGRAM_BOT_USERNAME=<same-public-username>
NEXT_PUBLIC_CUSTOMER_TELEGRAM_ENABLED=false
```

Never add `NEXT_PUBLIC_CUSTOMER_TELEGRAM_BOT_TOKEN`, an OTP, deep-link token, phone, or email to
logs/storage. OTP and start tokens are persisted only as keyed digests.

## Local verification

No real Telegram client is needed for the deterministic suite:

```bash
DEBUG=1 ./venv/bin/python manage.py test customer_telegram.tests
DEBUG=1 ./venv/bin/python manage.py makemigrations --check --dry-run
DEBUG=1 ./venv/bin/python manage.py check
```

Tests use a fake Bot API and cover contact ownership, neutral password reset, URL safety, orders,
webhook idempotency and campaign retries. For a real approved test account, enable the backend only
after migrations, build the storefront with the exact new username, create/link the test User from
the account security page, press Start, share the account owner's phone using the bot button, and
verify RU and UZ separately.

## Webhook and release preflight

After deploying with campaigns disabled:

```bash
python manage.py set_customer_telegram_webhook
python manage.py check_customer_telegram
```

The first command sends the exact URL, secret header and allowed updates without dropping pending
updates. The second checks `getWebhookInfo`, the exact hostname/path and a bounded pending count. It
does not print tokens, secrets or Telegram error descriptions.

## Campaigns

Campaigns are created in the existing BodySteel admin. Keep them as draft, fill both RU and UZ
title/body, optionally add paired button labels and an internal HTTPS BodySteel URL, choose exactly
one test recipient, then use test send. Test send never builds a mass audience. Publishing requires
the dedicated permission and an explicit confirmation page; the admin request only changes state.

Scheduled campaigns are picked up when `scheduled_at` is due. The one-shot worker builds recipients
idempotently and re-checks active/blocked/opt-in state immediately before delivery:

```bash
python manage.py send_customer_telegram_campaigns --limit 100
```

The worker is bounded to 20 messages per second and reserves at least one second between marketing
messages to the same chat. It honors `Retry-After`, recovers stale leases and
classifies blocked/permanent/transient failures without saving raw Telegram responses. Install the
units in `conf/systemd/` after adapting only their deployment paths. Set
`CUSTOMER_TELEGRAM_CAMPAIGNS_ENABLED=0` to stop queue building/delivery. Do not send a production
mass campaign without separate approval.

## Unlink and retention

Customers can use the account page, the bot menu, or `/unlink`. Unlink removes the User relation,
turns marketing off and expires active account links; orders remain intact. `/stop` disables only
marketing. Account soft-delete explicitly performs the same security unlink.

Run cleanup daily (the supplied timer is a template):

```bash
python manage.py purge_customer_telegram_records \
  --link-retention-days 7 --update-retention-days 30 --delivery-retention-days 90
```

Unexpired links, unfinished campaigns and current consent evidence are retained. Expired links are
kept for the configured safety window before deletion. Expired hashed customer-Telegram rate-limit
rows are also removed; campaign aggregates remain after old technical recipient failures are removed.

## Rollout and rollback

The supplied systemd units match the production `root:www-data` service identity and
`/etc/bodysteel/gunicorn-release.env`; replace the literal `RELEASE_ID` with the deployed release
directory during the same release switch. The normal systemd hardening remains enabled.

Roll out backend first with both flags off, back up PostgreSQL, apply append-only migrations, run
`check --deploy`, install the disabled worker timer, configure the new webhook, then enable the bot
for one approved test account. Smoke `/start`, RU/UZ, registration OTP, reset OTP, account link,
orders, opt-in/out and one test campaign. Confirm the staff bot still receives order notifications.
Only then build the storefront with `NEXT_PUBLIC_CUSTOMER_TELEGRAM_ENABLED=true`; enable campaigns
last.

Rollback is non-destructive: rebuild storefront with the public flag `false`, set both backend flags
to `0`, stop the campaign timer and optionally call `delete_webhook` for the new bot. Do not roll back
migrations or touch the staff bot. SMS/email fallback remains available.

## Troubleshooting

- Secret mismatch: Telegram requests receive 403; re-run webhook setup with the same secret-store value.
- Bot blocked: the chat becomes inactive, marketing is disabled, and future campaigns skip it.
- 429: the recipient is retried after the larger of local backoff and Telegram `retry_after`.
- Expired link: request a new link on the site; resending invalidates the previous token/code.
- Different Telegram phone: no account is linked and the response stays neutral.
- Empty orders: guest and differently owned orders are intentionally invisible.
- Inactive/deleted User: linking and order access are denied; marketing remains off.

Never troubleshoot by printing env files, full Bot API URLs, webhook bodies, OTP messages, contact
numbers or raw Telegram error payloads.
