"""Observe an E02 pytest child without modifying tests or pytest reports."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

_root = Path(os.environ["E02_OBSERVER_DIR"])
_out = _root / str(os.getpid())
_out.mkdir(parents=True, exist_ok=False)


def _save(name: str, value: object) -> None:
    (_out / name).write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def _event(kind: str, **fields: object) -> None:
    row = {"kind": kind, "pid": os.getpid(), "monotonic_ns": time.monotonic_ns(), **fields}
    with (_out / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


_control_names = (
    "POLISYOS_R1_REMOVE_V3_ARTIFACTID_SCALAR",
    "POLISYOS_R6_FOREIGN_CONTEXT_IDENTITY_REMOVAL",
    "POLISYOS_R7_REMOVE_ACTIVE_PROBE_SUPPRESSION",
)
_save("process.json", {"pid": os.getpid(), "ppid": os.getppid(), "argv": sys.argv,
                       "property_controls": {key: os.environ.get(key) for key in _control_names}})


def pytest_collection_finish(session: pytest.Session) -> None:
    """Record the final selected nodes in this process."""
    _save("collection.json", {
        "pid": os.getpid(),
        "nodes": [{"id": item.nodeid, "path": str(item.path)} for item in session.items],
        "config": str(session.config.inipath),
        "collect_only": bool(session.config.option.collectonly),
    })


def pytest_collectreport(report: pytest.CollectReport) -> None:
    """Preserve collection failure and module-level skip details."""
    if report.outcome != "passed":
        _event("collection_report", nodeid=report.nodeid, outcome=report.outcome,
               longrepr=str(report.longrepr))


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Keep each setup, call and teardown report separately."""
    _event("test_report", nodeid=report.nodeid, phase=report.when,
           outcome=report.outcome, duration_seconds=report.duration,
           wasxfail=getattr(report, "wasxfail", None),
           longrepr=str(report.longrepr) if report.longrepr is not None else None)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    """Snapshot loaded owned modules, without importing additional modules."""
    modules = []
    files = {}
    for name, module in sorted(sys.modules.items()):
        if name.split(".")[0] not in {"polisyos", "tools", "tests"}:
            continue
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        key = str(path)
        if key not in files:
            try:
                files[key] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            except OSError as exc:
                files[key] = {"read_error": type(exc).__name__}
        modules.append({"module": name, "origin": str(origin), "resolved": key})
    _save("origins.json", {"pid": os.getpid(), "scope": "session_finish_snapshot",
                           "modules": modules, "files": files})
    _save("session.json", {"pid": os.getpid(), "exitstatus": int(exitstatus),
                           "collected": int(session.testscollected),
                           "config": str(session.config.inipath)})
