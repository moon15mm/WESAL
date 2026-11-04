# syntax=docker/dockerfile:1.7
# WESAL web (Next.js standalone).  Build: docker build -t wesal-frontend frontend/
# Behind a TLS-intercepting proxy: --secret id=extra_ca,src=/path/ca.crt --build-arg HTTPS_PROXY=...
ARG NODE_IMAGE=node:22-bookworm-slim

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=secret,id=extra_ca,mode=0444 \
    if [ -f /run/secrets/extra_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/extra_ca npm_config_cafile=/run/secrets/extra_ca; fi; \
    npm ci --no-audit --no-fund

FROM ${NODE_IMAGE} AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run check:i18n && npx next build

FROM ${NODE_IMAGE} AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN groupadd --system --gid 10001 wesal && useradd --system --uid 10001 --gid wesal --home /app wesal
COPY --from=build --chown=wesal:wesal /app/.next/standalone ./
COPY --from=build --chown=wesal:wesal /app/.next/static ./.next/static
COPY --from=build --chown=wesal:wesal /app/public ./public
USER wesal
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/ar').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
