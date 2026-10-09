from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.analytics.sensitivity import SensitivityAnalysisBundle
from polisyos.ir.governance.validation import Phase5GateComponent, ValidationReport
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_FAIRNESS_AUDIT_REPORT_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.phase5_preflight import (
    Phase5ArtifactPreflightInput,
    Phase5ValidationBlocked,
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
    store = FileSystemCAS(tmp_path)
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    fairness_ref = store.put_json(
        {
            "kind": "scientist.fairness_audit_report",
            "status": "REFUSE",
            "deployable": False,
            "auto_decision_allowed": False,
            "audit_id": "audit-1",
        },
        PutOptions(
            kind="scientist.fairness_audit_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.fairness_audit_report", version="1.0"),
        ),
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


def test_analyst_publication_persists_blocking_judge_verdict_when_missing_input(tmp_path) -> None:
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
    assert result.judge_verdict_ref is not None
    assert result.validation_report.judge_verdict_ref == str(result.judge_verdict_ref.artifact_id)
    assert any("judge" in failure.lower() for failure in result.validation_report.gate_failures)


def test_analyst_publication_accepts_attached_full_judge_verdict(tmp_path) -> None:
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

    assert result.publishable
    assert result.judge_verdict_ref is not None
    assert result.validation_report.verdict == "pass"


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
