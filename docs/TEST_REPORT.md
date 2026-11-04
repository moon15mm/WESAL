# Test report

Date: **2026-11-04** · Revision: branch `claude/wesal-marketplace-platform-7ug6rk`

| Suite | Result | Where it ran |
|---|---|---|
| Backend (pytest, real PostgreSQL 16 + RLS, no DB mocks) | **38 passed / 0 failed** | host (Python 3.13) **and** inside the production backend image (Python 3.12, Ubuntu 24.04) |
| Frontend static checks | type check clean · i18n 1,746 keys × 4 locales, 1,072 static keys used, 0 missing · production build OK | host and inside the frontend image build |
| Browser E2E (Playwright, Chromium) | **20 passed / 0 failed** (desktop 1360×900 + Pixel 7) | against the demo environment (`next` standalone + API + PostgreSQL) |
| Production stack (docker compose) | deploy, health gate, TLS/headers, release, rollback, migrate 0002→0003 — all OK | local Docker, self-signed certificate |
| Backup / restore | encrypted backup, verify, production restore, decrypt-without-key refused — all OK | production stack |
| Load test | 0 errors; see below | API on host, 4 uvicorn workers |
| Dependency audit | `pip-audit`: no known vulnerabilities · `npm audit --omit=dev`: 0 vulnerabilities | host |

## Acceptance scenarios

| # | Scenario | Covered by | Result |
|---|---|---|---|
| 1 | Supplier registers, uploads CR, admin verifies, supplier lists products and appears in the market | `test_modules::test_supplier_registration_verification_scenario_1` | ✅ |
| 2 | Independent rep: request authorization → supplier issues terms → rep accepts → visit → rep order → store approves exact version → supplier accepts → delivery → completion → commission due → approved → paid; acquisition recorded | `test_scenarios::test_scenario_independent_representative_full_cycle` + E2E `order-flow.spec.ts` (UI) | ✅ |
| 3 | Store direct order → supplier counter-offer → store accepts → partial delivery with damage → collection evidence | `test_scenarios::test_scenario_direct_order_with_quote_and_partial_delivery` | ✅ |
| 4 | Security attempts: other supplier reads order (404), forged `X-Business-Id` (403), staff without permission, rep approving on behalf of store, supplier acting on a store endpoint, order after authorization cancelled, rep adjusting commission, raw-SQL cross-tenant read | `test_scenarios::test_scenario_security_attempts`, `::test_rls_blocks_cross_tenant_reads_at_database_level`, E2E `security.spec.ts` | ✅ |
| 5 | Multilingual: UI in ar/en/ur/hi with correct direction, localized API errors and notifications, PDFs in each script, legal pages | `test_i18n_backend.py` (5 tests), E2E `i18n.spec.ts` (10 tests), visual review of PDFs and screenshots | ✅ |

## Backend tests (38)

* **Auth (8):** registration + CSRF, duplicate & weak passwords, lockout & sessions, phone login & revoke,
  password reset revokes sessions, MFA & admin-requires-MFA, bearer mode, profile locale.
* **Catalog (5):** marketplace visibility, shared product identity by barcode & offer comparison, customer price
  list + promotion, offer isolation, CSV import.
* **Modules (6):** scenario 1, returns adjust commission exactly once + dispute flow, order dispute + ratings +
  reports + PDF/CSV/XLSX exports, AI features + scheduler jobs + notifications, authorization expiry blocks
  orders, privacy export + notification preferences.
* **Scenarios (4):** acceptance scenarios 2–4 and database-level RLS (incl. supplier cannot see an order awaiting
  store approval — regression test for the fix in migration 0003).
* **i18n (5):** every error code and notification event translated in 4 locales, identical key sets and
  parameters, localized error responses, 10 legal pages seeded and served in ar/en with fallback.
* **Integrations with isolated mocks (9):** Claude tool loop / refusal / tool errors / API-error mapping /
  missing key / endpoint fallback to the local engine; Unifonic, Twilio, WhatsApp Cloud and SMTP request shapes
  and error handling. **These do not prove the live providers accept the requests.**
* **Demo seed (1):** the demo dataset is produced through the real API and yields every expected order and
  commission state.

## E2E tests (20)

`i18n.spec.ts` (landing + signed-in dashboard in each of 4 locales with `lang`/`dir` checks and a scan for raw
message keys, language switcher, legal pages) · `order-flow.spec.ts` (rep builds order in the UI → supplier
cannot see it → store approves in the UI → supplier sees it) · `security.spec.ts` (anonymous redirect,
store blocked from supplier/admin APIs, CSRF required, wrong password) · `mobile.spec.ts` (bottom navigation,
add to cart and cart on a phone, no horizontal overflow on rep pages).

A crawl of **55 pages across store, supplier, rep and admin workspaces** found no page errors and no failing API
calls; screenshots were reviewed manually in Arabic (RTL), Urdu, Hindi and on a phone.

## Defects found and fixed during testing (this phase)

| Defect | Fix |
|---|---|
| Chart date ticks reordered by bidi in RTL (`042026/11/`) | strip bidi marks inside the LTR chart |
| Supplier commission cards ignored commissions in the hold period | "expected" card sums estimated + pending |
| KPI money values truncated on desktop / wrapped inside the currency on phones | non-breaking, responsive size |
| `CORS_ORIGINS` env value crashed startup unless JSON | accept comma-separated lists |
| Nginx kept old container IPs after a redeploy (502) | upstream re-resolution via Docker DNS + reload after switch |
| Nginx failed on hosts without IPv6 | IPv6 listeners opt-in |
| Backup required the API container to be running | archive the volume directly |
| Restore/backup used the `latest` tag instead of the deployed release | read `.deploy/current_tag` |
| `orders` RLS let suppliers read unapproved rep orders at SQL level | migration 0003 + regression test |
| Demo seeder: over-stock orders and wrong field names (caught by the API's own validation) | demo data corrected |

## Load test

`scripts/loadtest.py` — virtual users with **no think time** (each issues the next request immediately), mix of
60 % store (market, search, reports, orders, 10 % add-to-cart + checkout), 20 % supplier, 20 % representative.
Environment: 4 shared vCPUs running PostgreSQL, the API (4 uvicorn workers) and the load generator together;
rate limiting disabled to measure capacity.

| Virtual users | Requests | Throughput | Errors | p50 | p95 | p99 |
|---|---|---|---|---|---|---|
| 4 | 1,210 / 20 s | 60 req/s | 0 | 66 ms | 109 ms | 134 ms |
| 40 | 4,008 / 46 s | 87 req/s | 0 | 399 ms | 934 ms | 1,197 ms |

Interpretation: at light load responses are ~70 ms; the box saturates around 90 req/s, after which latency grows
by queueing, without errors. 40 zero-think-time users correspond to several hundred real concurrent users.
Heaviest endpoints under load: representative catalogue and supplier reports (~0.6 s p50 at saturation) — first
candidates for caching/indexing if real traffic requires it. Not tested: long-duration soak, larger datasets
(the demo has 19 products, ~15 orders), Nginx/TLS in the measurement path.

## Not tested / limitations

* Live providers: SMTP delivery, Unifonic/Twilio SMS, WhatsApp Cloud API, Web Push, Anthropic API — no credentials
  were available; adapters are tested with isolated mocks only.
* Real VPS, public DNS and Let's Encrypt issuance (self-signed certificate used locally).
* GitHub Actions workflow (`.github/workflows/ci.yml`) was written but not executed in GitHub.
* Browsers other than Chromium; screen readers / full accessibility audit.
* External penetration test.
