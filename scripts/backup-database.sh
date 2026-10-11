#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
umask 077
mkdir -p backups
backup="backups/bks-lab-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
uploads_backup="${backup%.dump}-uploads.tar.gz"
compose=(docker compose --env-file .env.production -f docker-compose.prod.yml)
trap 'rm -f -- "${backup}.partial" "${uploads_backup}.partial"' EXIT
"${compose[@]}" exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "${backup}.partial"
"${compose[@]}" exec -T db pg_restore --list < "${backup}.partial" > /dev/null
mv -- "${backup}.partial" "$backup"
# Editor uploads live outside the database; archive the whole volume.
"${compose[@]}" exec -T backend sh -c 'exec tar -C /app/uploads -czf - .' > "${uploads_backup}.partial"
mv -- "${uploads_backup}.partial" "$uploads_backup"
echo "Backup saved: $backup"
echo "Uploads saved: $uploads_backup"
