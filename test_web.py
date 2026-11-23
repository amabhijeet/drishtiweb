import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from gps import point, distance, validate, read_track
from werkzeug.security import generate_password_hash
import json

temp=tempfile.TemporaryDirectory()
os.environ.update(WEB_SECRET="test-only",DRISHTI_DATA_DIR=temp.name,WEB_USERS=json.dumps({"staff":{"hash":generate_password_hash("test"),"role":"operator"}}))
from app import app, schema

class WebTests(unittest.TestCase):
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
