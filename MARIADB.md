# Drishti on a DigitalOcean Droplet

Run the FastAPI worker and Gunicorn/Flask on the same Ubuntu Droplet, with one MariaDB 10.11 database and one shared media volume. The Compose overlay publishes MariaDB on `127.0.0.1:3307` for both host Gunicorn and host-network FastAPI. phpMyAdmin reaches `database:3306` inside its Compose network. Caddy continues to proxy the API and staff site over HTTPS.

## Schema

The video pipeline uses **surveys, segments and detections**. The existing image, report, attachment, clip and audit tables remain for their respective features. Schema migrations still use the existing migration ledger.

| Table | Relationships and storage |
| --- | --- |
| `surveys` | Survey ID matches the mobile session ID. Stores the first known device ID, UTC first recorded time, latest uploaded recording end time, and a processing rollup. |
| `segments` | Foreign key to its survey. Unique survey and sequence. Integer `duration_ms`, UTC start and lifecycle timestamps, and relative MP4 and GPX paths under `uploads/`. Original request JSON and fingerprint preserve upload retries. |
| `detections` | Foreign key to the original segment. Stores confidence, coordinates, bounding box, frame offset, review status, and an annotated JPEG path under `instances/`. |
| `images` | Idempotent still-image reports and detection metadata. Models, timestamps, and evidence references continue to use the existing image API. |
| `web_reports` | Video reports reference the exact detection and its segment via a composite foreign key. Still-image reports retain their original image-report ID and detection ID. |
| `web_media` | Foreign key to its report. Attachment paths are relative to `report-media/` on the shared volume. |
| `web_video_clips` | Foreign key to its original segment. Stores trim settings. |
| `web_audit` | Audit events referencing report or segment IDs according to the action. |
| `schema_migrations` | Migration versions, execution state, and UTC start and completion timestamps. |

MariaDB uses `DATETIME(3)` for event times. Connections set the session time zone to UTC. Older API clients still receive the existing field names and timestamp formats. The original duration in request JSON retains its precision for GPX processing and API responses.

The survey rollup describes the segments received so far. Processing takes precedence over queued, then failed, then done. The latest recording end is derived from recorded start plus segment duration. The uploader can submit more segments after those already received finish.

In the video workspace, a reviewer can save a detection as pending, verified, or rejected. The decision is stored on the detection and logged in the existing audit table. Public report publication is still managed through its existing controls.

## Deploy or upgrade

The following commands use an existing Gunicorn systemd service named `drishtiweb.service`. Set `WEB_SERVICE` to the actual unit name if it differs. Run Compose commands from the backend checkout.

1. Install Docker Engine 28 or later and Compose on Ubuntu and configure the existing Caddy HTTPS routes. Use the updated checkouts of both repositories. Record the currently deployed Git commits as `DEPLOYED_API_COMMIT` and `DEPLOYED_WEB_COMMIT` before updating either checkout, then stop the API and staff service before changing the database. Back up the existing MariaDB database and media volume together. For SQLite, back up its database along with the media volume while writers are stopped.
2. Create `/etc/drishti/database.env` with mode 600. Generate independent random hex passwords. Preserve any existing MariaDB passwords when upgrading because the image initializes accounts only on an empty volume.

   ```dotenv
   DRISHTI_PUBLIC_URL=https://your-api-hostname
   MARIADB_PASSWORD=REPLACE_WITH_APP_PASSWORD
   MARIADB_ROOT_PASSWORD=REPLACE_WITH_SEPARATE_ROOT_PASSWORD
   DRISHTI_DATABASE_URL=mysql://drishti:REPLACE_WITH_APP_PASSWORD@127.0.0.1:3307/drishti
   ```

3. From the Drishti backend checkout, use the overlay for every MariaDB deployment. Keep the API and staff service stopped while migrating.

   ```bash
   compose() {
     sudo docker compose --env-file /etc/drishti/database.env \
       -f server/compose.droplet.yaml -f server/compose.mysql.yaml "$@"
   }
   WEB_SERVICE=drishtiweb.service
   sudo systemctl stop "$WEB_SERVICE" # For an existing staff service
   compose stop api
   compose config --quiet
   compose up -d --wait database phpmyadmin
   # For existing data, complete the backup below before migrating.
   compose build api
   ```

   For an existing MariaDB or a fresh deployment, run `compose run --rm -T migrate`. For a SQLite import only, use the following sequence. Run the Python command from the web checkout with its dependencies installed, the same database URL loaded, and the original media root available. Then run the final migration from the backend checkout.

   ```bash
   compose run --rm -T migrate python -m app.migrate_db --baseline-only
   # From drishtiweb with DRISHTI_DATABASE_URL and DRISHTI_DATA_DIR loaded
   .venv/bin/python migrate_sqlite.py "$DRISHTI_DATA_DIR/drishti.sqlite3"
   # Back in the backend checkout
   compose run --rm -T migrate
   ```

4. Point Gunicorn’s `DRISHTI_DATA_DIR` at the same volume mounted as `/app/data` in the API container. Find the host path with `sudo docker volume inspect drishti-droplet-data --format '{{.Mountpoint}}'` using the configured volume name. Give the dedicated Flask service user read and traversal access to `uploads/` and `instances/`, and write access to `report-media/`. The migration writes attachments as UID/GID 10001 with mode 0640. On a default install, grant the Flask service supplemental GID 10001 and set `report-media/` to mode 2770 after migration so future attachments inherit the shared group. If the service cannot traverse the Docker volume parent path, expose the existing volume to it with a persistent host bind mount. For example, create `/srv/drishti-media` and bind the volume mount point there using `sudo mount --bind "$MEDIA_ROOT" /srv/drishti-media`, where `MEDIA_ROOT` is the resolved mount point from Docker. Add the equivalent bind mount to `/etc/fstab`, set Gunicorn’s `DRISHTI_DATA_DIR=/srv/drishti-media`, and configure the Gunicorn service with `RequiresMountsFor=/srv/drishti-media`. Keep the Docker storage parent permissions restricted. Use the Flask schema check below as the Gunicorn service’s startup precheck. Configure the same `DRISHTI_DATABASE_URL` for Gunicorn and FastAPI.

   ```bash
   # From the backend checkout
   compose up -d --wait api
   # From the web checkout, with the staff service environment loaded
   .venv/bin/python -m flask --app app init --require-mariadb
   ```

5. Start Gunicorn and verify the migration ledger and the API and web health through their normal entry points. Run from the backend checkout.

   ```bash
   sudo systemctl start "$WEB_SERVICE"
   sudo systemctl is-active "$WEB_SERVICE"
   compose ps
   compose exec -T database sh -c 'MYSQL_PWD="$MARIADB_PASSWORD" mariadb -udrishti drishti -e "SELECT version,state FROM schema_migrations ORDER BY version"'
   curl --fail --show-error --silent http://127.0.0.1:10000/health
   curl --fail --show-error --silent https://YOUR_API_HOSTNAME/health
   curl --fail --show-error --silent --output /dev/null https://YOUR_STAFF_HOSTNAME/login
   ```

   Expect versions 1 through 3 to be `applied`. Sign into the HTTPS staff portal as a reviewer. Open a known recording from the video library, seek in the player, download the GPX, open its annotated JPEG, and save a review decision. Check the video range request in the browser’s network tab for HTTP 206 and reload to confirm the review persisted. Keep phpMyAdmin on loopback. Open it through `ssh -N -L 8081:127.0.0.1:8081 YOUR_SSH_USER@YOUR_DROPLET_IP` and visit `http://127.0.0.1:8081` locally. Log in with the MariaDB application credentials.

## Backup and restore

Stop writers before making a matched database dump and media snapshot. Store both files with the deployed commits and a timestamp. Keep the files private.

```bash
umask 077
backup_dir=$(mktemp -d "$PWD/drishti-backup.XXXXXX")
printf '%s\n' "${DEPLOYED_API_COMMIT:?Set the previously deployed API commit}" > "$backup_dir/backend-commit.txt"
printf '%s\n' "${DEPLOYED_WEB_COMMIT:?Set the previously deployed portal commit}" > "$backup_dir/web-commit.txt"
compose exec -T database sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb-dump -uroot --single-transaction --routines --triggers --databases drishti' > "$backup_dir/drishti.sql"
compose run --rm -T --no-deps --user 0 migrate tar -czf - -C /app/data . > "$backup_dir/drishti-media.tar.gz"
test -s "$backup_dir/drishti.sql"
tar -tzf "$backup_dir/drishti-media.tar.gz" >/dev/null
```

Restore into **new, empty Docker volumes**. Stop the old stack, then point a new protected environment file at new names via `DRISHTI_DATABASE_VOLUME` and `DRISHTI_MEDIA_VOLUME`. Keep the original volumes and the backup in place. Use the chosen restore environment file in the Compose function.

```bash
compose up -d --wait database
compose exec -T database sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot' < "$backup_dir/drishti.sql"
compose run --rm -T --no-deps --user 0 migrate tar -xzpf - -C /app/data < "$backup_dir/drishti-media.tar.gz"
```

Set `backup_dir` to the directory containing the selected backup pair before restoring. For a pre-migration backup, start the commits recorded with it or rerun the explicit migration before starting the updated services. Point Flask at the restored media volume and verify the links and sample playback before reopening access.

## Rehearse with MariaDB 10.11 in Docker

Install both projects’ Python dependencies, the backend development dependencies, the mobile npm dependencies, FFmpeg, and Docker Compose on a test host. From the backend checkout, run:

```bash
DRISHTI_WEB_ROOT=../drishtiweb bash scripts/test-mariadb-docker.sh
```

The runner uses disposable schemas and a named Docker volume. It checks fresh and populated migrations, failure and retry, FK and uniqueness rules, concurrent mobile-format video uploads, inference, authenticated media, and database and API restart recovery.

## Migration failure and checklist

MariaDB DDL commits independently. The migrator records failures, leaves the database unavailable to the updated services, and can resume after the reported issue is corrected. Keep both writers stopped. Missing media must be recovered from the matching media backup. A duplicate sequence, invalid historical timestamp, or orphaned reference reports identifying information so an operator can verify and correct the source record without discarding IDs. For a failed migration after DDL started, either fix the reported issue and rerun or restore the matched backup into new volumes. Do not mark a failed version applied by hand. Restoring an earlier snapshot after traffic resumes omits newer writes.

- [ ] Confirm both services use the same loopback MariaDB URL and media volume.
- [ ] Test the migration and restore on a disposable copy using MariaDB 10.11 Docker.
- [ ] Stop writers, capture the backup pair, and run migrations.
- [ ] Verify migration state, API health, report linkage, GPX, JPEG, and video seeking.
- [ ] Reopen traffic after service restart and persistence checks pass.
