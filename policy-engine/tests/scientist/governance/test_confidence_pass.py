from __future__ import annotations

from statistics import NormalDist

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.ir.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.scientist.governance.passes.base import IssueSeverity, PassContext
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass
from polisyos.scientist.governance.profiles import ValidationProfile


def _normal_envelope(point: float, std: float, level: float = 0.95) -> UncertaintyEnvelope:
    z = NormalDist().inv_cdf((1.0 + level) / 2.0)
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - z * std, point + z * std),
        confidence_level=level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.DELTA_METHOD,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
    )


def _put_simulation_result_with_envelope(store: FileSystemCAS, *, point: float, std: float):
    program_ref = {
        "artifact_id": "sha256:" + "a" * 64,
        "kind": "foundry.program_graph",
        "media_type": "application/json",
    }
    exec_plan_ref = store.put_json(
        {"program_ref": program_ref, "order": []},
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"metric": 1}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    env_ref = persist_uncertainty_envelope(store, _normal_envelope(point=point, std=std))
    sim = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        uncertainty_envelopes={"metric": env_ref},
    )
    return store.put_json(
        sim,
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )


def test_confidence_pass_blocks_wide_ci(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    sim_ref = _put_simulation_result_with_envelope(store, point=1.0, std=0.4)

    ctx = PassContext(
        ir=None,
        state={"artifacts_index": {"simulation_result_ref": sim_ref}, "_store": store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_confidence_block",
    )

    issues = ConfidencePass().validate(ctx)
    assert any(issue.severity == IssueSeverity.BLOCKER for issue in issues)


def test_confidence_pass_accepts_narrow_ci(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    sim_ref = _put_simulation_result_with_envelope(store, point=10.0, std=0.5)

    ctx = PassContext(
        ir=None,
        state={"artifacts_index": {"simulation_result_ref": sim_ref}, "_store": store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_confidence_ok",
    )

    issues = ConfidencePass().validate(ctx)
    assert not any(issue.severity == IssueSeverity.BLOCKER for issue in issues)


def test_confidence_pass_reads_causal_envelope(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    causal_ref = persist_uncertainty_envelope(store, _normal_envelope(point=1.0, std=0.4))
    ctx = PassContext(
        ir=None,
        state={"artifacts_index": {"causal_envelope_ref": causal_ref}, "_store": store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_confidence_causal",
    )
    issues = ConfidencePass().validate(ctx)
    assert any(issue.severity == IssueSeverity.BLOCKER for issue in issues)
