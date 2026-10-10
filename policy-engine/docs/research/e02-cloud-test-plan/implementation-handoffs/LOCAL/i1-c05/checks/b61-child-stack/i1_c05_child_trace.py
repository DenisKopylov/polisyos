"""One-run, child-only stack capture for the B61 timed replay diagnostic."""

from __future__ import annotations

import faulthandler
import hashlib
import json
import multiprocessing as mp
import os
import platform
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


_OUT = Path(os.environ["I1_C05_DIAG_DIR"])
_STACK = _OUT / "child-stack.txt"
_META = _OUT / "runtime-input.jsonl"
_REPO = Path(os.environ["I1_C05_REPO"])
_HASH_PATHS = (
    _REPO / "src/polisyos/scientist/orchestration/engine/retry.py",
    _REPO / "src/polisyos/scientist/orchestration/engine/runner/_activity_worker.py",
    _REPO / "src/polisyos/scientist/orchestration/engine/runner/serialization.py",
    _REPO / "tests/unit/scientist/orchestration/engine/test_skg_snapshot_replay.py",
)


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _append(record: dict[str, object]) -> None:
    with _META.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, default=repr) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _state_inputs(state: object) -> dict[str, object]:
    inputs = getattr(state, "inputs", {})
    if not isinstance(inputs, dict):
        return {"type": type(inputs).__qualname__, "repr": repr(inputs)}
    result: dict[str, object] = {}
    for key, value in inputs.items():
        if hasattr(value, "model_dump"):
            try:
                value = value.model_dump(mode="json")
            except (TypeError, ValueError):
                value = repr(value)
        result[str(key)] = value
    return result


def _wrap_supervisor(original: Callable[..., object]) -> Callable[..., object]:
    def child_entry(*args: object, **kwargs: object) -> object:
        node = args[0] if args else None
        state = args[2] if len(args) > 2 else None
        params = getattr(state, "params", {})
        source = params.get("skg_db_path") if isinstance(params, dict) else None
        source_path = Path(source) if isinstance(source, str) else None
        process = mp.current_process()
        _append(
            {
                "event": "child_entry",
                "pid": os.getpid(),
                "ppid": os.getppid(),
                "process_name": process.name,
                "process_start_method": getattr(process, "_start_method", None),
                "multiprocessing_default": mp.get_start_method(),
                "supported_start_methods": mp.get_all_start_methods(),
                "python": sys.version,
                "executable": sys.executable,
                "platform": platform.platform(),
                "python_threads": [thread.name for thread in threading.enumerate()],
                "node_type": f"{type(node).__module__}.{type(node).__qualname__}",
                "state_run_id": getattr(state, "run_id", None),
                "state_inputs": _state_inputs(state),
                "source_path": str(source_path) if source_path is not None else None,
                "source_sha256": _sha256(source_path) if source_path is not None else None,
            }
        )
        with _STACK.open("a", encoding="utf-8", buffering=1) as stack_file:
            stack_file.write(
                f"child_entry pid={os.getpid()} ppid={os.getppid()} "
                f"process_start_method={getattr(process, '_start_method', None)}\n"
            )
            stack_file.flush()
            faulthandler.dump_traceback_later(3.0, repeat=True, file=stack_file)
            try:
                return original(*args, **kwargs)
            finally:
                faulthandler.cancel_dump_traceback_later()
                stack_file.write(f"child_exit pid={os.getpid()}\n")
                stack_file.flush()

    return child_entry


def pytest_configure(config: object) -> None:
    """Record parent runtime metadata without instrumenting its stacks."""
    _append(
        {
            "event": "parent_runtime",
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "multiprocessing_default": mp.get_start_method(),
            "supported_start_methods": mp.get_all_start_methods(),
            "python_threads": [thread.name for thread in threading.enumerate()],
            "source_sha256": {str(path.relative_to(_REPO)): _sha256(path) for path in _HASH_PATHS},
        }
    )


def pytest_collection_modifyitems(session: object, config: object, items: list[object]) -> None:
    """Wrap only the actual child process target before the selected test runs."""
    from polisyos.scientist.orchestration.engine import retry

    retry._node_execute_supervisor = _wrap_supervisor(retry._node_execute_supervisor)
