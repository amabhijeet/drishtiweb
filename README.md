# Drishti Web
Public road observation register and private staff workspace. Deploy beside the Drishti FastAPI service on its Droplet. Flask renders the interface and Leaflet clusters published locations. Flask was chosen to reuse the Python media stack and access the shared database and local evidence volume. The mobile API remains unchanged.

**Codebase navigation:** [File-by-file map](FILE_MAP.md) — Flask routes, templates, public/admin UX, data access, tests and deployment files. The [mobile/backend map](https://github.com/amabhijeet/drishti/blob/main/docs/FILE_MAP.md) covers the sibling repository.

## Install
Use Python 3.11+ on the host. Create a virtual environment, install requirements, and configure the following in a protected service environment file. Generate WEB_SECRET with Python secrets.token_hex(32). Generate each password hash with werkzeug.security.generate_password_hash using a password prompted via getpass.

| Variable | Value |
|---|---|
| WEB_SECRET | Random signing secret shared by web workers |
| WEB_USERS | JSON mapping usernames to objects with hash and role. reviewer can publish. operator can ingest and inspect. |
| DRISHTI_DATA_DIR | Existing Drishti data volume path containing uploads and instances, plus drishti.sqlite3 in SQLite mode |
| DRISHTI_API | Private server origin, default http://127.0.0.1:10000 |
| GPS_TOLERANCE_M | Independent reference tolerance, default 25 metres |

Run these commands from the checkout with the environment loaded. The service account needs write access to the database and read access to survey evidence. Back up the database and evidence together before initialization.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm ci
flask --app app init
gunicorn --workers 2 --threads 4 --timeout 240 --bind 127.0.0.1:11000 app:app
```

Use a separate HTTPS hostname with Caddy reverse_proxy 127.0.0.1:11000. Run Gunicorn under a service supervisor. Keep the capture API private. Configure ingress login throttling and upload limits. Session cookies require HTTPS. Node.js is required during installation to bundle Leaflet. Public OSM tiles require internet connectivity. Configure a licensed tile service for sustained traffic.

## Portal redesign and localhost preview

The public overview, published-report map, and staff workspace now share a responsive visual system. Staff pages include dashboard metrics, recent observations, a review queue, video library, player, GPS track download, AI evidence, and review controls. Only reports explicitly published by reviewers appear in the public explorer. Source MP4 and GPX files are not public.

To inspect the Flask staff workspace **without entering a password during local development**, use a disposable, SQLite-backed environment on your own computer:

```sh
export DRISHTI_ENV=development
export DRISHTI_LOCAL_NO_AUTH=1
export DRISHTI_DATA_DIR=/absolute/path/to/local/drishti-data
unset DRISHTI_DATABASE_URL
mkdir -p "$DRISHTI_DATA_DIR"
# Initialize the backend's SQLite tables first, using the backend checkout.
# Initialize the portal's SQLite report tables:
python -m flask --app app init
python -m flask --app app run --host 127.0.0.1 --port 11000
```

Open `http://127.0.0.1:11000/admin`. Preview mode assigns a local reviewer for interactive testing, without a password prompt. It is refused unless `DRISHTI_ENV=development`, the shared MariaDB URL is absent, and both the HTTP host and client are loopback. **Never use this flag on the Droplet, behind Caddy, or with production data.** Do not expose the local preview with a tunnel. Normal operation still requires `WEB_USERS`, `WEB_SECRET`, HTTPS and staff authentication.

The Vercel build (`node build-vercel.cjs`) generates four polished **static preview pages** with empty/offline observations. It does not host Flask routes or connect to live MariaDB. The public map becomes live only when Flask is hosted alongside the processing server. Keep production access controls in place when deploying.

## Workflow and routes
Public routes are /, /map, /reports/ID, /docs and authorized report attachments at /media/ID. Staff sign in at /login, upload on /admin, import current observations, and inspect source imagery and survey footage. The web app calls GET /v1/map and POST /v1/detect and /v1/segments. Video preview and GPX inspection read the existing local store. Web tables hold editorial decisions, selected media and an audit log within the shared database. /admin/reports/ID supports draft, reject, archive and publish. Public media must be manually sanitized before attaching. Public video containers may contain audio or metadata. Originals stay private. Print a report to save PDF.

## GPS methodology
/admin/gps accepts EXIF, Drishti GPS JSON, GPX, or a manually transcribed overlay. Coordinates are range checked. Ambiguous valid swapped pairs require independent reference evidence. Haversine distances use a 6,371 km mean Earth radius. Nearest track-point distance is diagnostic and cannot confirm time alignment. Non-increasing timestamps and speeds over 55 m/s are flagged. A reviewer can record a correction while preserving original camera coordinates. Survey camera locations approximate the observation position. GPS tests use synthetic fixtures. Field accuracy requires independently surveyed points and representative device samples.

## Verification
Run the following from this repository with the Python environment active. The browser integration test requires FFmpeg with H.264 encoding, Playwright Chromium, and a sibling Drishti backend checkout with its Python dependencies installed. It creates a disposable database and binds both processes to loopback.

```sh
npm ci
python -m unittest test_web
python -m unittest discover -s tests
python -m pip install playwright
python -m playwright install chromium
DRISHTI_CHECKOUT=../drishti bash tests/run-integration.sh
```

Set API_PYTHON to the backend interpreter and TEST_CHECKPOINT to a compatible local YOLO checkpoint when required. CHROMIUM_PATH optionally selects a Chromium executable. The browser suite checks public routes, staff login, gallery, map navigation, GPS views, authenticated video downloads and playback. Three synthetic cameras send distinct one-second MP4 segments concurrently, with an additional identical retry. The assertions check completed jobs, byte-for-byte source identity and simultaneous playback. The production backend processes the accepted jobs serially with one model worker. Measure full-resolution capacity on the target Droplet.

## Vercel public site
Vercel builds the overview, map shell, documentation and workspace availability page into public/. This deployment works on the assigned vercel.app domain without credentials. It displays a disconnected state until a persistent survey service is integrated. Use the Droplet installation above for authenticated operations and live reports. Local preview: run npm ci, install Jinja2 (included with Flask), run python build_public.py to refresh the checked-in HTML, run node build-vercel.cjs and serve the public directory with a clean-URL static server.

## Staff video library
Open **Review workspace → Video library** to find all accepted segments by survey, ID or processing status. In the editor, use the player position to mark the start and end, preview the selection, then save a named clip. Saved edits and audit entries use the shared Drishti database. Staff can play a saved selection or export it as an MP4. Exports are generated on demand and leave the source recording, GPX, and inference results intact.

On an existing Droplet install, install FFmpeg (including libx264) with `sudo apt-get install ffmpeg`, rerun `flask --app app init` with the existing service environment to add the clip table, and restart Gunicorn. The static Vercel site continues to show staff-service availability until the full backend is hosted.

## MariaDB and phpMyAdmin
See [Droplet cutover and data migration](MARIADB.md). Configure the same `DRISHTI_DATABASE_URL` for both services.
