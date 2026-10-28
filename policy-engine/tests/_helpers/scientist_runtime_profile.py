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
from pathlib import Path
from typing import Any


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
    loaded = []
    origin_errors = []
    selected_source_root = root / "policy-engine" / "src"
    for name, module in sorted(sys.modules.copy().items()):
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        path = Path(filename).resolve()
        is_product = name == "polisyos" or name.startswith("polisyos.")
        if path.suffix != ".py" or not (is_product or path.is_relative_to(root)):
            continue
        if is_product and not path.is_relative_to(selected_source_root):
            origin_errors.append({"module": name, "actual_path": str(path)})
        loaded.append(
            {
                "module": name,
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    receipt = {
        "entry": entry,
        "stages": stages,
        "loaded_project_python": loaded,
        "product_source_origin_errors": origin_errors,
        "scope": "Finite still-loaded Python set; no transient/native/data/process-tree tracing claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    if origin_errors:
        print(
            json.dumps({"product_source_origin_errors": origin_errors}), file=sys.stderr, flush=True
        )
    return 0 if not origin_errors and all(row["status"] == "PASS" for row in stages) else 1


if __name__ == "__main__":
    raise SystemExit(main())
