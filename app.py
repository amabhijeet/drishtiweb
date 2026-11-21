import functools
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import uuid
from urllib.parse import urlsplit

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
from flask import Flask, Response, abort, g, redirect, render_template, request, send_file, session
from PIL import Image, ImageOps
from werkzeug.security import check_password_hash
from gps import point, distance, validate, read_track, photo_gps

app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ["WEB_SECRET"], SESSION_COOKIE_SECURE=True,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  MAX_CONTENT_LENGTH=520*1024**2)
root = Path(os.environ["DRISHTI_DATA_DIR"]).resolve()
origin = os.environ.get("DRISHTI_API", "http://127.0.0.1:10000").rstrip("/")
roles = json.loads(os.environ["WEB_USERS"])
tolerance = float(os.getenv("GPS_TOLERANCE_M", "25"))
if not 0 < tolerance <= 1000:
    raise ValueError("GPS_TOLERANCE_M must be within (0, 1000]")
schema = """
CREATE TABLE IF NOT EXISTS web_reports(
 id TEXT PRIMARY KEY, source TEXT, source_id TEXT, original_lat REAL, original_lon REAL,
 lat REAL, lon REAL, confidence REAL, evidence TEXT, captured TEXT, title TEXT DEFAULT 'Pothole',
 description TEXT DEFAULT '', place TEXT DEFAULT '', severity TEXT DEFAULT 'Unassessed',
 status TEXT DEFAULT 'Draft', gps TEXT DEFAULT 'Valid coordinate format', discrepancy REAL);
CREATE TABLE IF NOT EXISTS web_media(id TEXT PRIMARY KEY, report TEXT, kind TEXT, name TEXT, data BLOB);
CREATE TABLE IF NOT EXISTS web_audit(id INTEGER PRIMARY KEY, at TEXT DEFAULT CURRENT_TIMESTAMP,
 actor TEXT, report TEXT, action TEXT);
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(root / "drishti.sqlite3", timeout=30)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.cli.command("init")
def init():
    with db() as conn:
        conn.execute("SELECT id FROM segments LIMIT 1")
        conn.executescript(schema)


@app.teardown_appcontext
def close(error):
    if "db" in g:
        g.db.close()


def audit(report, action):
    db().execute("INSERT INTO web_audit(actor,report,action) VALUES(?,?,?)",
                 (session["user"], report, action))


@app.before_request
def protect():
    session.setdefault("csrf", secrets.token_urlsafe(32))
    if request.method == "POST" and not hmac.compare_digest(session["csrf"], request.form.get("csrf", "")):
        abort(403)
    if request.path.startswith("/admin") and session.get("user") not in roles:
        return redirect("/login")


@app.after_request
def headers(response):
    response.headers.update({"X-Content-Type-Options":"nosniff", "Cache-Control":"private, no-store",
                             "X-Frame-Options":"DENY", "Referrer-Policy":"same-origin"})
    return response


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user","")
        account = roles.get(user)
        if not account or not check_password_hash(account["hash"], request.form.get("password","")):
            return render_template("page.html", page="login", error="Invalid login"), 401
        session.clear()
        session["user"] = user
        return redirect("/admin")
    return render_template("page.html", page="login")


@app.post("/admin/logout")
def logout():
    session.clear()
    return redirect("/")


def report(rid, public=False):
    row = db().execute("SELECT * FROM web_reports WHERE id=?", (rid,)).fetchone()
    if not row or (public and row["status"] != "Published"):
        abort(404)
    return row


@app.get("/")
@app.get("/map")
@app.get("/docs")
def public():
    rows = db().execute("SELECT id,title,place,lat,lon,severity,captured FROM web_reports WHERE status='Published' ORDER BY captured DESC")
    return render_template("page.html", page=request.path, rows=[dict(r) for r in rows])


@app.get("/reports/<rid>")
@app.get("/admin/reports/<rid>")
def details(rid):
    private = request.path.startswith("/admin")
    r = report(rid, not private)
    media = db().execute("SELECT id,kind,name FROM web_media WHERE report=? AND (? OR kind IN ('photo','video'))", (rid,private))
    return render_template("page.html",page="detail",r=r,media=media,private=private)


@app.get("/media/<mid>")
def media(mid):
    row = db().execute("""SELECT m.rowid AS blob_id, m.kind, m.name, length(m.data) AS size
        FROM web_media m JOIN web_reports r ON r.id=m.report WHERE m.id=?
        AND ((r.status='Published' AND m.kind IN ('photo','video')) OR ?)""",
        (mid, session.get("user") in roles)).fetchone()
    if not row:
        abort(404)
    if row["kind"] == "video":
        size = row["size"]
        start, stop = 0, size
        status = 200
        headers = {"Accept-Ranges":"bytes"}
        if "Range" in request.headers:
            bounds = request.range.range_for_length(size) if request.range else None
            if bounds is None:
                return Response(status=416, headers={"Content-Range":f"bytes */{size}"})
            start, stop = bounds
            status = 206
            headers["Content-Range"] = f"bytes {start}-{stop-1}/{size}"
        def chunks():
            # Short reads release SQLite snapshots between chunks and on disconnect.
            from contextlib import closing
            with closing(sqlite3.connect(root / "drishti.sqlite3", timeout=30)) as conn:
                offset = start
                while offset < stop:
                    with conn.blobopen("web_media","data",row["blob_id"],readonly=True) as blob:
                        blob.seek(offset)
                        chunk = blob.read(min(65536,stop-offset))
                    if not chunk:
                        break
                    offset += len(chunk)
                    yield chunk
        headers["Content-Length"] = str(stop-start)
        return Response(chunks(),status=status,headers=headers,mimetype="video/mp4")
    data = db().execute("SELECT data FROM web_media WHERE id=?", (mid,)).fetchone()[0]
    return send_file(io.BytesIO(data), mimetype={"photo":"image/jpeg","document":"application/pdf"}[row["kind"]],download_name=row["name"],as_attachment=row["kind"]=="document")



@app.get("/admin")
def admin():
    return render_template("page.html",page="admin",rows=db().execute("SELECT * FROM web_reports ORDER BY captured DESC").fetchall(),
        jobs=db().execute("SELECT id,session,status,created FROM segments ORDER BY created DESC").fetchall(),
        events=db().execute("SELECT * FROM web_audit ORDER BY id DESC LIMIT 100").fetchall())


@app.post("/admin/sync")
def sync():
    offset = 0
    with db() as conn:
        while True:
            response = requests.get(origin+"/v1/map",params={"limit":500,"offset":offset},timeout=15)
            response.raise_for_status()
            batch = response.json()
            for item in batch["detections"]:
                lat, lon = point(item["latitude"],item["longitude"])
                source_id = item["segmentId"]
                if item["source"] == "video":
                    parent = conn.execute("SELECT metadata FROM segments WHERE id=?",(source_id,)).fetchone()
                else:
                    parent = conn.execute("SELECT metadata FROM images WHERE id=?",(source_id,)).fetchone()
                meta = json.loads(parent[0]) if parent else {}
                conn.execute("""INSERT OR IGNORE INTO web_reports(id,source,source_id,original_lat,original_lon,lat,lon,confidence,evidence,captured)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",(item["id"],item["source"],source_id,lat,lon,lat,lon,item["confidence"],urlsplit(item["imageUrl"]).path,meta.get("timestamp") or meta.get("startedAt")))
            offset += len(batch["detections"])
            if offset >= batch["total"] or not batch["detections"]:
                break
        audit(None,"Imported observations")
    return redirect("/admin")


def safe_path(directory, name):
    base = (root/directory).resolve()
    path = (base/name).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        abort(404)
    return path


@app.get("/admin/evidence/<rid>")
def evidence(rid):
    path = report(rid)["evidence"] or ""
    if not path.startswith("/instances/"):
        abort(404)
    return send_file(safe_path("instances",path[len("/instances/"):]))


@app.get("/admin/segments/<sid>/<kind>")
def segment(sid,kind):
    row = db().execute("SELECT directory FROM segments WHERE id=?",(sid,)).fetchone()
    if not row or kind not in ("video","track"):
        abort(404)
    path = safe_path("uploads",Path(row[0])/("video.mp4" if kind=="video" else "track.gpx"))
    if kind=="track":
        points,warnings=read_track(path.read_bytes())
        return render_template("page.html",page="track",points=points,warnings=warnings)
    return send_file(path,mimetype="video/mp4",conditional=True,as_attachment=request.args.get("download")=="1")


@app.post("/admin/upload")
def upload():
    kind = request.form["kind"]
    fields = {"video":["video","gpx"],"image":["image"]}.get(kind)
    if not fields:
        abort(400)
    raw = request.form["metadata"]
    meta = json.loads(raw)
    key = meta["segmentId"] if kind=="video" else request.form["key"]
    files = {k:(request.files[k].filename,request.files[k].stream,request.files[k].mimetype) for k in fields}
    body = MultipartEncoder(fields={"metadata":raw, **files})
    result = requests.post(origin+("/v1/segments" if kind=="video" else "/v1/detect"), data=body,
                           headers={"Content-Type":body.content_type,"Idempotency-Key":key},timeout=180)
    result.raise_for_status()
    with db():
        audit(key,"Uploaded "+kind)
    return redirect("/admin")


@app.route("/admin/gps",methods=["GET","POST"])
def gps():
    result = None
    if request.method=="POST":
        image = request.files.get("image")
        location = photo_gps(Image.open(image)) if image else None
        if request.files.get("metadata"):
            m = json.load(request.files["metadata"])["gps"]
            sidecar = point(m["latitude"],m["longitude"])
            if location and distance(location,sidecar)>tolerance:
                raise ValueError("EXIF and sidecar disagree. Review the sources individually.")
            location = location or sidecar
        if request.form.get("lat"):
            location = point(request.form["lat"],request.form["lon"])
        ref = point(request.form["ref_lat"],request.form["ref_lon"]) if request.form.get("ref_lat") else None
        track, warnings = read_track(request.files["gpx"].read()) if request.files.get("gpx") else ([],[])
        status, meters = validate(location,ref,tolerance)
        result = dict(location=location,status=status,meters=meters,warnings=warnings,
                      nearest=min((distance(location,p[:2]) for p in track),default=None) if location else None)
    return render_template("page.html",page="gps",result=result,tolerance=tolerance)


@app.post("/admin/reports/<rid>")
def review(rid):
    if roles[session["user"]]["role"] != "reviewer":
        abort(403)
    status = request.form["status"]
    if status not in ("Draft","Published","Rejected","Archived"):
        abort(400)
    lat,lon = point(request.form["lat"], request.form["lon"])
    ref = point(request.form["ref_lat"],request.form["ref_lon"]) if request.form.get("ref_lat") else None
    gps_state, meters = validate((lat,lon),ref,tolerance)
    confirmed = request.form.get("confirmed")=="yes"
    if status=="Published" and (not confirmed or gps_state=="Location mismatch"):
        raise ValueError("Verify location and review every public attachment before publication.")
    if not ref and confirmed:
        gps_state="Manually reviewed location"
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        previous = report(rid)
        for file in request.files.getlist("attachments"):
            if not file.filename:
                continue
            raw = file.read(32*1024**2+1)
            if len(raw)>32*1024**2:
                abort(413)
            if raw.startswith(b"%PDF-"):
                kind="document"
            elif raw[4:8]==b"ftyp":
                import av
                with av.open(io.BytesIO(raw)) as container:
                    if not container.streams.video:
                        raise ValueError("Video stream missing")
                kind="video"
            else:
                img=Image.open(io.BytesIO(raw))
                if img.width*img.height > 24000000:
                    abort(413)
                out=io.BytesIO()
                ImageOps.exif_transpose(img).convert("RGB").save(out,"JPEG",quality=88)
                raw,kind=out.getvalue(),"photo"
            conn.execute("INSERT INTO web_media VALUES(?,?,?,?,?)",(uuid.uuid4().hex,rid,kind,file.filename,raw))
        conn.execute("UPDATE web_reports SET lat=?,lon=?,gps=?,discrepancy=?,title=?,description=?,place=?,severity=?,status=? WHERE id=?",
            (lat,lon,gps_state,meters,request.form["title"],request.form["description"],request.form["place"],request.form["severity"],status,rid))
        audit(rid,json.dumps(dict(previous=[previous["lat"],previous["lon"],previous["status"]],current=[lat,lon,status],reference=ref,validation=gps_state)))
    return redirect("/admin/reports/"+rid)


@app.errorhandler(requests.RequestException)
def upstream(error):
    return render_template("page.html",page="error",error="The processing service could not complete this request. Check its status and upload fields."),502


@app.errorhandler(ValueError)
@app.errorhandler(KeyError)
@app.errorhandler(OSError)
def invalid(error):
    return render_template("page.html",page="error",error="Unable to read this input. Check file format, metadata and coordinates."),400
