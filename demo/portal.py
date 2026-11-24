"""Entrypoint for the separately containerized public demonstration."""
import os
import secrets

if any(os.environ.get(k) for k in ("DRISHTI_DATABASE_URL", "DRISHTI_LOCAL_NO_AUTH", "WEB_USERS")):
    raise RuntimeError("Use the isolated demo service without production configuration.")

os.environ.update(DRISHTI_DATA_DIR="/demo-data", DRISHTI_API="http://processor:10000",
                  WEB_SECRET=secrets.token_hex(32), WEB_USERS='{"demo-visitor":{"role":"reviewer"}}')

from flask import redirect, request, session
from app import app, root

if not (root / ".public-demo").is_file():
    raise RuntimeError("Missing demo volume marker.")

app.config.update(SESSION_COOKIE_NAME="drishti_demo", SESSION_COOKIE_SECURE=False,
                  MAX_CONTENT_LENGTH=40 * 1024**2)


def demo_visitor():
    session["user"] = "demo-visitor"
    if request.path == "/login":
        return redirect("/admin", 303)


# Set the demo identity before the ordinary role and CSRF checks run.
app.before_request_funcs[None].insert(0, demo_visitor)
