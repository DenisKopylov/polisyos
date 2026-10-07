"""Focused canonical edge collector and actual fresh reader controls."""

import ast
import hashlib
import importlib
import importlib.util
import json
import os
import runpy
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


R = Path("/workspace/e02-E-continuation-20261006")
P = R / "policy-engine"
S = P / "src"
observed_o = Path(__file__).parent
REF = os.environ["REVIEW_SOURCE_SHA"]
OLD = "2c275dc69a5b544704256ee0ccd37649ae7e8ea4"


def blob(ref: object, path: object) -> object:
    return subprocess.check_output([_resolve_executable("git"), "show", ref + ":" + path], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


guard_path = "policy-engine/tools/devx/architecture/guardrails.py"
if not ((R / guard_path).read_bytes() == blob(REF, guard_path) == blob(OLD, guard_path)):
    raise AssertionError
spec = importlib.util.spec_from_file_location("e02_native_guardrails", R / guard_path)
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)
contract_path = "policy-engine/architecture/public_surface/contract.toml"
contract = blob(REF, contract_path)
if not (contract == blob(OLD, contract_path)):
    raise AssertionError
allowed = {}
for p in tomllib.loads(contract.decode())["package"]:
    root = guard._root_for_module(p["module"])
    allowed.setdefault(root, set()).update(p["supported_entrypoints"])
paths = {
    "polisyos.calibration": "policy-engine/src/polisyos/calibration/__init__.py",
    "polisyos.foundry.uncertainty": "policy-engine/src/polisyos/foundry/uncertainty/__init__.py",
    "polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty": (
        "policy-engine/src/polisyos/scientist/nod"  # Exact bound literal continuation.
        "es/builtins/simulate/propagate_uncertain"  # Exact bound literal continuation.
        "ty.py"  # Exact bound literal continuation.
    ),
}
snapshots = {}
for path in paths.values():
    if not ((R / path).read_bytes() == blob(REF, path)):
        raise AssertionError
    snapshots[path] = hashlib.sha256(blob(REF, path)).hexdigest()


def exact_selected_edges(ref: object) -> list[object]:
    edges = {}
    for source, path in paths.items():
        for n in ast.walk(ast.parse(blob(ref, path))):
            if not isinstance(n, ast.ImportFrom) or n.level != 0 or not n.module:
                continue
            guard._maybe_add_deep_import(
                edges=edges,
                allowed_entrypoints=allowed,
                source_module=source,
                source_root=guard._root_for_module(source),
                source_file=R / path,
                target_module=n.module,
            )
    return [
        {
            "key": e.key,
            "source": e.source_module,
            "target": e.target_module,
            "source_file": e.source_file,
        }
        for e in sorted(edges.values(), key=lambda e: e.key)
    ]


old = exact_selected_edges(OLD)
new = exact_selected_edges(REF)
original_iter = guard._iter_py_files
guard._iter_py_files = lambda: [R / path for path in paths.values()]
try:
    actual_collected = guard.collect_deep_import_edges(
        guard._parse_public_surface(R / contract_path)
    )
finally:
    guard._iter_py_files = original_iter
if not ({e.key for e in actual_collected} == {e["key"] for e in new}):
    raise AssertionError
target = "polisyos.calibration->polisyos.foundry.calibration.report"
if not (target in {e["key"] for e in old} and target not in {e["key"] for e in new}):
    raise AssertionError
if {e["key"] for e in new} - {e["key"] for e in old}:
    raise AssertionError
from polisyos import (  # noqa: E402 - source-bound fixture
    calibration as cal,
)
from polisyos.foundry import (  # noqa: E402 - source-bound fixture
    uncertainty as uncertainty,
)

owner = importlib.import_module("polisyos.foundry.calibration.report")
node = importlib.import_module("polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty")
if not (
    cal.load_foundry_calibration_report
    is uncertainty.load_foundry_calibration_report
    is owner.load_calibration_report
    is node.load_foundry_calibration_report
):
    raise AssertionError
if not (len(cal.__all__) == 29 and len(uncertainty.__all__) == 20):
    raise AssertionError
if not (
    "load_foundry_calibration_report" in cal.__all__
    and "load_foundry_calibration_report" in uncertainty.__all__
):
    raise AssertionError
from polisyos.core.artifacts import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
)
from polisyos.core.canon import (  # noqa: E402 - source-bound fixture
    CanonSpec,
)
from polisyos.scientist.nodes.builtins.state_keys import (  # noqa: E402 - source-bound fixture
    INPUT_CALIBRATION_REPORT_REF,
)

helper = runpy.run_path("tests/unit/scientist/nodes/test_calibration_report_consumer.py")
store, report, inputs, valid = helper["_fixture"](observed_o / "cas-route-cold-reader")
fresh = FileSystemCAS(store.root)
if not (cal.load_foundry_calibration_report(fresh, valid).schema_version == "2.0"):
    raise AssertionError
if not (
    uncertainty.load_foundry_calibration_report(fresh, valid)
    == cal.load_foundry_calibration_report(fresh, valid)
):
    raise AssertionError
if not (
    set(
        node._collect_input_envelopes(
            SimpleNamespace(store=fresh),
            SimpleNamespace(inputs={INPUT_CALIBRATION_REPORT_REF: valid}),
        )
    )
    == {"A.rate"}
):
    raise AssertionError
controls = []
for kind, schema, version in [
    ("funnel.calibration_report", "polisyos.foundry.CalibrationReport", "2.0"),
    ("foundry.calibration_report", "polisyos.foundry.FunnelCalibrationReport", "2.0"),
    ("foundry.calibration_report", "polisyos.foundry.CalibrationReport", "1.0"),
]:
    forged = store.put_json(
        report,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema, version=version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    if not (forged.artifact_id == valid.artifact_id):
        raise AssertionError
    for label, reader in [
        ("Calibration", cal.load_foundry_calibration_report),
        ("Foundry uncertainty", uncertainty.load_foundry_calibration_report),
    ]:
        try:
            reader(FileSystemCAS(store.root), forged)
        except ValueError as exc:
            controls.append(
                {
                    "reader": label,
                    "kind": kind,
                    "schema": schema,
                    "version": version,
                    "outcome": "REFUSED",
                    "reason": str(exc),
                }
            )
        else:
            raise AssertionError("malformed report accepted through a canonical facade")
    try:
        node._collect_input_envelopes(
            SimpleNamespace(store=FileSystemCAS(store.root)),
            SimpleNamespace(inputs={INPUT_CALIBRATION_REPORT_REF: forged}),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("malformed report accepted by actual consumer inlet")
modules = []
for name, module in sorted(sys.modules.items()):
    if name.startswith("polisyos.") and getattr(module, "__file__", None):
        path = Path(module.__file__).resolve()
        if not (path.is_relative_to(S)):
            raise AssertionError
        rel = "policy-engine/src/" + str(path.relative_to(S))
        expected = blob(REF, rel)
        if not (path.read_bytes() == expected):
            raise AssertionError
        modules.append(
            {"module": name, "path": rel, "sha256": hashlib.sha256(expected).hexdigest()}
        )
for path, h in snapshots.items():
    if not (hashlib.sha256((R / path).read_bytes()).hexdigest() == h):
        raise AssertionError
result = {
    "source_sha": REF,
    "tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "rev-parse", REF + "^{tree}"], cwd=R, text=True
    ).strip(),
    "old_sha": OLD,
    "property_paths": snapshots,
    "source_before_after_equal": True,
    "native_collector": (
        "guardrails.collect_deep_import_edges on exact3-file denomina"
        "tor, agrees with old/new _maybe_add_deep_import tracked-cont"
        "ract proof"
    ),
    "selected_source_modules": list(paths),
    "old_selected_edges": old,
    "new_selected_edges": new,
    "removed_crossroot_private_edge": target,
    "new_edges_introduced": 0,
    "exports": {"calibration": 29, "uncertainty": 20},
    "canonical_identity": True,
    "fresh_actual_consumer_inlet": (
        "valid Foundry report→fresh configured CAS→_collect_input_env"
        "elopes admits exact A.rate; 3 corrupt profiles refused"
    ),
    "malformed_reader_controls": controls,
    "actual_imported_modules": len(modules),
    "module_origins": modules,
    "code_verdict": "GO-bounded-canonical-routing-fix",
    "scope": (
        "This selected edge proof is not full global architecture PAS"
        "S. Unchanged strict reader/actual tiedproducer→Node→persiste"
        "d output/101callback removal proof reused from immutable r4;"
        " numeric common inlet properties reused from immutable r3."
    ),
}
(observed_o / "edge-identity-review.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            k: result[k]
            for k in [
                "source_sha",
                "tree",
                "old_sha",
                "source_before_after_equal",
                "removed_crossroot_private_edge",
                "new_edges_introduced",
                "exports",
                "canonical_identity",
                "malformed_reader_controls",
                "actual_imported_modules",
                "code_verdict",
                "scope",
            ]
        },
        indent=2,
    )
)
