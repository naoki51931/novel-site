#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
import ast


DECORATOR_RE = re.compile(
    r'^\s*@app\.(?P<method>get|post|put|delete|patch)\(\s*(?P<quote>["\'])(?P<path>.+?)(?P=quote)'
)


@dataclass
class DecoratorMeta:
    line: int
    method: str
    path: str


@dataclass
class ParamMeta:
    name: str
    source: str
    annotation: str | None
    default_source: str | None
    is_payload_model: bool
    payload_model_name: str | None


@dataclass
class RouteFunctionMeta:
    function_name: str
    async_def: bool
    start_line: int
    decorators: list[DecoratorMeta]
    params: list[ParamMeta]
    group: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main_py_path() -> Path:
    return repo_root() / "backend/app/main.py"


def state_path() -> Path:
    return repo_root() / "refactor_state.json"


def load_state(path: Path | None = None) -> dict:
    target = path or state_path()
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def detect_group(path: str) -> str:
    if path.startswith("/api/admin/"):
        return "admin"
    if path.startswith("/api/auth/"):
        return "auth"
    if path.startswith("/api/stripe/"):
        return "payments"
    if path.startswith("/api/support"):
        return "payments"
    if path.startswith("/api/membership"):
        return "payments"
    if path.startswith("/api/authors/me/support_plans"):
        return "payments"
    if path.startswith("/api/authors/me/balance"):
        return "payments"
    if path.startswith("/api/authors/me/payout_profile"):
        return "payments"
    if path.startswith("/api/ai/chat/"):
        return "ai_chat"
    if path.startswith("/api/ai/jobs"):
        return "ai_novel"
    if path.startswith("/api/ai/novels"):
        return "ai_novel"
    if path.startswith("/api/ai/episodes"):
        return "ai_novel"
    if path.startswith("/api/ai/"):
        return "ai_misc"
    if path.startswith("/api/i18n/"):
        return "i18n"
    if path.startswith("/api/board/"):
        return "board"
    if path.startswith("/api/tags"):
        return "tags"
    if path.startswith("/api/feed/"):
        return "feed"
    if path.startswith("/api/search/"):
        return "search"
    if path.startswith("/api/public/"):
        return "public"
    if path.startswith("/api/series/"):
        return "series"
    if path.startswith("/api/dms"):
        return "dms"
    if path.startswith("/api/episodes/"):
        return "episodes"
    if path.startswith("/api/novels/"):
        return "novels"
    if path.startswith("/api/me/"):
        return "me"
    return "other"


def _arg_source(source_text: str, node: ast.arg) -> str:
    segment = ast.get_source_segment(source_text, node)
    if segment:
        return segment.strip()
    if node.annotation is None:
        return node.arg
    annotation = ast.get_source_segment(source_text, node.annotation) or ast.unparse(node.annotation)
    return f"{node.arg}: {annotation}"


def _is_payload_model(annotation: str | None) -> tuple[bool, str | None]:
    if not annotation:
        return False, None
    normalized = annotation.replace(" ", "")
    if normalized.startswith(("Request", "Response", "Session", "dict", "list", "List", "Optional", "str", "int", "bool", "float")):
        return False, None
    if "Depends(" in normalized or "Query(" in normalized or "Header(" in normalized or "Body(" in normalized:
        return False, None
    base = annotation.split("[", 1)[0].split("|", 1)[0].strip()
    if "." in base:
        base = base.split(".")[-1]
    if not base or not re.match(r"^[A-Z][A-Za-z0-9_]*$", base):
        return False, None
    return True, base


def extract_routes(main_py: Path | None = None) -> list[RouteFunctionMeta]:
    target = main_py or main_py_path()
    source_text = target.read_text(encoding="utf-8")
    lines = source_text.splitlines()
    i = 0
    routes: list[RouteFunctionMeta] = []
    while i < len(lines):
        match = DECORATOR_RE.match(lines[i])
        if not match:
            i += 1
            continue
        decorators: list[DecoratorMeta] = []
        while i < len(lines):
            inner = DECORATOR_RE.match(lines[i])
            if inner:
                decorators.append(
                    DecoratorMeta(
                        line=i + 1,
                        method=inner.group("method").upper(),
                        path=inner.group("path"),
                    )
                )
                i += 1
                continue
            if lines[i].strip().startswith("@app."):
                i += 1
                continue
            break

        while i < len(lines) and not lines[i].lstrip().startswith(("def ", "async def ")):
            i += 1
        if i >= len(lines):
            break

        signature_start = i
        signature_lines = [lines[i]]
        paren_balance = lines[i].count("(") - lines[i].count(")")
        while i + 1 < len(lines) and paren_balance > 0:
            i += 1
            signature_lines.append(lines[i])
            paren_balance += lines[i].count("(") - lines[i].count(")")

        signature_text = "\n".join(signature_lines)
        signature_stub = signature_text + "\n    pass\n"
        node = ast.parse(signature_stub).body[0]
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            i += 1
            continue

        params: list[ParamMeta] = []
        positional = list(node.args.args)
        defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
        for arg, default in zip(positional, defaults):
            annotation = ast.get_source_segment(signature_stub, arg.annotation).strip() if arg.annotation is not None else None
            default_source = ast.get_source_segment(signature_stub, default).strip() if default is not None else None
            param_source = _arg_source(signature_stub, arg)
            if default_source is not None:
                param_source = f"{param_source} = {default_source}"
            payload_model, payload_model_name = _is_payload_model(annotation)
            params.append(
                ParamMeta(
                    name=arg.arg,
                    source=param_source,
                    annotation=annotation,
                    default_source=default_source,
                    is_payload_model=payload_model and arg.arg in {"payload", "req"},
                    payload_model_name=payload_model_name if arg.arg in {"payload", "req"} else None,
                )
            )
        routes.append(
            RouteFunctionMeta(
                function_name=node.name,
                async_def=isinstance(node, ast.AsyncFunctionDef),
                start_line=decorators[0].line,
                decorators=decorators,
                params=params,
                group=detect_group(decorators[0].path),
            )
        )
        i += 1
    return routes


def generated_block_markers(group: str) -> tuple[str, str]:
    upper = group.upper()
    return (
        f"# BEGIN AUTO-GENERATED ROUTER WRAPPERS: {upper}",
        f"# END AUTO-GENERATED ROUTER WRAPPERS: {upper}",
    )


def replace_generated_block(text: str, group: str, block_body: str) -> str:
    begin, end = generated_block_markers(group)
    wrapped = f"{begin}\n{block_body.rstrip()}\n{end}\n"
    if begin in text and end in text:
        pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
        return pattern.sub(wrapped, text)
    if text and not text.endswith("\n"):
        text += "\n"
    if text and not text.endswith("\n\n"):
        text += "\n"
    return text + wrapped
