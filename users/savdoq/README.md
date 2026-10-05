# SAVDOQ shopper chat sessions

Django issues the short-lived SAVDOQ widget sessions that let a signed-in customer use the AI
chat. SAVDOQ service credentials live only here; the storefront and the mobile app never hold
them.

`POST /api/v1/users/savdoq/session/` is a server-to-server boundary, like sign-in: it requires the
customer's DRF token, the storefront proxy token (`X-Storefront-Proxy-Token`) and
`Accept-Language: ru|uz`. The body must be empty. `X-Savdoq-Session: new` skips the stored session
and starts a new SAVDOQ conversation, because SAVDOQ keeps one conversation per widget session.

```json
{"data": {
  "session": {"accessToken": "…", "tokenType": "Bearer", "expiresAt": "…Z",
              "sessionId": "…", "shopperAuthenticated": true, "persistent": true},
  "site": {"apiOrigin": "https://rag.halysontech.uz", "publicKey": "wpk_…"}
}}
```

Errors: `401` without a customer session, `403 chat_refused` and `429 chat_rate_limited` (with
`Retry-After`) when SAVDOQ refuses, `503 chat_unavailable` for outages or missing configuration.

Sign-out, revoke-all, password change and account deletion revoke the customer's SAVDOQ sessions
before the account mutation. A failed revocation returns `503` and is not reported as a
completed sign-out.

## Configuration

Set these server-only environment values; leaving all of them empty turns the chat off.

| Variable | Value |
| --- | --- |
| `SAVDOQ_API_ORIGIN` | `https://rag.halysontech.uz` |
| `SAVDOQ_WIDGET_PUBLIC_KEY` | the storefront widget key, `wpk_…` |
| `SAVDOQ_SHOPPER_SERVICE_TOKEN` | SAVDOQ shopper-session service token |
| `SAVDOQ_SHOPPER_IDENTITY_KEY` | HMAC key for shopper identities |
| `SAVDOQ_STOREFRONT_ORIGIN` | the origin registered in SAVDOQ, default `https://bodysteel.uz` |

Copy `SAVDOQ_SHOPPER_SERVICE_TOKEN` and `SAVDOQ_SHOPPER_IDENTITY_KEY` unchanged from the former
storefront environment. The identity key must never change: SAVDOQ stores chat history under
`HMAC-SHA256(key, "bodysteel:v1:<customer id>")`, so a new key detaches every customer from
their history. `manage.py check --deploy` reports a partial or invalid configuration.

## Rollout

1. Deploy Django with these variables and run `migrate` (`users.0009`).
2. Deploy the storefront version that proxies `/api/savdoq/widget-session` to this endpoint.
3. Remove the three `SAVDOQ_*` secrets from the storefront environment.
