#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone

from router_refactor_lib import extract_routes, load_state, repo_root


def build_summary(routes) -> dict:
    by_group: dict[str, dict] = defaultdict(lambda: {"count": 0, "functions": []})
    for route in routes:
        group = route.group
        by_group[group]["count"] += len(route.decorators)
        by_group[group]["functions"].append(
            {
                "function_name": route.function_name,
                "start_line": route.start_line,
                "paths": [item.path for item in route.decorators],
                "methods": [item.method for item in route.decorators],
            }
        )
    return dict(sorted(by_group.items(), key=lambda item: (-item[1]["count"], item[0])))


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract @app routes from backend/app/main.py")
    parser.add_argument(
        "--main-py",
        default="backend/app/main.py",
        help="Path to main.py relative to the repo root",
    )
    parser.add_argument(
        "--state",
        default="refactor_state.json",
        help="Path to the router refactor state file",
    )
    parser.add_argument(
        "--output",
        default="reports/router_refactor_routes.json",
        help="Path to write the extracted route report",
    )
    args = parser.parse_args()

    repo = repo_root()
    main_py = repo / args.main_py
    state_file = repo / args.state
    output_path = repo / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    routes = extract_routes(main_py)
    state = load_state(state_file)
    completed_groups = set(state.get("completed_groups", []))

    summary = build_summary(routes)
    pending_counts = {
        group: item["count"]
        for group, item in summary.items()
        if group not in completed_groups
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "main_py": str(main_py.relative_to(repo)),
        "main_py_line_count": sum(1 for _ in main_py.open("r", encoding="utf-8")),
        "total_route_entries": sum(len(route.decorators) for route in routes),
        "remaining_app_route_functions": len(routes),
        "completed_groups": sorted(completed_groups),
        "pending_group_counts": dict(sorted(pending_counts.items(), key=lambda item: (-item[1], item[0]))),
        "groups": summary,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
