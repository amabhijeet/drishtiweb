# Drishti Web
Public road observation register and private staff workspace. Deploy beside the Drishti FastAPI service on its Droplet. Flask renders the interface and Leaflet clusters published locations. Flask was chosen to reuse the Python media stack and access the existing SQLite database and local evidence volume. The mobile API remains unchanged.

## Install
Use Python 3.11+ on the host. Create a virtual environment, install requirements, and configure the following in a protected service environment file. Generate WEB_SECRET with Python secrets.token_hex(32). Generate each password hash with werkzeug.security.generate_password_hash using a password prompted via getpass.

| Variable | Value |
|---|---|
| WEB_SECRET | Random signing secret shared by web workers |
| WEB_USERS | JSON mapping usernames to objects with hash and role. reviewer can publish. operator can ingest and inspect. |
| DRISHTI_DATA_DIR | Existing Drishti data volume path containing drishti.sqlite3, uploads and instances |
| DRISHTI_API | Private server origin, default http://127.0.0.1:10000 |
| GPS_TOLERANCE_M | Independent reference tolerance, default 25 metres |

Run these commands from the checkout with the environment loaded. The service account needs write access to the database and read access to survey evidence. Back up the database and evidence together before initialization.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app app init
gunicorn --workers 2 --timeout 240 --bind 127.0.0.1:11000 app:app
```

Use a separate HTTPS hostname with Caddy reverse_proxy 127.0.0.1:11000. Run Gunicorn under a service supervisor. Keep the capture API private. Configure ingress login throttling and upload limits. Session cookies require HTTPS. Public OSM tiles and Leaflet CDN access are required for the default map. Configure a licensed tile service for sustained traffic.

## Workflow and routes
Public routes are /, /map, /reports/ID, /docs and authorized report attachments at /media/ID. Staff sign in at /login, upload on /admin, import current observations, and inspect source imagery and survey footage. The web app calls GET /v1/map and POST /v1/detect and /v1/segments. Video preview and GPX inspection read the existing local store. Web tables hold editorial decisions, selected media and an audit log within the existing SQLite database. /admin/reports/ID supports draft, reject, archive and publish. Public media must be manually sanitized before attaching. Public video containers may contain audio or metadata. Originals stay private. Print a report to save PDF.

## GPS methodology
/admin/gps accepts EXIF, Drishti GPS JSON, GPX, or a manually transcribed overlay. Coordinates are range checked. Ambiguous valid swapped pairs require independent reference evidence. Haversine distances use a 6,371 km mean Earth radius. Nearest track-point distance is diagnostic and cannot confirm time alignment. Non-increasing timestamps and speeds over 55 m/s are flagged. A reviewer can record a correction while preserving original camera coordinates. Survey camera locations approximate the observation position. GPS tests use synthetic fixtures. Field accuracy requires independently surveyed points and representative device samples.
