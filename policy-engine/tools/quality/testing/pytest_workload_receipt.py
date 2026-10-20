"""Emit the exact path-to-node identity collected by one timed pytest child."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import shlex
import sys
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pluggy
import pytest

from tools.lib.fs import atomic_write_text
from tools.lib.timing import (
    PYTEST_WORKLOAD_PREDICATE_PROVENANCE,
    PYTEST_WORKLOAD_SCHEMA_VERSION,
)
from tools.lib.timing import (
    pytest_node_map_digest as _pytest_node_map_digest,
)

_ATTEMPT_ID_ENV = "POLISYOS_PYTEST_RECEIPT_ATTEMPT_ID"
_OUTPUT_PATH_ENV = "POLISYOS_PYTEST_RECEIPT_SIDECAR"
_OUTPUT_ROOT_ENV = "POLISYOS_PYTEST_RECEIPT_OUTPUT_ROOT"
_PHASES_OUTPUT_PATH_ENV = "POLISYOS_PYTEST_RECEIPT_PHASES_SIDECAR"
_WORKLOAD_RECEIPT_SCHEMA = "policyos.ukraine.c7.workload_receipt.v2"
_REPO_ROOT_ENV = "POLISYOS_PYTEST_RECEIPT_REPO_ROOT"
_TEST_PATHS_ENV = "POLISYOS_PYTEST_RECEIPT_TEST_PATHS"
_CODE_ROOT_ENV = "POLISYOS_PYTEST_RECEIPT_CODE_ROOT"
_COLLECTED_NODE_IDS: tuple[str, ...] | None = None
_PHASE_REPORTS: list[dict[str, str | None]] = []


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_collection_modifyitems(
    items: list[pytest.Item],
) -> Generator[None, object]:
    """Snapshot the collector output before every ordinary selection hook."""

    global _COLLECTED_NODE_IDS  # noqa: PLW0603 - one isolated pytest child owns this plugin.
    _COLLECTED_NODE_IDS = tuple(item.nodeid for item in items)
    yield


def _source_identity(path: Path, workspace_root: Path, code_root: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        return "workspace:" + resolved.relative_to(workspace_root).as_posix()
    except ValueError:
        try:
            return "code:" + resolved.relative_to(code_root).as_posix()
        except ValueError as exc:
            raise ValueError(
                f"pytest plugin source is outside the admitted roots: {resolved}"
            ) from exc


def _plugin_source_digests(session: pytest.Session, workspace_root: Path) -> dict[str, str]:
    """Bind every loaded repository plugin/conftest source; reject ambient plugins."""

    code_root = Path(os.environ[_CODE_ROOT_ENV]).resolve()
    sources: dict[str, str] = {}
    for plugin in session.config.pluginmanager.get_plugins():
        module = plugin if isinstance(plugin, ModuleType) else inspect.getmodule(plugin)
        if module is None:
            continue
        module_name = getattr(module, "__name__", "")
        if module_name == "pytest" or module_name.startswith(("_pytest.", "pluggy.")):
            continue
        source_name = getattr(module, "__file__", None)
        if not isinstance(source_name, str):
            raise ValueError(
                f"unlocated pytest plugin is outside the admitted profile: {module_name}"
            )
        source_path = Path(source_name)
        if source_path.suffix != ".py":
            raise ValueError(
                f"non-source pytest plugin is outside the admitted profile: {module_name}"
            )
        identity = _source_identity(source_path, workspace_root, code_root)
        sources[identity] = _sha256(source_path.resolve(strict=True).read_bytes())
    receipt_plugin = Path(__file__).resolve(strict=True)
    sources[_source_identity(receipt_plugin, workspace_root, code_root)] = _sha256(
        receipt_plugin.read_bytes()
    )
    return dict(sorted(sources.items()))


def _is_collection_hook(hook_name: str) -> bool:
    return (
        "collect" in hook_name
        or hook_name.startswith("pytest_collection")
        or hook_name in {"pytest_generate_tests", "pytest_itemcollected"}
    )


def _validate_collection_hook_surface(session: pytest.Session) -> None:
    """Reject unadmitted collectors and collection wrappers before admitting a node set."""

    plugin_manager = session.config.pluginmanager
    own_name = plugin_manager.get_name(sys.modules[__name__])
    for hook_name in dir(plugin_manager.hook):
        if not hook_name.startswith("pytest_") or not _is_collection_hook(hook_name):
            continue
        hook = getattr(plugin_manager.hook, hook_name)
        for implementation in hook.get_hookimpls():
            if implementation.plugin_name == own_name:
                continue
            wrapper = bool(
                getattr(implementation, "hookwrapper", False)
                or getattr(implementation, "wrapper", False)
            )
            module_name = getattr(implementation.function, "__module__", "")
            is_core = module_name == "pytest" or module_name.startswith(("_pytest.", "pluggy."))
            if hook_name == "pytest_collection_modifyitems":
                if wrapper and not is_core:
                    raise ValueError(
                        "pytest collection admission rejects a non-core modifyitems wrapper: "
                        f"{implementation.plugin_name} ({module_name})"
                    )
                continue
            if is_core:
                continue
            raise ValueError(
                "pytest collection admission rejects non-core collector hook "
                f"{hook_name} from {module_name}"
            )


def _collection_context(session: pytest.Session, workspace_root: Path) -> dict[str, object]:
    """Return the source-bound, sanitized collection profile used for this C7 run."""

    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") != "1":
        raise ValueError("pytest plugin autoload is not disabled for the C7 collection profile")
    if os.environ.get("PYTEST_PLUGINS"):
        raise ValueError("ambient PYTEST_PLUGINS was not sanitized")
    raw_addopts = os.environ.get("PYTEST_ADDOPTS", "")
    try:
        addopts = shlex.split(raw_addopts)
    except ValueError as exc:
        raise ValueError("ambient PYTEST_ADDOPTS is malformed") from exc
    if any(not option.startswith("--junitxml=") for option in addopts) or len(addopts) > 1:
        raise ValueError("ambient PYTEST_ADDOPTS is outside the JUnit-only profile")
    _validate_collection_hook_surface(session)
    option = session.config.option
    return {
        "profile": "policyos.ukraine.c7.collection.v1",
        "plugin_autoload": "disabled",
        "pluggy_version": pluggy.__version__,
        "ambient_controls": "sanitized",
        "hook_capture": "before_collection_modifyitems",
        "pytest_arguments": [str(argument) for argument in session.config.invocation_params.args],
        "approved_pytest_addopts": addopts,
        "repo_plugin_source_digests": _plugin_source_digests(session, workspace_root),
        "keyword_expression": str(getattr(option, "keyword", "") or ""),
        "mark_expression": str(getattr(option, "markexpr", "") or ""),
        "collect_only": bool(getattr(option, "collectonly", False)),
        "deselected_node_ids": [str(item) for item in (getattr(option, "deselect", None) or ())],
        "ignored_paths": [str(item) for item in (getattr(option, "ignore", None) or ())],
    }


def pytest_collection_finish(session: pytest.Session) -> None:
    """Persist the exact nodes pytest retained for execution in this child."""

    repo_root = Path(os.environ[_REPO_ROOT_ENV]).resolve()
    output_path = Path(os.environ[_OUTPUT_PATH_ENV]).resolve()
    output_root = Path(os.environ.get(_OUTPUT_ROOT_ENV, repo_root)).resolve(strict=True)
    output_path.relative_to(output_root)
    selected = json.loads(os.environ[_TEST_PATHS_ENV])
    if (
        not isinstance(selected, list)
        or not selected
        or any(not isinstance(path, str) for path in selected)
        or len(selected) != len(set(selected))
    ):
        raise ValueError("timed pytest receipt requires unique selected test paths")

    selected_by_absolute = {(repo_root / path).resolve(): path for path in selected}
    node_ids_by_path: dict[str, list[str]] = {path: [] for path in selected}
    unmatched_node_ids: list[str] = []
    final_node_ids = tuple(item.nodeid for item in session.items)
    if _COLLECTED_NODE_IDS is None or final_node_ids != _COLLECTED_NODE_IDS:
        raise ValueError("pytest receipt selection changed the complete collected workload")
    for item in session.items:
        selected_path = selected_by_absolute.get(Path(str(item.path)).resolve())
        if selected_path is None:
            unmatched_node_ids.append(item.nodeid)
            continue
        node_ids_by_path[selected_path].append(item.nodeid)
    if unmatched_node_ids:
        raise ValueError(
            "pytest receipt collected nodes outside the selected paths:" + repr(unmatched_node_ids)
        )
    if any(not node_ids for node_ids in node_ids_by_path.values()):
        raise ValueError("timed pytest receipt collected no nodes for a selected path")
    if sum(len(node_ids) for node_ids in node_ids_by_path.values()) != len(session.items):
        raise ValueError("pytest receipt node map does not cover the executed session")

    config_source = session.config.inipath
    if config_source is None:
        raise ValueError("timed pytest receipt requires an explicit pytest config")
    config_path = config_source.resolve().relative_to(repo_root).as_posix()
    source_digests = {path: _sha256((repo_root / path).read_bytes()) for path in selected}
    workload_identity = {
        "schema_version": PYTEST_WORKLOAD_SCHEMA_VERSION,
        "predicate_provenance": PYTEST_WORKLOAD_PREDICATE_PROVENANCE,
        "test_paths": selected,
        "source_digests": source_digests,
        "pytest_version": pytest.__version__,
        "config_path": config_path,
        "config_digest": _sha256(config_source.read_bytes()),
        "node_map_digest": _pytest_node_map_digest(node_ids_by_path),
    }
    collection_context = _collection_context(session, repo_root)
    payload = {
        "schema_version": _WORKLOAD_RECEIPT_SCHEMA,
        "attempt_id": os.environ[_ATTEMPT_ID_ENV],
        "node_ids_by_path": node_ids_by_path,
        "workload_identity": workload_identity,
        "collection_context": collection_context,
    }
    atomic_write_text(
        output_path,
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    )


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Retain every setup, call, and teardown outcome when explicitly requested."""

    if _PHASES_OUTPUT_PATH_ENV not in os.environ:
        return
    was_xfail = report.outcome == "passed" and getattr(report, "wasxfail", None) is not None
    outcome = "xpassed" if was_xfail else report.outcome
    reason: str | None = None
    if outcome in {"failed", "skipped"}:
        reason_text = getattr(report, "longreprtext", "")
        reason = str(reason_text).strip()[:2000] or f"pytest reported {outcome} without detail"
    elif outcome == "xpassed":
        reason = str(getattr(report, "wasxfail", "unexpected xpass")).strip()[:2000]
    _PHASE_REPORTS.append(
        {
            "node_id": report.nodeid,
            "when": report.when,
            "outcome": outcome,
            "reason": reason,
        }
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Persist same-child phase outcomes, including an empty collect-only receipt."""

    del session
    phases_output = os.environ.get(_PHASES_OUTPUT_PATH_ENV)
    if not phases_output:
        return
    repo_root = Path(os.environ[_REPO_ROOT_ENV]).resolve()
    output_root = Path(os.environ.get(_OUTPUT_ROOT_ENV, repo_root)).resolve(strict=True)
    phases_path = Path(phases_output).resolve()
    phases_path.relative_to(output_root)
    workload_path = Path(os.environ[_OUTPUT_PATH_ENV]).resolve()
    workload_path.relative_to(output_root)
    if not workload_path.is_file():
        return
    workload_bytes = workload_path.read_bytes()
    payload = {
        "schema_version": "policyos.timing.pytest_case_phases.v2",
        "attempt_id": os.environ[_ATTEMPT_ID_ENV],
        "workload_receipt_sha256": _sha256(workload_bytes),
        "pytest_exit_status": int(exitstatus),
        "phase_reports": _PHASE_REPORTS,
    }
    atomic_write_text(
        phases_path,
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    )
