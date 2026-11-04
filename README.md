# وِصال | WESAL

**كل السوق في اتصال واحد. — One Market. Connected.**

WESAL is a multi-party B2B marketplace for the Saudi retail & distribution sector. It connects
**stores / supermarkets**, **independent and company sales representatives**, **suppliers / brands**, and
**platform administrators** — with Arabic (default, RTL), English, Urdu (RTL) and Hindi throughout.

Core rules the platform enforces in code (not just in policy text):

* Representatives sell for a supplier **only under an active authorization** (products, areas, commission, dates).
* An order prepared by a representative **only becomes an order after the store explicitly approves** the exact
  version shown (version + snapshot hash). Any supplier change needs a new store approval.
* The **supplier delivers**, the **store pays the supplier directly** — the platform never holds funds or goods;
  it records collection status and commission payout evidence.
* Customers are not "owned"; acquisition source and history are recorded for commission and reporting.
* Every business only sees its own data — enforced by PostgreSQL row-level security, not only by the API.

## Repository layout

| Path | What |
|---|---|
| `backend/` | FastAPI modular monolith, SQLAlchemy 2, Alembic migrations, worker & scheduler, tests |
| `frontend/` | Next.js 16 (App Router) + React 19 + Tailwind 4 + next-intl, Playwright E2E |
| `brand/` | Logo system (outlined SVG, PNG, ICO, print PDF), brand guidelines, generators |
| `deploy/` | Nginx config, Postgres role bootstrap |
| `scripts/` | `deploy.sh`, `backup.sh`, `restore.sh`, `init-tls.sh`, `loadtest.py`, `gen_docs.py` |
| `docs/` | Architecture, database, API, security, deployment, backup, user guides, test report |
| `docker-compose.prod.yml` | Production stack · `docker-compose.yml` — local Postgres + Redis |

## Quick start (local development)

Requirements: Python 3.12+, Node 22, PostgreSQL 16, Redis 7 (or `docker compose up -d`), system libs
`libmagic1` and Pango (for PDF export).

```bash
docker compose up -d
```

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

```bash
cd backend && cp .env.example .env && .venv/bin/alembic upgrade head && .venv/bin/python -m app.cli seed-reference
```

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm ci && npm run dev
```

Open http://localhost:3000/ar. Create the first administrator:

```bash
cd backend && .venv/bin/python -m app.cli create-admin --email you@example.com --name "Your Name"
```

### Demo environment

A separate demo database with fictional companies, stores, representatives, products, orders in every
state, commissions, visits and complaints (never use in production — the app refuses):

```bash
cd backend && DEMO_MODE=true .venv/bin/python -m app.cli reset-demo --yes
```

All demo accounts use the password `Wesal-Demo-2026`; the command prints the account list
(e.g. `demo.store.rayyan@example.com`, `demo.supplier.nokhba@example.com`, `demo.rep.riyadh@example.com`).

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q
```

```bash
cd frontend && npm run check:i18n && npx tsc --noEmit
```

```bash
cd frontend && npx playwright test
```

(E2E runs against a running demo environment; see [docs/TEST_REPORT.md](docs/TEST_REPORT.md).)

## Documentation

* [Project status](PROJECT_STATUS.md) · [Changelog](CHANGELOG.md)
* [Architecture](docs/ARCHITECTURE.md) · [Database](docs/DATABASE.md) · [API](docs/API_DOCUMENTATION.md)
* [Security](docs/SECURITY.md) · [Deployment](docs/DEPLOYMENT.md) · [Backup & restore](docs/BACKUP_RESTORE.md)
* [دليل المستخدم (عربي)](docs/USER_GUIDE_AR.md) · [User guide (English)](docs/USER_GUIDE_EN.md)
* [Test report](docs/TEST_REPORT.md) · [Brand guidelines](brand/BRAND_GUIDELINES.md)

## Licence & legal

The legal documents shipped in `backend/app/seed/legal/` are **operational drafts that require review by a
lawyer licensed in Saudi Arabia**. Nothing in this repository claims that the platform holds any licence or
official certification.
