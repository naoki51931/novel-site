#!/usr/bin/env bash
set -euo pipefail

if [[ "${AUTO_REFACTOR_TIMEOUT_GUARD:-0}" != "1" ]] && command -v timeout >/dev/null 2>&1; then
  export AUTO_REFACTOR_TIMEOUT_GUARD=1
  exec timeout --foreground "${TIMEOUT_DURATION:-5h}" "$0" "$@"
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/reports/auto_refactor_main_py}"
STATE_FILE="${STATE_FILE:-$ROOT_DIR/refactor_state.json}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$REPORT_DIR"

BEFORE_REPORT="$REPORT_DIR/before.json"
AFTER_REPORT="$REPORT_DIR/after.json"
SUMMARY_FILE="$REPORT_DIR/summary.json"
GROUPS_FILE="$REPORT_DIR/groups.txt"
BASELINE_STATUS_FILE="$REPORT_DIR/baseline_git_status.txt"

if command -v git >/dev/null 2>&1; then
  (
    cd "$ROOT_DIR"
    git status --short --untracked-files=all
  ) >"$BASELINE_STATUS_FILE" || true
else
  : >"$BASELINE_STATUS_FILE"
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/extract_routes.py" --state "${STATE_FILE#$ROOT_DIR/}" --output "${BEFORE_REPORT#$ROOT_DIR/}" >/dev/null

"$PYTHON_BIN" - "$STATE_FILE" "$BEFORE_REPORT" >"$GROUPS_FILE" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
report = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
completed = set(state.get("completed_groups", []))
router_files = state.get("router_files", {})
pending_counts = report.get("pending_group_counts", {})

groups = [
    group
    for group, _count in sorted(
        pending_counts.items(),
        key=lambda item: (-int(item[1]), item[0]),
    )
    if group in router_files and group not in completed and int(pending_counts.get(group, 0) or 0) > 0
]
print("\n".join(groups))
PY

mapfile -t TARGET_GROUPS_RAW <"$GROUPS_FILE" || true
TARGET_GROUPS=()
for GROUP in "${TARGET_GROUPS_RAW[@]:-}"; do
  if [[ -n "$GROUP" ]]; then
    TARGET_GROUPS+=("$GROUP")
  fi
done

if [[ "${#TARGET_GROUPS[@]}" -eq 0 ]]; then
  "$PYTHON_BIN" - "$SUMMARY_FILE" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

summary = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "processed_groups": [],
    "message": "no pending configured groups",
}
Path(sys.argv[1]).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
  exit 0
fi

PROCESSED=()
for GROUP in "${TARGET_GROUPS[@]}"; do
  echo "processing group=${GROUP}" >&2
  bash "$ROOT_DIR/scripts/run_refactor_batch.sh" "$GROUP" --apply
  "$PYTHON_BIN" "$ROOT_DIR/scripts/extract_routes.py" --state "${STATE_FILE#$ROOT_DIR/}" --output "${AFTER_REPORT#$ROOT_DIR/}" >/dev/null
  "$PYTHON_BIN" "$ROOT_DIR/scripts/verify_main_py_shrink.py" \
    "$BEFORE_REPORT" \
    "$AFTER_REPORT" \
    --require-decrease \
    --baseline-status-file "$BASELINE_STATUS_FILE" \
    --allowed-path backend/app/main.py \
    --allowed-path backend/app/routers/ \
    --allowed-path refactor_state.json \
    --allowed-path reports/ \
    --allowed-path scripts/
  mv "$AFTER_REPORT" "$BEFORE_REPORT"
  PROCESSED+=("$GROUP")
done

"$PYTHON_BIN" - "$SUMMARY_FILE" "${PROCESSED[@]}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

summary = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "processed_groups": sys.argv[2:],
}
Path(sys.argv[1]).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
