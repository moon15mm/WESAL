#!/usr/bin/env bash
# Obtain the first TLS certificate before Nginx can start on 443.
#
#   ./scripts/init-tls.sh letsencrypt ops@example.com   # real certificate (DNS must already point here, port 80 free)
#   ./scripts/init-tls.sh self-signed                   # staging / local testing only
#
# Renewal afterwards: `docker compose -f docker-compose.prod.yml --profile tls up -d certbot`
# (renews twice a day via the webroot served by Nginx) and reload Nginx weekly from cron:
#   0 4 * * 1  cd /opt/wesal && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
export WESAL_TAG=${WESAL_TAG:-$(cat .deploy/current_tag 2>/dev/null || echo latest)}  # release recorded by deploy.sh
COMPOSE=${COMPOSE:-docker compose -f docker-compose.prod.yml}
MODE=${1:-}
case "$MODE" in
  letsencrypt)
    EMAIL=${2:?email required}
    $COMPOSE --profile tls run --rm -p 80:80 --entrypoint certbot certbot certonly --standalone \
      -d "$WESAL_DOMAIN" --email "$EMAIL" --agree-tos --no-eff-email --non-interactive ;;
  self-signed)
    $COMPOSE --profile tls run --rm --entrypoint sh certbot -c "
      set -e; d=/etc/letsencrypt/live/$WESAL_DOMAIN; mkdir -p \$d
      python3 - <<'PY'
import datetime, os
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
dom = os.environ.get('WESAL_DOMAIN', '$WESAL_DOMAIN')
key = ec.generate_private_key(ec.SECP256R1())
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, dom)])
now = datetime.datetime.now(datetime.timezone.utc)
cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(dom)]), critical=False).sign(key, hashes.SHA256()))
d = '/etc/letsencrypt/live/' + dom
open(d + '/privkey.pem', 'wb').write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
open(d + '/fullchain.pem', 'wb').write(cert.public_bytes(serialization.Encoding.PEM))
PY
      chmod 600 \$d/privkey.pem" ;;
  *) sed -n '2,9p' "$0"; exit 2 ;;
esac
echo "init-tls: certificate ready for $WESAL_DOMAIN"
