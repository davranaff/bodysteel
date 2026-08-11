# REGOS inventory synchronization

REGOS is the source of truth for the `Product.quantity` shown by the BodySteel
site. The integration has three compatible routes:

1. **Recommended for the current REGOS screen — local integration webhook.**
   BodySteel acknowledges each callback immediately, saves it in a durable
   queue, then reads the authoritative balance through `Item/GetExt`.
2. **Alternative — REGOS To Server.** REGOS pushes the complete selected stock
   list to BodySteel at the period configured in REGOS.
3. **Repair/reconciliation — direct REGOS API.** The `sync_regos_inventory`
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

# Value delivered by REGOS as connected_integration_id after saving the local
# integration. It is required to authenticate callbacks.
REGOS_CONNECTED_INTEGRATION_ID=<connected-integration-id>

# Optional: only sell inventory from these REGOS warehouse IDs.
REGOS_STOCK_IDS=12,18
REGOS_API_TIMEOUT_SECONDS=15
```

`REGOS_API_ENDPOINT` is useful when REGOS supplies a non-default endpoint; if
it is set, it takes precedence over `REGOS_INTEGRATION_KEY`.

## REGOS local integration setup

This corresponds to the **Local integrations → Create** screen in
`regos.online`.

| REGOS field | Value |
| --- | --- |
| Name | `BodySteel — синхронизация остатков` |
| URL handler | `https://api.bodysteel.uz/integration/v1/regos/webhook` |
| Webhooks | `DocChequeClosed`, `DocOrderDeliveryPerformed`, `DocOrderDeliveryReturned`, `DocOrderDeliveryPerformCanceled`, `ItemAdded`, `ItemEdited`, `ItemDeleted`, `ItemDeleteMarked` |

After saving, copy the displayed full **Endpoint** into
`REGOS_API_ENDPOINT`, and copy the integration ID REGOS delivers as
`connected_integration_id` into `REGOS_CONNECTED_INTEGRATION_ID`. Do not
publish that URL or ID. The production `bodysteel-regos-sync.timer` processes
the queue every minute and retries an unavailable REGOS API with exponential
backoff. Keep the direct reconciliation command scheduled nightly as a repair
path.

### Product lifecycle events

| REGOS event | BodySteel result |
| --- | --- |
| `ItemAdded` | creates a **hidden REGOS draft**; it cannot be sold before review |
| `ItemEdited` | refreshes stock, code/article and price; a published card keeps its editorial name |
| `ItemDeleted`, `ItemDeleteMarked` | archives the linked site card and sets its available quantity to `0` without deleting its history or images |

In Django Admin open **Products**, filter **"Черновики REGOS"**, fill in the
photo/category/content, select the required cards, then use **"Опубликовать
выбранные черновики REGOS"**. Published REGOS cards are shown on the website;
draft and archived cards are excluded from catalog APIs, carts and orders.

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
