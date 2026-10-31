from __future__ import annotations

from types import SimpleNamespace
from typing import Literal, cast

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.analytics.sensitivity import SensitivityAnalysisBundle
from polisyos.ir.governance.validation import Phase5GateComponent, ValidationReport
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXPLANATION_BUNDLE_REF,
    ARTIFACT_FAIRNESS_AUDIT_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.phase5_preflight import (
    Phase5ArtifactPreflightInput,
    Phase5ValidationBlocked,
    _input_refs_for_publication,
    build_phase5_validation_report,
    enforce_phase5_validation_report,
    run_phase5_artifact_preflight,
)


def _ctx() -> ExecutionContext:
    return cast("ExecutionContext", object())


def _state(**params: object) -> ExperimentState:
    return ExperimentState(run_id="phase5-test", params=dict(params))


def _passing_judge_verdict() -> dict[str, object]:
    return {
        "per_judge": {
            name: {"judge_name": name, "passed": True, "is_fatal": True}
            for name in (
                "structural",
                "statistical",
                "robustness",
                "governance",
                "reproducibility",
                "compute",
            )
        },
        "composite_decision": "promote",
        "blocking_failures": [],
        "warnings": [],
    }


def test_validation_report_lineage_keeps_selected_artifact_and_judge_profiles(tmp_path) -> None:
    from polisyos.core.artifacts import ArtifactRef, ensure_ir_artifact_store
    from polisyos.ir.governance.validation import persist_validation_report

    store = FileSystemCAS(tmp_path / "cas")
    artifact = store.put_json(
        {"synthetic": "target"},
        PutOptions(kind="test.target", media_type="application/json"),
        return_selected_profile=True,
    )
    judge = store.put_json(
        {"synthetic": "judge"},
        PutOptions(kind="test.judge", media_type="application/json"),
        return_selected_profile=True,
    )
    inputs = _input_refs_for_publication(artifact, judge)
    report = persist_validation_report(
        ensure_ir_artifact_store(store),
        ValidationReport(error_summary="synthetic", issues=[]),
        inputs=inputs,
    )
    manifest = store.get_manifest(ArtifactRef.model_validate(report.model_dump(mode="json")))
    edges = {edge.role: edge for edge in manifest.inputs}
    assert edges["artifact"].manifest_profile_sha256 == artifact.manifest_profile_sha256
    assert edges["judge_verdict"].manifest_profile_sha256 == judge.manifest_profile_sha256


def test_validation_report_v2_accepts_legacy_and_phase5_payloads() -> None:
    legacy = ValidationReport(error_summary="ok", issues=[])
    assert legacy.schema_version == "2.0"
    assert legacy.verdict == "pass"
    assert legacy.readiness == "ready"

    report = ValidationReport(
        error_summary="blocked",
        issues=[],
        verdict="blocked",
        readiness="blocked",
        phase5_components=[
            Phase5GateComponent(
                name="prior_sensitivity",
                status="blocked",
                blockers=["Prior-sensitivity checks were not run."],
            )
        ],
        gate_failures=["Prior-sensitivity checks were not run."],
    )
    assert report.phase5_components[0].name == "prior_sensitivity"


def test_preflight_blocks_prior_sensitivity_not_run() -> None:
    report = build_phase5_validation_report(
        _ctx(),
        _state(),
        artifact_payload={
            "contract_id": "foundry.bayesian.posterior_result.v1",
            "prior_sensitivity": {"status": "NOT_RUN"},
        },
        artifact_kind="posterior_result",
    )

    assert report.verdict == "blocked"
    assert "Prior-sensitivity checks were not run." in report.gate_failures
    with pytest.raises(Phase5ValidationBlocked):
        enforce_phase5_validation_report(report)


def test_preflight_blocks_missing_conditional_coverage_for_interval_claim() -> None:
    report = build_phase5_validation_report(
        _ctx(),
        _state(),
        artifact_payload={
            "contract_id": "foundry.ml.prediction_interval_result.v1",
            "lower": [0.1],
            "upper": [0.9],
        },
        artifact_kind="prediction_interval_result",
    )

    assert report.verdict == "blocked"
    assert any("conditional coverage" in failure.lower() for failure in report.gate_failures)


def test_preflight_blocks_unbounded_diagnostic_only_explanations() -> None:
    report = build_phase5_validation_report(
        _ctx(),
        _state(),
        artifact_payload={
            "kind": "scientist.explanation_bundle",
            "faithfulness_claim": "diagnostic_only",
            "display_policy": "diagnostic_only",
            "berl_validation": {"status": "pass"},
        },
        artifact_kind="scientist.explanation_bundle",
    )

    assert report.verdict == "blocked"
    assert any("bounded-infidelity" in failure for failure in report.gate_failures)
    assert any("diagnostic-only" in failure for failure in report.gate_failures)


def test_preflight_blocks_required_fairness_refusal() -> None:
    report = build_phase5_validation_report(
        _ctx(),
        _state(high_impact=True),
        artifact_payload={"fairness_audit": {"status": "REFUSE"}},
        artifact_kind="scientist.fairness_audit_report",
    )

    assert report.verdict == "blocked"
    assert any(failure == "Fairness audit status is refuse." for failure in report.gate_failures)


def test_preflight_blocks_sensitivity_indices_without_uncertainty() -> None:
    report = build_phase5_validation_report(
        _ctx(),
        _state(),
        artifact_payload={
            "kind": "scientist.sensitivity_analysis_bundle",
            "bundle_id": "bundle-1",
            "indices": [{"name": "sobol_total", "estimate": 0.42}],
        },
        artifact_kind="scientist.sensitivity_analysis_bundle",
    )

    assert report.verdict == "blocked"
    assert any("lacks uncertainty evidence" in failure for failure in report.gate_failures)


def test_preflight_blocks_canonical_sensitivity_bundle_without_indices() -> None:
    report = build_phase5_validation_report(
        _ctx(),
        _state(),
        artifact_payload={
            "kind": "scientist.sensitivity_analysis_bundle",
            "bundle_id": "bundle-1",
            "indices": [],
        },
        artifact_kind="scientist.sensitivity_analysis_bundle",
    )

    assert report.verdict == "blocked"
    assert any("no normalized index list" in failure for failure in report.gate_failures)


def test_sensitivity_bundle_requires_uncertainty_or_explicit_blocking_reason() -> None:
    with pytest.raises(ValidationError):
        SensitivityAnalysisBundle(
            bundle_id="bundle-1",
            indices=[{"name": "sobol_total", "estimate": 0.42}],
        )

    bundle = SensitivityAnalysisBundle(
        bundle_id="bundle-1",
        indices=[{"name": "sobol_total", "estimate": 0.42, "ci": (0.2, 0.6)}],
    )
    assert bundle.indices[0].ci == (0.2, 0.6)


def test_preflight_blocks_strict_advisor_disagreement_states() -> None:
    report = build_phase5_validation_report(
        _ctx(),
        _state(phase5_require_advisor_consensus=True),
        artifact_payload={
            "cross_method_consensus": {
                "status": "not_comparable",
                "recommendation_allowed": False,
            }
        },
        artifact_kind="scientist.method_advisor_result",
    )

    assert report.verdict == "blocked"
    assert any("not_comparable" in failure for failure in report.gate_failures)


def test_preflight_blocks_missing_required_six_judge_stack() -> None:
    report = build_phase5_validation_report(
        _ctx(),
        _state(phase5_require_judge_verdict=True),
        artifact_payload={"summary": "candidate decision packet"},
        artifact_kind="scientist.decision_packet",
    )

    assert report.verdict == "blocked"
    assert any("six-judge" in failure.lower() for failure in report.gate_failures)


def test_preflight_loads_fairness_ref_from_cas(tmp_path) -> None:
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.ir.analytics.fairness_audit_report import (
        FairnessAuditReport,
        persist_fairness_audit_report,
    )

    store = FileSystemCAS(tmp_path)
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    fairness_ref = ArtifactRef.model_validate(
        persist_fairness_audit_report(
            ensure_ir_artifact_store(store),
            FairnessAuditReport(
                status="REFUSE",
                deployable=False,
                auto_decision_allowed=False,
                audit_id="synthetic-refusing-audit",
            ),
        ).model_dump(mode="json")
    )
    state = ExperimentState(
        run_id="phase5-test",
        params={"high_impact": True},
        artifacts_index={ARTIFACT_FAIRNESS_AUDIT_REPORT_REF: fairness_ref},
    )

    report = build_phase5_validation_report(
        ctx,
        state,
        artifact_payload={"requires_fairness_audit": True},
        artifact_kind="scientist.decision_packet",
    )

    assert report.verdict == "blocked"
    assert str(fairness_ref.artifact_id) in report.evidence_refs
    assert any(failure == "Fairness audit status is refuse." for failure in report.gate_failures)


@pytest.mark.parametrize(
    ("reference", "expected_error"),
    [
        ("not-an-artifact-ref", "explanation_bundle_ref_invalid"),
        ("sha256:" + "1" * 64, "explanation_bundle_ref_invalid"),
        (
            {
                "artifact_id": "sha256:" + "0" * 64,
                "kind": "scientist.other_bundle",
                "media_type": "application/json",
            },
            "explanation_bundle_ref_invalid",
        ),
        (
            {
                "artifact_id": "sha256:" + "0" * 64,
                "kind": "scientist.explanation_bundle",
                "media_type": "application/json",
            },
            "explanation_bundle_manifest_contract_mismatch",
        ),
        (
            {
                "artifact_id": "sha256:" + "0" * 64,
                "kind": "scientist.explanation_bundle",
                "media_type": "application/json",
                "manifest_profile_sha256": "sha256:not-a-digest",
            },
            "explanation_bundle_ref_invalid",
        ),
    ],
)
def test_preflight_refuses_present_malformed_explanation_refs(
    tmp_path, reference: object, expected_error: str
) -> None:
    store = FileSystemCAS(tmp_path)
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    report = build_phase5_validation_report(
        ctx,
        _state(),
        artifact_payload={ARTIFACT_EXPLANATION_BUNDLE_REF: reference},
        artifact_kind="scientist.decision_packet",
    )

    resolution = next(
        component
        for component in report.phase5_components
        if component.name == "evidence_resolution"
    )
    assert resolution.status == "blocked"
    failed_refs = report.normalized_payload["phase5"]["failed_evidence_refs"]
    assert any(expected_error in str(item) for item in failed_refs)


def test_preflight_blocks_underachieved_prior_sensitivity_tier() -> None:
    report = build_phase5_validation_report(
        _ctx(),
        _state(),
        artifact_payload={
            "prior_sensitivity": {
                "status": "PASS",
                "readiness_tier_requested": "ReadinessTier.TIER_2",
                "readiness_tier_achieved": "tier_1",
            }
        },
        artifact_kind="foundry.bayesian.posterior_result.v2",
    )

    assert report.verdict == "blocked"
    assert any("tier was not achieved" in failure for failure in report.gate_failures)


def test_analyst_publication_blocks_without_a_selected_judge_attempt(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    result = run_phase5_artifact_preflight(
        ctx,
        _state(),
        Phase5ArtifactPreflightInput(
            artifact_payload={"summary": "analyst packet"},
            artifact_kind="scientist.decision_packet",
            analyst_facing=True,
        ),
    )

    assert not result.publishable
    assert result.judge_verdict is None
    assert result.judge_verdict_ref is None
    assert result.validation_report.judge_verdict_ref is None
    assert any("judge" in failure.lower() for failure in result.validation_report.gate_failures)


def test_analyst_publication_blocks_unbound_attached_judge_verdict(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    result = run_phase5_artifact_preflight(
        ctx,
        _state(judge_verdict=_passing_judge_verdict()),
        Phase5ArtifactPreflightInput(
            artifact_payload={"summary": "analyst packet"},
            artifact_kind="scientist.decision_packet",
            analyst_facing=True,
        ),
    )

    assert not result.publishable
    assert result.judge_verdict_ref is None
    assert result.validation_report.verdict == "blocked"


def _present_berl_payload() -> dict[str, object]:
    """Portable real BERL contract input, independently bounded heldout evidence."""
    return {
        "kind": "scientist.explanation_bundle",
        "bundle_id": "portable-berl",
        "created_at": "2026-10-08T00:00:00Z",
        "faithfulness_claim": "bounded",
        "display_policy": "analyst_display",
        "model": {"model_id": "model", "model_hash": "sha256:fixture", "model_class": "linear"},
        "prediction": {
            "prediction_id": "p",
            "row_id": "r",
            "output_name": "y",
            "output_scale": "kg",
            "raw_score": 1.0,
        },
        "feature_context": {
            "feature_values_ref": "fixture:features",
            "feature_schema_version": "1",
        },
        "assumptions": {
            "perturbation_distribution": {"name": "portable"},
            "feature_dependence_policy": {"primary": "marginal"},
        },
        "methods": [
            {
                "method_id": "portable",
                "library": "fixture",
                "library_version": "1",
                "params": {"draws": 100},
                "infidelity": {
                    "point_estimate": 0.002,
                    "upper_bound": 0.01,
                    "confidence": 0.95,
                    "n_eval_perturbations": 100,
                    "residual_cap": 1.0,
                    "bound_type": "empirical_bernstein_heldout",
                    "evaluation_split": "heldout",
                },
            }
        ],
        "audit": {"code_version": "fixture@1", "random_seeds": [1]},
    }


def test_preflight_runs_present_berl_input_and_ignores_success_marker() -> None:
    payload = _present_berl_payload()
    report = build_phase5_validation_report(
        _ctx(), _state(), artifact_payload=payload, artifact_kind="scientist.explanation_bundle"
    )
    component = next(c for c in report.phase5_components if c.name == "explanation")
    assert component.status == "pass"
    payload["methods"][0]["infidelity"]["upper_bound"] = 0.9
    report = build_phase5_validation_report(
        _ctx(), _state(), artifact_payload=payload, artifact_kind="scientist.explanation_bundle"
    )
    assert any("p95_infidelity_upper_bound_exceeds_tolerance" in x for x in report.gate_failures)


@pytest.mark.parametrize(
    ("profile", "expected_violation"),
    [
        ("conditional_observational", "conditional_feature_law_unverified"),
        ("future_profile", "feature_dependence_profile_unsupported"),
    ],
)
def test_preflight_blocks_unadmitted_feature_dependence_profiles(
    profile: str,
    expected_violation: str,
) -> None:
    payload = _present_berl_payload()
    policy = payload["assumptions"]["feature_dependence_policy"]
    policy["primary"] = profile
    method = payload["methods"][0]
    method["assumptions"] = {"feature_dependence_policy": profile}
    payload["audit"]["artifact_refs"] = ["cas://self-attested/conditional-law-verified"]

    report = build_phase5_validation_report(
        _ctx(), _state(), artifact_payload=payload, artifact_kind="scientist.explanation_bundle"
    )
    component = next(c for c in report.phase5_components if c.name == "explanation")

    assert component.status == "blocked"
    assert any(expected_violation in blocker for blocker in component.blockers)


def test_preflight_preserves_typed_reason_for_malformed_profile() -> None:
    payload = _present_berl_payload()
    payload["assumptions"]["feature_dependence_policy"]["primary"] = {
        "profile": "conditional_observational"
    }

    report = build_phase5_validation_report(
        _ctx(), _state(), artifact_payload=payload, artifact_kind="scientist.explanation_bundle"
    )
    component = next(c for c in report.phase5_components if c.name == "explanation")

    assert component.status == "blocked"
    assert any("feature_dependence_profile_malformed" in item for item in component.blockers)


def test_preflight_blocks_method_policy_profile_mismatch() -> None:
    payload = _present_berl_payload()
    payload["methods"][0]["assumptions"] = {"feature_dependence_policy": "marginal_interventional"}

    report = build_phase5_validation_report(
        _ctx(), _state(), artifact_payload=payload, artifact_kind="scientist.explanation_bundle"
    )
    component = next(c for c in report.phase5_components if c.name == "explanation")

    assert component.status == "blocked"
    assert any("method_feature_dependence_profile_mismatch" in item for item in component.blockers)


@pytest.mark.parametrize("mutation", ["marker_only", "malformed", "unavailable"])
def test_preflight_fails_closed_when_actual_berl_validation_is_unavailable(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _present_berl_payload()
    if mutation == "marker_only":
        payload = {
            "kind": "scientist.explanation_bundle",
            "faithfulness_claim": "bounded",
            "berl_validation": {"status": "pass"},
        }
    elif mutation == "malformed":
        payload["model"] = {"model_id": "model"}
    else:
        import polisyos.scientist.validation.phase5_preflight as phase5

        monkeypatch.setattr(phase5, "_run_berl_validation", lambda record: None)
    report = build_phase5_validation_report(
        _ctx(), _state(), artifact_payload=payload, artifact_kind="scientist.explanation_bundle"
    )
    expected_reason = {
        "marker_only": "feature_dependence_profile_malformed",
        "malformed": "explanation_bundle_invalid",
        "unavailable": "validation unavailable or input malformed",
    }[mutation]
    assert any(expected_reason in x for x in report.gate_failures)


def test_publication_result_uses_same_persisted_owner_loaded_report(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.scientist.validation.phase5_preflight as phase5_preflight

    store = FileSystemCAS(tmp_path / "cas")
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    original_loader = phase5_preflight.load_validation_report
    loaded: list[tuple[object, object]] = []

    def observe_owner_load(store_arg, ref_arg):
        report_arg = original_loader(store_arg, ref_arg)
        loaded.append((ref_arg, report_arg))
        return report_arg

    monkeypatch.setattr(phase5_preflight, "load_validation_report", observe_owner_load)
    result = run_phase5_artifact_preflight(
        ctx,
        _state(judge_verdict=_passing_judge_verdict()),
        Phase5ArtifactPreflightInput(
            artifact_payload={"summary": "analyst packet"},
            artifact_kind="scientist.decision_packet",
            analyst_facing=True,
        ),
    )

    assert not result.publishable
    assert len(loaded) == 1
    loaded_ref, loaded_report = loaded[0]
    assert loaded_ref == result.validation_ref
    assert result.validation_report is loaded_report
    assert result.readiness == loaded_report.readiness
    assert result.publishable == (
        loaded_report.verdict not in {"fail", "blocked"}
        and loaded_report.readiness not in {"restricted", "blocked"}
    )


@pytest.mark.parametrize("corruption", ["missing_profile", "foreign_schema"])
def test_preflight_refuses_fairness_evidence_with_an_invalid_selected_profile(
    tmp_path, corruption: str
) -> None:
    """Phase 5 must resolve the owner-selected manifest, not just identical bytes."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.ir.analytics.fairness_audit_report import (
        FairnessAuditReport,
        FairnessAuditReportRef,
        load_fairness_audit_report,
        persist_fairness_audit_report,
    )

    store = FileSystemCAS(tmp_path)
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    selected = ArtifactRef.model_validate(
        persist_fairness_audit_report(
            ensure_ir_artifact_store(store),
            FairnessAuditReport(
                status="PASS",
                deployable=True,
                auto_decision_allowed=True,
                audit_id="synthetic-audit",
            ),
        ).model_dump(mode="json")
    )
    assert selected.manifest_profile_sha256 is not None
    state = ExperimentState(
        run_id="phase5-test",
        params={"high_impact": True},
        artifacts_index={ARTIFACT_FAIRNESS_AUDIT_REPORT_REF: selected},
    )
    report = build_phase5_validation_report(
        ctx,
        state,
        artifact_payload={"requires_fairness_audit": True},
        artifact_kind="scientist.decision_packet",
    )
    assert report.verdict == "pass"
    assert store.verify(selected).ok

    if corruption == "missing_profile":
        invalid = selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
        assert not store.verify(invalid).ok
    else:
        manifest = store.get_manifest(selected)
        invalid = store.put_bytes(
            store.get_bytes(selected),
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=SchemaInfo(name="foreign.fairness_audit_report", version="1.0"),
                canon=manifest.canon,
            ),
            return_selected_profile=True,
        )
        assert store.verify(invalid).ok
        with pytest.raises(ValueError):
            load_fairness_audit_report(
                ensure_ir_artifact_store(store),
                FairnessAuditReportRef.model_validate(invalid.model_dump(mode="json")),
            )
    assert invalid.artifact_id == selected.artifact_id
    assert invalid.manifest_profile_sha256 != selected.manifest_profile_sha256
    changed = state.model_copy(deep=True)
    changed.artifacts_index[ARTIFACT_FAIRNESS_AUDIT_REPORT_REF] = invalid
    refused = build_phase5_validation_report(
        ctx,
        changed,
        artifact_payload={"requires_fairness_audit": True},
        artifact_kind="scientist.decision_packet",
    )
    assert refused.verdict == "blocked"
    assert any(
        component.name == "evidence_resolution" and component.status == "blocked"
        for component in refused.phase5_components
    )


def test_preflight_does_not_discard_a_conflicting_same_role_report(tmp_path) -> None:
    """A second selected report cannot be hidden by an earlier role with the same name."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.ir.analytics.fairness_audit_report import (
        FairnessAuditReport,
        persist_fairness_audit_report,
    )

    store = FileSystemCAS(tmp_path)
    ir_store = ensure_ir_artifact_store(store)

    def persist(status: Literal["PASS", "REFUSE"], audit_id: str) -> ArtifactRef:
        audit = FairnessAuditReport(
            status=status,
            deployable=status == "PASS",
            auto_decision_allowed=status == "PASS",
            audit_id=audit_id,
        )
        return ArtifactRef.model_validate(
            persist_fairness_audit_report(ir_store, audit).model_dump(mode="json")
        )

    passing = persist("PASS", "synthetic-passing-audit")
    refusing = persist("REFUSE", "synthetic-refusing-audit")
    assert store.verify(passing).ok and store.verify(refusing).ok
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    state = ExperimentState(
        run_id="phase5-conflicting-fairness",
        params={"high_impact": True},
        artifacts_index={ARTIFACT_FAIRNESS_AUDIT_REPORT_REF: passing},
    )
    passing_report = build_phase5_validation_report(
        ctx,
        state,
        artifact_payload={"requires_fairness_audit": True},
        artifact_kind="scientist.decision_packet",
    )
    assert passing_report.verdict == "pass"

    state.reports_index[ARTIFACT_FAIRNESS_AUDIT_REPORT_REF] = refusing
    conflicted = build_phase5_validation_report(
        ctx,
        state,
        artifact_payload={"requires_fairness_audit": True},
        artifact_kind="scientist.decision_packet",
    )
    assert conflicted.verdict == "blocked"


def test_preflight_blocks_required_fairness_when_store_is_unavailable(tmp_path) -> None:
    """A selected ref is not evidence that the required audit was read."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.ir.analytics.fairness_audit_report import (
        FairnessAuditReport,
        persist_fairness_audit_report,
    )

    store = FileSystemCAS(tmp_path)
    selected = ArtifactRef.model_validate(
        persist_fairness_audit_report(
            ensure_ir_artifact_store(store),
            FairnessAuditReport(
                status="PASS",
                deployable=True,
                auto_decision_allowed=True,
                audit_id="synthetic-audit",
            ),
        ).model_dump(mode="json")
    )
    state = ExperimentState(
        run_id="phase5-unavailable-store",
        params={"high_impact": True},
        artifacts_index={ARTIFACT_FAIRNESS_AUDIT_REPORT_REF: selected},
    )
    context = cast("ExecutionContext", SimpleNamespace(store=store))
    baseline = build_phase5_validation_report(
        context,
        state,
        artifact_payload={"requires_fairness_audit": True},
        artifact_kind="scientist.decision_packet",
    )
    assert baseline.verdict == "pass"

    unavailable = build_phase5_validation_report(
        cast("ExecutionContext", SimpleNamespace(store=None)),
        state,
        artifact_payload={"requires_fairness_audit": True},
        artifact_kind="scientist.decision_packet",
    )
    assert unavailable.verdict == "blocked"


def test_preflight_consumes_the_real_selected_shift_report_readiness(tmp_path) -> None:
    """A persisted typed shift downgrade must reach the preflight consumer."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.ir.analytics.shift_diagnostics import (
        CalibrationInfo,
        ShiftComponent,
        ShiftDiagnosticReport,
        build_readiness_impact,
        load_shift_diagnostic_report,
        persist_shift_diagnostic_report,
    )
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_SHIFT_DIAGNOSTIC_REPORT_REF

    store = FileSystemCAS(tmp_path)
    ir_store = ensure_ir_artifact_store(store)
    clear = ShiftComponent(status="not_detected", severity_bucket="none")
    report = ShiftDiagnosticReport(
        report_id="synthetic-shift",
        generated_at="2026-01-01T00:00:00Z",
        model_id="synthetic-model",
        model_version="1",
        task_type="classification",
        modality="tabular_administrative",
        training_reference_id="synthetic-training",
        current_window_id="synthetic-window",
        current_window_start="2026-01-01",
        current_window_end="2026-01-31",
        n_reference=10,
        n_current=10,
        label_availability="none",
        power_status="sufficient",
        calibration=CalibrationInfo(
            operating_characteristic_library_version="synthetic",
            calibration_id="synthetic",
            reference_comparison_type="training_vs_current",
            target_report_fpr=0.05,
            null_regime="synthetic",
            power_summary={"available": True},
        ),
        schema_shift=ShiftComponent(status="confirmed", severity_bucket="severe"),
        marginal_shift=clear,
        support_shift=clear,
        label_prior_shift=clear,
        concept_shift=ShiftComponent(
            status="unassessable_until_labels", severity_bucket="unassessable"
        ),
        prediction_output_shift=clear,
        harmful_shift_risk=clear,
        global_verdict="schema_shift",
        detector_results=(),
        readiness_impact=build_readiness_impact(base_readiness="ready", downgrade_level=3),
        human_summary="Synthetic severe schema shift.",
        limitations=(),
        recommended_next_checks=(),
    )
    selected_ir = persist_shift_diagnostic_report(ir_store, report)
    assert load_shift_diagnostic_report(
        ir_store, selected_ir
    ).readiness_impact.resulting_readiness == ("blocked")
    selected = ArtifactRef.model_validate(selected_ir.model_dump(mode="json"))
    context = cast("ExecutionContext", SimpleNamespace(store=store))
    state = ExperimentState(
        run_id="phase5-shift-readiness",
        artifacts_index={ARTIFACT_SHIFT_DIAGNOSTIC_REPORT_REF: selected},
    )
    preflight = build_phase5_validation_report(
        context,
        state,
        artifact_payload={"summary": "synthetic candidate"},
        artifact_kind="scientist.decision_packet",
    )
    shift = next(
        component for component in preflight.phase5_components if component.name == "shift"
    )
    assert shift.status == "blocked"
    assert preflight.verdict == "blocked"


@pytest.mark.parametrize("placement", ["params", "archive_payload"])
def test_phase5_does_not_reissue_a_six_judge_verdict_from_unbound_history(
    tmp_path, placement: str
) -> None:
    """A valid-shaped historical verdict is not an owner-selected current attempt."""
    store = FileSystemCAS(tmp_path)
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    fake = _passing_judge_verdict()
    params = (
        {"reported_policy_promotion_history": [{"params": {"judge_verdict": fake}}]}
        if placement == "params"
        else {}
    )
    payload: dict[str, object] = {"summary": "synthetic candidate"}
    if placement == "archive_payload":
        payload["reported_history"] = {"judge_verdict": fake}
    result = run_phase5_artifact_preflight(
        ctx,
        _state(**params),
        Phase5ArtifactPreflightInput(
            artifact_payload=payload,
            artifact_kind="scientist.decision_packet",
            analyst_facing=True,
        ),
    )
    assert not result.publishable
    assert result.judge_verdict is None
    assert result.judge_verdict_ref is None


def test_analyst_report_does_not_admit_a_caller_supplied_judge_marker() -> None:
    """Six plausible pass records cannot substitute for an owner-selected attempt."""
    report = build_phase5_validation_report(
        _ctx(),
        _state(),
        artifact_payload={
            "judge_verdict": _passing_judge_verdict(),
            "judge_verdict_ref": "sha256:" + "a" * 64,
        },
        artifact_kind="scientist.decision_packet",
        analyst_facing=True,
    )
    judges = next(
        component for component in report.phase5_components if component.name == "six_judges"
    )
    assert judges.status == "blocked"
    assert report.verdict == "blocked"
    assert report.judge_verdict_ref is None
    assert report.normalized_payload["phase5"]["judge_selection_status"] == "not_established"
    assert report.normalized_payload["phase5"]["reported_judge_verdict_ref"] == "sha256:" + "a" * 64


def test_historical_judges_do_not_activate_a_current_optional_check() -> None:
    """An archived verdict remains history even for a non-publication diagnostic."""
    report = build_phase5_validation_report(
        _ctx(),
        _state(),
        artifact_payload={"reported_history": {"judge_verdict": _passing_judge_verdict()}},
        artifact_kind="scientist.decision_packet",
        analyst_facing=False,
    )
    judges = next(
        component for component in report.phase5_components if component.name == "six_judges"
    )
    assert judges.status == "not_applicable"
    assert judges.required is False
