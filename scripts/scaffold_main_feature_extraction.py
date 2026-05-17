#!/usr/bin/env python3
import argparse
import ast
from pathlib import Path


def _find_top_level_functions(module: ast.Module) -> dict[str, ast.FunctionDef]:
    found: dict[str, ast.FunctionDef] = {}
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            found[node.name] = node
    return found


def _build_delegate_call(func: ast.FunctionDef, service_name: str) -> str:
    args: list[str] = []
    for arg in func.args.posonlyargs:
        args.append(f"{arg.arg}={arg.arg}")
    for arg in func.args.args:
        args.append(f"{arg.arg}={arg.arg}")
    if func.args.vararg:
        args.append(f"*{func.args.vararg.arg}")
    for arg in func.args.kwonlyargs:
        args.append(f"{arg.arg}={arg.arg}")
    if func.args.kwarg:
        args.append(f"**{func.args.kwarg.arg}")
    return f"return {service_name}({', '.join(args)})"


def _build_service_stub(func: ast.FunctionDef, original_src: str) -> str:
    header = original_src.splitlines()[0]
    renamed_header = header.replace(f"def {func.name}(", f"def {func.name}_service(", 1)
    commented = "\n".join(f"# {line}" if line else "#" for line in original_src.splitlines())
    return "\n".join(
        [
            renamed_header,
            '    """Scaffold generated from main.py. Replace the commented body with a real extraction."""',
            "    from .. import main as legacy",
            '    raise NotImplementedError("Replace scaffolded body before use")',
            "",
            "    # Original source for reference:",
            commented,
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold feature-service extraction stubs and main.py delegators."
    )
    parser.add_argument("--main-path", required=True)
    parser.add_argument("--feature-path", required=True)
    parser.add_argument("--functions", nargs="+", required=True)
    args = parser.parse_args()

    main_path = Path(args.main_path)
    feature_path = Path(args.feature_path)
    source = main_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = _find_top_level_functions(tree)

    missing = [name for name in args.functions if name not in functions]
    if missing:
        raise SystemExit(f"Functions not found: {', '.join(missing)}")

    lines = source.splitlines()
    service_stubs: list[str] = []
    replacements: list[tuple[int, int, str]] = []

    for name in args.functions:
        func = functions[name]
        start = func.lineno
        end = func.end_lineno
        original_src = "\n".join(lines[start - 1 : end])
        service_stubs.append(_build_service_stub(func, original_src).rstrip())
        replacements.append(
            (
                start,
                end,
                "\n".join(
                    [
                        lines[start - 1],
                        f"    from .features.{feature_path.stem} import {name}_service",
                        "",
                        f"    {_build_delegate_call(func, f'{name}_service')}",
                    ]
                ),
            )
        )

    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_output = "\n\n".join(service_stubs) + "\n"
    if feature_path.exists():
        feature_path.write_text(feature_path.read_text(encoding='utf-8') + "\n" + feature_output, encoding="utf-8")
    else:
        feature_path.write_text(feature_output, encoding="utf-8")

    updated_lines = list(lines)
    for start, end, replacement in sorted(replacements, reverse=True):
        updated_lines[start - 1 : end] = replacement.splitlines()
    main_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
