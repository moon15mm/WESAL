#!/usr/bin/env bash
# Restore a WESAL backup produced by scripts/backup.sh
#
#   ./scripts/restore.sh verify <file.tar.gpg>               # restore into a scratch DB, check, drop it (safe, run weekly)
#   ./scripts/restore.sh production <file.tar.gpg> --yes     # REPLACE the live database and files
#
# Decryption needs the private key (GPG) or BACKUP_PASSPHRASE_FILE on the machine doing the restore.
# "production" first takes a safety backup of the current state, stops the app services, restores,
# runs migrations (in case the backup predates the current schema) and health-checks.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
export WESAL_TAG=${WESAL_TAG:-$(cat .deploy/current_tag 2>/dev/null || echo latest)}  # release recorded by deploy.sh
COMPOSE=${COMPOSE:-docker compose -f docker-compose.prod.yml}
MODE=${1:-}; FILE=${2:-}; CONFIRM=${3:-}
[ -n "$MODE" ] && [ -f "$FILE" ] || { sed -n '2,10p' "$0"; exit 2; }

if [ -f "$FILE.sha256" ]; then (cd "$(dirname "$FILE")" && sha256sum -c "$(basename "$FILE").sha256" >/dev/null) || { echo "restore: checksum mismatch" >&2; exit 1; }; fi
umask 077
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
DEC=(gpg --batch --yes --decrypt)
[ -n "${BACKUP_PASSPHRASE_FILE:-}" ] && DEC=(gpg --batch --yes --pinentry-mode loopback --passphrase-file "$BACKUP_PASSPHRASE_FILE" --decrypt)
"${DEC[@]}" "$FILE" 2>/dev/null | tar -C "$WORK" -xf -
(cd "$WORK" && grep -E '^[0-9a-f]{64}  ' manifest.txt | sha256sum -c --quiet) || { echo "restore: archive content checksum mismatch" >&2; exit 1; }
echo "restore: archive OK — $(grep created_utc "$WORK/manifest.txt")"

psql_owner() { $COMPOSE exec -T postgres psql -v ON_ERROR_STOP=1 -U wesal_owner -d "$1" -tA -c "$2"; }

if [ "$MODE" = "verify" ]; then
  DB=wesal_restore_check
  psql_owner postgres "DROP DATABASE IF EXISTS $DB"
  psql_owner postgres "CREATE DATABASE $DB OWNER wesal_owner"
  $COMPOSE exec -T postgres pg_restore -U wesal_owner -d "$DB" --exit-on-error < "$WORK/db.dump"
  echo "restore: verify counts in restored copy:"
  for t in users businesses products orders commissions audit_logs; do
    printf '  %-14s %s\n' "$t" "$(psql_owner "$DB" "SELECT count(*) FROM $t")"
  done
  echo "  rls_tables     $(psql_owner "$DB" "SELECT count(*) FROM pg_class WHERE relrowsecurity AND relforcerowsecurity")"
  echo "  alembic        $(psql_owner "$DB" "SELECT version_num FROM alembic_version")"
  tar -tzf "$WORK/storage.tgz" >/dev/null && echo "  storage files  $(tar -tzf "$WORK/storage.tgz" | grep -vc '/$')"
  psql_owner postgres "DROP DATABASE $DB"
  echo "restore: verification succeeded (scratch database dropped)"
  exit 0
fi

[ "$MODE" = "production" ] && [ "$CONFIRM" = "--yes" ] || { echo "restore: production restore needs: production <file> --yes" >&2; exit 2; }
echo "restore: taking a safety backup of the current state first"
./scripts/backup.sh pre-restore
$COMPOSE stop nginx frontend api worker scheduler
psql_owner postgres "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='wesal' AND pid <> pg_backend_pid()" >/dev/null
psql_owner postgres "DROP DATABASE wesal"
psql_owner postgres "CREATE DATABASE wesal OWNER wesal_owner"
psql_owner wesal "REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT CONNECT ON DATABASE wesal TO wesal_app"
$COMPOSE exec -T postgres pg_restore -U wesal_owner -d wesal --exit-on-error < "$WORK/db.dump"
docker run --rm -i -v "${COMPOSE_PROJECT_NAME:-wesal}_storage:/data/storage" "${POSTGRES_IMAGE:-postgres:16-alpine}" \
  sh -c 'find /data/storage -mindepth 1 -delete && tar -C /data -xzf - && chown -R 10001:10001 /data/storage' < "$WORK/storage.tgz"
$COMPOSE --profile ops run --rm migrate
$COMPOSE up -d api worker scheduler frontend nginx
for i in $(seq 1 30); do
  if $COMPOSE exec -T api curl -fsS http://127.0.0.1:8000/api/v1/health/ready >/dev/null 2>&1; then echo "restore: done, API healthy"; exit 0; fi
  sleep 2
done
echo "restore: API not healthy after restore — check logs" >&2; exit 1
