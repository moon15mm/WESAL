# WESAL – Project Status

> Living status file. Updated at every significant milestone so work can resume after any interruption.

## Current phase
Phase 2/3 – Foundation & business modules (backend).

## Done
- Environment inspected (Python 3.13, Node 22, PostgreSQL 16, Redis, Docker available; GitHub raw/Google Fonts blocked → fonts via npm @fontsource).
- Backend skeleton (FastAPI, SQLAlchemy 2.1, Alembic), 83-table schema (migration 0001).
- Security migration 0002: restricted runtime DB role, forced row-level security on tenant tables, append-only audit/history tables.
- Core: config, sessions (opaque tokens, HMAC-hashed), CSRF double-submit, argon2id, TOTP MFA + recovery codes, OTP codes, rate limiting, secure uploads, audit log, i18n, RBAC catalog.
- Auth module + tests (8 passing).

## Next
- Business modules: businesses/branches/team, catalog, pricing, reps, authorizations, CRM, visits, orders, approvals, offers, delivery, returns, commissions, ratings, complaints, notifications API, reports, AI, admin.
- Frontend (Next.js), brand assets, Docker/Nginx, docs.

## Decisions
See ARCHITECTURE.md (to be written) – key ones:
- Modular monolith; sync SQLAlchemy; transactional outbox + DB-polling worker instead of Celery (fewer moving parts, exactly-once enqueue with business change).
- Server-side sessions (revocable, device list) instead of JWT.
- Product identity (products) separated from supplier offers (supplier_products); size/flavour variants are distinct products (barcode identity), packaging levels in product_units.

## External blockers
- No VPS / domain / SMTP / SMS / WhatsApp / AI keys provided – integrations implemented behind adapters, tested with in-memory mocks only.
