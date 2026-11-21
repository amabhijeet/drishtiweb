"""Integration checks using disposable SQLite and real HTTP route handlers."""
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

from PIL import Image
from werkzeug.security import generate_password_hash
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("WEB_USERS","{}")
os.environ.setdefault("WEB_SECRET","tests-only")
os.environ.setdefault("DRISHTI_DATA_DIR",tempfile.gettempdir())
import app as web


class ReviewTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        old=web.root,web.roles
        self.addCleanup(lambda: (setattr(web,"root",old[0]),setattr(web,"roles",old[1])))
        web.root=Path(folder.name)
        web.roles={r:{"role":r,"hash":generate_password_hash("test")} for r in ("operator","reviewer")}
        with sqlite3.connect(web.root/"drishti.sqlite3") as db:
            db.executescript(web.schema)
            db.execute("INSERT INTO web_reports(id,original_lat,original_lon,lat,lon) VALUES('r',26,91,26,91)")
        self.client=web.app.test_client()

    def login(self,role):
        with self.client.session_transaction() as session:
            session.update(user=role,csrf="token")

    def form(self,**extra):
        return dict(dict(csrf="token",status="Published",confirmed="yes",lat="26",lon="91",title="Pothole",description="Reviewed",severity="Moderate",place="Site"),**extra)

    def test_operator_cannot_publish(self):
        self.login("operator")
        self.assertEqual(self.client.post("/admin/reports/r",data=self.form()).status_code,403)

    def test_reference_mismatch(self):
        self.login("reviewer")
        self.assertEqual(self.client.post("/admin/reports/r",data=self.form(ref_lat="0",ref_lon="0")).status_code,400)
        self.assertEqual(self.client.get("/reports/r").status_code,404)

    def test_gallery_visibility_and_archive(self):
        self.login("reviewer")
        data=io.BytesIO()
        Image.new("RGB",(20,20)).save(data,"PNG")
        files=[(io.BytesIO(data.getvalue()),name) for name in ("first.png","second.png")]
        self.assertEqual(self.client.post("/admin/reports/r",data=self.form(attachments=files)).status_code,302)
        public=web.app.test_client()
        page=public.get("/reports/r")
        self.assertEqual(page.status_code,200)
        self.assertEqual(page.data.count(b'<img src="/media/'),2)
        with sqlite3.connect(web.root/"drishti.sqlite3") as db:
            mids=db.execute("SELECT id FROM web_media").fetchall()
        for mid, in mids:
            self.assertEqual(public.get("/media/"+mid).mimetype,"image/jpeg")
        self.client.post("/admin/reports/r",data=self.form(status="Archived"))
        self.assertEqual(public.get("/reports/r").status_code,404)
        for mid, in mids:
            self.assertEqual(public.get("/media/"+mid).status_code,404)

    def test_published_video_ranges(self):
        payload=bytes(range(256))*1024
        with sqlite3.connect(web.root/"drishti.sqlite3") as db:
            db.execute("INSERT INTO web_media VALUES('vid','r','video','clip.mp4',?)",(payload,))
            db.execute("UPDATE web_reports SET status='Published' WHERE id='r'")
        for header,expected in [("bytes=100-199",payload[100:200]),("bytes=-15",payload[-15:]),("bytes=65535-",payload[65535:])]:
            response=self.client.get("/media/vid",headers={"Range":header})
            self.assertEqual(response.status_code,206)
            self.assertEqual(response.data,expected)
            self.assertEqual(int(response.headers["Content-Length"]),len(expected))
        self.assertEqual(self.client.get("/media/vid",headers={"Range":"bytes=999999-"}).status_code,416)
        self.assertEqual(self.client.head("/media/vid").headers["Content-Length"],str(len(payload)))
        self.assertEqual(self.client.get("/media/vid").data,payload)

    def test_detection_links_and_private_originals(self):
        with sqlite3.connect(web.root/"drishti.sqlite3") as db:
            db.executescript("""
                CREATE TABLE segments(id TEXT PRIMARY KEY,directory TEXT,video_path TEXT,gpx_path TEXT,status TEXT);
                CREATE TABLE detections(id TEXT PRIMARY KEY,segment TEXT,image TEXT);
                INSERT INTO segments VALUES('source','legacy','original/video.mp4','original/track.gpx','done');
                INSERT INTO detections VALUES('r','source','frame.jpg');
                UPDATE web_reports SET source='video',source_id='source',status='Published' WHERE id='r';
            """)
        media = web.root/"uploads"/"original"
        media.mkdir(parents=True)
        (media/"video.mp4").write_bytes(b"video")
        (media/"track.gpx").write_bytes(b"<gpx/>")
        (web.root/"instances").mkdir()
        (web.root/"instances"/"frame.jpg").write_bytes(b"annotated")
        assets = {
            "/admin/segments/source/video?download=1": b"video",
            "/admin/segments/source/track?download=1": b"<gpx/>",
            "/admin/detections/r/image": b"annotated",
        }
        for url in assets:
            self.assertEqual(self.client.get(url).status_code,302)
        self.assertNotIn(b'/admin/detections/r/image', self.client.get("/reports/r").data)
        self.login("reviewer")
        details = self.client.get("/admin/reports/r").data
        self.assertIn(b'/admin/videos/source#r', details)
        self.assertIn(b'/admin/segments/source/track?download=1', details)
        self.assertIn(b'/admin/detections/r/image', details)
        for url, contents in assets.items():
            with self.client.get(url) as response:
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.data,contents)
        self.assertEqual(self.client.get("/admin/detections/unknown/image").status_code,404)
