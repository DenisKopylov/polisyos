"""Observe actual worker receipts during the unchanged runtime API contract gate.

No product import occurs until runpy executes the real module. Each subprocess
call is delegated once with the original arguments and its result is returned
unchanged. Complete worker transport is emitted once on stderr; gate stdout and
exit behavior remain the owner's. This observer does not invoke extra workers.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys

TARGET = "tools.ops_runners.runtime.check_runtime_api_contract"
INVOKER = "src/polisyos/runtime/http/services/governed_projections.py"
TRACKER = "src/polisyos/runtime/http/services/governed_projection_dependencies.py"
CHECKER = "tools/ops_runners/runtime/check_runtime_api_contract.py"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def emit(kind: str, value: object) -> None:
    print("GY_OPENAPI_OBSERVER_" + kind + " " + json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False,
    ), file=sys.stderr, flush=True)


def source_pins(paths: list[Path]) -> dict[str, str]:
    return {str(path): sha(path.read_bytes()) for path in paths}


def transport(value: str | bytes | None) -> object:
    """Preserve a text result or losslessly retain partial timeout bytes."""
    if isinstance(value, bytes):
        return {"encoding": "base64", "raw_bytes": base64.b64encode(value).decode("ascii")}
    return value


def worker_target(root: Path) -> Path:
    """Derive the actual worker entry from the unchanged invoker's assignment."""
    source = (root / INVOKER).read_text(encoding="utf-8")
    names = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "worker_path"
            for target in node.targets
        ):
            continue
        call = node.value
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and ast.unparse(call.func.value) == "Path(__file__)"
                and call.func.attr == "with_name" and len(call.args) == 1
                and not call.keywords):
            names.append(ast.literal_eval(call.args[0]))
    independent = re.findall(
        r'worker_path\s*=\s*Path\(__file__\)\.with_name\("([^"\n]+)"\)', source,
    )
    if len(names) != 1 or names != independent or Path(names[0]).name != names[0]:
        raise ValueError("actual_worker_entry_not_uniquely_reconciled")
    target = (root / INVOKER).with_name(names[0])
    if not target.is_file():
        raise ValueError("actual_worker_entry_missing")
    return target


def command_value(args: tuple, kwargs: dict) -> object:
    value = args[0] if args else kwargs["args"]
    if isinstance(value, (list, tuple)):
        return [os.fsdecode(part) for part in value]
    return os.fsdecode(value)


def main() -> None:
    root = Path.cwd().resolve()
    if root.name != "policy-engine" or not (root / "pyproject.toml").is_file():
        raise ValueError("invoke_from_actual_product_root")
    worker = worker_target(root)
    paths = [Path(__file__).resolve(), root / "_build/gy_gaps/receipt.py",
             root / INVOKER, root / TRACKER, root / CHECKER, worker]
    before = source_pins(paths)
    original_run, original_argv = subprocess.run, sys.argv
    observed: list[dict] = []
    worker_call_indices: list[int] = []
    gate_exit: object = None
    gate_exception: str | None = None

    def observe_run(*args, **kwargs):
        argv = command_value(args, kwargs)
        index = len(observed)
        cwd = os.fsdecode(kwargs.get("cwd", Path.cwd()))
        is_worker = (isinstance(argv, list) and len(argv) > 1
                     and Path(argv[1]).absolute() == worker)
        call = {"index": index, "argv": argv, "cwd": cwd,
                "actual_governed_worker": is_worker}
        observed.append(call)
        projection_id = None
        if is_worker:
            worker_call_indices.append(index)
            try:
                request = json.loads(kwargs["input"])
                projection_id = request["projection_id"]
            except (KeyError, TypeError, ValueError):
                projection_id = "unreadable_actual_request"
        try:
            result = original_run(*args, **kwargs)
        except BaseException as error:
            call["exception_type"] = type(error).__name__
            if is_worker:
                emit("WORKER_NONRECEIPT", {**call, "projection_id": projection_id,
                    "error": str(error),
                    "stdout": transport(getattr(error, "stdout", None)),
                    "stderr": transport(getattr(error, "stderr", None))})
            raise
        call["returncode"] = result.returncode
        if is_worker:
            emit("WORKER_RECEIPT", {**call, "projection_id": projection_id,
                "stdout": result.stdout, "stderr": result.stderr,
                "stdout_utf8_sha256": sha(result.stdout.encode("utf-8")),
                "stderr_utf8_sha256": sha(result.stderr.encode("utf-8"))})
        return result

    emit("START", {"target_module": TARGET, "target_argv": sys.argv[1:],
        "actual_worker_entry": str(worker), "source_pins_before": before,
        "mode": "delegate_once_observe_only_no_additional_worker"})
    subprocess.run = observe_run
    sys.argv = [TARGET, *original_argv[1:]]
    try:
        runpy.run_module(TARGET, run_name="__main__", alter_sys=True)
        gate_exit = 0
    except SystemExit as error:
        gate_exit = 0 if error.code is None else error.code
        raise
    except BaseException as error:
        gate_exception = type(error).__name__
        raise
    finally:
        subprocess.run, sys.argv = original_run, original_argv
        after = source_pins(paths)
        emit("READBACK", {"target_module": TARGET, "gate_exit_code": gate_exit,
            "gate_exception_type": gate_exception, "source_pins_after": after,
            "source_bytes_unchanged": before == after,
            "complete_observed_subprocess_calls": observed,
            "actual_worker_call_indices": worker_call_indices,
            "worker_observed": bool(worker_call_indices),
            "gate_stdout_redirected": False, "worker_result_or_arguments_changed": False})


if __name__ == "__main__":
    main()
