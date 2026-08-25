# BodySteel customer authentication

## Trust boundary

Browser code calls only the explicit same-origin Next.js adapters. The adapters verify exact
`Origin`, project allowlisted JSON and send a server-only `X-Storefront-Proxy-Token` to Django.
Django rejects direct calls without that token using constant-time comparison. RU/UZ is selected in
`Accept-Language` and acknowledged in `Content-Language`; locale-suffixed fields are not part of the
contract.

The same independent `BODYSTEEL_STOREFRONT_PROXY_TOKEN` (minimum 32 UTF-8 bytes) must be injected into
the Django and Next.js processes. It must never use `SECRET_KEY`, an Integration bearer token or an
OTP hashing key, and must never reach browser bundles or logs.

## Registration contract

`POST /api/v1/users/phone_verification/`:

```json
{"email":"shopper@example.test","phone":"+998901234567"}
```

A `201` response contains only `challenge_id`, `expires_in` and `resend_after`. No `User` exists yet.
The six-digit code is generated with `secrets`, stored only as keyed HMAC and expires after five
minutes by default. Resending overwrites the prior code after a 60-second cooldown.

`POST /api/v1/users/signup/`:

```json
{
  "challenge_id":"550e8400-e29b-41d4-a716-446655440000",
  "code":"482901",
  "password":"a strong password",
  "password_confirm":"a strong password"
}
```

The transaction locks the challenge, allows at most five guesses, applies Django password validators,
creates the user/token once and consumes the challenge. Concurrent verification cannot create two
accounts. Error bodies contain a stable `error.code`; `429` also returns bounded `retry_after` and
`Retry-After`.
The extended registration payload also accepts `username`, `first_name` and `last_name`; the
storefront requires all three identity fields. The registration OTP confirms the phone. Email is
verified separately through the authenticated email-change flow.

## Account security routes

The same fixed boundary exposes the following flows:

```text
POST /api/v1/users/password/forgot/
POST /api/v1/users/password/reset/
PUT  /api/v1/users/password/change/
POST /api/v1/users/delete/
GET  /api/v1/users/sessions/
POST /api/v1/users/sessions/revoke-all/
POST /api/v1/users/email/change/start/
POST /api/v1/users/phone/change/start/
POST /api/v1/users/contact/verify/
POST /api/v1/users/signout/
```

Forgot-password always returns a neutral `202` receipt, stores only the keyed challenge digest,
limits attempts and invalidates the old authentication token after a successful reset. Account
deletion requires the current password plus the literal `DELETE`, keeps order/course history,
anonymizes the customer identity, marks the account inactive and revokes the token. The current
compatibility session store is one DRF token per account; `revoke-all` therefore invalidates the
active account token and the response explicitly clears the browser cookie.

## SMS delivery

Production uses the fixed HTTPS Eskiz login and SMS endpoints through `httpx`, bounded responses,
short timeouts and disabled redirects. The adapter caches the provider token in-process and retries
an SMS exactly once only after an explicit `401`. It does not retry network/timeout failures because
delivery may already have occurred; such a challenge remains verifiable with status `unknown`.
The multipart field names and endpoints follow the
[official Eskiz Postman collection](https://documenter.getpostman.com/view/663428/TVK5eMco).

Required production configuration:

```dotenv
SMS_BACKEND=eskiz
ESKIZ_PROVIDER_EMAIL=...
ESKIZ_PROVIDER_PASSWORD=...
ESKIZ_FROM_TO=...
ESKIZ_OTP_TEMPLATE=BodySteel verification code: {code}
BODYSTEEL_STOREFRONT_PROXY_TOKEN=...
PHONE_VERIFICATION_HASH_KEY=...
AUTH_RATE_LIMIT_HASH_KEY=...
AUTH_CHALLENGE_HASH_KEY=...
PASSWORD_RESET_TTL_SECONDS=600
PASSWORD_RESET_RESEND_SECONDS=60
PASSWORD_RESET_MAX_ATTEMPTS=5
AUTH_EMAIL_BACKEND=smtp
DEFAULT_FROM_EMAIL=no-reply@bodysteel.uz
AUTH_TRUSTED_PROXY_NETWORKS=10.0.0.0/8,192.0.2.10/32
```

The four auth secrets must be independently generated and stored. The Eskiz message template must
be approved by the provider before rollout, as required in the
[provider moderation notice](https://www.eskiz.uz/news/vazhnaya-informaciya-po-usluge-sms-informirovaniya-ucell).
`SMS_BACKEND=disabled` is the safe local default and causes code delivery to fail closed.
It is also a valid production fallback while Telegram-only OTP is enabled; no placeholder Eskiz
credentials are required. Set `SMS_BACKEND=eskiz` only together with real provider credentials.
For local development use `DEBUG=1`, `SMS_BACKEND=local` and `AUTH_EMAIL_BACKEND=local`. Codes are
kept only in bounded process memory and are exposed only through the dev-only OTP endpoint used by
the local storefront; no code is written to the database or logs.

## Abuse controls and operations

PostgreSQL persists fixed-window limits for registration phone/email/IP and sign-in phone/IP. IPs are
resolved only through explicitly trusted proxy networks and stored as keyed HMAC, never raw. These
application limits are defense in depth; the edge proxy must also rate-limit the three auth routes.

Apply append-only migrations `users.0005_auth_security` and
`users.0006_phoneverificationchallenge_first_name_and_more`, then schedule cleanup:

```bash
python manage.py purge_auth_security_records
python manage.py check --deploy
```

Run the auth test suite on both SQLite and PostgreSQL. Never perform a live SMS smoke with a customer
number without explicit approval; use an approved staging recipient and confirm the provider request
format/template before enabling public traffic.
