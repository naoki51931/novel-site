#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from router_refactor_lib import extract_routes, load_state, repo_root, replace_generated_block


HELPER_BLOCK = """from typing import Any, Dict, List, Literal, Optional

from fastapi import BackgroundTasks, Body, Depends, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
"""


def _wrapper_signature(route) -> str:
    parts = []
    for param in route.params:
        if param.is_payload_model:
            if param.default_source is not None:
                parts.append(f"{param.name}: dict = {param.default_source}")
            else:
                parts.append(f"{param.name}: dict")
        else:
            parts.append(param.source)
    return ",\n    ".join(parts)


def _wrapper_call(route) -> tuple[list[str], str]:
    prelude: list[str] = []
    kwargs: list[str] = []
    for param in route.params:
        if param.is_payload_model and param.payload_model_name:
            local_name = f"{param.name}_model"
            parse_expr = f"_parse_payload(legacy.{param.payload_model_name}, {param.name})"
            prelude.append(f"    {local_name} = {parse_expr}")
            kwargs.append(f"{param.name}={local_name}")
        else:
            kwargs.append(f"{param.name}={param.name}")
    invoke = f"legacy.{route.function_name}({', '.join(kwargs)})"
    return prelude, invoke


def generate_group_block(group: str) -> str:
    routes = [route for route in extract_routes() if route.group == group]
    if not routes:
        raise SystemExit(f"no routes found for group={group}")

    chunks = [HELPER_BLOCK.rstrip(), ""]
    for route in routes:
        for decorator in route.decorators:
            chunks.append(f'@router.{decorator.method.lower()}("{decorator.path}")')
        signature = _wrapper_signature(route)
        async_prefix = "async " if route.async_def else ""
        chunks.append(f"{async_prefix}def {route.function_name}(")
        if signature:
            chunks.append(f"    {signature}")
        chunks.append("):")
        chunks.append("    from .. import main as legacy")
        prelude, invoke = _wrapper_call(route)
        if prelude:
            chunks.extend(prelude)
        if route.async_def:
            chunks.append(f"    return await {invoke}")
        else:
            chunks.append(f"    return {invoke}")
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate router wrappers for a route group")
    parser.add_argument("--group", required=True, help="Route group name from extract_routes.py")
    parser.add_argument("--write", action="store_true", help="Write the generated block into the router file")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output file for the generated wrapper block",
    )
    args = parser.parse_args()

    state = load_state()
    router_files = state.get("router_files", {})
    router_relative = router_files.get(args.group)
    if not router_relative:
        raise SystemExit(f"router file is not configured for group={args.group}")

    generated = generate_group_block(args.group)
    repo = repo_root()
    output_path = Path(args.output) if args.output else repo / "reports" / f"router_wrappers_{args.group}.py"
    if not output_path.is_absolute():
        output_path = repo / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated, encoding="utf-8")

    if args.write:
        router_path = repo / router_relative
        original = router_path.read_text(encoding="utf-8")
        updated = replace_generated_block(original, args.group, generated)
        router_path.write_text(updated, encoding="utf-8")

    print(generated)


if __name__ == "__main__":
    main()
