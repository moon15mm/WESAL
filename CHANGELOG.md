# Changelog

All notable changes. Dates are UTC. Versions follow semantic versioning once released.

## [1.0.0-rc.1] – 2026-11-04

### Added
- **Platform:** FastAPI modular monolith (19 modules, 283 API operations), PostgreSQL schema of 83 tables with
  Alembic migrations, outbox worker and scheduler; Next.js web app with store, representative, supplier,
  business and admin workspaces plus marketing site.
- **Business rules:** authorization-scoped representative selling; store approval of representative orders with
  version + snapshot hash; 17-state order engine; supplier offers and change approvals; delivery confirmation with
  shortages/damage; collection evidence (no funds held); returns; commission engine with hold period, approval,
  payout evidence, disputes and one-time return adjustments; ratings bound to real transactions; complaints.
- **Catalog:** shared product identity by barcode, supplier offers, price lists (customer/region/default),
  promotions (percent/fixed/quantity tier), CSV import, Arabic-aware search.
- **CRM & field work:** customers with acquisition source and history, notes, contacts, opportunities, store
  discovery, visits with consent-based location, tasks and targets.
- **i18n:** Arabic (default), English, Urdu, Hindi across UI, API errors, notifications and documents; automated
  completeness checks; runtime translation overrides.
- **Reports:** role reports and order documents in CSV (formula-safe), XLSX (RTL) and PDF (embedded fonts per script).
- **AI assistant:** local engine (order text parsing, scoped Q&A, reorder forecast, rep opportunities) and an
  optional Claude adapter with strict, read-only tools and local fallback.
- **Security:** RLS on 37 tenant tables, append-only audit/history, Argon2id, TOTP MFA (mandatory for admins),
  revocable server-side sessions, CSRF protection, rate limits, hardened uploads, security headers.
- **Brand:** original logo system (outlined SVG, PNG, ICO, print PDF), app icon, splash, social image, PWA
  manifest, brand guidelines.
- **Legal:** 10 policy drafts in Arabic and English published as content pages (pending legal review).
- **Demo:** fictional demo dataset built through the real API; `reset-demo` command; refused in production.
- **Operations:** Docker images, production compose with Nginx/TLS, `deploy.sh` with health gate and rollback,
  GPG-encrypted backups with off-site copy and retention, `restore.sh` verify/production, TLS bootstrap, CI
  workflow, load-test script, documentation set.

### Security
- Migration `0003`: suppliers can no longer read representative orders that await store approval, even at the
  SQL level.
