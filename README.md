# Expensitor

An AI Financial Co-Pilot. Expensitor helps users decide whether their **future
planned expenses** are financially possible and guides them toward affording
their goals — using a domain-specific intelligence engine (no paid LLM APIs).

> **Status:** Week 1 — backend foundation (FastAPI + PostgreSQL + SQLAlchemy +
> Alembic + Docker). Auth, money CRUD, currency conversion, and the intelligence
> engine arrive in later phases.

## Tech stack (MVP)

- **Mobile:** Flutter + Material 3 + Riverpod + GoRouter *(later phase)*
- **Backend:** FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16
- **AI/ML:** Pandas + Scikit-learn *(later phase, all deterministic — no LLM)*
- **Infra:** Docker Compose (api + db only)

## Project layout

```
EXPENSITOR/
├── backend/
│   ├── app/
│   │   ├── core/        # config, database engine/session
│   │   ├── db/          # declarative Base + mixins
│   │   ├── models/      # SQLAlchemy models (10 tables)
│   │   ├── api/v1/      # routers (system health for now)
│   │   ├── seed/        # idempotent currency + category seeds
│   │   ├── schemas/     # (later)
│   │   ├── services/    # (later)
│   │   └── intelligence/# (later) the projection / co-pilot engine
│   ├── alembic/         # migrations
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
└── .env / .env.example
```

## Quick start

1. Create your env file and set real secrets:
   ```bash
   cp .env.example .env
   # edit .env: set SECRET_KEY and POSTGRES_PASSWORD
   ```
2. Build and run (migrations + seeds run automatically):
   ```bash
   docker compose up --build
   ```
3. Verify:
   - API docs:    http://localhost:8000/docs
   - Liveness:    http://localhost:8000/api/v1/health
   - Readiness:   http://localhost:8000/api/v1/ready   (checks DB)

## Database

- Migrations are managed by Alembic (`backend/alembic`). The initial migration
  creates all 10 MVP tables and the `pg_trgm` extension.
- Run migrations manually inside the api container:
  ```bash
  docker compose exec api alembic upgrade head
  ```
- Re-run seeds (idempotent):
  ```bash
  docker compose exec api python -m app.seed.run_seeds
  ```

## Notes

- Money is stored as `NUMERIC` (never float). Every income/expense keeps its
  original amount + currency + exchange-rate snapshot + base-currency value.
- The initial Alembic migration is hand-authored to match the models; future
  changes should use `alembic revision --autogenerate`.
