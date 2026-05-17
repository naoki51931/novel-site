#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="${STATE_FILE:-$ROOT_DIR/refactor_state.json}"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/reports}"
BACKEND_LOG_FILE="$REPORT_DIR/router_refactor_backend.log"
RESULT_FILE="$REPORT_DIR/router_refactor_smoke.json"
BASE_URL="${BASE_URL:-https://127.0.0.1}"
HOST_HEADER="${HOST_HEADER:-lexis-novel.com}"

mkdir -p "$REPORT_DIR"

python3 -m py_compile \
  "$ROOT_DIR/backend/app/main.py" \
  "$ROOT_DIR"/backend/app/routers/*.py \
  "$ROOT_DIR"/backend/app/features/*.py

(cd "$ROOT_DIR" && docker compose up --build -d >/tmp/router_refactor_compose.log 2>&1)
(cd "$ROOT_DIR" && docker compose ps > "$REPORT_DIR/router_refactor_ps.txt")
(cd "$ROOT_DIR" && docker compose logs --since=15m backend > "$BACKEND_LOG_FILE" 2>&1 || true)

python3 - "$BASE_URL" "$HOST_HEADER" <<'PY'
import ssl
import sys
import time
import urllib.error
import urllib.request

base_url = sys.argv[1].rstrip("/")
host_header = sys.argv[2]
ssl_ctx = ssl._create_unverified_context()
deadline = time.time() + 60
last_error = ""

while time.time() < deadline:
    req = urllib.request.Request(
        url=f"{base_url}/api/support_plans?author_user_id=1",
        method="GET",
        headers={"Host": host_header},
    )
    try:
        with urllib.request.urlopen(req, context=ssl_ctx) as res:
            status = int(res.getcode())
            if status in (200, 401, 422):
                raise SystemExit(0)
            last_error = f"unexpected status={status}"
    except urllib.error.HTTPError as exc:
        if int(exc.code) in (200, 401, 422):
            raise SystemExit(0)
        last_error = f"http error={exc.code}"
    except Exception as exc:
        last_error = repr(exc)
    time.sleep(2)

raise SystemExit(f"backend readiness check failed: {last_error}")
PY

python3 - "$STATE_FILE" "$RESULT_FILE" "$BASE_URL" "$HOST_HEADER" <<'PY'
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

state_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
base_url = sys.argv[3].rstrip("/")
host_header = sys.argv[4]

state = json.loads(state_path.read_text(encoding="utf-8"))
tests = state.get("smoke_tests", [])
ssl_ctx = ssl._create_unverified_context()
results = []
all_ok = True

for test in tests:
    method = test["method"].upper()
    path = test["path"]
    url = f"{base_url}{path}"
    payload = test.get("json")
    body = None
    headers = {"Host": host_header}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=body, method=method, headers=headers)
    expected = set(test.get("expected_status", []))
    actual_status = None
    response_body = ""
    ok = False
    try:
        with urllib.request.urlopen(req, context=ssl_ctx) as res:
            actual_status = int(res.getcode())
            response_body = res.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        actual_status = int(exc.code)
        response_body = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        response_body = repr(exc)

    ok = actual_status in expected
    if not ok:
        all_ok = False
    results.append(
        {
            "name": test.get("name") or f"{method} {path}",
            "method": method,
            "path": path,
            "expected_status": sorted(expected),
            "actual_status": actual_status,
            "ok": ok,
            "response_body_preview": response_body[:500],
        }
    )

report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "base_url": base_url,
    "host_header": host_header,
    "ok": all_ok,
    "results": results,
}
result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
if not all_ok:
    raise SystemExit(1)
PY
