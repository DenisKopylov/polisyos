from __future__ import annotations

from statistics import NormalDist

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.ir.analytics.uncertainty import (
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


def test_confidence_pass_missing_envelope_returns_empty() -> None:
    """When no simulation result or causal envelope exist, pass returns no issues."""
    ctx = PassContext(
        ir=None,
        state={},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_confidence_missing",
    )
    issues = ConfidencePass().validate(ctx)
    assert issues == []


def test_confidence_pass_missing_store_returns_empty(tmp_path) -> None:
    """When _store is absent, pass returns no issues even with refs."""
    store = FileSystemCAS(tmp_path)
    sim_ref = _put_simulation_result_with_envelope(store, point=1.0, std=0.4)
    ctx = PassContext(
        ir=None,
        state={"artifacts_index": {"simulation_result_ref": sim_ref}},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_confidence_no_store",
    )
    issues = ConfidencePass().validate(ctx)
    assert issues == []


def test_confidence_pass_exactly_at_ci_ratio_threshold(tmp_path) -> None:
    """CI ratio exactly at threshold should NOT trigger a blocker.

    strict threshold: uncertainty_max_ci_width_ratio=0.5
    We need ci_width / point == 0.5 exactly.
    For a normal 95% CI: width = 2 * z * std.
    ratio = (2 * z * std) / point = 0.5 -> std = 0.5 * point / (2 * z).
    """
    z = NormalDist().inv_cdf(0.975)
    point = 10.0
    std = 0.5 * point / (2 * z)

    store = FileSystemCAS(tmp_path)
    sim_ref = _put_simulation_result_with_envelope(store, point=point, std=std)
    ctx = PassContext(
        ir=None,
        state={"artifacts_index": {"simulation_result_ref": sim_ref}, "_store": store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_confidence_boundary",
    )
    issues = ConfidencePass().validate(ctx)
    ci_ratio_issues = [i for i in issues if i.code == "CONFIDENCE_CI_RATIO_EXCEEDED"]
    assert len(ci_ratio_issues) == 0


def test_confidence_pass_non_gate_eligible_triggers_gate_ratio_blocker(tmp_path) -> None:
    """Envelope with gate_eligible=False triggers CONFIDENCE_GATE_ELIGIBILITY_LOW
    when min_gate_eligible_ratio > 0 (strict has 0.5)."""
    store = FileSystemCAS(tmp_path)
    env = UncertaintyEnvelope(
        point_estimate=10.0,
        confidence_interval=(9.5, 10.5),
        confidence_level=0.95,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.DELTA_METHOD,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=False,
    )
    env_ref = persist_uncertainty_envelope(store, env)

    program_ref = {
        "artifact_id": "sha256:" + "b" * 64,
        "kind": "foundry.program_graph",
        "media_type": "application/json",
    }
    exec_plan_ref = store.put_json(
        {"program_ref": program_ref, "order": []},
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"m": 1}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    sim = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        uncertainty_envelopes={"m": env_ref},
    )
    sim_ref = store.put_json(
        sim, PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    ctx = PassContext(
        ir=None,
        state={"artifacts_index": {"simulation_result_ref": sim_ref}, "_store": store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_confidence_gate",
    )
    issues = ConfidencePass().validate(ctx)
    gate_issues = [i for i in issues if i.code == "CONFIDENCE_GATE_ELIGIBILITY_LOW"]
    assert len(gate_issues) == 1
    assert gate_issues[0].severity == IssueSeverity.BLOCKER


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
