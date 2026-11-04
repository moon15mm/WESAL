# WESAL – Project Status

> Living status file. Updated at every significant milestone so work can resume after any interruption.

## Current phase
Phase 4 – Backend & frontend feature-complete (backend 27 tests; frontend builds, 1746 i18n keys × 4 locales). Next: brand assets, legal docs, demo seed, Docker/Nginx, E2E, docs.

## Done
- Environment inspected (Python 3.13, Node 22, PostgreSQL 16, Redis, Docker available; GitHub raw/Google Fonts blocked → fonts via npm @fontsource).
- Backend skeleton (FastAPI, SQLAlchemy 2.1, Alembic), 83-table schema (migration 0001).
- Security migration 0002: restricted runtime DB role, forced row-level security on tenant tables, append-only audit/history tables.
- Core: config, sessions (opaque tokens, HMAC-hashed), CSRF double-submit, argon2id, TOTP MFA + recovery codes, OTP codes, rate limiting, secure uploads, audit log, i18n, RBAC catalog.
- Auth module + tests.
- Modules: businesses/branches/team/roles/documents/coverage, catalog (offers, brands, CSV import, price lists, promotions, marketplace, compare), reps (profile, docs, directory, company reps, tasks, targets), authorizations (+commission agreements, history, renewal), CRM (customers, notes, contacts, source changes, opportunities, discovery), visits, orders (carts, direct, rep orders + approval snapshots, offers, change approvals, fulfillment, delivery confirmation, collections, invoices), returns, commissions (engine, approval, payouts, disputes, adjustments), ratings, complaints/disputes, notifications (in-app + outbox), reports (CSV/XLSX/PDF), order PDF (ar/en/ur/hi), AI (local engine + Claude adapter), admin, privacy (PDPL export/deletion), worker + scheduler.
- Backend locales (ar/en/ur/hi, 332 keys) with automated completeness test.

## Next
- Brand assets (SVG/PNG), demo seed, legal docs, Docker/Nginx/deploy/backup scripts, docs, E2E tests.

## Fixed bugs (log)
- RLS: INSERT…RETURNING on audit_logs failed (no SELECT policy) → implicit_returning disabled.
- RLS: ORM writes inside system_context flushed after context restore → system_context now flushes.
- Order line identities lost when supplier quoted → build_items updates lines in place.
- autoflush disabled caused stale reads → enabled.
- Arabic PDF digits broken (Arabic subset font) → Latin font first in Arabic family stack.

## Decisions
See ARCHITECTURE.md (to be written) – key ones:
- Modular monolith; sync SQLAlchemy; transactional outbox + DB-polling worker instead of Celery (fewer moving parts, exactly-once enqueue with business change).
- Server-side sessions (revocable, device list) instead of JWT.
- Product identity (products) separated from supplier offers (supplier_products); size/flavour variants are distinct products (barcode identity), packaging levels in product_units.

## External blockers
- No VPS / domain / SMTP / SMS / WhatsApp / AI keys provided – integrations implemented behind adapters, tested with in-memory mocks only.
