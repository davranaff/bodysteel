# REGOS inventory synchronization

REGOS is the source of truth for the `Product.quantity` shown by the BodySteel
site. The integration has two compatible routes:

1. **Recommended — REGOS To Server.** REGOS pushes the complete selected stock
   list to BodySteel at the period configured in REGOS. This has no polling
   worker to operate and is the best option for keeping the site current.
2. **Repair/reconciliation — direct REGOS API.** The `sync_regos_inventory`
   command reads `Item/GetExt`. Run it from cron every night, and on demand
   after the initial setup. It is also a useful diagnostic path.

Both paths use `allowed` inventory, rather than `common`, so stock reserved in
REGOS is not offered for sale on the site. Fractional quantities are rejected:
the current BodySteel product model supports only whole pieces.

For example, when a cashier makes an offline POS sale and REGOS changes an
item's available quantity from `5` to `4`, the next To Server export updates
the same site product from `5` to `4`. Set the To Server period to 1 minute if
that is the maximum acceptable delay. A completed offline return works in the
same direction: REGOS changing available quantity from `4` to `5` restores the
site inventory to `5` on the next export.

## Environment

Add these deployment secrets (never commit them):

```dotenv
# Required for REGOS To Server receiver. Use a generated, unique password.
REGOS_TO_SERVER_USERNAME=bodysteel-regos
REGOS_TO_SERVER_PASSWORD=<random-secret>

# Required only for the direct reconciliation command. REGOS gives this when
# you create a local integration. Either this key or the full endpoint is used.
REGOS_INTEGRATION_KEY=<connected-integration-id>
# REGOS_API_ENDPOINT=https://integration.regos.uz/gateway/out/<key>/v1

# Optional: only sell inventory from these REGOS warehouse IDs.
REGOS_STOCK_IDS=12,18
REGOS_API_TIMEOUT_SECONDS=15
```

`REGOS_API_ENDPOINT` is useful when REGOS supplies a non-default endpoint; if
it is set, it takes precedence over `REGOS_INTEGRATION_KEY`.

## REGOS To Server setup

In **REGOS Store Management → Settings and security → Integrations → To
Server**, enable the integration and set:

| REGOS field | Value |
| --- | --- |
| URL | `https://api.bodysteel.uz/integration/v1/regos/to-server` |
| Requires authorization | enabled |
| Login / password | `REGOS_TO_SERVER_USERNAME` / `REGOS_TO_SERVER_PASSWORD` |
| Period | the required maximum delay (normally 1–5 minutes) |
| Stock / enterprise | the same stock scope as the web store |

Press **Test** before enabling it. The endpoint accepts the documented
JSON-RPC 2.0 export. It returns per-request counts but never returns stock data
or credentials.

## Matching rules and first run

On the first successful sync a site product is linked only when the REGOS name
exactly matches `name_ru` or `name_uz` after case/space normalization. The
saved REGOS ID, code and article are then used for every following sync, so
later product renames are safe. Records that cannot be matched are skipped and
reported as `unmatched`; they never overwrite an arbitrary product.

For a product whose name is intentionally different, fill the REGOS ID, code
or article fields in Django Admin once. This one-time identity mapping cannot
be safely inferred from credentials alone.

## Direct reconciliation

After deploying and migrating, verify direct API access with:

```bash
python manage.py sync_regos_inventory
```

Set a nightly cron entry (or your platform's scheduled-command equivalent):

```cron
15 3 * * * cd /srv/bodysteel && /srv/bodysteel/venv/bin/python manage.py sync_regos_inventory
```

The command fails non-zero on an invalid configuration, transport error or
REGOS business error, making it suitable for existing monitoring. It does not
create products, prices, or orders; its sole write responsibility is stock and
the stable identity mapping.
