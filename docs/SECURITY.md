# Security

This document describes the controls implemented in code, how they were verified, and the residual risks
that remain. Report vulnerabilities privately to the platform operator (security contact configured in
platform settings); do not open public issues for them.

## Threat model in one paragraph

WESAL holds commercial data of competing businesses (prices, customers, sales, commissions). The main risks
are **cross-tenant data access** (a supplier seeing a competitor's customers or orders), **unauthorized order
or commission manipulation** (e.g. a representative inflating a price, approving on a store's behalf),
**account takeover**, **malicious uploads**, and **tampering with the audit trail**. The platform holds no
payment funds, which removes card-data scope (no PCI DSS), but payout evidence and documents are sensitive.

## Controls

| Area | Implementation | Verified by |
|---|---|---|
| Tenant isolation | PostgreSQL RLS with `FORCE ROW LEVEL SECURITY` on 37 tenant tables; runtime role owns nothing and has `NOBYPASSRLS`; context set per transaction; `X-Business-Id` validated against active membership | `test_scenarios::test_rls_blocks_cross_tenant_reads_at_database_level` (raw SQL as the app role), cross-tenant API tests (`404` for other tenants' resources) |
| Order integrity | Prices computed server-side by the pricing engine; reps cannot send prices; store approval requires version + SHA-256 snapshot hash; suppliers cannot see unapproved rep orders (API **and** RLS, migration 0003) | scenario tests 2/3/4, E2E `order-flow.spec.ts` |
| Authorization scope | Rep orders/catalogue checked against active authorization (status, dates, products/categories/brands, cities) | `test_scenarios`, `test_modules` |
| Authentication | Argon2id password hashes; password policy (length ≥10, 3 character classes, common-password list, not containing email/phone); account lock after 5 failures for 15 min; verification codes hashed, single-use, expiring, attempt-limited | `test_auth.py` |
| MFA | TOTP (RFC 6238) + one-time recovery codes; secrets encrypted at rest (Fernet); **mandatory for platform admin endpoints** (`MFA_ENFORCE_ADMIN=true`) | `test_auth.py` (`make_admin` enrols MFA) |
| Sessions | Opaque 256-bit random tokens; only HMAC-SHA256 stored; idle + absolute expiry (shorter for sensitive roles); list/revoke sessions; password change revokes others | `test_auth.py` |
| CSRF | Double-submit cookie (`wesal_csrf` + `X-CSRF-Token`, constant-time compare) on every state-changing cookie request; `SameSite=Lax` | E2E `security.spec.ts` |
| Cookies | `HttpOnly` session, `Secure` in production (startup refuses otherwise), scoped path | production config validation |
| RBAC | 51 permissions, 13 system roles across platform / retailer / supplier scopes + custom business roles; every endpoint declares its permission; admin actions additionally need platform permissions | `test_modules`, `test_scenarios` |
| Rate limiting | Redis counters per account/IP for login, OTP, registration, password reset, MFA, AI, exports; Nginx per-IP limits | E2E (lockout observed), `test_auth` |
| Uploads | Size limit (8 MB); type by magic bytes (`python-magic`), allow-list per purpose; images decoded and **re-encoded** (strips metadata/polyglots, decompression-bomb guard); PDFs with JavaScript/Launch/embedded files rejected; private files served only after a relationship check, denials audited; stored outside the web root with random names | `test_modules` (unsafe upload rejected) |
| Output encoding | React escaping; Markdown renderer without raw HTML; CSV export neutralises formula injection (`=`, `+`, `-`, `@`); JSON only from the API | code review, report tests |
| Security headers | CSP (`default-src 'self'`, `frame-ancestors 'none'`), HSTS (2 years), `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` (geolocation self only), COOP | checked through Nginx in the compose test |
| Audit trail | `audit_logs`, `order_status_history`, `authorization_history` append-only (DB trigger + revoked UPDATE/DELETE); app role cannot read audit logs; denied access attempts logged in a separate transaction | RLS test |
| Secrets | Only from environment (`.env`, `chmod 600`); `.env*` git-ignored; production start fails on default/short `SECRET_KEY`, missing `FIELD_ENCRYPTION_KEY`, insecure cookies, demo mode or non-SMTP email | `config.validate_production` |
| Privacy | Location only with explicit consent at visit check-in/out (no background tracking); data export & deletion requests; retention job | `test_modules` |
| AI | Tools only read data the user may already access; cannot create prices or approve/change orders; provider swappable and can be disabled; external provider off by default | `test_integrations_mocked.py`, `test_modules` |
| Transport & network | TLS 1.2/1.3 at Nginx; Postgres/Redis on an internal Docker network; containers run as non-root, read-only root FS, `no-new-privileges`, all capabilities dropped | compose test |
| Dependencies | Pinned versions; `pip-audit` and `npm audit` in CI — both reported **0 known vulnerabilities** on 2026-11-04 | CI |
| Backups | GPG-encrypted (public key; private key kept off the server), checksummed, off-site copy via rclone, restore verification | `scripts/restore.sh verify` run |

## OWASP Top 10 (2021) mapping

| Risk | Mitigation |
|---|---|
| A01 Broken access control | RBAC per endpoint + RLS in the database + relationship checks for files; tests for cross-tenant access |
| A02 Cryptographic failures | Argon2id, HMAC-hashed tokens, Fernet for TOTP secrets, TLS only, HSTS |
| A03 Injection | SQLAlchemy parameterised queries only; no string-built SQL with user input; CSV formula neutralisation |
| A04 Insecure design | Business invariants enforced server-side (store approval, authorization scope, no rep pricing, no double commission via unique constraints) |
| A05 Security misconfiguration | Production config validation; docs hidden in production; minimal container images; security headers |
| A06 Vulnerable components | Pinned dependencies, automated audits in CI |
| A07 Identification & auth failures | Lockout, rate limits, MFA, session expiry/revocation, generic login errors |
| A08 Software & data integrity | Approval snapshot hashes; append-only history; images built from the repository with pinned bases |
| A09 Logging & monitoring | Structured JSON logs with request IDs; audit log incl. denials; job run records |
| A10 SSRF | The server does not fetch user-supplied URLs (provider endpoints are fixed in code) |

## Security review performed (2026-11-04)

* Static review of every router for permission dependencies and tenant filters; RLS policies reviewed table by
  table. **Finding fixed:** the `orders` policy let a supplier read rep orders still awaiting store approval at
  the SQL level (the API already hid them) → tightened in migration `0003` with a regression test.
* **Finding fixed:** `CORS_ORIGINS` from the environment crashed startup unless written as JSON (availability) —
  now accepts comma-separated values.
* Browser checks: anonymous access redirects to login, a store cannot call supplier/admin APIs, CSRF-less POST
  is rejected, wrong password shows an error and repeated logins are rate limited.
* Dependency audits clean (see above).

## Residual risks & recommendations

* **No external penetration test** has been performed. Commission one before handling real customers.
* Uploaded PDFs/Office files are not scanned by an antivirus engine (only structural checks). Add ClamAV or a
  scanning service if documents will be opened by staff on desktops.
* No WAF/DDoS protection beyond Nginx limits — consider a CDN/WAF in front of the VPS.
* Centralised log shipping and alerting are not configured (logs rotate locally). Ship JSON logs to a SIEM and
  alert on `access_denied` spikes, login lockouts and job failures.
* Platform staff with `platform.*` permissions can read all private files (needed for verification); keep the
  admin group small and MFA-protected; their actions are audited.
* SMS/WhatsApp/AI provider integrations are implemented and mock-tested but **not verified against live
  accounts**; review each provider's data-processing terms (PDPL cross-border transfer) before enabling.
* Content Security Policy allows `'unsafe-inline'` scripts/styles (required by the current Next.js build);
  moving to nonce-based CSP is a hardening follow-up.
