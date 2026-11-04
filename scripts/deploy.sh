#!/usr/bin/env bash
# Zero-surprise deployment for a single VPS.
#
#   ./scripts/deploy.sh            # deploy the checked-out revision
#   ./scripts/deploy.sh --rollback # go back to the previously deployed image tag
#
# Steps: build images tagged with the git revision → encrypted pre-deploy backup → migrations →
# restart services → health check through Nginx → on failure, automatic rollback to the previous tag.
# Migrations are written expand/contract (additive first), so the previous release keeps working on the
# migrated schema. If a release ever needs a destructive migration, restore the pre-deploy backup with
# scripts/restore.sh instead of an image rollback.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "deploy: .env missing (cp .env.example .env and fill it)" >&2; exit 2; }
set -a; . ./.env; set +a
COMPOSE=${COMPOSE:-docker compose -f docker-compose.prod.yml}
STATE=.deploy; mkdir -p "$STATE"
PREV=$(cat "$STATE/current_tag" 2>/dev/null || true)
BUILD_ARGS=${DOCKER_BUILD_ARGS:-}

health() {
  for i in $(seq 1 45); do
    if $COMPOSE exec -T nginx wget -q -O /dev/null --no-check-certificate "https://127.0.0.1/api/v1/health/ready" --header "Host: $WESAL_DOMAIN" 2>/dev/null \
       && $COMPOSE exec -T nginx wget -q -O /dev/null --no-check-certificate "https://127.0.0.1/ar" --header "Host: $WESAL_DOMAIN" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

switch_to() {
  export WESAL_TAG=$1
  $COMPOSE up -d --remove-orphans postgres redis
  $COMPOSE --profile ops run --rm migrate
  $COMPOSE up -d --remove-orphans api worker scheduler frontend nginx
  $COMPOSE exec -T nginx nginx -s reload >/dev/null 2>&1 || true
}

if [ "${1:-}" = "--rollback" ]; then
  [ -n "$PREV" ] || { echo "deploy: no previous release recorded" >&2; exit 1; }
  ROLLBACK_TO=$(cat "$STATE/previous_tag" 2>/dev/null || echo "$PREV")
  echo "deploy: rolling back to $ROLLBACK_TO"
  export WESAL_TAG=$ROLLBACK_TO
  $COMPOSE up -d api worker scheduler frontend nginx
  $COMPOSE exec -T nginx nginx -s reload >/dev/null 2>&1 || true
  health && echo "$ROLLBACK_TO" > "$STATE/current_tag" && echo "deploy: rollback healthy" && exit 0
  echo "deploy: rollback unhealthy — consider scripts/restore.sh with the last pre-deploy backup" >&2; exit 1
fi

TAG=${WESAL_TAG_OVERRIDE:-$(git rev-parse --short=12 HEAD)}
[ -z "$(git status --porcelain --untracked-files=no 2>/dev/null)" ] || echo "deploy: WARNING working tree has uncommitted changes" >&2
echo "deploy: building $TAG (previous: ${PREV:-none})"
# shellcheck disable=SC2086
docker build $BUILD_ARGS -t "${WESAL_BACKEND_IMAGE:-wesal-backend}:$TAG" backend/
# shellcheck disable=SC2086
docker build $BUILD_ARGS -t "${WESAL_FRONTEND_IMAGE:-wesal-frontend}:$TAG" frontend/

if $COMPOSE ps --status running postgres 2>/dev/null | grep -q postgres; then
  echo "deploy: pre-deploy backup"
  ./scripts/backup.sh "pre-$TAG"
else
  echo "deploy: first installation (no running database) — skipping pre-deploy backup"
fi

switch_to "$TAG"
if health; then
  [ -n "$PREV" ] && [ "$PREV" != "$TAG" ] && echo "$PREV" > "$STATE/previous_tag"
  echo "$TAG" > "$STATE/current_tag"
  echo "$(date -u +%FT%TZ) $TAG ok" >> "$STATE/history.log"
  echo "deploy: $TAG is live and healthy"
  exit 0
fi

echo "deploy: $TAG failed health checks" >&2
echo "$(date -u +%FT%TZ) $TAG failed" >> "$STATE/history.log"
$COMPOSE logs --tail=50 api frontend nginx >&2 || true
if [ -n "$PREV" ]; then
  echo "deploy: rolling back to $PREV" >&2
  export WESAL_TAG=$PREV
  $COMPOSE up -d api worker scheduler frontend nginx
  $COMPOSE exec -T nginx nginx -s reload >/dev/null 2>&1 || true
  health && echo "deploy: rolled back to $PREV (healthy)" >&2
fi
exit 1
