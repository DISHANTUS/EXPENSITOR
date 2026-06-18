#!/usr/bin/env sh
# Production startup (Render): apply migrations, run idempotent seeds, then serve
# on the platform-provided $PORT. Kept as a file so there is zero shell-quoting
# ambiguity in the deploy command.
set -e

alembic upgrade head
python -m app.seed.run_seeds
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
