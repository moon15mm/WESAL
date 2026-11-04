# Backup & restore

## What is backed up

`scripts/backup.sh` produces one encrypted archive `wesal-<UTC>[-label].tar.gpg` plus a `.sha256` file:

| Inside | Content |
|---|---|
| `db.dump` | `pg_dump -Fc` of the `wesal` database: schema, data, RLS policies, grants, triggers |
| `storage.tgz` | the uploaded-files volume (documents, images, proofs) |
| `manifest.txt` | creation time, git revision, image tag, SHA-256 of both files |

Not included (keep separately, in a password manager): the `.env` file — especially `FIELD_ENCRYPTION_KEY`
(MFA secrets) and `SECRET_KEY` (session hashing; losing it only logs everyone out).

## Encryption & storage

* Default: **asymmetric GPG** to `BACKUP_GPG_RECIPIENT`. The server holds only the public key, so a server
  compromise cannot decrypt old backups. Keep the private key offline (and a second copy with another officer).
* Alternative: symmetric AES-256 with `BACKUP_PASSPHRASE_FILE` (simpler, weaker operationally).
* The script refuses to write unencrypted backups.
* Off-site: set `BACKUP_RCLONE_REMOTE` (e.g. an S3-compatible bucket in-Kingdom with object-lock/versioning).
* Local retention: `BACKUP_KEEP_DAYS` (default 14 days); keep longer retention off-site (e.g. 30 daily, 12 monthly).
* `deploy.sh` takes an extra `pre-<release>` backup before every deployment; `restore.sh production` takes a
  `pre-restore` backup before replacing anything.

## Schedule (recommended)

| When | What |
|---|---|
| Daily 01:30 | `./scripts/backup.sh nightly` (cron on the host) |
| Weekly | `./scripts/restore.sh verify <latest>` on a machine holding the private key |
| Quarterly | Full restore drill into a staging server, timed, recorded below |

Targets: **RPO ≤ 24 h** (daily dumps; add WAL archiving/PITR such as pgBackRest if a smaller RPO is needed),
**RTO ≤ 2 h** for a full restore on a prepared server.

## Verify a backup (non-destructive)

```bash
./scripts/restore.sh verify /var/backups/wesal/wesal-20261104T084308Z-nightly.tar.gpg
```

Checks the archive checksum and the content checksums, restores into a scratch database
`wesal_restore_check`, prints row counts, the number of RLS-protected tables and the migration version, lists
storage files, and drops the scratch database.

## Restore production

```bash
./scripts/restore.sh production /var/backups/wesal/wesal-20261104T084308Z-nightly.tar.gpg --yes
```

1. verifies checksums and decrypts;
2. takes a safety backup of the current state (`pre-restore`);
3. stops Nginx, frontend, API, worker, scheduler;
4. recreates the database and restores the dump; replaces the uploaded files;
5. runs migrations (if the backup is older than the code);
6. starts the services and waits for the health check.

## Restore on a new server (disaster recovery)

1. Prepare the server as in [DEPLOYMENT.md](DEPLOYMENT.md) §1–3, restoring the saved `.env`.
2. Import the backup private key (temporarily) or copy the archive to a machine that has it.
3. `./scripts/deploy.sh` (creates an empty database and the services).
4. `./scripts/restore.sh production <archive> --yes`.
5. Remove the private key from the server again, rotate any credentials that may have been exposed.

## Drill log

| Date | Type | Backup | Result |
|---|---|---|---|
| 2026-11-04 | verify | `wesal-20261104T084308Z-nightly` | OK — 38 RLS tables, migration 0002, counts matched |
| 2026-11-04 | production restore (test stack) | same | OK — data rolled back to backup state (3 → 2 users), services healthy |
| 2026-11-04 | decryption without private key | same | correctly impossible |
