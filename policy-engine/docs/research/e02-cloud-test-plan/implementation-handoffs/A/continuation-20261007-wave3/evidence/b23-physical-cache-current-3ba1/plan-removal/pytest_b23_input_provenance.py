"""Record runtime source provenance for the bounded B23 removal probe.

Load with ``PYTHONPATH=<this-directory> pytest -p pytest_b23_input_provenance``.
The plugin observes imports and test outcomes; it does not patch application code.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.machinery
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
TARGET_NODE = (
    "tests/unit/remediation/test_sim_03.py::"
    "test_physical_run_identity_binds_seed_and_plan_and_reexecutes_each_request"
)
TARGET_MODULE = "tests.unit.remediation.test_sim_03"
HELPER_MODULE = "tests.unit.runtime.quality.test_joint_simulation_horizon"
GENERATION_TEST_MODULE = "tests.unit.runtime.quality.test_generation_cycle"
REMOVAL_ENV = "POLISYOS_SIM03_PHYSICAL_IDENTITY_REMOVAL_PROBE"
OUTPUT_ENV = "POLISYOS_B23_INPUT_PROVENANCE_OUTPUT"

# These are the direct test/helper inputs and source owners on the NCM selection,
# registry, coupling, and physical-run paths. The loaded-module inventory below
# supplements this short set without serializing a repository-wide import dump.
PINNED_INPUT_PATHS = {
    "target_test": "policy-engine/tests/unit/remediation/test_sim_03.py",
    "test_fixture_helper": (
        "policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py"
    ),
    "joint_simulation_controller": (
        "policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py"
    ),
    "ncm_engine": (
        "policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py"
    ),
    "causal_registration": (
        "policy-engine/src/polisyos/foundry/methods/catalog/causal/__init__.py"
    ),
    "causal_protocols": (
        "policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py"
    ),
    "method_registry": (
        "policy-engine/src/polisyos/foundry/methods/selection/registry.py"
    ),
    "coupling_composition": (
        "policy-engine/src/polisyos/runtime/quality/design_axes/coupling_composition.py"
    ),
    "world_model_binding": (
        "policy-engine/src/polisyos/runtime/quality/world_model_record.py"
    ),
    "intervention_atom_binding": (
        "policy-engine/src/polisyos/runtime/quality/intervention_atom_binding.py"
    ),
    "smm_test_import": "policy-engine/src/polisyos/foundry/coupling/estimation.py",
}
CONTEXT_OBSERVER_PATHS = {
    "generation_cycle_test_context_only": (
        "policy-engine/tests/unit/runtime/quality/test_generation_cycle.py"
    ),
}

LOADED_MODULE_PREFIXES = (
    "polisyos.runtime.quality",
    "polisyos.foundry.methods.catalog.causal",
    "polisyos.foundry.methods.selection",
    "polisyos.runtime.quality.design_axes",
    "polisyos.foundry.coupling",
    "tests.unit.runtime.quality.test_generation_cycle",
)
MAX_LOADED_MODULE_ORIGINS = 80


def _git(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(REPOSITORY_ROOT), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def _head() -> str | None:
    return _git("rev-parse", "HEAD")


def _resolved(path: str | os.PathLike[str] | None) -> Path | None:
    if not path:
        return None
    try:
        candidate = Path(path)
        if not candidate.is_absolute():
            repository_candidate = REPOSITORY_ROOT / candidate
            if repository_candidate.exists():
                candidate = repository_candidate
        return candidate.resolve()
    except (OSError, RuntimeError):
        return None


def _relative_to_repo(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return None


def _source_file_record(relative_path: str, source_commit: str | None) -> dict[str, Any]:
    absolute = REPOSITORY_ROOT / relative_path
    try:
        payload = absolute.read_bytes()
    except OSError as exc:
        return {
            "repository_path": relative_path,
            "absolute_path": str(absolute),
            "read_error": f"{type(exc).__name__}: {exc}",
        }

    source_blob = None
    if source_commit:
        source_blob = _git("rev-parse", f"{source_commit}:{relative_path}")
    return {
        "repository_path": relative_path,
        "absolute_path": str(absolute.resolve()),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "working_tree_git_blob": _git("hash-object", "--", relative_path),
        "source_commit_git_blob": source_blob,
        "working_tree_matches_source_commit": bool(
            source_blob and _git("hash-object", "--", relative_path) == source_blob
        ),
        "git_status_for_path": _git("status", "--short", "--", relative_path),
    }


def _module_file(module: Any) -> Path | None:
    path = _resolved(getattr(module, "__file__", None))
    if path and path.suffix in {".pyc", ".pyo"}:
        try:
            source = importlib.machinery.SourceFileLoader.get_filename(
                getattr(module, "__name__", ""),
            )
            return _resolved(source)
        except (ImportError, OSError):
            return path
    return path


def _loaded_modules_for_expected_path(expected_path: str) -> list[dict[str, Any]]:
    expected = _resolved(REPOSITORY_ROOT / expected_path)
    found: list[dict[str, Any]] = []
    if expected is None:
        return found
    for module_name, module in sorted(sys.modules.items()):
        loaded_path = _module_file(module)
        if loaded_path != expected:
            continue
        spec = getattr(module, "__spec__", None)
        found.append(
            {
                "module_name": module_name,
                "module_file": str(getattr(module, "__file__", "")),
                "spec_origin": getattr(spec, "origin", None),
                "resolved_source_path": str(loaded_path),
                "repository_path": _relative_to_repo(loaded_path),
            }
        )
    return found


def _loaded_project_module_origins() -> dict[str, Any]:
    records: list[dict[str, str | None]] = []
    for module_name, module in sorted(sys.modules.items()):
        if not any(
            module_name == prefix or module_name.startswith(prefix + ".")
            for prefix in LOADED_MODULE_PREFIXES
        ):
            continue
        origin = _module_file(module)
        if origin is None:
            continue
        records.append(
            {
                "module_name": module_name,
                "module_file": str(getattr(module, "__file__", "")),
                "spec_origin": getattr(getattr(module, "__spec__", None), "origin", None),
                "repository_path": _relative_to_repo(origin),
            }
        )
    truncated = max(0, len(records) - MAX_LOADED_MODULE_ORIGINS)
    return {
        "modules": records[:MAX_LOADED_MODULE_ORIGINS],
        "total_matching_modules": len(records),
        "truncated_count": truncated,
    }


def _ast_function_digest(path: Path | None, name: str) -> dict[str, Any]:
    if path is None:
        return {"function_name": name, "status": "source_path_unavailable"}
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        return {
            "function_name": name,
            "source_path": str(path),
            "status": "source_parse_error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    candidates = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if not candidates:
        return {
            "function_name": name,
            "source_path": str(path),
            "status": "function_not_found_at_module_scope",
        }
    node = candidates[0]
    source_ast = ast.dump(node, annotate_fields=True, include_attributes=False)
    return {
        "function_name": name,
        "source_path": str(path),
        "source_line_start": node.lineno,
        "source_line_end": node.end_lineno,
        "source_ast_sha256": hashlib.sha256(source_ast.encode("utf-8")).hexdigest(),
        "status": "recorded",
    }


def _callable_record(target_module: Any, helper_module: Any, name: str) -> dict[str, Any]:
    function = getattr(target_module, name, None) if target_module else None
    helper_export = getattr(helper_module, name, None) if helper_module else None
    code = getattr(function, "__code__", None)
    code_path = _resolved(getattr(code, "co_filename", None))
    result: dict[str, Any] = {
        "name": name,
        "target_alias_present": callable(function),
        "helper_export_present": callable(helper_export),
        "target_alias_is_helper_export": bool(function is not None and function is helper_export),
        "callable_module": getattr(function, "__module__", None),
        "callable_qualname": getattr(function, "__qualname__", None),
        "co_filename": getattr(code, "co_filename", None),
        "resolved_co_filename": str(code_path) if code_path else None,
        "co_firstlineno": getattr(code, "co_firstlineno", None),
        "ast": _ast_function_digest(code_path, name),
    }
    if code is not None:
        result["code_bytes_sha256"] = hashlib.sha256(code.co_code).hexdigest()
    return result


def _module_for_expected_path(expected_path: str) -> Any | None:
    expected = _resolved(REPOSITORY_ROOT / expected_path)
    if expected is None:
        return None
    for module in tuple(sys.modules.values()):
        if _module_file(module) == expected:
            return module
    return None


def _snapshot(label: str) -> dict[str, Any]:
    source_commit = _head()
    inputs = {
        role: _source_file_record(path, source_commit)
        for role, path in PINNED_INPUT_PATHS.items()
    }
    target_test_module = sys.modules.get(TARGET_MODULE) or _module_for_expected_path(
        PINNED_INPUT_PATHS["target_test"]
    )
    helper_module = sys.modules.get(HELPER_MODULE) or _module_for_expected_path(
        PINNED_INPUT_PATHS["test_fixture_helper"]
    )
    target_path = _module_file(target_test_module) if target_test_module else None
    helper_path = _module_file(helper_module) if helper_module else None
    test_function = getattr(target_test_module, TARGET_NODE.rsplit("::", 1)[1], None)
    test_code = getattr(test_function, "__code__", None)
    context_observers = {
        role: {
            "source_file": _source_file_record(path, source_commit),
            "loaded_module_origins": _loaded_modules_for_expected_path(path),
            "scope": "context only; excluded from the B23 direct input closure",
        }
        for role, path in CONTEXT_OBSERVER_PATHS.items()
    }
    return {
        "label": label,
        "source_commit": source_commit,
        "probe_value": os.environ.get(REMOVAL_ENV),
        "target_node": TARGET_NODE,
        "input_files": inputs,
        "context_observers": context_observers,
        "loaded_target_module": (
            {
                "module_name": getattr(target_test_module, "__name__", None),
                "module_file": getattr(target_test_module, "__file__", None),
                "spec_origin": getattr(
                    getattr(target_test_module, "__spec__", None), "origin", None
                ),
                "resolved_source_path": str(target_path) if target_path else None,
                "module_found_by_native_path": bool(target_path),
                "selected_test_callable_module": getattr(test_function, "__module__", None),
                "selected_test_callable_co_filename": getattr(test_code, "co_filename", None),
            }
            if target_test_module
            else None
        ),
            "loaded_helper_module": (
            {
                "module_name": getattr(helper_module, "__name__", None),
                "module_file": getattr(helper_module, "__file__", None),
                "spec_origin": getattr(getattr(helper_module, "__spec__", None), "origin", None),
                "resolved_source_path": str(helper_path) if helper_path else None,
                "module_found_by_native_path": bool(helper_path),
            }
            if helper_module
            else None
        ),
        "generation_cycle_test_module_if_loaded": {
            "canonical_name_present": GENERATION_TEST_MODULE in sys.modules,
            "loaded_module_origins": _loaded_modules_for_expected_path(
                CONTEXT_OBSERVER_PATHS["generation_cycle_test_context_only"]
            ),
        },
        "bound_test_fixture_callables": {
            name: _callable_record(target_test_module, helper_module, name)
            for name in ("_atom", "_request")
        }
        if target_test_module
        else {},
        "selected_test_ast": _ast_function_digest(
            target_path,
            TARGET_NODE.rsplit("::", 1)[1],
        ),
        "loaded_project_module_origins": _loaded_project_module_origins(),
    }


class B23InputProvenancePlugin:
    def __init__(self) -> None:
        self.output_path = os.environ.get(OUTPUT_ENV)
        self.record: dict[str, Any] = {
            "schema": "policyos.e02.b23_runtime_input_provenance.v1",
            "plugin_path": str(Path(__file__).resolve()),
            "plugin_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "repository_root": str(REPOSITORY_ROOT),
            "requested_target_node": TARGET_NODE,
            "requested_probe": os.environ.get(REMOVAL_ENV),
            "snapshots": [],
            "collected_nodeids": [],
            "test_reports": [],
        }

    def pytest_sessionstart(self, session: Any) -> None:
        self.record["session_start_commit"] = _head()
        self.record["pre_collection_source_files"] = {
            role: _source_file_record(path, self.record["session_start_commit"])
            for role, path in PINNED_INPUT_PATHS.items()
        }

    def pytest_collection_finish(self, session: Any) -> None:
        self.record["collected_nodeids"] = [item.nodeid for item in session.items]
        self.record["collection_scope_is_exact_target"] = (
            self.record["collected_nodeids"] == [TARGET_NODE]
        )
        self.record["snapshots"].append(_snapshot("post_collection_pre_test"))

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item: Any) -> Any:
        if item.nodeid != TARGET_NODE:
            yield
            return
        self.record["snapshots"].append(_snapshot("immediately_before_target_call"))
        yield
        self.record["snapshots"].append(_snapshot("immediately_after_target_call"))

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.nodeid != TARGET_NODE:
            return
        self.record["test_reports"].append(
            {
                "nodeid": report.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "longrepr": str(report.longrepr)[:4000] if report.failed else None,
            }
        )

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        self.record["session_finish_commit"] = _head()
        self.record["pytest_exitstatus"] = exitstatus
        self.record["pytest_testsfailed"] = getattr(session, "testsfailed", None)
        self.record["snapshots"].append(_snapshot("session_finish"))
        self.record["head_unchanged"] = (
            self.record.get("session_start_commit") == self.record.get("session_finish_commit")
        )
        self.record["loaded_module_file_stability"] = _module_file_stability(
            self.record["snapshots"]
        )
        if not self.output_path:
            self.record["write_error"] = f"Set {OUTPUT_ENV} to a unique ignored JSON path."
            return
        output = Path(self.output_path).expanduser().resolve()
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            self.record["output_path"] = str(output)
            temporary = output.with_suffix(output.suffix + ".tmp")
            temporary.write_text(
                json.dumps(self.record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(output)
        except OSError as exc:
            self.record["write_error"] = f"{type(exc).__name__}: {exc}"


def _module_file_stability(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for role in ("target_test", "test_fixture_helper"):
        records = [snapshot["input_files"].get(role, {}) for snapshot in snapshots]
        hashes = [item.get("sha256") for item in records]
        blobs = [item.get("working_tree_git_blob") for item in records]
        commits = [snapshot.get("source_commit") for snapshot in snapshots]
        result[role] = {
            "sha256_values": hashes,
            "working_tree_git_blob_values": blobs,
            "source_commit_values": commits,
            "bytes_stable_across_snapshots": len(set(hashes)) == 1 and bool(hashes[0]),
            "working_tree_blob_stable_across_snapshots": len(set(blobs)) == 1
            and bool(blobs[0]),
            "source_commit_stable_across_snapshots": len(set(commits)) == 1 and bool(commits[0]),
        }
        module_key = "loaded_target_module" if role == "target_test" else "loaded_helper_module"
        module_records = [snapshot.get(module_key) or {} for snapshot in snapshots]
        module_paths = [item.get("resolved_source_path") for item in module_records]
        module_names = [item.get("module_name") for item in module_records]
        result[role]["loaded_module_path_values"] = module_paths
        result[role]["loaded_module_name_values"] = module_names
        result[role]["loaded_module_path_stable"] = len(set(module_paths)) == 1 and bool(
            module_paths[0]
        )
        result[role]["loaded_module_name_stable"] = len(set(module_names)) == 1 and bool(
            module_names[0]
        )
    return result


def pytest_configure(config: Any) -> None:
    config.pluginmanager.register(B23InputProvenancePlugin(), "b23-input-provenance")
