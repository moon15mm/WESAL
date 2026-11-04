# syntax=docker/dockerfile:1.7
# WESAL API / worker / scheduler image (Ubuntu 24.04 LTS, Python 3.12).
#   docker build -t wesal-backend backend/
# Behind a TLS-intercepting proxy, pass its CA without baking it into the image:
#   docker build --secret id=extra_ca,src=/path/ca.crt --build-arg HTTPS_PROXY=... backend/
ARG BASE_IMAGE=ubuntu:24.04

FROM ${BASE_IMAGE} AS base
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8
# apt helper: uses the optional proxy CA secret for this RUN only
RUN printf '%s\n' '#!/bin/sh' 'set -e' \
      'if [ -f /run/secrets/extra_ca ]; then' \
      '  sed -i "s#http://#https://#g" /etc/apt/sources.list.d/ubuntu.sources' \
      '  echo "Acquire::https::CAInfo \"/run/secrets/extra_ca\";" > /etc/apt/apt.conf.d/99extra-ca' \
      'fi' \
      'apt-get update' \
      'apt-get install -y --no-install-recommends "$@"' \
      'rm -rf /var/lib/apt/lists/* /etc/apt/apt.conf.d/99extra-ca' \
      'sed -i "s#https://#http://#g" /etc/apt/sources.list.d/ubuntu.sources' \
    > /usr/local/bin/apt-install && chmod 0755 /usr/local/bin/apt-install

FROM base AS build
RUN --mount=type=secret,id=extra_ca,mode=0444 apt-install python3 python3-venv python3-dev build-essential
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=secret,id=extra_ca,mode=0444 \
    if [ -f /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; \
    python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --disable-pip-version-check -r /tmp/requirements.txt

FROM base AS runtime
# libmagic: upload type sniffing · pango/harfbuzz: WeasyPrint PDFs (Arabic/Urdu/Hindi shaping)
# postgresql-client: backups/restore · tini: signal handling
RUN --mount=type=secret,id=extra_ca,mode=0444 apt-install \
        python3 ca-certificates libmagic1t64 libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
        shared-mime-info postgresql-client curl tini \
    && groupadd --system --gid 10001 wesal \
    && useradd --system --uid 10001 --gid wesal --home-dir /app --shell /usr/sbin/nologin wesal
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STORAGE_DIR=/data/storage ENV=production
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY --chown=wesal:wesal alembic.ini ./
COPY --chown=wesal:wesal alembic ./alembic
COPY --chown=wesal:wesal app ./app
COPY --chmod=0755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN mkdir -p /data/storage && chown -R wesal:wesal /data
USER wesal
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD curl -fsS http://127.0.0.1:8000/api/v1/health/live || exit 1
ENTRYPOINT ["/usr/bin/tini", "--", "docker-entrypoint.sh"]
CMD ["api"]
