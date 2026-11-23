import io
import os
import sqlite3
import tempfile
import unittest
import importlib
from pathlib import Path
from unittest.mock import patch
from gps import point, distance, validate, read_track
from werkzeug.security import generate_password_hash
import json

temp=tempfile.TemporaryDirectory()
os.environ.update(WEB_SECRET="test-only",DRISHTI_DATA_DIR=temp.name,WEB_USERS=json.dumps({"staff":{"hash":generate_password_hash("test"),"role":"operator"}}))
from app import app, schema

class WebTests(unittest.TestCase):
    def test_staff_tunnel(self):
        import app as portal
        token = "a" * 64
        with patch.dict(os.environ, {"DRISHTI_STAFF_TUNNEL_TOKEN": token}):
            importlib.reload(portal)
            self.addCleanup(importlib.reload, portal)
            with sqlite3.connect(Path(temp.name) / "drishti.sqlite3") as db:
                db.executescript(portal.schema)
                db.execute("CREATE TABLE IF NOT EXISTS segments(id TEXT)")
                db.execute("INSERT INTO web_reports(id,status) VALUES('tunnel-draft','Draft')")
                db.execute("INSERT INTO web_media VALUES('tunnel-photo','tunnel-draft','photo','test.jpg',X'0102')")
            c = portal.app.test_client()
            origin = "http://127.0.0.1:11001"
            header = {"X-Drishti-Staff-Tunnel": token}
            self.assertEqual(c.get("/admin/reports/tunnel-draft", base_url=origin, headers=header).status_code, 200)
            self.assertEqual(c.get("/media/tunnel-photo", base_url=origin, headers=header).data, b"\x01\x02")
            self.assertEqual(c.get("/media/tunnel-photo", base_url=origin).status_code, 404)
            self.assertEqual(c.get("/admin", base_url=origin).status_code, 404)
            self.assertEqual(c.get("/login", base_url=origin).status_code, 404)
            self.assertEqual(c.get("/login", base_url=origin, headers=header).location, "/admin")
            self.assertEqual(c.post("/admin/sync", base_url=origin, headers=header).status_code, 403)
            self.assertEqual(c.get("/admin", base_url="https://public.invalid", headers=header).status_code, 404)
            self.assertEqual(c.get("/admin", base_url=origin, headers=header,
                                   environ_overrides={"REMOTE_ADDR": "10.0.0.1"}).status_code, 404)
    def test_gps(self):
        self.assertAlmostEqual(distance((0,0),(0,1)),111195,delta=5)
        for bad in [(91,0),(0,181),(float("nan"),0)]:
            with self.assertRaises(ValueError): point(*bad)
        self.assertEqual(validate(None,None,25)[0],"Missing GPS evidence")
        self.assertEqual(validate((0,0),(0,0),25)[0],"Reference matched")
        self.assertEqual(validate((0,0),(0,1),25)[0],"Location mismatch")
        track=b'<gpx><trkseg><trkpt lat="0" lon="0"><time>2026-01-01T00:00:00Z</time></trkpt><trkpt lat="0" lon="1"><time>2026-01-01T00:00:01Z</time></trkpt></trkseg></gpx>'
        self.assertTrue(read_track(track)[1])

    def test_public_boundary(self):
        with sqlite3.connect(Path(temp.name)/"drishti.sqlite3") as db:
            db.executescript(schema)
            db.execute("INSERT INTO web_reports(id,status) VALUES('private-id','Draft')")
        c=app.test_client()
        for path in ["/","/map","/docs","/login"]:
            self.assertEqual(c.get(path).status_code,200)
        self.assertEqual(c.get('/reports/private-id').status_code,404)
        self.assertNotIn(b'private-id',c.get('/map').data)
        self.assertEqual(c.get('/admin').status_code,302)
        self.assertEqual(c.post('/admin/sync').status_code,403)

if __name__=='__main__': unittest.main()
