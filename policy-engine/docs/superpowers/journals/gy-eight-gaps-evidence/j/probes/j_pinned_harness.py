"""Run one planned scratch module, preserving stdout and binding harness bytes.

Only stderr gains one execution packet. --describe-only imports no target owner.
This is for future already-required commands, never a retrospective execution pin.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    "_build.gy-gaps.j.static_rederivations",
    "_build.gy_gaps.d1_strangle",
    "_build.gy_gaps.j_inventory_history",
    "_build.gy_gaps.refresh_m1_snapshot",
    "_build.gy_gaps.refresh_m1_hashes",
    "_build.gy_gaps.phase2_current_corruption",
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def module_source(name: str) -> Path:
    require((name == "_build" or name.startswith("_build."))
            and all(part not in {"", ".", ".."} for part in name.split(".")),
            "module_not_a_scratch_harness")
    base = ROOT.joinpath(*name.split("."))
    candidates = [base.with_suffix(".py"), base / "__init__.py"]
    found = [path for path in candidates if path.is_file()]
    require(len(found) == 1 and found[0].resolve().is_relative_to(ROOT / "_build"),
            "scratch_module_source_unresolved:" + name)
    return found[0]


def sources(module: str) -> dict[str, str]:
    pending, seen = [module, "_build.gy_gaps.j_pinned_harness", "_build.gy_gaps.receipt"], {}
    while pending:
        name = pending.pop()
        path = module_source(name)
        relative = path.relative_to(ROOT).as_posix()
        if relative in seen:
            continue
        raw = path.read_bytes()
        seen[relative] = hashlib.sha256(raw).hexdigest()
        tree = ast.parse(raw, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names if alias.name.startswith("_build."))
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("_build."):
                try:
                    module_source(node.module)
                except ValueError:
                    pending.extend(node.module + "." + alias.name for alias in node.names)
                else:
                    pending.append(node.module)
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == "import_module" and node.args
                  and isinstance(node.args[0], ast.Constant) and type(node.args[0].value) is str
                  and node.args[0].value.startswith("_build.")):
                pending.append(node.args[0].value)
        for parent in path.parents:
            if parent == ROOT:
                break
            initializer = parent / "__init__.py"
            if initializer.is_file():
                package = ".".join(parent.relative_to(ROOT).parts)
                pending.append(package)
    return dict(sorted(seen.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True, choices=sorted(TARGETS))
    parser.add_argument("--describe-only", action="store_true")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    require(Path.cwd().resolve() == ROOT, "run_from_product_root")
    arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    before = sources(args.module)
    if args.describe_only:
        require(sources(args.module) == before, "harness_changed_during_description")
        print(json.dumps({"mode": "source_description_only", "module": args.module,
                          "arguments": arguments, "harness_source_refs": before,
                          "target_executed": False}, sort_keys=True))
        return 0
    spec = importlib.util.find_spec(args.module)
    require(spec is not None and spec.origin is not None
            and Path(spec.origin).resolve() == module_source(args.module).resolve(),
            "executing_module_origin_differs_from_bound_source")
    original_argv = sys.argv
    code, disposition = None, "exception"
    try:
        sys.argv = [str(module_source(args.module)), *arguments]
        try:
            runpy.run_module(args.module, run_name="__main__", alter_sys=True)
        except SystemExit as error:
            code = 0 if error.code is None else error.code if type(error.code) is int else 1
            if error.code is not None and type(error.code) is not int:
                print(error.code, file=sys.stderr)
        else:
            code = 0
        disposition = "returned"
    finally:
        sys.argv = original_argv
        after = sources(args.module)
        delta = {path: {"before": before[path] if path in before else None,
                        "after": after[path] if path in after else None,
                        "before_present": path in before, "after_present": path in after}
                 for path in sorted(before.keys() | after.keys())
                 if path not in before or path not in after or before[path] != after[path]}
        print("GY_J_HARNESS_EXECUTION " + json.dumps({
            "module": args.module, "arguments": arguments, "target_executed": True,
            "harness_source_refs": before, "harness_source_unchanged": before == after,
            "complete_harness_source_delta": delta,
            "target_disposition": disposition, "target_returncode": code,
        }, sort_keys=True), file=sys.stderr, flush=True)
        require(before == after, "executing_harness_changed")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
