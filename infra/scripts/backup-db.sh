#!/usr/bin/env bash
set -euo pipefail
cd /opt/joldinaw
mkdir -p backups
chmod 700 backups
docker compose --env-file .env.production -f compose.prod.yaml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backups/db-$(date -u +%Y%m%dT%H%M%SZ).dump"
chmod 600 backups/*.dump
