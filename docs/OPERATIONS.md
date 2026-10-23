# Operations

Local diagnostics: `docker compose ps`, `docker compose logs --tail=100 api worker`, `curl http://localhost:8000/ready`. Failed parser records show safe errors; repair/reupload a document or correct its extracted text. Queue outages persist failed status. Worker crashes/timeouts may leave a processing record requiring administrator recovery; automatic stale-job reconciliation is pending.

Production: use `docker compose --env-file .env.production -f compose.prod.yaml ...` with BACKEND_IMAGE/FRONTEND_IMAGE set to the current approved digests. `bash infra/scripts/backup-db.sh` makes a private custom-format database dump. Also back up the private CV storage volume and reviewed model cache, encrypted off-host with an explicit retention policy. Database-only backup is insufficient to restore original documents.

Restore into a disposable rehearsal environment first. Stop application writes, verify the target database and backup, then run `CONFIRM_RESTORE=yes bash infra/scripts/restore-db.sh backups/<file>.dump`; restore matching file storage, migrate if necessary, restart and verify authorized record access/citations. Rehearsal has not been performed on the initial host.

Model updates: acquire/review weights explicitly offline, record source commit/checksum, evaluate independently, mount the approved local model and set EMBEDDING_PATH/EMBEDDING_REVISION. Restart the worker only after reviewing compatibility; old results keep their model metadata. No normal startup trains or downloads.

Retention: organization admins should review documents on the agreed schedule and delete through the API/UI. Deletion cascades live data, while backup expiry must be handled separately. Restrict storage/log access. Never log CV contents or bearer tokens. Audit rows contain minimal IDs and actions. Automatic retention scheduling and orphan-file reconciliation remain future hardening work.
