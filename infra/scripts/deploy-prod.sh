#!/usr/bin/env bash
set -euo pipefail
cd /opt/joldinaw
backend=${1:?backend digest required}
frontend=${2:?frontend digest required}
[[ "$backend" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]] || exit 2
[[ "$frontend" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]] || exit 2
export BACKEND_IMAGE="$backend" FRONTEND_IMAGE="$frontend"
compose=(docker compose --env-file .env.production -f compose.prod.yaml)
previous_backend=''
previous_frontend=''
if [[ -f .release ]]; then
  mapfile -t previous < .release
  previous_backend=${previous[0]}
  previous_frontend=${previous[1]}
fi
"${compose[@]}" config --quiet
"${compose[@]}" pull
"${compose[@]}" run --rm migrate
if "${compose[@]}" up -d --wait --wait-timeout 180 &&
   "${compose[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready')"; then
  [[ ! -f .release ]] || cp .release .release.previous
  printf '%s\n%s\n' "$backend" "$frontend" > .release
else
  "${compose[@]}" logs --tail=60 api worker
  if [[ -n "$previous_backend" && -n "$previous_frontend" ]]; then
    export BACKEND_IMAGE="$previous_backend" FRONTEND_IMAGE="$previous_frontend"
    "${compose[@]}" up -d --wait --wait-timeout 180
  fi
  exit 1
fi
