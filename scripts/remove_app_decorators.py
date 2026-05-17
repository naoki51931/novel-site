#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from router_refactor_lib import extract_routes, repo_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove @app decorators from main.py for a route group")
    parser.add_argument("--group", required=True, help="Route group name from extract_routes.py")
    parser.add_argument("--apply", action="store_true", help="Apply changes to backend/app/main.py")
    args = parser.parse_args()

    repo = repo_root()
    main_py = repo / "backend/app/main.py"
    lines = main_py.read_text(encoding="utf-8").splitlines()
    routes = [route for route in extract_routes(main_py) if route.group == args.group]
    if not routes:
        raise SystemExit(f"no routes found for group={args.group}")

    remove_lines = {
        decorator.line
        for route in routes
        for decorator in route.decorators
    }
    preview = []
    for route in routes:
        preview.append(
            {
                "function_name": route.function_name,
                "paths": [decorator.path for decorator in route.decorators],
                "lines": [decorator.line for decorator in route.decorators],
            }
        )

    if args.apply:
        kept = [line for idx, line in enumerate(lines, start=1) if idx not in remove_lines]
        main_py.write_text("\n".join(kept) + "\n", encoding="utf-8")

    for item in preview:
        print(f"{item['function_name']}: lines={item['lines']} paths={item['paths']}")


if __name__ == "__main__":
    main()
