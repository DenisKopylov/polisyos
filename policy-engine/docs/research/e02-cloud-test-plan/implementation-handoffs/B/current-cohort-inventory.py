"""Observe a real pytest invocation without selecting tests or changing outcomes.

Copy these exact bytes to an ignored tools directory as ``current_cohort_inventory.py``
and load them with ``-p current_cohort_inventory``. Set only the explicit output setting
``E02_B_COHORT_INVENTORY_PATH`` to a fresh absolute Git-ignored path. The collection
checkpoint is persisted before execution; the final snapshot accompanies full stdout
and JUnit. This is observation, not a test, finding-closure gate, or import read-set audit.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Protocol

import pytest
from _pytest.skipping import xfailed_key

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence
    from typing import BinaryIO

type Record = dict[str, Any]

_SOURCE_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
    "current-cohort-inventory.py"
)
_ACTIVE: _Inventory | None = None


class _Gateway(Protocol):
    id: str


class _WorkerNode(Protocol):
    gateway: _Gateway


def _git(cwd: Path, *args: str) -> tuple[bytes, Record]:
    executable = shutil.which("git")
    if executable is None:
        return b"", {"args": list(args), "state": "unreadable_git_unavailable"}
    try:
        result = subprocess.run(  # noqa: S603 - argv-only read-only Git operations
            [executable, "-C", str(cwd), *args], capture_output=True, check=False
        )
    except OSError as exc:
        return b"", {"args": list(args), "state": "unreadable", "error_type": type(exc).__name__}
    receipt = {
        "args": list(args),
        "returncode": result.returncode,
        "stdout_bytes": len(result.stdout),
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_bytes": len(result.stderr),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
    }
    return result.stdout, receipt


def _snapshot(repo: Path) -> Record:
    result: Record = {"repo": str(repo), "read_operations": []}
    for key, args in (
        ("head", ("rev-parse", "HEAD")),
        ("tree", ("rev-parse", "HEAD^{tree}")),
        ("branch", ("symbolic-ref", "-q", "HEAD")),
        ("object_format", ("rev-parse", "--show-object-format")),
        ("tracked_status", ("status", "--porcelain=v1", "--untracked-files=no")),
    ):
        raw, receipt = _git(repo, *args)
        result["read_operations"].append(receipt)
        result[key] = (
            raw.decode("utf-8", errors="replace").strip()
            if receipt.get("returncode") == 0
            else None
        )
    return result


def _file_identity(path: Path, object_format: str) -> Record:
    """Hash observed file bytes, retaining unreadability and changing-file ambiguity."""
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            sha256 = hashlib.sha256()
            blob = hashlib.new(object_format, usedforsecurity=False)
            blob.update(f"blob {before.st_size}\0".encode())
            byte_count = 0
            while chunk := stream.read(1024 * 1024):
                byte_count += len(chunk)
                sha256.update(chunk)
                blob.update(chunk)
            after = os.fstat(stream.fileno())
        stable = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) and byte_count == before.st_size
        return {
            "state": "read" if stable else "read_changed_during_measurement",
            "bytes_read": byte_count,
            "sha256": sha256.hexdigest(),
            "git_blob_oid_from_observed_bytes": blob.hexdigest(),
            "stable_during_read": stable,
        }
    except (OSError, ValueError) as exc:
        return {
            "state": "unreadable",
            "error_type": type(exc).__name__,
            "errno": getattr(exc, "errno", None),
        }


def _item(item: pytest.Item) -> Record:
    return {
        "nodeid": item.nodeid,
        "path": str(item.path),
        "location": list(item.location),
        "originalname": getattr(item, "originalname", None),
        "markers": [mark.name for mark in item.iter_markers()],
        "fixture_names": list(getattr(item, "fixturenames", ())),
        "has_callspec": hasattr(item, "callspec"),
        "parameter_values": "not_serialized; actual parameterization is retained in nodeid",
    }


def _report(report: pytest.CollectReport | pytest.TestReport) -> Record:
    text = report.longreprtext if report.longrepr is not None else ""
    return {
        "nodeid": report.nodeid,
        "outcome": report.outcome,
        "location": list(report.location) if isinstance(report, pytest.TestReport) else None,
        "longrepr_type": type(report.longrepr).__name__,
        "longrepr_utf8_bytes": len(text.encode()),
        "longrepr_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "diagnostic_text": "not_copied; complete diagnostics remain in native stdout/JUnit",
    }


def _number(value: float) -> float | str:
    return value if math.isfinite(value) else str(value)


@dataclass
class _Inventory:
    config: pytest.Config
    repo: Path
    output: Path
    stream: BinaryIO
    started: Record
    worker_id: str | None
    state: str = "configured_collection_pending"
    items: list[Record] = field(default_factory=list)
    collect_reports: list[Record] = field(default_factory=list)
    deselected: list[Record] = field(default_factory=list)
    runtime_reports: list[Record] = field(default_factory=list)
    annotations: dict[int, Record] = field(default_factory=dict)
    worker_collections: list[Record] = field(default_factory=list)
    finished: bool = False

    def persist(self, *, final: Record | None = None) -> None:
        payload: Record = {
            "schema": "policyos.e02.pytest_inventory.v1",
            "state": self.state,
            "predicate_basis": "recomputed_observation_not_finding_admission",
            "pytest_version": pytest.__version__,
            "python_version": sys.version,
            "python_executable": sys.executable,
            "rootpath": str(self.config.rootpath),
            "worker_id": self.worker_id,
            "selectors": list(self.config.args),
            "ini_path": str(self.config.inipath) if self.config.inipath is not None else None,
            "ini_addopts": self.config.getini("addopts"),
            "junit_path": getattr(self.config.option, "xmlpath", None),
            "git_at_start": self.started,
            "session_items_before_execution": self.items,
            "collection_reports": self.collect_reports,
            "deselected_items": self.deselected,
            "runtime_phase_reports": self.runtime_reports,
            "xdist_worker_collection_reports": self.worker_collections,
            "counts": {
                "session_items": len(self.items),
                "collect_reports": len(self.collect_reports),
                "collection_failed": sum(r["outcome"] == "failed" for r in self.collect_reports),
                "collection_skipped": sum(r["outcome"] == "skipped" for r in self.collect_reports),
                "deselected": len(self.deselected),
                "runtime_phase_reports": len(self.runtime_reports),
            },
            "unresolved_by_construction": [
                "No universal import read-set: sys.modules origins are a finish-time snapshot.",
                "File hashes observe backing bytes, not loader reads or in-memory substitutions.",
                "Transient/removed and child modules plus resources/services are unmeasured.",
                "Nodeid/collection presence never proves PASS, property adequacy or closure.",
                "Abrupt death may leave only the pre-execution checkpoint or a partial JSON write.",
                "Environment values, mark/parameter arguments, locals and streams are omitted.",
                "Diagnostic text is hash-bound here; full native stdout/JUnit remains separate.",
                "Pytest9 evaluated-xfail stash is an explicit version-bound diagnostic dependency.",
                "xdist worker artifacts are separate; controller modules do not cover workers.",
            ],
        }
        if final is not None:
            payload.update(final)
        data = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
        self.stream.seek(0)
        self.stream.write(data)
        self.stream.truncate()
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def module_origins(self) -> Record:
        sha = self.started.get("head")
        object_format = self.started.get("object_format")
        tracked: dict[str, str] = {}
        operations = []
        if isinstance(sha, str):
            raw, receipt = _git(self.repo, "ls-tree", "-rz", "--full-tree", sha)
            operations.append(receipt)
            if receipt.get("returncode") == 0:
                for entry in raw.split(b"\0"):
                    if not entry:
                        continue
                    info, raw_name = entry.split(b"\t", 1)
                    _, kind, oid = info.split(b" ", 2)
                    if kind == b"blob":
                        tracked[os.fsdecode(raw_name)] = oid.decode("ascii")
        modules = []
        files: dict[str, Record] = {}
        stdlib = Path(sysconfig.get_path("stdlib")).resolve()
        sites = [Path(sysconfig.get_path(key)).resolve() for key in ("purelib", "platlib")]
        module_snapshot = sys.modules.copy()
        for name, module in sorted(module_snapshot.items()):
            if not isinstance(module, ModuleType):
                modules.append(
                    {
                        "module": name,
                        "state": "non_module_entry",
                        "entry_type": type(module).__name__,
                    }
                )
                continue
            attributes = vars(module)
            spec = attributes.get("__spec__")
            origin = getattr(spec, "origin", None)
            declared = attributes.get("__file__")
            if (
                not isinstance(declared, str)
                and isinstance(origin, str)
                and origin not in {"built-in", "frozen"}
            ):
                declared = origin
            row: Record = {
                "module": name,
                "spec_origin": origin if isinstance(origin, str) else None,
            }
            if not isinstance(declared, str):
                row.update(state="fileless_module", file_identity=None)
                modules.append(row)
                continue
            try:
                path = Path(declared).resolve()
            except (OSError, RuntimeError) as exc:
                row.update(state="unresolved_origin_path", error_type=type(exc).__name__)
                modules.append(row)
                continue
            key = str(path)
            row.update(state="file_backed_module", declared_file=declared, file_identity=key)
            modules.append(row)
            if key in files:
                continue
            relative = (
                path.relative_to(self.repo).as_posix() if path.is_relative_to(self.repo) else None
            )
            expected = tracked.get(relative) if relative is not None else None
            if object_format in {"sha1", "sha256"}:
                measured = _file_identity(path, object_format)
            else:
                measured = {"state": "unreadable_git_object_format", "object_format": object_format}
            if relative is not None:
                scope = (
                    "repository_tracked_file"
                    if expected is not None
                    else "repository_untracked_or_ignored_file"
                )
            elif any(path.is_relative_to(site) for site in sites):
                scope = "external_installed_package_file"
            else:
                scope = "standard_library_file" if path.is_relative_to(stdlib) else "external_file"
            files[key] = {
                "path": key,
                "scope": scope,
                "backend": "extension_module_file"
                if path.suffix in {".so", ".pyd", ".dylib"}
                else "file_backed_loader_origin",
                "repository_path": relative,
                "expected_git_blob_oid": expected,
                "source_git_byte_match": (
                    measured["git_blob_oid_from_observed_bytes"] == expected
                    if expected is not None and measured.get("stable_during_read")
                    else None
                ),
                "actual_read": measured,
            }
        loaded_identity = _file_identity(Path(__file__).resolve(), object_format or "sha1")
        expected_instrument = tracked.get(_SOURCE_PATH)
        return {
            "observed_modules": modules,
            "observed_file_backends": list(files.values()),
            "module_entry_denominator": len(modules),
            "distinct_file_backend_denominator": len(files),
            "git_tree_read_operations": operations,
            "tracked_instrument_source_path": _SOURCE_PATH,
            "tracked_instrument_blob_oid": expected_instrument,
            "loaded_instrument_file": str(Path(__file__).resolve()),
            "loaded_instrument_identity": loaded_identity,
            "loaded_instrument_source_git_byte_match": (
                loaded_identity.get("git_blob_oid_from_observed_bytes") == expected_instrument
                if expected_instrument is not None and loaded_identity.get("stable_during_read")
                else None
            ),
            "resource_boundary": (
                "Fixture/data/resource/backend/service reads are unmeasured, never an empty set."
            ),
        }


def pytest_configure(config: pytest.Config) -> None:
    """Reserve an exclusive ignored artifact before pytest collects any items."""
    global _ACTIVE
    setting = os.environ.get("E02_B_COHORT_INVENTORY_PATH")
    if setting is None or not Path(setting).is_absolute():
        raise pytest.UsageError("E02_B_COHORT_INVENTORY_PATH must be a fresh absolute ignored path")
    repo_raw, receipt = _git(config.rootpath, "rev-parse", "--show-toplevel")
    if receipt.get("returncode") != 0:
        raise pytest.UsageError("Cohort inventory requires a readable Git worktree")
    repo = Path(os.fsdecode(repo_raw).strip()).resolve()
    output = Path(setting).resolve()
    workerinput = getattr(config, "workerinput", None)
    worker_id = workerinput.get("workerid") if isinstance(workerinput, dict) else None
    if isinstance(worker_id, str):
        if not worker_id or not all(c.isalnum() or c in "_-" for c in worker_id):
            raise pytest.UsageError("Invalid pytest worker identity for exclusive inventory output")
        output = output.with_name(output.name + "." + worker_id + ".json")
    else:
        worker_id = None
    _, ignored = _git(repo, "check-ignore", "--quiet", "--no-index", "--", str(output))
    if not output.is_relative_to(repo) or ignored.get("returncode") != 0:
        raise pytest.UsageError("Cohort inventory output must be inside actual Git-ignored storage")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as exc:
        raise pytest.UsageError("Cohort inventory output could not be exclusively created") from exc
    started = _snapshot(repo)
    started["read_operations"].extend([receipt, ignored])
    _ACTIVE = _Inventory(config, repo, output, os.fdopen(descriptor, "wb"), started, worker_id)
    _ACTIVE.persist()


def pytest_collectreport(report: pytest.CollectReport) -> None:
    """Retain every actual collector outcome, including errors and module skips."""
    if _ACTIVE is not None:
        _ACTIVE.collect_reports.append(
            {**_report(report), "result_nodeids": [n.nodeid for n in report.result]}
        )


def pytest_deselected(items: Sequence[pytest.Item]) -> None:
    """Record each actual deselection without changing selection."""
    if _ACTIVE is not None:
        _ACTIVE.deselected.extend(_item(item) for item in items)


@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session: pytest.Session) -> None:
    """Persist the complete post-selection item set before runtime starts."""
    if _ACTIVE is not None:
        _ACTIVE.items = [_item(item) for item in session.items]
        _ACTIVE.state = "collection_finished_runtime_pending"
        _ACTIVE.persist()


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Observe evaluated xfail semantics after pytest produces its final report."""
    report = yield
    if _ACTIVE is not None:
        evaluated = item.stash.get(xfailed_key, None)
        wasxfail = getattr(report, "wasxfail", None)
        classification: str = report.outcome
        if isinstance(wasxfail, str):
            classification = (
                "xfail" if report.skipped else "xpass" if report.passed else report.outcome
            )
        elif (
            call.when == "call"
            and call.excinfo is None
            and report.failed
            and evaluated is not None
            and evaluated.strict
            and not item.config.getoption("runxfail")
        ):
            classification = "strict_xpass"
        _ACTIVE.annotations[id(report)] = {
            "classification": classification,
            "has_wasxfail": isinstance(wasxfail, str),
            "evaluated_xfail": evaluated is not None,
            "evaluated_xfail_strict": evaluated.strict if evaluated is not None else None,
            "call_had_exception": call.excinfo is not None,
        }
    return report


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record every observed setup/call/teardown phase without altering it."""
    if _ACTIVE is not None:
        annotation = _ACTIVE.annotations.pop(id(report), {})
        _ACTIVE.runtime_reports.append(
            {
                **_report(report),
                "when": report.when,
                "duration": _number(report.duration),
                "start": _number(report.start),
                "stop": _number(report.stop),
                **annotation,
            }
        )


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_node_collection_finished(node: _WorkerNode, ids: list[str]) -> None:
    """Retain worker-provided actual nodeids when xdist is chosen by the caller."""
    if _ACTIVE is not None:
        _ACTIVE.worker_collections.append({"worker": node.gateway.id, "nodeids": list(ids)})
        _ACTIVE.persist()


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    """Persist actual exit/outcomes and current-process file-origin identities."""
    if _ACTIVE is not None:
        _ACTIVE.state = "session_finished"
        origins = _ACTIVE.module_origins()
        _ACTIVE.persist(
            final={
                "session_exitstatus": int(exitstatus),
                "session_testscollected": session.testscollected,
                "session_testsfailed": session.testsfailed,
                "git_at_finish": _snapshot(_ACTIVE.repo),
                "module_origin_snapshot": origins,
            }
        )
        _ACTIVE.finished = True


def pytest_unconfigure(config: pytest.Config) -> None:
    """Close the artifact; preserve an explicit incomplete state after early failure."""
    global _ACTIVE
    if _ACTIVE is not None and _ACTIVE.config is config:
        try:
            if not _ACTIVE.finished:
                _ACTIVE.state = "incomplete_no_sessionfinish"
                _ACTIVE.persist(
                    final={"session_exitstatus": None, "git_at_finish": _snapshot(_ACTIVE.repo)}
                )
        finally:
            _ACTIVE.stream.close()
            _ACTIVE = None
