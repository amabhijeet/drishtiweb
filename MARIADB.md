# MariaDB cutover on the Drishti Droplet

MariaDB stores survey and review records. phpMyAdmin is an administrative interface for MariaDB. The existing Drishti media volume still stores source video, GPX, and filesystem evidence.

Both repositories must contain the MariaDB changes. Run these steps in a maintenance window on the Droplet. Keep the old SQLite file and the media volume together in a backup. Do not remove the original Docker volume.

1. Stop the web service and the processing API so both stop writing. From the Drishti backend checkout, run `sudo docker compose -f server/compose.droplet.yaml stop api` with the existing deployment environment. Back up the full Drishti data volume while both services are stopped.
2. Create a protected environment file such as `/etc/drishti/database.env` (mode 600), using independent random hex passwords for the application account and root. Use the same application password in both settings below.

   ```dotenv
   DRISHTI_PUBLIC_URL=https://your-existing-api-hostname
   MARIADB_PASSWORD=REPLACE_WITH_RANDOM_HEX
   MARIADB_ROOT_PASSWORD=REPLACE_WITH_DIFFERENT_RANDOM_HEX
   DRISHTI_DATABASE_URL=mysql://drishti:REPLACE_WITH_RANDOM_HEX@127.0.0.1:3307/drishti
   ```

3. From the updated backend checkout, start the database and phpMyAdmin, then initialize the processing tables without starting the API worker.

   ```bash
   compose() {
     sudo docker compose --env-file /etc/drishti/database.env \
       -f server/compose.droplet.yaml -f server/compose.mysql.yaml "$@"
   }
   compose up -d --wait database phpmyadmin
   compose build api
   compose run --rm --no-deps api python -c 'from app.storage import Store; Store("/app/data")'
   ```

4. From the updated web checkout, install the Python requirements. Add the same `DRISHTI_DATABASE_URL` to the web service environment alongside its existing settings. Keep `DRISHTI_DATA_DIR` pointed at the existing media volume. In a shell with that environment loaded, initialize the web tables and import SQLite.

   ```bash
   .venv/bin/python -m flask --app app init
   .venv/bin/python migrate_sqlite.py "$DRISHTI_DATA_DIR/drishti.sqlite3"
   ```

   Skip the import for a fresh installation. The importer leaves SQLite intact, refuses a populated destination, and verifies the per-table row counts inside one transaction. It includes report attachments, trim edits, audit records, and original request IDs. Keep both application processes stopped during import.

5. From the backend checkout, run `compose up -d --wait api` using the same Compose function. Restart Gunicorn with its updated environment. Verify `/health`, the video library, a published report, a video range request and a saved clip. Use the overlay and environment file for future API upgrades so the API continues writing to MariaDB.

To access phpMyAdmin from your computer, open an SSH tunnel and then visit `http://127.0.0.1:8081` locally.

```bash
ssh -N -L 8081:127.0.0.1:8081 YOUR_SSH_USER@YOUR_DROPLET_IP
```

Log in as `drishti` using the application password. The database and phpMyAdmin bind to Droplet loopback. Back up MariaDB and the media volume together after cutover. Reverting to the old SQLite snapshot after accepting writes on MariaDB would omit those new writes.
