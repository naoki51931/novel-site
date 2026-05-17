#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
GROUP="${1:-}"
APPLY_FLAG="${2:-}"
STATE_FILE="${STATE_FILE:-$ROOT_DIR/refactor_state.json}"

if [[ -z "$GROUP" ]]; then
  echo "usage: $0 <group> [--apply]" >&2
  exit 1
fi

python3 "$ROOT_DIR/scripts/extract_routes.py" >/dev/null

if [[ "$APPLY_FLAG" != "--apply" ]]; then
  python3 "$ROOT_DIR/scripts/gen_router_wrappers.py" --group "$GROUP"
  python3 "$ROOT_DIR/scripts/remove_app_decorators.py" --group "$GROUP"
  echo "dry-run only. pass --apply to write files." >&2
  exit 0
fi

python3 "$ROOT_DIR/scripts/gen_router_wrappers.py" --group "$GROUP" --write >/dev/null
python3 "$ROOT_DIR/scripts/remove_app_decorators.py" --group "$GROUP" --apply >/dev/null
bash "$ROOT_DIR/scripts/smoke_router_refactor.sh"

python3 - "$STATE_FILE" "$GROUP" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

state_path = Path(sys.argv[1])
group = sys.argv[2]
state = json.loads(state_path.read_text(encoding="utf-8"))
completed = set(state.get("completed_groups", []))
completed.add(group)
state["completed_groups"] = sorted(completed)
state["updated_at"] = datetime.now(timezone.utc).isoformat()
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

python3 "$ROOT_DIR/scripts/extract_routes.py" >/dev/null
echo "completed group=$GROUP" >&2
