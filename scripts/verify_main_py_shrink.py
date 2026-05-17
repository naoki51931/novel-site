#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_git_status_lines(lines: list[str]) -> list[str]:
    changed: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        path_part = line[3:]
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        changed.append(path_part.strip())
    return changed


def _git_changed_paths(repo_root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    return _parse_git_status_lines(result.stdout.splitlines())


def _detect_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
        if (candidate / "backend" / "app" / "main.py").exists():
            return candidate
    return start.resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that backend/app/main.py shrank or stayed stable after router refactor work."
    )
    parser.add_argument("before", help="Path to the report captured before changes")
    parser.add_argument("after", help="Path to the report captured after changes")
    parser.add_argument(
        "--require-decrease",
        action="store_true",
        help="Fail unless main.py line count strictly decreases",
    )
    parser.add_argument(
        "--allowed-path",
        action="append",
        default=[],
        help="Allowed changed path prefix relative to the repository root; can be passed multiple times",
    )
    parser.add_argument(
        "--baseline-status-file",
        default=None,
        help="Optional git status snapshot file captured before the operation; those paths are ignored",
    )
    args = parser.parse_args()

    before_path = Path(args.before).resolve()
    after_path = Path(args.after).resolve()
    before = _load_report(before_path)
    after = _load_report(after_path)
    repo_root = _detect_repo_root(before_path)

    before_lines = int(before.get("main_py_line_count", 0) or 0)
    after_lines = int(after.get("main_py_line_count", 0) or 0)
    before_routes = int(before.get("remaining_app_route_functions", 0) or 0)
    after_routes = int(after.get("remaining_app_route_functions", 0) or 0)
    before_entries = int(before.get("total_route_entries", 0) or 0)
    after_entries = int(after.get("total_route_entries", 0) or 0)

    errors: list[str] = []
    if after_lines > before_lines:
        errors.append(f"main.py line count increased: {before_lines} -> {after_lines}")
    if args.require_decrease and after_lines >= before_lines:
        errors.append(f"main.py line count did not decrease: {before_lines} -> {after_lines}")
    if after_routes > before_routes:
        errors.append(f"remaining app route functions increased: {before_routes} -> {after_routes}")
    if after_entries > before_entries:
        errors.append(f"total route entries increased: {before_entries} -> {after_entries}")

    baseline_paths: set[str] = set()
    if args.baseline_status_file:
        baseline_lines = Path(args.baseline_status_file).read_text(encoding="utf-8").splitlines()
        baseline_paths = set(_parse_git_status_lines(baseline_lines))

    changed_paths = [path for path in _git_changed_paths(repo_root) if path not in baseline_paths]
    unexpected_paths: list[str] = []
    if args.allowed_path and changed_paths:
        allowed = tuple(args.allowed_path)
        unexpected_paths = [path for path in changed_paths if not path.startswith(allowed)]
        if unexpected_paths:
            errors.append(
                "unexpected changed paths detected: " + ", ".join(sorted(unexpected_paths))
            )

    summary = {
        "before_lines": before_lines,
        "after_lines": after_lines,
        "before_remaining_route_functions": before_routes,
        "after_remaining_route_functions": after_routes,
        "before_total_route_entries": before_entries,
        "after_total_route_entries": after_entries,
        "baseline_paths": sorted(baseline_paths),
        "changed_paths": changed_paths,
        "unexpected_paths": unexpected_paths,
        "ok": not errors,
        "errors": errors,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
