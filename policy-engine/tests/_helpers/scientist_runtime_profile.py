"""Fresh-process node discovery and native backend diagnostic, never chain proof."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib
import json
import os
import platform
import sys
import traceback
from importlib.machinery import EXTENSION_SUFFIXES, ModuleSpec
from pathlib import Path
from typing import Any


def _classify_origin_candidate(
    field: str, value: object, *, project_roots: tuple[Path, ...]
) -> dict[str, Any]:
    """Retain lexical claims and failed resolutions before any fallback choice."""
    row: dict[str, Any] = {
        "field": field,
        "raw": value if isinstance(value, str) else None,
        "value_type": type(value).__name__,
        "is_absolute": False,
        "lexical_project_claim": False,
        "resolved_project_scope": False,
    }
    if value is None:
        return {**row, "status": "absent"}
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        return {**row, "status": "not_established", "reason": "relative_virtual_or_opaque"}
    lexical = Path(os.path.normpath(value))
    row.update(
        is_absolute=True,
        lexical_path=str(lexical),
        lexical_project_claim=any(
            Path(value).is_relative_to(bound) or lexical.is_relative_to(bound)
            for bound in project_roots
        ),
    )
    try:
        # Lexical annotation must never rewrite the physical operand: symlink/..
        # semantics belong to the filesystem, not normpath.
        resolved = Path(value).resolve(strict=True)
        if not resolved.is_file():
            return {**row, "status": "not_established", "reason": "not_regular_file"}
    except (OSError, RuntimeError, ValueError) as exc:
        return {
            **row,
            "status": "not_established",
            "reason": "absolute_origin_resolution_failed",
            "error_type": type(exc).__name__,
        }
    return {
        **row,
        "status": "established",
        "resolved_path": str(resolved),
        "resolved_project_scope": any(resolved.is_relative_to(bound) for bound in project_roots),
    }


def collect_loaded_module_sources(
    modules: dict[str, object],
    *,
    repo_root: Path,
    product_roots: tuple[Path, ...] | None = None,
) -> dict[str, Any]:
    """Resolve all origin claims, fail required scope, then select physical source."""
    root = repo_root.resolve(strict=True)
    project_roots = tuple(root / "policy-engine" / name for name in ("src", "tests", "tools"))
    configured_roots = (
        product_roots if product_roots is not None else (root / "policy-engine/src/polisyos",)
    )
    admitted = []
    for path in configured_roots:
        if not path.is_absolute():
            raise ValueError("admitted_product_root_must_be_absolute")
        resolved = path.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("admitted_product_root_must_be_directory")
        admitted.append(resolved)
    admitted_product_roots = tuple(admitted)
    loaded = []
    product_errors = []
    project_errors = []
    unresolved_external = []
    product_namespaces = []
    product_other_files = []
    external_files = 0
    for name, module in sorted(modules.items()):
        is_product = name == "polisyos" or name.startswith("polisyos.")
        metadata_errors = []

        def attribute(
            owner: object, field: str, errors: list[dict[str, str]] = metadata_errors
        ) -> object:
            try:
                return getattr(owner, field, None)
            except Exception as exc:  # Importer hooks are not trusted origin evidence.
                errors.append({"field": field, "error_type": type(exc).__name__})
                return None

        filename = attribute(module, "__file__")
        spec = attribute(module, "__spec__")
        if spec is not None and not isinstance(spec, ModuleSpec):
            metadata_errors.append({"field": "__spec__", "error_type": "UnsupportedModuleSpec"})
        spec_origin = attribute(spec, "origin")
        locations = attribute(spec, "submodule_search_locations")
        candidates = [
            _classify_origin_candidate(
                "module_spec_origin", spec_origin, project_roots=project_roots
            ),
            _classify_origin_candidate("absolute_file", filename, project_roots=project_roots),
        ]
        metadata = {
            "module": name,
            "spec_origin": spec_origin if isinstance(spec_origin, str) else None,
            "raw_file": filename if isinstance(filename, str) else None,
            "origin_candidates": candidates,
            "metadata_errors": metadata_errors,
        }
        required_project = any(
            row["lexical_project_claim"] or row["resolved_project_scope"] for row in candidates
        )
        failed_project_claim = any(
            row["lexical_project_claim"]
            and (row["status"] != "established" or not row["resolved_project_scope"])
            for row in candidates
        )
        if metadata_errors or (not is_product and failed_project_claim):
            errors = (
                product_errors
                if is_product
                else project_errors
                if required_project
                else unresolved_external
            )
            errors.append(
                {
                    **metadata,
                    "status": "not_established",
                    "reason": "required_project_or_module_metadata_unresolved",
                }
            )
            continue
        if is_product and spec_origin is None and filename is None and locations is not None:
            try:
                paths = [Path(value) for value in locations]
                if not paths or not all(path.is_absolute() for path in paths):
                    raise ValueError("namespace_paths_not_absolute")
                paths = [path.resolve(strict=True) for path in paths]
                if not all(path.is_dir() for path in paths):
                    raise ValueError("namespace_paths_not_directories")
                if not all(
                    any(path.is_relative_to(bound) for bound in admitted_product_roots)
                    for path in paths
                ):
                    raise ValueError("namespace_paths_outside_bound")
            except (OSError, RuntimeError, TypeError, ValueError):
                product_errors.append(
                    {**metadata, "status": "not_established", "reason": "product_namespace_unbound"}
                )
            else:
                product_namespaces.append(
                    {
                        **metadata,
                        "status": "bounded_namespace",
                        "search_roots": list(map(str, paths)),
                    }
                )
            continue
        established = [row for row in candidates if row["status"] == "established"]
        # Every present product claim must resolve consistently inside the
        # admitted installation. A second readable origin cannot erase failure.
        failed_product_claim = any(
            row["status"] == "not_established"
            or (
                row["status"] == "established"
                and not any(
                    Path(row["resolved_path"]).is_relative_to(bound)
                    for bound in admitted_product_roots
                )
            )
            for row in candidates
        )
        if is_product and (
            failed_product_claim or len({row["resolved_path"] for row in established}) > 1
        ):
            product_errors.append(
                {
                    **metadata,
                    "status": "not_established",
                    "reason": "product_origin_claim_invalid",
                }
            )
            continue
        if not established:
            row = {**metadata, "status": "not_established", "reason": "no_real_absolute_origin"}
            (product_errors if is_product else unresolved_external).append(row)
            continue
        selected = established[0]  # Spec precedence applies only after all required claims pass.
        path = Path(selected["resolved_path"])
        if not is_product and any(row["status"] == "not_established" for row in candidates):
            unresolved_external.append(
                {**metadata, "status": "not_established", "reason": "alternative_origin_unresolved"}
            )
        if not is_product and not any(path.is_relative_to(bound) for bound in project_roots):
            external_files += 1
            continue
        if (
            is_product
            and path.suffix != ".py"
            and not any(str(path).endswith(suffix) for suffix in EXTENSION_SUFFIXES)
        ):
            product_errors.append(
                {**metadata, "status": "not_established", "reason": "product_origin_kind_unknown"}
            )
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            (product_errors if is_product else project_errors).append(
                {
                    **metadata,
                    "status": "not_established",
                    "reason": "selected_source_bytes_unreadable",
                    "selected_path": str(path),
                    "error_type": type(exc).__name__,
                }
            )
            continue
        row = {**metadata, "path": str(path), "sha256": digest, "origin_basis": selected["field"]}
        if path.suffix == ".py":
            loaded.append(row)
        elif is_product:
            product_other_files.append(row)
        else:
            external_files += 1
    return {
        "loaded_project_python": loaded,
        "product_source_origin_errors": product_errors,
        "project_source_origin_errors": project_errors,
        "not_established_nonproduct_origins": unresolved_external,
        "bounded_product_namespaces": product_namespaces,
        "loaded_non_python_product_origins": product_other_files,
        "external_regular_file_module_count": external_files,
        "enumerated_module_count": len(modules),
        "admitted_product_roots": list(map(str, admitted_product_roots)),
    }


def main() -> int:
    """Run real discovery/native calls and retain each actual error and loaded source."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve(strict=True)
    entry = {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "executable": sys.executable,
        "argv": sys.argv,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "dont_write_bytecode": sys.flags.dont_write_bytecode,
        "pycache_prefix": sys.pycache_prefix,
        "pycache_initially_empty": bool(sys.pycache_prefix)
        and not any(Path(sys.pycache_prefix).rglob("*")),
    }
    stages: list[dict[str, Any]] = []

    def stage(name: str, call: Any) -> None:
        try:
            result = call()
        except Exception as exc:  # Retain actual diagnostic errors without substituting a node.
            error = traceback.format_exc()
            print(error, file=sys.stderr, end="", flush=True)
            stages.append(
                {"stage": name, "status": "ERROR", "type": type(exc).__name__, "traceback": error}
            )
        else:
            stages.append({"stage": name, "status": "PASS", "result": result})
        print(json.dumps(stages[-1], sort_keys=True), flush=True)

    def interpreter_profile() -> dict[str, Any]:
        assert platform.python_implementation() == "CPython" and sys.version_info[:2] == (3, 14)
        assert entry["dont_write_bytecode"] and entry["pycache_initially_empty"], entry
        return entry

    def discover() -> dict[str, Any]:
        from polisyos.scientist import discover_scientist_nodes

        registry, report = discover_scientist_nodes(include_dev_scan=False)
        diagnostic = dataclasses.asdict(report)
        print(json.dumps({"actual_discovery_report": diagnostic}, sort_keys=True), flush=True)
        assert not report.errors and not report.discovery_errors, diagnostic
        required = (
            "scientist.node_build_data_snapshot@1.0.0",
            "scientist.node_compile_foundry@1.0.0",
        )
        resolved = []
        for node_id in required:
            node = registry.get(node_id)
            resolved.append(str(node.spec.metadata.component_id))
        return {"include_dev_scan": False, "required_resolved": resolved, "report": diagnostic}

    def native_sklearn() -> dict[str, Any]:
        import sklearn
        from sklearn.utils import murmurhash3_32

        # This calls the installed compiled extension; distribution metadata alone is insufficient.
        value = murmurhash3_32("policyos-runtime-profile", seed=0, positive=True)
        assert isinstance(value, int) and 0 <= value < 2**32
        module = importlib.import_module(murmurhash3_32.__module__)
        origin = Path(module.__file__).resolve(strict=True)
        return {
            "version": sklearn.__version__,
            "callable": murmurhash3_32.__module__ + "." + murmurhash3_32.__name__,
            "origin": str(origin),
            "origin_sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
            "returned_uint32": value,
        }

    def numpy_method() -> dict[str, Any]:
        import numpy as np

        from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator

        output = ExAnteSimulationEstimator.pure_step(
            {"baseline": np.array([10.0, 20.0, 40.0]), "scenario": np.array([11.0, 18.0, 44.0])},
            {"poverty_line": None},
        )
        assert output["result"]["mean_change"] == 1.0, output
        return {"numpy_version": np.__version__, "actual_mean": output["result"]["mean_change"]}

    stage("interpreter_profile", interpreter_profile)
    stage("builtin_node_discovery", discover)
    stage("sklearn_native_call", native_sklearn)
    stage("numpy_registered_method_call", numpy_method)
    origins = collect_loaded_module_sources(sys.modules.copy(), repo_root=root)
    origin_errors = [
        *origins["product_source_origin_errors"],
        *origins["project_source_origin_errors"],
    ]
    receipt = {
        "entry": entry,
        "stages": stages,
        **origins,
        "scope": "Finite still-loaded Python set; no transient/native/data/process-tree tracing claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    if origin_errors:
        print(
            json.dumps(
                {
                    "product_source_origin_errors": origins["product_source_origin_errors"],
                    "project_source_origin_errors": origins["project_source_origin_errors"],
                }
            ),
            file=sys.stderr,
            flush=True,
        )
    return 0 if not origin_errors and all(row["status"] == "PASS" for row in stages) else 1


if __name__ == "__main__":
    raise SystemExit(main())
