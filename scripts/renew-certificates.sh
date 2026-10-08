#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
compose=(docker compose --env-file .env.production -f docker-compose.prod.yml)
"${compose[@]}" run --rm certbot renew --webroot --webroot-path /var/www/certbot --quiet
"${compose[@]}" exec -T nginx nginx -t
"${compose[@]}" exec -T nginx nginx -s reload
