#!/bin/sh
# Usage: docker-entrypoint.sh api | worker | scheduler | migrate | cli <args> | <any command>
set -e
case "$1" in
  api)
    shift
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers \
      --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}" --workers "${API_WORKERS:-2}" --no-server-header "$@" ;;
  worker)    exec python -m app.workers.worker ;;
  scheduler) exec python -m app.workers.scheduler ;;
  migrate)
    # migrations run with the owner role; the services themselves only use the RLS-restricted role
    python -m alembic upgrade head
    exec python -m app.cli seed-reference ;;
  cli)       shift; exec python -m app.cli "$@" ;;
  *)         exec "$@" ;;
esac
