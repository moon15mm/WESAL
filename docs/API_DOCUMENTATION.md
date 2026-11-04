# API documentation

* Base path: `/api/v1` (same origin as the web app behind Nginx).
* **283 operations** — full index: [API_ENDPOINTS.md](API_ENDPOINTS.md); machine-readable schema:
  [openapi.json](openapi.json) (OpenAPI 3, regenerated with `scripts/gen_docs.py`).
* Interactive docs (`/api/docs`, `/api/redoc`) are served by the API in development; Nginx blocks them in production.

## Conventions

| Topic | Rule |
|---|---|
| Language | `X-Locale: ar \| en \| ur \| hi` (falls back to `Accept-Language`, then `ar`). Error messages, notification texts and generated documents follow it. |
| Business context | Users who belong to several businesses send `X-Business-Id: <uuid>`; it must be an active membership (otherwise `403`, and the attempt is audited). Without it the first membership of the right type is used. |
| Money | Decimal **strings** (`"30.00"`), currency `SAR`. Never floats. |
| Time | ISO-8601 UTC (`2026-11-04T09:30:00Z`); clients display in `Asia/Riyadh`. |
| Pagination | `?page=1&page_size=20` (max 100) → `{"items": [...], "total": n, "page": 1, "page_size": 20}` |
| IDs | UUIDs; human numbers (`WSL-2026-000123`) are for display and search. |

## Authentication

**Browser (default):** `POST /auth/login` sets two cookies — `wesal_session` (`HttpOnly`, `Secure`, `SameSite=Lax`,
opaque random token; only its HMAC is stored server-side) and `wesal_csrf` (readable). Every non-GET request must
echo the CSRF cookie in `X-CSRF-Token` (double-submit). Fetch a fresh CSRF cookie with `GET /auth/csrf`.

**API clients / mobile:** send `X-Auth-Mode: bearer` on login to also receive `session_token` in the body, then use
`Authorization: Bearer <token>` (CSRF is not required for bearer requests).

```bash
curl -s -X POST https://wesal.example.com/api/v1/auth/login -H 'content-type: application/json' -H 'x-auth-mode: bearer' -d '{"identifier":"owner@store.example","password":"…"}'
```

When MFA is enabled the login response is `{"mfa_required": true}`; complete it with
`POST /auth/mfa/verify {"code": "123456"}` (TOTP or a recovery code). Platform-admin endpoints require an
MFA-verified session. Sessions expire after inactivity and at an absolute limit (shorter for admins and
supplier managers); `GET /auth/sessions` lists and `DELETE /auth/sessions/{id}` revokes them.

## Errors

```json
{"error": {"code": "authorization_area_not_covered", "message": "المدينة خارج نطاق تفويضك لهذه الشركة.",
           "params": {"city": "جدة"}, "fields": {}, "request_id": "5a1f…"}}
```

| Status | Typical codes |
|---|---|
| 400/422 | `validation_failed` (with `fields`), `insufficient_stock`, `invalid_phone`, business-rule codes |
| 401 | `unauthorized` (missing, expired or revoked session), `mfa_required` |
| 403 | `permission_denied`, `csrf_failed`, `authorization_missing`, `authorization_product_not_covered` |
| 404 | `not_found` — also returned for resources of other tenants (no existence leak) |
| 409 | `conflict`, `invalid_transition`, `order_version_changed` (approval hash/version mismatch), `already_rated` |
| 429 | `rate_limited` (`params.retry_after` = seconds to wait) |
| 503 | `integration_unavailable` (e.g. SMS provider not configured) |

All codes are translated in the four languages (`backend/app/locales/*.json`); a test fails if one is missing.

## Rate limits

Per account and per IP in Redis (examples: login 10 / 5 min per identifier and 30 / 5 min per IP; registration
10 / hour per IP; OTP 10 / hour; AI assistant 30 / hour per user; personal-data export 5 / hour). Nginx adds
per-IP request-rate limits (`/api` 20 r/s, auth endpoints 5 r/s, with bursts).

## Main flows

### 1 · Store direct order

```text
PUT  /retailer/carts/{supplier_id}/items   {"offer_id": "…", "unit": "carton", "quantity": 3}
POST /retailer/carts/{supplier_id}/checkout {"notes": "…", "branch_id": "…"}          → order status "new"
POST /supplier/orders/{id}/accept          {}                                          → "approved"
  or POST /supplier/orders/{id}/offer      {"items":[{order_item_id, quantity, unit_price, discount}], "delivery_fee": "0"} → "quoted"
POST /retailer/orders/{id}/accept-offer    {"version": 2, "snapshot_hash": "…"}        → "approved"
POST /supplier/orders/{id}/prepare | /ready | /dispatch {driver_name, vehicle_plate} | /deliver (multipart, proof)
POST /retailer/orders/{id}/confirm-delivery {"items":[{order_item_id, received_qty, damaged_qty}]} → "completed"
POST /supplier/orders/{id}/collections     (multipart: amount, method, reference, evidence) → payment status
```

### 2 · Representative order (store approval required)

```text
GET  /rep/catalog?supplier_id=…            only products/areas inside an active authorization
POST /rep/visits                           {"retailer_id": "…", "purpose": "order_taking", "start_now": true, "lat": …, "lng": …}
POST /rep/orders                           {"retailer_id","supplier_id","items":[…],"visit_id"} → "pending_retailer_approval"
GET  /retailer/orders/{id}                 → "pending_approval": {"version", "snapshot_hash", "snapshot"}
POST /retailer/orders/{id}/approve         {"version", "snapshot_hash"}                → "new" (now visible to supplier)
POST /retailer/orders/{id}/reject | /request-changes {"reason"}
```

Prices always come from the supplier's pricing engine; a representative cannot send a price.

### 3 · Authorization lifecycle

```text
POST /rep/authorizations                       {"supplier_id", "message"}             (rep requests)   → "sent"
POST /supplier/authorizations                  {…scope…}                              (supplier invites) → "draft"
POST /supplier/authorizations/{id}/issue       {"type","agreement_id","all_products","products","areas","start_date","end_date","terms"} → "pending_rep"
POST /rep/authorizations/{id}/accept           {"terms_hash"}                         → "active"
POST /supplier/authorizations/{id}/suspend | /resume | /cancel | /renew {"reason" …}
```

Expiry is automatic (scheduler); every change is appended to `authorization_history`.

### 4 · Commissions

```text
GET  /rep/commissions                          list + summary per status
POST /rep/commissions/{id}/dispute             {"reason", "expected_amount"}
POST /supplier/commissions/approve             {"commission_ids": [...]}
POST /supplier/commission-payments             (multipart: commission_ids, method, reference, evidence)
POST /supplier/commission-disputes/{id}/resolve {"accept", "resolution", "resolved_amount"}
```

### 5 · Reports & exports

`GET /reports/{retailer|supplier|rep}?date_from=&date_to=&format=json|csv|xlsx|pdf` (platform KPIs: `/admin/*`) and
`GET /orders/{id}/document.pdf?locale=ar|en|ur|hi` (defaults to the user's document language). Exports are audited and limited to the caller's own data.

## Webhooks / integrations

The platform currently makes only outbound calls (SMTP, SMS, WhatsApp, Web Push, optional Anthropic). There are no
inbound webhooks; delivery receipts from providers are not consumed yet.
