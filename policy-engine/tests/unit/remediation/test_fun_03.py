"""FUN-03 regression witnesses for calibration and promotion boundaries."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir import UncertaintyType
from polisyos.scientist.methods.search.calibration_report import (
    FunnelCalibrationReport,
    load_funnel_calibration_report,
    persist_funnel_calibration_report,
)
from polisyos.scientist.methods.search.funnel.level6_promotion import (
    Level6PromotionStage,
)
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
    UncertaintyEnvelope,
    UncertaintyEstimate,
)
from polisyos.scientist.methods.search.stages import CorrelationTracker
from polisyos.scientist.methods.search.voi_scheduler import PredictiveVOIScheduler
from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as runtime
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def _stage(
    level: int,
    result: FunnelStageResult,
) -> MagicMock:
    stage = MagicMock(spec=FunnelStage)
    stage.fidelity_level = level
    stage.stage_name = result.stage_name
    stage.estimated_cost_usd = 0.1
    stage.evaluate.return_value = result
    return stage


def _envelope(*, statistical: float, model: float) -> UncertaintyEnvelope:
    envelope = UncertaintyEnvelope.unknown(source="FUN-03 witness")
    return envelope.with_update(
        UncertaintyType.STATISTICAL,
        UncertaintyEstimate(
            level=statistical,
            source="same-scope statistical witness",
            quantification_method="test_measurement",
            is_reducible=True,
        ),
    ).with_update(
        UncertaintyType.MODEL,
        UncertaintyEstimate(
            level=model,
            source="independent model-risk witness",
            quantification_method="test_measurement",
            is_reducible=True,
        ),
    )


def _stage_result(level: int, envelope: UncertaintyEnvelope) -> FunnelStageResult:
    return FunnelStageResult(
        policy_candidate={"candidate_id": "fun-03"},
        objective_value=0.5,
        is_promising=True,
        stage_name=f"L{level}",
        uncertainty_envelope=envelope,
        fidelity_level=level,
    )


def _uncertainty_level(payload: dict[str, Any], uncertainty_type: UncertaintyType) -> float:
    return float(payload["uncertainties"][uncertainty_type.value]["level"])


def _artifact_ref(hex_digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{hex_digit * 64}",
        kind="test",
        media_type="application/json",
    )


def test_same_scope_refinement_is_current_while_history_keeps_unknown_risk() -> None:
    historical_unknown = UncertaintyEnvelope.unknown(source="deterministic gate")
    refined = _envelope(statistical=0.1, model=0.8)

    orchestrator = FunnelOrchestrator(
        [
            _stage(0, _stage_result(0, historical_unknown)),
            _stage(4, _stage_result(4, refined)),
        ]
    )
    ticket = orchestrator.submit({"candidate_id": "fun-03"}, {"domain": "same-scope"})
    outcome = orchestrator.advance(ticket, policy="full")

    assert outcome.uncertainty_envelope.uncertainties[UncertaintyType.STATISTICAL].level == 1.0
    current = outcome.final_result
    assert current is not None
    assert current.uncertainty_envelope.uncertainties[
        UncertaintyType.STATISTICAL
    ].level == pytest.approx(0.1)
    assert current.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == pytest.approx(
        0.8
    )
    assert (
        _uncertainty_level(
            current.feedback["uncertainty_historical_max"], UncertaintyType.STATISTICAL
        )
        == 1.0
    )
    assert _uncertainty_level(
        current.feedback["uncertainty_current"], UncertaintyType.STATISTICAL
    ) == pytest.approx(0.1)
    assert _uncertainty_level(
        outcome.stage_results[4].feedback["uncertainty_current"], UncertaintyType.STATISTICAL
    ) == pytest.approx(0.1)


@pytest.mark.parametrize(
    "scope_key",
    ["subject_id", "value_slot", "input_signature", "procedure_id", "population_scope"],
)
def test_scope_identity_prevents_cross_scope_continuation(scope_key: str) -> None:
    historical_unknown = UncertaintyEnvelope.unknown(source="scope A not assessed")
    refined = _envelope(statistical=0.1, model=0.8)
    stage = _stage(4, _stage_result(4, historical_unknown))
    stage.evaluate.side_effect = [
        _stage_result(4, historical_unknown),
        _stage_result(4, refined),
    ]
    orchestrator = FunnelOrchestrator([stage])
    candidate = {"candidate_id": "fun-03"}
    scope_a = {
        "subject_id": "subject-a",
        "value_slot": "value-a",
        "input_signature": "inputs-a",
        "procedure_id": "procedure-a",
        "population_scope": "population-a",
    }
    scope_b = {**scope_a, scope_key: f"{scope_a[scope_key]}-other"}

    ticket_a = orchestrator.submit(candidate, scope_a)
    outcome_a = orchestrator.advance(ticket_a, policy="full")
    ticket_b = orchestrator.submit(candidate, scope_b)

    assert ticket_b is not ticket_a
    assert ticket_b.stage_results == {}
    outcome_b = orchestrator.advance(ticket_b, policy="full")
    assert stage.evaluate.call_count == 2
    assert outcome_a.uncertainty_envelope.uncertainties[UncertaintyType.STATISTICAL].level == 1.0
    assert outcome_b.final_result is not None
    assert outcome_b.final_result.uncertainty_envelope.uncertainties[
        UncertaintyType.STATISTICAL
    ].level == pytest.approx(0.1)


def test_empty_tracker_has_one_explicit_not_established_routing_state() -> None:
    tracker = CorrelationTracker()

    metrics = tracker.compute_metrics()

    assert metrics["sample_count"] == 0
    assert metrics["calibration_state"] == "not_established"
    assert metrics["routing_mode"] == tracker.routing_mode()
    assert metrics["routing_mode"] == "no_promotion"
    assert metrics["promotion_ban_active"] is False
    assert tracker.drift_alerts() == []


def test_persisted_empty_report_fails_closed_over_stale_normal_mode(tmp_path) -> None:
    state = ExperimentState(run_id="fun-03-report-run")
    store = FileSystemCAS(tmp_path / ".polisyos")
    report = FunnelCalibrationReport(
        current_mode="normal",
        routing_health={"sample_count": 0, "promotion_ban_active": False},
    )
    report_ref = persist_funnel_calibration_report(store, report)
    loaded_report = load_funnel_calibration_report(store, report_ref)

    metrics = runtime._resolve_runtime_correlation_metrics(state, loaded_report)

    assert metrics["sample_count"] == 0
    assert metrics["calibration_state"] == "not_established"
    assert metrics["routing_mode"] == "no_promotion"
    assert (
        runtime._resolve_degradation_mode(
            state,
            calibration_report=loaded_report,
        )
        == "no_promotion"
    )


def test_statistically_bad_tracker_is_observed_drift_not_empty_state() -> None:
    tracker = CorrelationTracker(drift_window_size=5)
    for index in range(5):
        tracker.record(
            MagicMock(
                predicted_score=float(index), objective_value=float(index), is_promising=True
            ),
            MagicMock(
                actual_score=float(5 - index),
                objective_value=float(5 - index),
                is_promising=True,
            ),
            f"fun-03-{index}",
        )

    metrics = tracker.compute_metrics()

    assert metrics["calibration_state"] == "observed"
    assert metrics["sample_count"] == 5
    assert metrics["routing_mode"] == "no_promotion"
    assert tracker.promotion_ban_active() is True


def test_level6_degradation_preflight_reads_existing_payload_without_runner() -> None:
    calls: list[str] = []
    payload = {"decision": "complete", "reason": "already calculated"}

    def runner(_candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, str]:
        calls.append("runner")
        return {"decision": "complete"}

    result = Level6PromotionStage(promotion_runner=runner).evaluate(
        {"candidate_id": "fun-03"},
        {
            "funnel_degradation_mode": "no_promotion",
            "promotion_result": payload,
        },
    )

    assert calls == []
    assert result.terminal_action == "defer_to_human"
    assert result.feedback["promotion_result"] == payload
    assert result.feedback["promotion_result_read_only"] is True


def test_level6_owner_recheck_happens_before_effectful_runner() -> None:
    calls: list[str] = []

    def runner(_candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, str]:
        calls.append("runner")
        return {"decision": "complete"}

    result = Level6PromotionStage(
        promotion_runner=runner,
        promotion_owner_recheck=lambda _candidate, _context: False,
    ).evaluate({"candidate_id": "fun-03"}, {"funnel_degradation_mode": "normal"})

    assert calls == []
    assert result.terminal_action == "defer_to_human"
    assert any(
        card.failure_type == "promotion_owner_recheck_failed" for card in result.failure_cards
    )


def test_level6_normal_path_bool_preflight_cannot_admit_runner_effects() -> None:
    """A bool preflight cannot replace the missing promotion-purpose permit port."""
    calls: list[str] = []

    def recheck(_candidate: dict[str, Any], _context: dict[str, Any]) -> bool:
        calls.append("recheck")
        return True

    def runner(_candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, str]:
        calls.append("runner")
        return {"decision": "complete"}

    stage = Level6PromotionStage(
        promotion_runner=runner,
        promotion_owner_recheck=recheck,
    )
    result = stage.evaluate({"candidate_id": "fun-03"}, {"funnel_degradation_mode": "normal"})

    assert calls == []
    assert result.terminal_action == "defer_to_human"
    assert result.feedback["promotion_admission_status"] == "bridge_missing"
    assert result.feedback["promotion_required_contract"] == (
        "owner_issued_promotion_permit_and_revoke_serialized_commit"
    )
    # Completion here interprets a prepared result; it grants no callback/write authority.
    prepared = {"decision": "complete", "reason": "already calculated"}
    read_only = stage.evaluate(
        {"candidate_id": "fun-03"},
        {"funnel_degradation_mode": "normal", "promotion_result": prepared},
    )
    assert calls == []
    assert read_only.terminal_action == "complete"
    assert read_only.feedback["promotion_result_read_only"] is True
    assert read_only.feedback["promotion_result"] == prepared


def test_production_owner_recheck_requires_explicit_write_permission(monkeypatch) -> None:
    candidate_ref = _artifact_ref("a")
    evidence_ref = _artifact_ref("b")
    state = ExperimentState(run_id="fun-03-owner-run")

    class _EvidenceBundle:
        def __init__(self, bound_candidate_ref: ArtifactRef) -> None:
            self.candidate_ref = bound_candidate_ref
            self.compatible_runs: list[str] = []

        def assert_compatible_with_run(self, run_id: str) -> None:
            self.compatible_runs.append(run_id)

    bundle = _EvidenceBundle(candidate_ref)
    monkeypatch.setattr(runtime, "load_promotion_evidence_bundle", lambda _store, _ref: bundle)
    context = {
        "funnel_degradation_mode": "normal",
        "policy_candidate_ref": candidate_ref,
        "promotion_evidence_bundle_ref": evidence_ref,
    }
    ctx = MagicMock(store=MagicMock())

    assert runtime._policy_promotion_owner_recheck(ctx, state, candidate_ref, context) is False
    assert (
        runtime._policy_promotion_owner_recheck(
            ctx,
            state,
            candidate_ref,
            {**context, "promotion_write_allowed": False},
        )
        is False
    )
    assert (
        runtime._policy_promotion_owner_recheck(
            ctx,
            state,
            candidate_ref,
            {**context, "promotion_write_allowed": True},
        )
        is True
    )
    assert bundle.compatible_runs == [state.run_id]


def test_orchestrator_honors_persisted_no_promotion_projection_without_tracker() -> None:
    calls: list[str] = []

    def runner(_candidate: dict[str, Any], _context: dict[str, Any]) -> dict[str, str]:
        calls.append("runner")
        return {"decision": "complete"}

    orchestrator = FunnelOrchestrator([Level6PromotionStage(promotion_runner=runner)])
    ticket = orchestrator.submit(
        {"candidate_id": "fun-03"},
        {
            "funnel_degradation_mode": "no_promotion",
            "correlation_metrics": {
                "sample_count": 0,
                "calibration_state": "not_established",
                "routing_mode": "no_promotion",
            },
        },
    )
    outcome = orchestrator.advance(ticket, policy="full")

    assert calls == []
    assert outcome.degradation_mode == "no_promotion"
    assert outcome.final_action == "defer_to_human"


class _ControlledEvaluationVector:
    def __init__(self, metadata: dict[str, Any] | None = None) -> None:
        self.metadata = dict(metadata or {})
        self.feasible = True
        self.blocking_reasons: list[str] = []

    def model_copy(self, *, update: dict[str, Any]) -> _ControlledEvaluationVector:
        return _ControlledEvaluationVector(update.get("metadata", self.metadata))

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        del mode
        return {
            "feasible": self.feasible,
            "blocking_reasons": list(self.blocking_reasons),
            "metadata": dict(self.metadata),
        }


def _install_actual_runtime_node_dependencies(
    monkeypatch,
    tmp_path,
    *,
    mode: str,
    revoke_legacy_marker_on_callback: bool = False,
) -> dict[str, Any]:
    """Stub non-funnel boundaries while retaining node, L4, orchestrator, and L6."""
    run_id = f"fun-03-node-{mode}"
    store = FileSystemCAS(tmp_path / run_id)
    ctx = SimpleNamespace(
        store=store,
        eval_safety_execution_context=None,
        eval_safety_verifier=None,
    )
    state = ExperimentState(
        run_id=run_id,
        params={"policy_mode": True},
        artifacts_index={},
        reports_index={},
    )
    candidate = PolicyCandidateSchema.model_construct(
        candidate_id="candidate_fun_03",
        metadata={"domain": "controlled-test"},
    )
    candidate_ref = _artifact_ref("a")
    runtime_request = SimpleNamespace(
        candidate=candidate,
        candidate_ref=candidate_ref,
        uncertainty_envelope=_envelope(statistical=0.3, model=0.4),
        governance_report=None,
        causal_report=None,
        distributional_report=None,
        cross_graph_profile=None,
        evidence_sources=None,
        simulation_metrics={"policy_value": 0.2},
        ambiguity_certificate=None,
        ambiguity_certificate_ref=None,
    )
    backend_calls: list[str] = []
    runner_calls: list[str] = []
    owner_checks: list[bool] = []
    promotion_writes: list[dict[str, Any]] = []
    selection_vector = _ControlledEvaluationVector()
    provenance = SimpleNamespace(
        backend_kind="controlled_test_backend",
        promotable_source=True,
        degradation_mode=None,
        source_components=(),
        notes=(),
    )
    selection_artifact = SimpleNamespace(
        evaluation_vector=selection_vector,
        provenance=provenance,
    )

    class _Backend:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def evaluate(self, _candidate: Any, *, fidelity: str, **_kwargs: Any) -> Any:
            backend_calls.append(fidelity)
            return SimpleNamespace(
                simulation_results={"gdp_change": 0.2, "gov_balance": 0.0},
                evaluation_vector=_ControlledEvaluationVector(),
                provenance=provenance,
            )

    class _PassingStage:
        def __init__(self, fidelity_level: int) -> None:
            self._fidelity_level = fidelity_level

        @property
        def fidelity_level(self) -> int:
            return self._fidelity_level

        @property
        def stage_name(self) -> str:
            return f"controlled_L{self._fidelity_level}"

        @property
        def estimated_cost_usd(self) -> float:
            return 0.01

        def evaluate(
            self,
            candidate_payload: dict[str, Any],
            _context: dict[str, Any],
        ) -> FunnelStageResult:
            return FunnelStageResult(
                policy_candidate=candidate_payload,
                objective_value=0.0,
                is_promising=True,
                stage_name=self.stage_name,
                uncertainty_envelope=UncertaintyEnvelope.unknown(
                    source="controlled pre/post-L4 stage"
                ),
                fidelity_level=self.fidelity_level,
                feedback={"verdict": "APPROVE"},
            )

    class _BenchmarkRegistry:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def record_evaluation(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def resolve_family_bundle(self, *_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                hidden_holdout_evaluation_ref=None,
                rotating_challenge_evaluation_refs=[],
            )

        def require_promotion_evidence(self, *_args: Any, **_kwargs: Any) -> list[str]:
            return []

        def record(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    voi_scheduler = PredictiveVOIScheduler()
    strategic_output = SimpleNamespace(
        strategic_scm_ref=None,
        strategic_response_bundle_ref=None,
        strategic_response_summary=None,
        warnings=(),
    )
    original_owner_recheck = runtime._policy_promotion_owner_recheck
    original_promotion_runner = runtime._policy_promotion_runner

    def observe_owner_recheck(
        owner_ctx: Any,
        owner_state: ExperimentState,
        owner_candidate_ref: ArtifactRef,
        owner_context: dict[str, Any],
    ) -> bool:
        owner_checks.append(owner_context.get("promotion_write_allowed") is True)
        return original_owner_recheck(
            owner_ctx,
            owner_state,
            owner_candidate_ref,
            owner_context,
        )

    def observe_promotion_runner(
        owner_ctx: Any,
        owner_state: ExperimentState,
        owner_candidate: PolicyCandidateSchema,
        owner_candidate_ref: ArtifactRef,
        owner_context: dict[str, Any],
    ) -> Any:
        runner_calls.append("runner")
        return original_promotion_runner(
            owner_ctx,
            owner_state,
            owner_candidate,
            owner_candidate_ref,
            owner_context,
        )

    def extract_level4_evaluation(
        _owner_ctx: Any,
        *,
        candidate_ref: ArtifactRef,
        context: dict[str, Any],
    ) -> tuple[object, ArtifactRef]:
        if revoke_legacy_marker_on_callback:
            context["promotion_write_allowed"] = False
        return object(), candidate_ref

    replacements: dict[str, Any] = {
        "_is_policy_mode": lambda _state: True,
        "resolve_policy_runtime_request": lambda *_args: runtime_request,
        "_resolve_policy_runtime_source_statuses": lambda **_kwargs: {},
        "ProductionPolicyEvaluationBackend": _Backend,
        "_world_model_record_from_state": lambda _state: None,
        "policy_runtime_input_signature": lambda **_kwargs: "controlled-input-signature",
        "build_policy_runtime_evaluation": lambda *_args, **_kwargs: selection_artifact,
        "persist_policy_evaluation_vector": lambda *_args, **_kwargs: _artifact_ref("b"),
        "_resolve_existing_strategic_output": lambda _state: strategic_output,
        "_build_runtime_abstraction_metadata": lambda *_args, **_kwargs: {},
        "build_selection_benchmark_evaluation": lambda **_kwargs: SimpleNamespace(
            loop_id="loop_fun_03"
        ),
        "persist_benchmark_evaluation": lambda *_args, **_kwargs: _artifact_ref("c"),
        "_resolve_benchmark_scope": lambda **_kwargs: {
            "artifact_family": "controlled_policy",
            "claim_mode": "estimation",
            "query_type": "policy",
            "estimator_name": "controlled",
            "readiness_target": "deployment_ready",
        },
        "BenchmarkRegistry": _BenchmarkRegistry,
        "_load_existing_promotion_evidence": lambda *_args, **_kwargs: None,
        "_register_runtime_benchmark_inputs": lambda *_args, **_kwargs: None,
        "_run_and_register_phase_d4_challenge_suites": lambda *_args, **_kwargs: ([], [], ()),
        "_dedupe_phase_d4_rotating_refs": lambda _ctx, refs: list(refs),
        "_load_benchmark_if_present": lambda *_args, **_kwargs: None,
        "_ensure_calibration_report": lambda *_args, **_kwargs: _artifact_ref("d"),
        "load_funnel_calibration_report": lambda *_args, **_kwargs: SimpleNamespace(
            current_mode=mode,
            routing_health={},
        ),
        "_ensure_platform_meta_report": lambda *_args, **_kwargs: None,
        "_ensure_stress_test_report": lambda *_args, **_kwargs: None,
        "_resolve_replay_bundle_ref": lambda *_args, **_kwargs: None,
        "_resolve_degradation_mode": lambda *_args, **_kwargs: mode,
        "_resolve_runtime_correlation_metrics": lambda *_args, **_kwargs: {
            "sample_count": 0,
            "calibration_state": "not_established",
            "routing_mode": mode,
        },
        "_resolve_runtime_correlation_tracker": lambda *_args, **_kwargs: None,
        "load_predictive_voi_scheduler": lambda *_args, **_kwargs: voi_scheduler,
        "persist_predictive_voi_scheduler": lambda *_args, **_kwargs: None,
        "_resolve_runtime_policy_evaluation": lambda *args, **kwargs: (
            kwargs["fallback"],
            kwargs["candidate_ref"],
        ),
        "persist_voi_run_report": lambda *_args, **_kwargs: _artifact_ref("e"),
        "_candidate_search_payload": lambda candidate_arg, _state: {
            "candidate_id": candidate_arg.candidate_id,
            "metadata": dict(candidate_arg.metadata),
        },
        "Level0StaticValidator": lambda: _PassingStage(0),
        "Level1CheapHeuristic": lambda: _PassingStage(1),
        "Level2CausalPlausibility": lambda: _PassingStage(2),
        "Level3MediumFidelity": lambda **_kwargs: _PassingStage(3),
        "Level5RefutationGovernanceStage": lambda **_kwargs: _PassingStage(5),
        "_policy_promotion_owner_recheck": observe_owner_recheck,
        "_policy_promotion_runner": observe_promotion_runner,
        "_extract_level4_policy_evaluation": extract_level4_evaluation,
        "run_promotion_with_evidence": lambda **kwargs: promotion_writes.append(kwargs)
        or {"decision": "complete"},
    }
    for name, value in replacements.items():
        monkeypatch.setattr(runtime, name, value)

    return {
        "ctx": ctx,
        "state": state,
        "candidate": candidate,
        "candidate_ref": candidate_ref,
        "backend_calls": backend_calls,
        "runner_calls": runner_calls,
        "owner_checks": owner_checks,
        "promotion_writes": promotion_writes,
        "store": store,
    }


@pytest.mark.parametrize("mode", ["no_promotion", "reduced_judge", "auto_cap"])
def test_run_policy_blueprint_execute_caps_promotion_after_real_l4_candidate_work(
    tmp_path,
    monkeypatch,
    mode: str,
) -> None:
    harness = _install_actual_runtime_node_dependencies(
        monkeypatch,
        tmp_path,
        mode=mode,
    )

    outcome = runtime.RunPolicyBlueprintRuntimeNode().execute(
        harness["ctx"],
        harness["state"],
    )

    assert outcome.status == "ok"
    assert harness["backend_calls"] == ["full"]
    assert harness["runner_calls"] == []
    assert harness["promotion_writes"] == []
    assert outcome.state.params["_funnel_outcome"]["final_action"] == "defer_to_human"
    level6 = outcome.state.params["_funnel_outcome"]["stage_results"]["6"]
    assert level6["terminal_action"] == "defer_to_human"
    assert "degraded_mode_promotion_cap" in {
        card["failure_type"] for card in level6["failure_cards"]
    }
    assert (
        outcome.state.params["_funnel_outcome"]["stage_results"]["4"]["feedback"][
            "policy_runtime_fidelity"
        ]
        == "full"
    )


def test_run_policy_blueprint_execute_refuses_bool_admission_after_real_l4_work(
    tmp_path,
    monkeypatch,
) -> None:
    """Typed permit/serialized writer positive is UNRUN; legacy markers admit zero effects."""
    harness = _install_actual_runtime_node_dependencies(
        monkeypatch,
        tmp_path,
        mode="normal",
        revoke_legacy_marker_on_callback=True,
    )

    outcome = runtime.RunPolicyBlueprintRuntimeNode().execute(
        harness["ctx"],
        harness["state"],
    )

    assert outcome.status == "ok"
    assert harness["backend_calls"] == ["full"]
    assert harness["runner_calls"] == []
    assert harness["owner_checks"] == []
    assert harness["promotion_writes"] == []
    assert outcome.state.params["_funnel_outcome"]["final_action"] == "defer_to_human"
    assert "policy_promotion_result" not in outcome.state.params
    level6 = outcome.state.params["_funnel_outcome"]["stage_results"]["6"]
    assert level6["feedback"]["promotion_admission_status"] == "bridge_missing"
    assert level6["feedback"]["promotion_required_contract"] == (
        "owner_issued_promotion_permit_and_revoke_serialized_commit"
    )
