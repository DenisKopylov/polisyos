(
    "Independent canonical reader identity, a"  # Exact bound literal continuation.
    "ctual fresh consumer and removal control"  # Exact bound literal continuation.
    "."  # Exact bound literal continuation.
)

import hashlib
import importlib
import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from polisyos import calibration as facade
from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import SimulationResult
from polisyos.foundry.uncertainty import PropagationDispatcher
from polisyos.ir.analytics.uncertainty import PosteriorSamplesCarrier, load_uncertainty_envelope
from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as node
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
)


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
S = R / "policy-engine/src"
observed_o = Path(__file__).parent
REF = "43c443b6f1015d57cf624598531ef99c22a296e6"
property_paths = [
    "policy-engine/src/polisyos/calibration/__init__.py",
    (
        "policy-engine/src/polisyos/scientist/nod"  # Exact bound literal continuation.
        "es/builtins/simulate/propagate_uncertain"  # Exact bound literal continuation.
        "ty.py"  # Exact bound literal continuation.
    ),
    "policy-engine/src/polisyos/foundry/calibration/report.py",
    (
        "policy-engine/tests/unit/scientist/nodes"  # Exact bound literal continuation.
        "/test_calibration_report_consumer.py"  # Exact bound literal continuation.
    ),
    "policy-engine/tests/unit/calibration/test_evidence_facades.py",
]
before = {}
for p in property_paths:
    expected = subprocess.check_output([_resolve_executable("git"), "show", REF + ":" + p], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    if not ((R / p).read_bytes() == expected):
        raise AssertionError
    before[p] = hashlib.sha256(expected).hexdigest()
owner = importlib.import_module("polisyos.foundry.calibration.report")
if not (
    facade.load_foundry_calibration_report
    is owner.load_calibration_report
    is node.load_foundry_calibration_report
):
    raise AssertionError
if not ("load_foundry_calibration_report" in facade.__all__ and len(facade.__all__) == 29):
    raise AssertionError
if hasattr(facade, "CalibrationReport"):
    raise AssertionError
if not (owner.CalibrationReport.__module__ == "polisyos.foundry.calibration.report"):
    raise AssertionError
mutant = os.environ.get("REMOVE_FOUNDRY_READER_ADMISSION") == "1"
if mutant:

    def unsafe_reader(store: object, ref: object) -> object:
        return owner.CalibrationReport.model_validate(
            from_canonical_bytes(store.get_bytes(ref.artifact_id))
        )

    owner.load_calibration_report.__code__ = unsafe_reader.__code__
    if not (
        facade.load_foundry_calibration_report
        is owner.load_calibration_report
        is node.load_foundry_calibration_report
    ):
        raise AssertionError

helper = runpy.run_path("tests/unit/scientist/nodes/test_calibration_report_consumer.py")
base = observed_o / ("cas-reader-removed" if mutant else "cas-reader-positive")
results = []
for label, kind, schema, version in [
    ("wrong-kind", "funnel.calibration_report", "polisyos.foundry.CalibrationReport", "2.0"),
    (
        "wrong-schema",
        "foundry.calibration_report",
        "polisyos.foundry.FunnelCalibrationReport",
        "2.0",
    ),
    (
        "wrong-payload-version",
        "foundry.calibration_report",
        "polisyos.foundry.CalibrationReport",
        "1.0",
    ),
]:
    store, report, inputs, valid = helper["_fixture"](base / label)
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
    fresh = FileSystemCAS(store.root)
    ctx, state = helper["_node_fixture"](fresh, forged, {"A.rate": 1.0})
    callback_count = [0]
    dispatch_count = [0]
    original_build = node._build_propagation_fn
    original_dispatch = PropagationDispatcher.propagate

    def counted_build(
        *args: object,
        original_build: object = original_build,
        callback_count: object = callback_count,
        **kwargs: object,
    ) -> tuple[object, ...]:
        fn, mapped = original_build(*args, **kwargs)

        def counted(*, callback_count: object = callback_count, **params: object) -> object:
            callback_count[0] += 1
            return fn(**params)

        counted._sensitivity_map = fn._sensitivity_map
        return counted, mapped

    def counted_dispatch(
        *args: object,
        dispatch_count: object = dispatch_count,
        original_dispatch: object = original_dispatch,
        **kwargs: object,
    ) -> object:
        dispatch_count[0] += 1
        return original_dispatch(*args, **kwargs)

    node._build_propagation_fn = counted_build
    PropagationDispatcher.propagate = counted_dispatch
    try:
        try:
            outcome = node.PropagateUncertaintyNode().execute(ctx, state)
        except ValueError as exc:
            error = str(exc)
            outcome = None
        else:
            error = None
    finally:
        node._build_propagation_fn = original_build
        PropagationDispatcher.propagate = original_dispatch
    result = {
        "fixture": label,
        "same_payload_artifact_id": str(valid.artifact_id),
        "different_manifest_profile": valid.manifest_profile_sha256
        != forged.manifest_profile_sha256,
        "kind": kind,
        "schema": schema,
        "manifest_version": version,
        "callback_count": callback_count[0],
        "dispatch_count": dispatch_count[0],
        "refusal": error,
        "outcome": None if outcome is None else outcome.status,
        "removed_admission": mutant,
    }
    _write_stdout(json.dumps(result), flush=True)
    results.append(result)
    if not (callback_count[0] == dispatch_count[0] == 0 and error is not None):
        raise AssertionError(
            "canonical export retained but stripped reader admission reac"
            "hed actual consumer callbacks"
        )

# One real configured Calibrator producer proves the alias reaches the persisted joint law.
tied = runpy.run_path("tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py")
store = FileSystemCAS(base / "real-tied-calibrator")
report_ref, report = tied["_run_b197_tied_calibrator"](store)
fresh = FileSystemCAS(store.root)
read_report = facade.load_foundry_calibration_report(fresh, report_ref)
if not (
    read_report.schema_version == "2.0"
    and set(read_report.uncertainty_envelopes)
    == {
        "A.rate",
        "B.rate",
    }
):
    raise AssertionError
ctx, state = helper["_node_fixture"](fresh, report_ref, {"A.rate": 1.0, "B.rate": -1.0})
outcome = node.PropagateUncertaintyNode().execute(ctx, state)
if not (outcome.status == "ok"):
    raise AssertionError
fresh_again = FileSystemCAS(store.root)
sim = SimulationResult.model_validate(
    from_canonical_bytes(
        fresh_again.get_bytes(
            outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF].artifact_id
        )
    )
)
envelope = load_uncertainty_envelope(fresh_again, sim.uncertainty_envelopes["y"])
if not (
    isinstance(envelope.distribution_payload, PosteriorSamplesCarrier)
    and not envelope.gate_eligible
):
    raise AssertionError
samples = np.asarray(envelope.distribution_payload.samples)
# Independent algebra: the two calibrated rate coordinates share one draw, so A-B is zero.
if not (len(samples) == 100 and np.max(np.abs(samples)) < 1e-12):
    raise AssertionError
receipt = from_canonical_bytes(
    fresh_again.get_bytes(
        outcome.state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF].artifact_id
    )
)
if not (receipt["mapped_params"] == ["A.rate", "B.rate"]):
    raise AssertionError
positive = {
    "producer": "actual Calibrator tied parameter projection",
    "persisted_report_ref": report_ref.model_dump(mode="json"),
    "fresh_read_schema_version": read_report.schema_version,
    "consumer": "PropagateUncertaintyNode.execute",
    "outcome": outcome.status,
    "output_ref": sim.uncertainty_envelopes["y"].model_dump(mode="json"),
    "joint_draw_oracle": "A and B use shared coordinate; A-B=0 for every draw",
    "sample_count": len(samples),
    "maximum_abs_contrast": float(np.max(np.abs(samples))),
    "gate_eligible": False,
}
modules = []
for name, module in sorted(sys.modules.items()):
    if name.startswith("polisyos.") and getattr(module, "__file__", None):
        path = Path(module.__file__).resolve()
        if not (path.is_relative_to(S)):
            raise AssertionError
        rel = "policy-engine/src/" + str(path.relative_to(S))
        expected = subprocess.check_output(  # noqa: S603 - source-bound fixture
            [_resolve_executable("git"), "show", REF + ":" + rel], cwd=R
        )
        if not (path.read_bytes() == expected):
            raise AssertionError
        modules.append(
            {"module": name, "path": rel, "sha256": hashlib.sha256(expected).hexdigest()}
        )
for p, h in before.items():
    if not (hashlib.sha256((R / p).read_bytes()).hexdigest() == h):
        raise AssertionError
result = {
    "source_sha": REF,
    "source_tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "rev-parse", REF + "^{tree}"], cwd=R, text=True
    ).strip(),
    "property_paths": before,
    "source_before_after_equal": True,
    "canonical_identity": True,
    "calibration_exports": 29,
    "distinct_Foundry_and_Funnel_reports": True,
    "negatives": results,
    "positive": positive,
    "actual_import_modules": len(modules),
    "module_origins": modules,
    "verdict": "GO-bounded-canonical-reader-alias-and-actual-consumer",
    "limitations": (
        "Content/kind/schema integrity does not establish source fit/"
        "served evaluator authority; B197 remains held in committed l"
        "edger."
    ),
}
(observed_o / "calibration-reader-independent.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            k: result[k]
            for k in [
                "source_sha",
                "source_tree",
                "source_before_after_equal",
                "canonical_identity",
                "calibration_exports",
                "negatives",
                "positive",
                "actual_import_modules",
                "verdict",
                "limitations",
            ]
        },
        indent=2,
    )
)
