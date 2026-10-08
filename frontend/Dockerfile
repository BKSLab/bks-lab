FROM node:24-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline --no-audit --no-fund --maxsockets=4 --fetch-retries=3 --fetch-timeout=60000

FROM node:24-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
ARG SITE_URL=https://bks-lab.ru
ARG CONTACT_EMAIL=
ARG NEXT_PUBLIC_ADS_ENABLED=false
ARG NEXT_PUBLIC_YANDEX_AD_SIDEBAR_ID=
ARG NEXT_PUBLIC_YANDEX_AD_ARTICLE_ID=
ARG NEXT_PUBLIC_YANDEX_AD_NOTES_ID=
ENV SITE_URL=$SITE_URL CONTACT_EMAIL=$CONTACT_EMAIL
ENV NEXT_PUBLIC_ADS_ENABLED=$NEXT_PUBLIC_ADS_ENABLED
ENV NEXT_PUBLIC_YANDEX_AD_SIDEBAR_ID=$NEXT_PUBLIC_YANDEX_AD_SIDEBAR_ID
ENV NEXT_PUBLIC_YANDEX_AD_ARTICLE_ID=$NEXT_PUBLIC_YANDEX_AD_ARTICLE_ID
ENV NEXT_PUBLIC_YANDEX_AD_NOTES_ID=$NEXT_PUBLIC_YANDEX_AD_NOTES_ID
# The image is built independently of running application services.
RUN API_INTERNAL_URL=http://127.0.0.1:9 API_PROXY_URL=http://backend:8000 npm run build -- --webpack

FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nextjs && adduser --system --uid 1001 --ingroup nextjs nextjs
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nextjs /app/public ./public
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
