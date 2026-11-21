#!/usr/bin/env bash
# Run from the web repository with both repositories' Python dependencies installed.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${DRISHTI_CHECKOUT:?Set to the Drishti mobile/backend repository}"
api_dir=$(cd "$DRISHTI_CHECKOUT/server" && pwd)
api_python=${API_PYTHON:-$api_dir/.venv/bin/python}
api_python="$(cd "$(dirname "$api_python")" && pwd)/$(basename "$api_python")"
web_python=${WEB_PYTHON:-"$PWD/.venv/bin/python"}
driver_python=${BROWSER_PYTHON:-$web_python}
export DRISHTI_MODEL=$(realpath "${TEST_CHECKPOINT:-$api_dir/best.pt}")
test -s "$DRISHTI_MODEL"
export DRISHTI_DATA_DIR=$(mktemp -d)
export TEST_WEB_URL=http://localhost:11170 DRISHTI_API=http://127.0.0.1:10170
export WEB_SECRET=$("$web_python" -c 'import secrets; print(secrets.token_hex(32))')
export TEST_USER=tester TEST_PASSWORD=test-only TEST_FIXTURE_REPORT=browser-gallery
export WEB_USERS=$("$web_python" -c 'import json; from werkzeug.security import generate_password_hash; print(json.dumps({"tester":{"hash":generate_password_hash("test-only"),"role":"reviewer"}}))')
export DRISHTI_DEVICE=cpu OMP_NUM_THREADS=2 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
unset DRISHTI_PUBLIC_URL
(cd "$api_dir" && exec "$api_python" -m uvicorn app.app:app --host 127.0.0.1 --port 10170) >"$DRISHTI_DATA_DIR/api.log" 2>&1 &
api_pid=$!
cleanup() {
  kill "$api_pid" ${web_pid:-} 2>/dev/null || true
  wait "$api_pid" ${web_pid:-} 2>/dev/null || true
  echo "Disposable test database and logs: $DRISHTI_DATA_DIR"
}
trap cleanup EXIT
ready() {
  for attempt in {1..60}; do
    kill -0 "$2" || return 1
    curl --noproxy '*' -fs "$1" >/dev/null && return 0
    sleep 1
  done
  return 1
}
ready "$DRISHTI_API/health" "$api_pid"
"$web_python" -m flask --app app init
ffmpeg -loglevel error -f lavfi -i color=blue:s=160x120:r=10 -t 1 -c:v libx264 -pix_fmt yuv420p "$DRISHTI_DATA_DIR/fixture.mp4"
"$web_python" tests/seed_browser.py "$DRISHTI_DATA_DIR" "$DRISHTI_DATA_DIR/fixture.mp4"
"$web_python" -m gunicorn --workers 2 --threads 4 --bind 127.0.0.1:11170 app:app >"$DRISHTI_DATA_DIR/web.log" 2>&1 &
web_pid=$!
ready "$TEST_WEB_URL/" "$web_pid"
"$driver_python" tests/browser_streams.py
