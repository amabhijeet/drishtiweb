# AI Agent Instructions — Drishti Web

**File ownership lookup:** [FILE_MAP.md](FILE_MAP.md) for every web/admin route and template, and [backend/mobile file map](https://github.com/amabhijeet/drishti/blob/main/docs/FILE_MAP.md) for the sibling repository.

**Read the canonical, self-contained architecture reference first:** [Drishti System Architecture](https://github.com/amabhijeet/drishti/blob/main/docs/ARCHITECTURE.md).

The architecture spans **two repos**: `amabhijeet/drishti` contains React Native, FastAPI, YOLO, migrations and Docker; this repo `amabhijeet/drishtiweb` contains the Flask public and government staff portal.

Before editing this repo, read `README.md`, `MARIADB.md`, `app.py`, `mysql_db.py`, `templates/page.html`, `templates/videos.html`, and the canonical architecture reference.

**Strict invariants:**
- Flask connects to the **same MariaDB 10.11 database and shared media volume** as FastAPI; it does not own the ingestion API.
- Raw AI detections are imported into drafts using `POST /admin/sync`. Only human-reviewed `web_reports.status='Published'` is shown on `/`, `/map` and public report details.
- Detector `pending/verified/rejected` is separate from report `Draft/Published/Rejected/Archived`.
- Original source MP4/GPX/annotated evidence belongs to protected staff views; publication requires deliberate sanitized attachments.
- The real admin has authenticated sessions, operator/reviewer roles and POST CSRF. `DRISHTI_LOCAL_NO_AUTH=1` is restricted to local development, loopback and SQLite; never use on DigitalOcean/production.
- Static Vercel build is a read-only, disconnected preview; it does not serve live Flask/MariaDB operations.
- Maintain existing video playback (HTTP Range), GPX download, annotated images, detection review, trimming/export, GPS validation, audit and mobile image-report compatibility.
- Don't add new tables, rewrite the backend or bypass authentication to satisfy design requests.
- Run relevant `python -m unittest test_web`, `python -m unittest discover -s tests`, browser integration tests when possible; report limitations honestly.

If API contract, migration or deployment changes are needed, inspect and coordinate edits with the sibling `drishti` repository.
