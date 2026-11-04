# Deployment (single VPS, Docker Compose)

Tested end-to-end on 2026-11-04 in an isolated environment: first install, TLS (self-signed), migrations,
health checks through Nginx, a second release, manual rollback, automatic rollback after a failed health gate,
encrypted backup, restore verification and a full production restore. Not yet run on a real VPS with a real
domain and Let's Encrypt certificate.

## 1 · Server

* Ubuntu 24.04 LTS, 4 vCPU / 8 GB RAM / 80 GB SSD is comfortable for launch (the API sustained ~90 req/s on
  4 shared vCPUs in the load test — see [TEST_REPORT.md](TEST_REPORT.md)).
* Prefer a region in the Kingdom (data residency, PDPL).
* DNS `A` (and `AAAA` if you enable IPv6 in the Nginx template) record → server IP.

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl git gnupg ufw rclone unattended-upgrades
```

```bash
curl -fsSL https://get.docker.com | sudo sh
```

Firewall — only SSH and web:

```bash
sudo ufw default deny incoming && sudo ufw default allow outgoing && sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable
```

SSH hardening: key-only login (`PasswordAuthentication no`, `PermitRootLogin no` in `/etc/ssh/sshd_config`),
a non-root deploy user in the `docker` group, automatic security updates (`sudo dpkg-reconfigure unattended-upgrades`).
Note that Docker publishes ports outside ufw's chains; the compose file publishes only 80/443 (Nginx).

## 2 · Configuration

```bash
sudo mkdir -p /opt/wesal && sudo chown $USER /opt/wesal && git clone <repository-url> /opt/wesal
```

```bash
cd /opt/wesal && cp .env.example .env && chmod 600 .env
```

Fill **every** value in `.env` (generation commands are at the top of the file). Required in production:
`WESAL_DOMAIN`, `DB_OWNER_PASSWORD`, `DB_APP_PASSWORD`, `REDIS_PASSWORD`, `SECRET_KEY` (≥32 random chars),
`FIELD_ENCRYPTION_KEY`, SMTP settings, `BACKUP_GPG_RECIPIENT`. The API refuses to start with insecure values.
Keep a copy of `.env` in your password manager — `FIELD_ENCRYPTION_KEY` is needed to read MFA secrets after a restore.

Backup key: create the GPG key pair on an **offline/admin workstation**, import only the public key on the server:

```bash
gpg --export --armor backup@your-company.example > backup-public.asc
```

```bash
gpg --import backup-public.asc
```

## 3 · TLS certificate (first time)

```bash
./scripts/init-tls.sh letsencrypt ops@your-company.example
```

Then enable automatic renewal (twice daily) and a weekly Nginx reload:

```bash
docker compose -f docker-compose.prod.yml --profile tls up -d certbot
```

```bash
(crontab -l 2>/dev/null; echo "0 4 * * 1 cd /opt/wesal && docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload") | crontab -
```

For a staging box without public DNS use `./scripts/init-tls.sh self-signed`.

## 4 · First deployment

```bash
./scripts/deploy.sh
```

It builds `wesal-backend:<git-sha>` and `wesal-frontend:<git-sha>`, starts Postgres/Redis (creating the
restricted `wesal_app` role on first start), runs migrations + reference data with the owner role, starts
`api`, `worker`, `scheduler`, `frontend`, `nginx`, and waits for `https://…/api/v1/health/ready` and the home
page through Nginx. Then create the first administrator (prints a one-time generated password):

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.cli create-admin --email admin@your-company.example --name "Platform Admin"
```

Sign in, enrol MFA (required for admin pages), then in **Admin → Content** review the legal drafts and
**Admin → Settings** set support e-mail/phone.

## 5 · Updates & rollback

```bash
git pull && ./scripts/deploy.sh
```

Every deploy: encrypted pre-deploy backup → migrations → restart → health gate. If the health gate fails, the
script restores the previous image tag automatically. Manual rollback to the previous release:

```bash
./scripts/deploy.sh --rollback
```

Release history: `.deploy/history.log`; current/previous tags: `.deploy/current_tag`, `.deploy/previous_tag`.
Because migrations are additive (expand/contract, see [DATABASE.md](DATABASE.md)), an image rollback keeps
working on the newer schema. If a release ever contains a destructive migration, roll back by restoring its
pre-deploy backup (`scripts/restore.sh production …`).

Behind a TLS-intercepting corporate proxy, pass the CA and proxy to the builds:
`DOCKER_BUILD_ARGS="--secret id=extra_ca,src=/path/ca.crt --build-arg HTTPS_PROXY=http://proxy:3128" ./scripts/deploy.sh`.

## 6 · Scheduled operations (cron on the host)

```bash
(crontab -l 2>/dev/null; echo "30 1 * * * cd /opt/wesal && ./scripts/backup.sh nightly >> /var/log/wesal-backup.log 2>&1"; echo "30 3 * * 0 cd /opt/wesal && ./scripts/restore.sh verify \$(ls -t /var/backups/wesal/wesal-*.tar.gpg | head -1) >> /var/log/wesal-restore-check.log 2>&1") | crontab -
```

The restore check needs the private key; run it on a machine that has it (or use a separate verification
server), see [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

## 7 · Operations

| Task | Command |
|---|---|
| Status | `docker compose -f docker-compose.prod.yml ps` |
| Logs (JSON) | `docker compose -f docker-compose.prod.yml logs -f --tail=100 api worker scheduler nginx` |
| Health | `curl -fsS https://$WESAL_DOMAIN/api/v1/health/ready` |
| Admin CLI | `docker compose -f docker-compose.prod.yml exec api python -m app.cli --help` |
| DB shell (owner) | `docker compose -f docker-compose.prod.yml exec postgres psql -U wesal_owner wesal` |
| Scale workers | `docker compose -f docker-compose.prod.yml up -d --scale worker=2` |

Monitoring to add on day one: an external uptime check on `/api/v1/health/ready`, disk-space alerts, and the
**Admin → System** page (DB/Redis status, failed notifications, scheduled job runs).

## 8 · Demo environment

Run a separate stack/database (never the production one) with `DEMO_MODE=true`, `ENV=development` and
`COOKIE_SECURE=true` behind HTTPS, then `python -m app.cli reset-demo --yes`. Production refuses demo seeding.

## 9 · Integrations to configure (each optional, each untested against live accounts)

| Feature | Variables | Notes |
|---|---|---|
| SMS OTP / alerts | `SMS_PROVIDER=unifonic` + `UNIFONIC_APP_SID`, or `twilio` + `TWILIO_*` | Sender ID must be registered with CST in KSA |
| WhatsApp | `WHATSAPP_PROVIDER=meta_cloud`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | Business-initiated messages need approved templates |
| Web push | `PUSH_PROVIDER=webpush`, `VAPID_*` | |
| AI (Claude) | `AI_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` | Sends minimal user-scoped data to Anthropic; check PDPL transfer requirements first |
