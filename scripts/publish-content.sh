#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
compose=(docker compose --env-file .env.production -f docker-compose.prod.yml)

if [[ "${1:-}" == "--pull" ]]; then
  git diff --quiet && git diff --cached --quiet || { echo "Commit or save local changes before pulling." >&2; exit 1; }
  git pull --ff-only
elif [[ $# -ne 0 ]]; then
  echo "Usage: bash scripts/publish-content.sh [--pull]" >&2
  exit 1
fi

# Backend checks file mtimes at a five-second TTL. Let that TTL expire before
# invalidating Next caches, so a hot backend cannot refill them with old text.
sleep 6
"${compose[@]}" exec -T frontend node - <<'NODE'
(async () => {
  for (const path of ['articles', 'notes', 'projects']) {
    const response = await fetch(`${process.env.API_INTERNAL_URL}/api/v1/${path}`, {signal:AbortSignal.timeout(10000)});
    if (!response.ok) throw Error(`Content refresh failed: ${response.status}`);
  }
  const response = await fetch('http://127.0.0.1:3000/api/revalidate', {
    method:'POST', headers:{authorization:`Bearer ${process.env.REVALIDATE_SECRET}`}, signal:AbortSignal.timeout(10000),
  });
  if (!response.ok) throw Error(`Revalidation failed: ${response.status}`);
  for (const path of ['/', '/blog', '/notes', '/projects', '/sitemap.xml']) {
    const page = await fetch(`http://127.0.0.1:3000${path}`, {signal:AbortSignal.timeout(20000)});
    if (!page.ok) throw Error(`Page warm-up failed: ${path} (${page.status})`);
    await page.arrayBuffer();
  }
  console.log('Content published; frontend caches refreshed.');
})().catch(error => { console.error(error.message); process.exitCode=1; });
NODE
