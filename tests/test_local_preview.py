"""Regression checks for the deliberately localhost-only password-free preview."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class LocalPreviewTests(unittest.TestCase):
    def run_snippet(self, enabled, script):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "DRISHTI_DATA_DIR": tmp, "DRISHTI_ENV": "development"}
            env.pop("DRISHTI_DATABASE_URL", None)
            env.pop("WEB_USERS", None)
            env.pop("WEB_SECRET", None)
            if enabled:
                env["DRISHTI_LOCAL_NO_AUTH"] = "1"
            else:
                env.pop("DRISHTI_LOCAL_NO_AUTH", None)
            return subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                env=env, capture_output=True, text=True)

    def test_localhost_preview_allows_workspace_but_rejects_remote_client(self):
        result = self.run_snippet(True, """
import sqlite3
from pathlib import Path
import os
with sqlite3.connect(Path(os.environ['DRISHTI_DATA_DIR'])/'drishti.sqlite3') as db:
    db.executescript('''
        CREATE TABLE segments (id TEXT PRIMARY KEY);
    ''')
import app
assert app.app.test_cli_runner().invoke(args=['init']).exit_code == 0
client = app.app.test_client()
assert client.get('/login', base_url='http://127.0.0.1:11000').status_code == 302
assert client.get('/admin', base_url='http://127.0.0.1:11000').status_code == 200
assert client.get('/admin', base_url='http://127.0.0.1:11000', environ_overrides={'REMOTE_ADDR':'203.0.113.4'}).status_code == 403
assert client.get('/admin', base_url='http://public.example').status_code == 403
assert client.get('/media/private', base_url='http://127.0.0.1:11000',
                  environ_overrides={'REMOTE_ADDR':'203.0.113.4'}).status_code == 403
assert client.get('/media/private', base_url='http://127.0.0.1:11000',
                  headers={'X-Forwarded-For':'203.0.113.4'}).status_code == 403
assert client.get('/admin', base_url='http://[::1]:11000',
                  environ_overrides={'REMOTE_ADDR':'::1'}).status_code == 200
""")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preview_refuses_production_mode(self):
        result = self.run_snippet(True, """
import os
os.environ['DRISHTI_ENV'] = 'production'
import app
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DRISHTI_ENV=development", result.stderr)

    def test_preview_refuses_mariadb_database(self):
        result = self.run_snippet(True, """
import os
os.environ['DRISHTI_DATABASE_URL'] = 'mysql://unused:unused@localhost/unused'
import app
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shared MariaDB", result.stderr)

if __name__ == '__main__':
    unittest.main()
