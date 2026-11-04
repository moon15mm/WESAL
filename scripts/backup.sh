#!/usr/bin/env bash
# Encrypted backup of the WESAL database + uploaded files.
#
#   ./scripts/backup.sh [label]
#
# Produces  $BACKUP_DIR/wesal-<UTC timestamp>[-label].tar.gpg  (+ .sha256), containing:
#   db.dump       pg_dump custom format (schema, data, RLS policies, grants)
#   storage.tgz   uploaded files volume
#   manifest.txt  timestamp, git revision, image tag, checksums
# Encryption: GPG public key (BACKUP_GPG_RECIPIENT, recommended — the private key never lives on the
# server) or a symmetric passphrase file (BACKUP_PASSPHRASE_FILE). Unencrypted backups are refused.
# Off-site: copied with rclone when BACKUP_RCLONE_REMOTE is set. Old local copies beyond
# BACKUP_KEEP_DAYS are removed.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
export WESAL_TAG=${WESAL_TAG:-$(cat .deploy/current_tag 2>/dev/null || echo latest)}  # release recorded by deploy.sh

COMPOSE=${COMPOSE:-docker compose -f docker-compose.prod.yml}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/wesal}
KEEP=${BACKUP_KEEP_DAYS:-14}
LABEL=${1:-}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
NAME="wesal-${STAMP}${LABEL:+-$LABEL}"
umask 077
mkdir -p "$BACKUP_DIR"
WORK=$(mktemp -d "${BACKUP_DIR}/.work.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

if [ -n "${BACKUP_GPG_RECIPIENT:-}" ]; then
  ENC=(gpg --batch --yes --trust-model always --encrypt --recipient "$BACKUP_GPG_RECIPIENT")
elif [ -n "${BACKUP_PASSPHRASE_FILE:-}" ] && [ -r "$BACKUP_PASSPHRASE_FILE" ]; then
  ENC=(gpg --batch --yes --pinentry-mode loopback --passphrase-file "$BACKUP_PASSPHRASE_FILE" --symmetric --cipher-algo AES256)
else
  echo "backup: set BACKUP_GPG_RECIPIENT (preferred) or BACKUP_PASSPHRASE_FILE — refusing to write an unencrypted backup" >&2
  exit 2
fi

echo "backup: dumping database"
$COMPOSE exec -T postgres pg_dump -U wesal_owner -d wesal -Fc --no-password > "$WORK/db.dump"
[ -s "$WORK/db.dump" ] || { echo "backup: empty database dump" >&2; exit 1; }

echo "backup: archiving uploaded files"
# read the volume directly so this works whether or not the app containers are running
docker run --rm -v "${COMPOSE_PROJECT_NAME:-wesal}_storage:/data/storage:ro" "${POSTGRES_IMAGE:-postgres:16-alpine}" \
  tar -C /data -czf - storage > "$WORK/storage.tgz"

{
  echo "created_utc=$STAMP"
  echo "git_revision=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "image_tag=${WESAL_TAG:-latest}"
  (cd "$WORK" && sha256sum db.dump storage.tgz)
} > "$WORK/manifest.txt"

tar -C "$WORK" -cf - manifest.txt db.dump storage.tgz | "${ENC[@]}" --output "$BACKUP_DIR/$NAME.tar.gpg"
(cd "$BACKUP_DIR" && sha256sum "$NAME.tar.gpg" > "$NAME.tar.gpg.sha256")
echo "backup: wrote $BACKUP_DIR/$NAME.tar.gpg ($(du -h "$BACKUP_DIR/$NAME.tar.gpg" | cut -f1))"

if [ -n "${BACKUP_RCLONE_REMOTE:-}" ]; then
  echo "backup: copying off-site to $BACKUP_RCLONE_REMOTE"
  rclone copy "$BACKUP_DIR/$NAME.tar.gpg" "$BACKUP_RCLONE_REMOTE"
  rclone copy "$BACKUP_DIR/$NAME.tar.gpg.sha256" "$BACKUP_RCLONE_REMOTE"
else
  echo "backup: WARNING no off-site copy (BACKUP_RCLONE_REMOTE not set)" >&2
fi

find "$BACKUP_DIR" -maxdepth 1 -name 'wesal-*.tar.gpg*' -type f -mtime +"$KEEP" -print -delete | sed 's/^/backup: pruned /'
echo "$BACKUP_DIR/$NAME.tar.gpg"
