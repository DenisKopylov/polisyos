(
    "Actual Scientist uncertainty and welfare"  # Exact bound literal continuation.
    " consumers, forged denominator control."  # Exact bound literal continuation.
)

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry import uncertainty as public
from polisyos.foundry.uncertainty import sampling_admission as canonical
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


mode = sys.argv[1]
root = Path(sys.argv[2])
source = Path(sys.argv[3]).resolve()
required = (
    "BoundedIndicatorResponse",
    "reconcile_draw_outcomes",
    "sampling_content_digest",
    "verify_mean_certificate",
)
if not (all(getattr(public, n) is getattr(canonical, n) for n in required)):
    raise AssertionError
if not (set(required) <= set(public.__all__)):
    raise AssertionError
if mode == "denominator_removed":
    public.reconcile_draw_outcomes = lambda *a, **kw: set()
from polisyos.scientist.nodes.builtins.simulate import (  # noqa: E402 - source-bound fixture
    propagate_uncertainty as un,
)
from polisyos.scientist.nodes.builtins.simulate import (  # noqa: E402 - source-bound fixture
    propagate_welfare as wn,
)
from polisyos.scientist.nodes.builtins.state_keys import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)

if not (un.reconcile_draw_outcomes is wn.reconcile_draw_outcomes is public.reconcile_draw_outcomes):
    raise AssertionError
if un.verify_mean_certificate is not public.verify_mean_certificate:
    raise AssertionError
if wn.sampling_content_digest is not public.sampling_content_digest:
    raise AssertionError

store = FileSystemCAS(root / "uncertainty-cas")
registry = build_default_registry_bundle(store).bundle_ref
run = RunContext.start(
    store=store, registry_bundle=registry, run_id="independent-facade-uncertainty"
)
ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("independent.facade"))
env = UncertaintyEnvelope(
    point_estimate=0.5,
    confidence_interval=(0.0, 1.0),
    distribution_family=DistributionFamily.UNIFORM,
    source=UncertaintySource.CALIBRATION,
    interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
    is_heuristic_ci=True,
    gate_eligible=False,
)
env_ref = persist_uncertainty_envelope(store, env)
data = store.put_json(
    {"state": {}}, PutOptions(kind="foundry.state_snapshot", media_type="application/json")
)
snapshot = store.put_json(
    DataSnapshot(data_ref=data, uncertainty_envelope_ref=env_ref),
    PutOptions(
        kind="fabric.data_snapshot",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
    ),
)
plan = store.put_json(
    {
        "program_ref": {
            "artifact_id": str(data.artifact_id),
            "kind": "foundry.program_graph",
            "media_type": "application/json",
        },
        "order": [],
    },
    PutOptions(kind="foundry.exec_plan", media_type="application/json"),
)
metrics = store.put_json(
    Metrics(values={"independent_metric": 10}),
    PutOptions(kind="foundry.metrics", media_type="application/json"),
)
sim = store.put_json(
    SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics.artifact_id),
    ),
    PutOptions(kind="foundry.simulation_result", media_type="application/json"),
)
state = ExperimentState(
    run_id="independent-facade-uncertainty",
    inputs={INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=snapshot.artifact_id)},
    artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim},
    params={
        "propagation_config": {
            "preferred_method": "monte_carlo",
            "mc_n_samples": 128,
            "mc_batch_size": 128,
            "mc_min_valid_samples": 10,
            "mc_seed": 41,
            "compute_sensitivity": False,
        },
        "propagation_sensitivity": {"independent_metric": {"data_snapshot": 1.0}},
    },
)
outcome = un.PropagateUncertaintyNode().execute(ctx, state)
if not (outcome.status == "ok"):
    raise AssertionError
fresh = FileSystemCAS(root / "uncertainty-cas")
report_ref = outcome.state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF]
report = from_canonical_bytes(fresh.get_bytes(report_ref.artifact_id))
provenance = report["draw_outcome_provenance"]
if not (provenance["requested_draw_count"] == provenance["attempted_draw_count"] == 128):
    raise AssertionError
if not (
    len(provenance["draw_records"]) == 128 and provenance["outcome_denominator_complete"] is True
):
    raise AssertionError
if not (public.reconcile_draw_outcomes(provenance, ["independent_metric"]) == set()):
    raise AssertionError

original_persist = un._persist_report


def persist_corrupt_report(*args: object, **kwargs: object) -> object:
    ref = original_persist(*args, **kwargs)
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    payload["draw_outcome_provenance"]["requested_draw_count"] += 1
    # Shape and completed marker retained; all CAS bytes/hash are freshly correct.
    return store.put_json(
        payload,
        PutOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


un._persist_report = persist_corrupt_report
try:
    un.PropagateUncertaintyNode().execute(ctx, state)
    refusal = None
except ValueError as exc:
    refusal = str(exc)
_write_stdout(
    json.dumps(
        {
            "mode": mode,
            "actual_node_forged_denominator_refusal": refusal,
            "export_names_retained": all(n in public.__all__ for n in required),
        }
    ),
    flush=True,
)
if not (refusal is not None and "denominator" in refusal):
    raise AssertionError(refusal)

welfare_store = FileSystemCAS(root / "welfare-cas")
called = []


def evaluator(x: object) -> dict[str, object]:
    called.append(x)
    return {"welfare": x, "welfare_pe": x, "welfare_ge": x if x >= 0 else np.nan}


welfare_env = env.model_copy(update={"point_estimate": 0.0, "confidence_interval": (-1.0, 1.0)})
context = SimpleNamespace(
    dependence_context=wn._ResolvedDependenceContext(
        ref=None,
        structure=None,
        correlation_matrix=None,
        parameter_order=("x",),
        strategy="unknown",
        warnings=(),
        diagnostics={},
    ),
    dependence_structure_ref=None,
)
result = wn._propagate_credible_interval(
    SimpleNamespace(store=welfare_store),
    SimpleNamespace(
        params={
            "propagation_config": {"mc_n_samples": 128, "mc_min_valid_samples": 10, "mc_seed": 41}
        }
    ),
    welfare_params={"credible_method": "monte_carlo"},
    context=context,
    simulation_fn=evaluator,
    nominal_params={"x": 0.0},
    input_envelopes={"x": welfare_env},
    calibration_source=None,
)
fresh = FileSystemCAS(root / "welfare-cas")
samples = wn._load_verified_welfare_samples(fresh, result.sample_bundle_ref)
receipt = wn._load_welfare_draw_outcomes(
    fresh, wn.ArtifactRef.model_validate(result.diagnostics["draw_outcomes_ref"])
)
expected_success = [x for x in called if x >= 0]
if not (len(called) == receipt["attempted_draw_count"] == receipt["requested_draw_count"] == 128):
    raise AssertionError
if not (receipt["failed_draw_count"] == sum(x < 0 for x in called)):
    raise AssertionError
if not (receipt["successful_draw_count"] == len(expected_success)):
    raise AssertionError
if not (result.credible_interval is None and samples.metadata["gate_eligible"] is False):
    raise AssertionError
if result.result_map["welfare"]["point_estimate"] is not None:
    raise AssertionError
if not (np.isclose(result.result_map["welfare"]["conditional_mean"], np.mean(expected_success))):
    raise AssertionError
np.testing.assert_array_equal(samples.welfare_draws, expected_success)
origins = {
    n: str(Path(m.__file__).resolve())
    for n, m in sys.modules.items()
    if n.startswith("polisyos.") and getattr(m, "__file__", None)
}
if not (all(Path(p).is_relative_to(source) for p in origins.values())):
    raise AssertionError
_write_stdout(
    json.dumps(
        {
            "mode": mode,
            "uncertainty_attempted": 128,
            "welfare_full_inputs": called,
            "welfare_attempted": 128,
            "welfare_success": len(expected_success),
            "welfare_failed": sum(x < 0 for x in called),
            "conditional_mean": float(np.mean(expected_success)),
            "gate_eligible": False,
            "module_origins": origins,
        },
        sort_keys=True,
    ),
    flush=True,
)
