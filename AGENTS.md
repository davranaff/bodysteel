# BodySteel engineering rules

These rules apply to the Django store backend.

- Keep the SAVDOQ Integration API store-owned. It may read catalog/inventory/cart application data,
  but it must never import or connect to SAVDOQ databases, workers, AI providers or tenant tables.
- External JSON uses canonical names such as `name` and `description`. RU/UZ selection is transported
  only through `Accept-Language` and `Content-Language`; language-suffixed model fields stay private.
- Organize Integration API code by feature: HTTP boundaries call one catalog/cart operation and do
  not expose Django model rows directly.
- Keep handwritten production files at or below 250 lines and functions focused. Avoid catch-all
  helper modules and implementation logic in `__init__.py`.
- Bearer tokens are server-only environment secrets. Compare digests constant-time; never log raw
  credentials, request bodies, AI session IDs or restore tokens.
- Validate unknown query/body fields, sizes, identifiers, timestamps and content types at the HTTP
  boundary. Problem responses must not expose stack traces, SQL or settings.
- Product pagination must be deterministic and cursor values opaque/tamper-evident. `updatedAfter`
  is strict (`updated_at > watermark`) and every representation-changing relation must bump the
  product watermark.
- Cart creation must recheck live stock and use durable transactional idempotency. An exact replay
  returns the same receipt; a reused key with different input returns `409`.
- Storefront order creation requires a bounded `Idempotency-Key`. Persist only its digest and a
  normalized request fingerprint; an exact replay must not repeat stock, coupon, bonus or notification
  side effects.
- Public registration/sign-in routes are server-to-server boundaries. Require the independent
  storefront proxy token plus `Accept-Language`; never allow a direct browser call to bypass the
  Next.js exact-Origin adapter.
- Registration creates `User` only after a durable, expiring, single-use OTP challenge succeeds.
  Store only keyed OTP/rate-limit digests, enforce attempt/cooldown limits transactionally and never
  log codes, raw IPs, passwords, provider tokens or auth request bodies.
- Store-authored HTML must use `SanitizedHtmlField` and the versioned allowlist policy. Do not add
  executable editor JavaScript, bypass sanitation with `update()`/`bulk_update()`, or change an
  existing policy version; add a new policy and append-only data migration instead.
- The local `ckeditor.fields` module is historical-migration compatibility only. It must never be
  added to `INSTALLED_APPS`, served as static content or used by current models/admin forms.
- Store changes create webhook rows in the same business transaction. HTTP delivery runs only from
  the outbox worker with exact-body HMAC, bounded leases/retries and redirects disabled.
- `order.completed` payloads are allowlisted and PII-free. Never send shopper names, phones,
  addresses, payment details, restore capabilities or arbitrary order fields to SAVDOQ.
- Migrations are append-only. Do not rewrite migrations that may have been deployed.
- Every Integration API change requires focused Django tests for auth, RU/UZ, pagination/delta,
  ETag, inventory, validation, idempotency and restore-token behavior.
