#!/usr/bin/env bash
set -euo pipefail
cd /opt/joldinaw
dump=${1:?backup file required}
[[ ${CONFIRM_RESTORE:-} == yes ]] || { echo 'Stop API/workers and set CONFIRM_RESTORE=yes after reviewing the target database'; exit 2; }
docker compose --env-file .env.production -f compose.prod.yaml exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$dump"
