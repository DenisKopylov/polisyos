from __future__ import annotations

from statistics import NormalDist

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import (
    ArtifactRef as CoreArtifactRef,
)
from polisyos.core.artifacts.manifest import (
    InputRef as CoreInputRef,
)
from polisyos.core.artifacts.manifest import (
    SchemaInfo as CoreSchemaInfo,
)
from polisyos.core.artifacts.manifest import (
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    Metrics,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.registry.refs import UncertaintyEnvelopeRef
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
    env_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store), _normal_envelope(point=point, std=std)
    )
    sim = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        uncertainty_envelopes={"metric": env_ref},
    )
    return store.put_json(
        sim,
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )


def _put_simulation_result_views_with_lineage(
    store: FileSystemCAS,
) -> tuple[SimulationResultRef, SimulationResultRef]:
    """Write same-content SimulationResult views with distinguishable input lineage."""
    program_ref = {
        "artifact_id": "sha256:" + "1" * 64,
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
    envelope_payload = _normal_envelope(point=10.0, std=0.5)
    envelope_ref_payload = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store), envelope_payload
    )
    envelope_ref = CoreArtifactRef.model_validate(envelope_ref_payload)
    report_ref = store.put_json(
        {"schema_version": "1.1", "diagnostics": []},
        PutOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=CoreSchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
        ),
    )
    base_ref = store.put_bytes(
        b"base simulation lineage",
        PutOptions(kind="test.base_simulation_result", media_type="application/octet-stream"),
    )
    config_ref = store.put_bytes(
        b"propagation config lineage",
        PutOptions(kind="test.propagation_config", media_type="application/octet-stream"),
    )
    simulation = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        uncertainty_envelopes={
            "metric": UncertaintyEnvelopeRef.model_validate(envelope_ref_payload)
        },
        propagation_report_ref=report_ref,
    )
    shared_lineage = [
        input_ref_from_artifact_ref(envelope_ref, role="metric_envelope.metric"),
        input_ref_from_artifact_ref(report_ref, role="propagation_report"),
        input_ref_from_artifact_ref(base_ref, role="base_simulation_result"),
        input_ref_from_artifact_ref(config_ref, role="propagation_config"),
    ]
    schema = CoreSchemaInfo(name="polisyos.core.SimulationResult", version="1.3")
    default_ref = store.put_json(
        simulation,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=schema,
            inputs=shared_lineage,
        ),
    )
    selected_lineage = [
        CoreInputRef(
            artifact_id="sha256:" + "f" * 64,
            role="metric_envelope.metric",
            manifest_profile_sha256=envelope_ref.manifest_profile_sha256,
        ),
        *shared_lineage[1:],
    ]
    selected_ref = store.put_json(
        simulation,
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=schema,
            inputs=selected_lineage,
        ),
    )
    assert default_ref.artifact_id == selected_ref.artifact_id
    assert default_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
    return (
        SimulationResultRef.model_validate(default_ref.model_dump(mode="python")),
        SimulationResultRef.model_validate(selected_ref.model_dump(mode="python")),
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
    env_ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(store), env)

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
        sim,
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
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


def test_confidence_pass_limits_unverified_narrow_ci(tmp_path) -> None:
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
    assert any(issue.code == "CONFIDENCE_ENVELOPE_ADMISSION_LIMITED" for issue in issues)
    assert not any(issue.code == "CONFIDENCE_CI_RATIO_EXCEEDED" for issue in issues)


def test_confidence_pass_preserves_selected_simulation_lineage_view(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    default_ref, selected_ref = _put_simulation_result_views_with_lineage(store)

    def validate(ref: SimulationResultRef) -> list:
        ctx = PassContext(
            ir=None,
            state={"artifacts_index": {"simulation_result_ref": ref}, "_store": store},
            registry_bundle=None,
            profile=ValidationProfile.strict(),
            run_id=(
                f"R_confidence_selected_{ref.manifest_profile_sha256[-6:]}"
                if ref.manifest_profile_sha256 is not None
                else "R_confidence_selected_default"
            ),
        )
        return ConfidencePass().validate(ctx)

    default_issues = validate(default_ref)
    selected_issues = validate(selected_ref)
    default_admission = next(
        issue.message
        for issue in default_issues
        if issue.code == "CONFIDENCE_ENVELOPE_ADMISSION_LIMITED"
    )
    selected_admission = next(
        issue.message
        for issue in selected_issues
        if issue.code == "CONFIDENCE_ENVELOPE_ADMISSION_LIMITED"
    )

    assert "simulation_result_lineage_mismatch:metric_envelope.metric" not in default_admission
    assert "simulation_result_lineage_mismatch:metric_envelope.metric" in selected_admission


def test_confidence_pass_reads_causal_envelope(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    causal_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store), _normal_envelope(point=1.0, std=0.4)
    )
    ctx = PassContext(
        ir=None,
        state={"artifacts_index": {"causal_envelope_ref": causal_ref}, "_store": store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_confidence_causal",
    )
    issues = ConfidencePass().validate(ctx)
    assert any(issue.severity == IssueSeverity.BLOCKER for issue in issues)
