# Drishti Web — File-by-File Codebase Map

> **"Kaunsi file mein kya hai?"** Complete navigation guide for the `amabhijeet/drishtiweb` Flask public/admin site, based on the current `main` repository tree on 22 November 2026.
>
> **Start with the [full system architecture](https://github.com/amabhijeet/drishti/blob/main/docs/ARCHITECTURE.md)** and the companion [mobile/backend file map](https://github.com/amabhijeet/drishti/blob/main/docs/FILE_MAP.md). Code is more authoritative than the documentation; check it before editing.

## 1. What this repository owns

This repository owns the **Flask website and government staff portal**, NOT React Native recording, FastAPI upload processing, YOLO inference or the migration ledger. Those are in [amabhijeet/drishti](https://github.com/amabhijeet/drishti).

```text
drishtiweb/
├── app.py                  Flask server: public/admin/auth/media/review routes
├── mysql_db.py             Shared MariaDB connection, transaction and schema gate
├── gps.py                  Web GPS inspection / coordinate validation utilities
├── migrate_sqlite.py       One-time older SQLite → MariaDB import utility
├── templates/
│   ├── page.html           Main Flask page template: public/admin/reports/GPS
│   └── videos.html         Staff video library, player, detections and clips
├── static/
│   ├── site.css            Design system and responsive layout
│   ├── map.js              Leaflet map, clusters, report/track interaction
│   └── video-editor.js     Playback trim, position and detection time seek
├── build-vercel.cjs        Generates static public preview (no live database)
├── build_public.py         Older Jinja-based public preview generator
├── prepare-map.cjs        Installs/copies vendored Leaflet map assets
├── public-pages/           Checked-in static HTML preview artifacts (legacy inputs)
├── vercel.json             Vercel build, routing and output config
├── requirements.txt       Flask / Gunicorn / PyMySQL / PyAV dependencies
├── package.json           Leaflet / marker cluster dependencies and postinstall
├── tests/                 Browser, media/review, development-mode tests
├── MARIADB.md             Production DB/media/migrations/cutover runbook
├── README.md              Install, usage, verification and deployment guide
└── AGENTS.md              Mandatory AI-agent context and safety rules
```

## 2. The central server files

| File | What is in it / when to edit |
|---|---|
| `app.py` | **Main Flask application**. App configuration, session/CSRF hooks, sign-in/out, public routes, admin dashboard, manual API import, video library/workspace, report editing, media serving, GPS inspection, detection review, trim/export, errors. This is the main source of web business logic. |
| `mysql_db.py` | MariaDB connection from `DRISHTI_DATABASE_URL`, cursor/SQL compatibility, UTC session, transaction helpers, requires migrations 1–3 applied. Edit if DB connection/transaction compatibility changes, **not** for ad hoc schema changes. |
| `gps.py` | Staff GPS validation helpers: coordinate parsing, distance/tolerance, GPX reading, warnings and image EXIF GPS. **Not** the source of API video-frame interpolation (that is `drishti/server/app/gps.py`). |
| `migrate_sqlite.py` | Transitional import from older SQLite site/data storage to the shared MariaDB system. Use only during planned migration with backups and matching schema; not a normal request handler. |

### `app.py`: route ownership and effects

| URL/handler | Meaning / data affected |
|---|---|
| `GET /`, `GET /map`, `GET /docs` | Public landing, published observation map and documentation; reads `web_reports` with `status='Published'`. |
| `GET /reports/<rid>` | Public report details **only if published**; shows allowed media. |
| `GET /media/<mid>` | Public approved attachments for published reports; additional media may be accessible for authenticated staff. |
| `GET /login`, `POST /login` | Staff login with configured hashed-password `WEB_USERS`, Flask session. |
| `POST /admin/logout` | Staff logout. |
| `GET /admin` | Dashboard: report counts, video count, reports, activity. |
| `POST /admin/sync` | **Pulls** raw observations from FastAPI `GET /v1/map`, creates draft staff `web_reports` without duplicates; does **not** publish. |
| `POST /admin/upload` | Manually proxies image or video+GPX upload to FastAPI. Normal phone upload goes to FastAPI directly. |
| `GET /admin/videos` | Paginated/filterable database-backed segment library. |
| `GET /admin/videos/<sid>` | Recording player, GPS, detected frames and saved clip list. |
| `POST /admin/videos/<sid>` | Save video trim start/end/title metadata; source MP4 is preserved. |
| `GET /admin/segments/<sid>/video` | Authenticated original MP4, supports Range/seek. |
| `GET /admin/segments/<sid>/track` | Authenticated original GPX download or parsed track map. |
| `GET /admin/detections/<id>/image` | Authenticated original annotated detection JPEG. |
| `POST /admin/detections/<id>/review` | **Reviewer-only** `pending/verified/rejected` detection status and audit. |
| `GET /admin/reports/<rid>` | Staff report detail with original evidence links. |
| `POST /admin/reports/<rid>` | **Reviewer-only** report fields, location/reference checks, uploads and `Draft/Published/Rejected/Archived`; requires explicit confirmation to publish. |
| `GET /admin/evidence/<rid>` | Staff access to source detection evidence. |
| `GET /admin/video-clips/<clip_id>/download` | Render trimmed MP4 on demand via FFmpeg; original remains unchanged. |
| `GET/POST /admin/gps` | Staff GPS manual/EXIF/GPX checks. |

**Critical distinction:** the API's `/v1/map` returns **raw observations** for internal staff import. The public Flask `/map` returns **published editorial reports**. Never directly expose the former as the latter.

## 3. Templates — which page's markup lives where

| File / branch | Content |
|---|---|
| `templates/page.html` | Shared top-level page layout, header/nav/footer and Jinja conditional page bodies. |
| `page.html`, `page='/'` | Public overview hero, explanation and published observations. |
| `page.html`, `page='/map'` | Leaflet published-report explorer and filtering. |
| `page.html`, `page='/docs'` | Explanation of survey, detection and review methodology. |
| `page.html`, `page='admin'` | Professional staff dashboard: metrics, report list, queue actions, import, upload, activity. |
| `page.html`, `page='detail'` | Public/staff report summary, approved evidence; conditional staff editing and publication form. |
| `page.html`, `page='gps'` / `page='track'` | GPS comparison form and parsed GPX map. |
| `page.html`, `page='login'` / `page='offline'` | Login and disconnected states. |
| `templates/videos.html`, `page='videos'` | Search, status filters, list/pagination of recorded segments. |
| `templates/videos.html`, `page='video_workspace'` | Video player, trim form, detection cards, annotate links, review statuses, saved clip downloads. |

Templates are **not the authorization layer**. Route-level checks in `app.py` must continue to protect requests even if buttons are hidden or a staff UI is redesigned.

## 4. Styling, maps and player controls

| File | Responsibility |
|---|---|
| `static/site.css` | Main design tokens, nav, typography, cards, responsive public site, admin dashboard/sidebar, forms, tables, video/map layouts, breakpoints and print style. |
| `static/map.js` | Leaflet/OpenStreetMap initialization, published report markers, optional clustering, popup links, list filtering and GPX polyline map rendering. |
| `static/video-editor.js` | MP4 playback, set trim start/end from playhead, preview and play saved clips, jump from detection card to video timestamp. |
| `prepare-map.cjs` | Uses npm Leaflet dependencies to copy required third-party browser assets under `static/vendor` for deployment. Generated vendor output is not listed as tracked source. |
| `package.json`, `package-lock.json` | Leaflet and markercluster dependencies, `postinstall` preparation. Use `npm ci` before launching web app. |
| `requirements.txt` | Flask, Gunicorn, PyMySQL, Pillow, PyAV, HTTP multipart and GPS/XML Python packages. |

### Public preview versus operational Flask portal

| File | What it does |
|---|---|
| `build-vercel.cjs` | Generates the *static* public overview, map, docs and **read-only admin preview** under `public/`. It is not a live Flask or MariaDB server. |
| `vercel.json` | Configures static build output and URL rewrites for Vercel. |
| `build_public.py` | Alternate/older Jinja-based page rendering into `public-pages/`. Inspect whether current build actually calls it before editing. |
| `public-pages/index.html`, `map.html`, `docs.html`, `login.html` | Checked-in generated/legacy public HTML; may lag the active `build-vercel.cjs` output. **Don't treat these as the operational production Flask templates.** |

If task is to make **real** staff dashboard or published DB records available on the deployed domain: edit Flask `app.py`/`templates/`, Gunicorn/Caddy config, database/shared volume. Editing `public-pages/*.html` alone cannot deliver it.

## 5. Data ownership and permission model

The **FastAPI** repo owns video ingestion, worker, detection rows and MariaDB migrations. The **Flask** web repo owns editorial `web_reports` and source review UI while sharing the database and filesystem.

| Resource | Source of truth | Web access |
|---|---|---|
| Survey session | `surveys` from FastAPI receipt/rollup | Admin summary |
| Video clip/job | `segments` from FastAPI | Admin video library, player and clip editor |
| AI finding | `detections` from worker | Admin evidence/review (pending/verified/rejected) |
| Original recording | Media volume `uploads/` | Authenticated staff routes only |
| Annotated frame | Media volume `instances/` | Authenticated staff evidence |
| Public report | `web_reports` created from import | Staff edits; only `Published` is public |
| Curated photo/video/PDF | `web_media` plus `report-media/` | Approved media for public; other attachments staff-only |
| Trim metadata | `web_video_clips` | Staff clip editing/export |
| Review history | `web_audit` | Staff activity dashboard |

**Roles:** `operator` can inspect/import; `reviewer` can change detection review status, curate/publish. POST requires CSRF. The local no-password preview is only for loopback, development and SQLite (not public VPS).

## 6. Deployment ownership

| File/location | Role |
|---|---|
| `README.md` | Web install/run commands, environment variables, UX and tests. |
| `MARIADB.md` | **Authoritative full-stack MariaDB/Flask deployment and recovery runbook**: shared media, migration order, rollback and phpMyAdmin. |
| `mysql_db.py` | Database connection URL and migration-state precondition. |
| `/etc/drishti/web.env` (**not in repo**) | Production secret signing key, hashed staff users, shared database URL, media directory, private FastAPI URL. |
| `drishtiweb.service` systemd unit (**not tracked in repo**) | Long-running Gunicorn process as restricted staff service user, loopback port 11000. |
| `Caddyfile` (**server configuration, not tracked here**) | Public website hostname proxies to Gunicorn 11000, separate restricted API hostname proxies to FastAPI 10000. |
| `drishti/server/compose.mysql.yaml` (**other repo**) | Single MariaDB 10.11 + phpMyAdmin + migrations; loopback 3307/8081. |
| `drishti/server/compose.droplet.yaml` (**other repo**) | CPU FastAPI in Docker, host network and private media volume. |

**Deployment notes:** Same `DRISHTI_DATABASE_URL` for FastAPI and Flask; both access same media data. phpMyAdmin on loopback 8081 via SSH tunnel. Do not place `WEB_SECRET`, `WEB_USERS`, DB passwords, API trusted egress address or SSH keys into Git.

## 7. Tests

| File | What it tests / does |
|---|---|
| `test_web.py` | Core web GPS helpers and public/private report boundaries. |
| `tests/test_media_review.py` | Authenticated original evidence, video range serving, attachments, permission controls, detection review and audit. |
| `tests/test_local_preview.py` | Loopback-only SQLite development preview restrictions; rejects public host/MariaDB. |
| `tests/browser_streams.py` | Playwright browser journey: page responsiveness, video streaming/seeking, reports, concurrent uploads and clipping; requires running disposable services. |
| `tests/seed_browser.py` | Setup/fixtures for browser integration scenario. |
| `tests/run-integration.sh` | Launches/tests disposable web + processing integration using Playwright, FFmpeg and sibling backend. |

Run targeted tests with the requirements installed:

```bash
python -m unittest test_web
python -m unittest discover -s tests
# Full browser integration needs separate backend, browser binaries and fixtures:
DRISHTI_CHECKOUT=../drishti bash tests/run-integration.sh
```

Do not claim tests passed merely because they exist. Video/browser tests may require Docker, data/model fixtures, sufficient local CPU, and Chromium.

## 8. "I need to change X" quick lookup

| Feature/change | Files first | Also inspect |
|---|---|---|
| Public landing page styling or content | `templates/page.html`, `static/site.css` | Static preview `build-vercel.cjs` for parity |
| Public map markers/search | `app.py` public DB query, `templates/page.html`, `static/map.js` | Publication status and Leaflet cluster setup |
| Admin navigation/dashboard metrics | `app.py` `admin()`, `templates/page.html`, `static/site.css` | Database report/status queries |
| Video library/filters | `app.py` `video_library()`, `templates/videos.html` | `segments` schema, pagination/status |
| Video playback/trim/export | `app.py` `video_workspace()/export_clip()`, `templates/videos.html`, `static/video-editor.js` | Original media permissions, HTTP Range, FFmpeg |
| Detection annotation and time seeking | `templates/videos.html`, `static/video-editor.js`, `app.py` `detection_image()` | Actual `detections` and `instances/` in FastAPI repo |
| Reviewer approval/publish | `app.py` `review_detection()/review()`, `templates/page.html` | Roles/CSRF, DB constraints, audit, public filtering |
| Missing observations in admin | `app.py` `sync()` and FastAPI `/v1/map` | worker status, `web_reports` and MariaDB migration |
| GPS warnings/verification | `gps.py`, `app.py` `gps()/review()` | Video frame GPS logic in backend `server/app/gps.py` |
| DB errors or schema mismatch | `mysql_db.py`, `MARIADB.md` | **Other repo** `server/app/migrate_db.py`; don't patch SQL around migrations |
| Unauthenticated dev preview | `app.py`, `tests/test_local_preview.py` | Never expose on VPS; static admin preview is read-only |
| Vercel static design | `build-vercel.cjs`, `vercel.json` | `public-pages/` may be legacy output |
| HTTPS/port/volume | `MARIADB.md`, systemd/Caddy config | Backend Compose files; don't run API-only bootstrap over dual-host Caddy |
| Tests/new defect | `test_web.py`, `tests/` | Add smallest relevant regression check |

## 9. Handoff rules for AI agents

1. Read this file plus [full architecture](https://github.com/amabhijeet/drishti/blob/main/docs/ARCHITECTURE.md) and `AGENTS.md`.
2. Identify page/route/model/table and exact implementation file before editing. Trace request all the way to persistent media/DB and public side effects.
3. Keep original MP4/GPX private; public sees only human-published reports, not raw `/v1/map`.
4. Preserve Flask authentication, role authorization, CSRF and non-public evidence. No-passkey requests should **not** result in internet-facing unprotected operations.
5. Preserve old image-report behavior and existing migrations when adding functionality.
6. Where source code changes materially, update both this file map and the canonical architecture if affected. Log tested/unverified status honestly.
