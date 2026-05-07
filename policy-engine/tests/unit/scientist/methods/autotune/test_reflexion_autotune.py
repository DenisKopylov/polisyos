from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.failure_card import (
    FailureCard,
    FailureSeverity,
    FailureSource,
    RemediationTarget,
)
from polisyos.scientist.agent.reflexion import ReflexionDecision, ReflexionOrchestrator
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.reflexion import (
    RecoverableRoutingDecision,
    ReflexionReplayRecorder,
    ReflexionRoutingConfig,
    ReflexionRoutingEvaluator,
    ReflexionRoutingRule,
    default_reflexion_policy,
)


def _failure_card(
    *, severity: FailureSeverity = FailureSeverity.RECOVERABLE, error_code: str = "schema_error"
) -> FailureCard:
    return FailureCard(
        source_step=FailureSource.VALIDATOR_SCHEMA,
        run_id="run-1",
        error_code=error_code,
        severity=severity,
        violation_summary="schema mismatch",
        remediation_advice="fix schema",
        remediation_target=RemediationTarget.FORMALIZER,
        attempt_number=1,
        max_iterations=3,
    )


def test_reflexion_hard_rules_override_autotuned_routing(tmp_path, monkeypatch) -> None:
    store_root = tmp_path / ".polisyos"
    monkeypatch.setenv("POLISYOS_CAS_ROOT", str(store_root))
    monkeypatch.setenv("POLISYOS_SEARCH_REGISTRY_ROOT", str(store_root / "search_registry"))
    store = FileSystemCAS(store_root)
    registry = ChampionRegistry(root=store_root / "search_registry", store=store)
    candidate_ref = persist_mutation_artifact(
        store,
        ReflexionRoutingConfig(
            rules=[
                ReflexionRoutingRule(
                    error_codes=["fatal_error"],
                    decision=RecoverableRoutingDecision.RETURN_TO_DRAFTER,
                )
            ]
        ),
    )
    evaluation_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="reflexion_routing",
            suite_id="replay",
            suite_version="1.0",
            candidate_ref=candidate_ref,
            selection_metrics={"retry_success_rate": 1.0},
            holdout_metrics={"retry_success_rate": 1.0},
            sample_counts={
                BenchmarkSplit.SELECTION.value: 1,
                BenchmarkSplit.HOLDOUT.value: 1,
            },
            guardrails={"unsafe_nonhuman_route_rate_zero": True},
            promotable=True,
        ),
    )
    registry.consider_promotion(
        "reflexion_routing",
        candidate_ref,
        evaluation_ref,
        default_reflexion_policy(),
    )

    decision = ReflexionOrchestrator().evaluate_failure(
        _failure_card(severity=FailureSeverity.FATAL, error_code="fatal_error"),
        {},
    )

    assert decision is ReflexionDecision.ABORT_WITH_REPORT


def test_reflexion_replay_benchmark_promotes_better_recoverable_route(
    tmp_path, monkeypatch
) -> None:
    store_root = tmp_path / ".polisyos"
    monkeypatch.setenv("POLISYOS_CAS_ROOT", str(store_root))
    monkeypatch.setenv("POLISYOS_SEARCH_REGISTRY_ROOT", str(store_root / "search_registry"))
    store = FileSystemCAS(store_root)
    registry = ChampionRegistry(root=store_root / "search_registry", store=store)
    recorder = ReflexionReplayRecorder()
    recorder.record_case(
        case_id="case-1",
        card=_failure_card(error_code="schema_error"),
        decision_outcomes={
            RecoverableRoutingDecision.RETURN_TO_FORMALIZER.value: False,
            RecoverableRoutingDecision.RETURN_TO_DRAFTER.value: True,
        },
    )
    suite_ref = persist_benchmark_suite(
        store, recorder.write_dataset(output_dir=tmp_path / "replay")
    )
    candidate_ref = persist_mutation_artifact(
        store,
        ReflexionRoutingConfig(
            rules=[
                ReflexionRoutingRule(
                    error_codes=["schema_error"],
                    decision=RecoverableRoutingDecision.RETURN_TO_DRAFTER,
                )
            ]
        ),
    )
    evaluator = ReflexionRoutingEvaluator(store=store, registry=registry)
    evaluation = evaluator.evaluate(
        candidate_ref, suite_ref, {"store": store, "registry": registry}
    )
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    decision = registry.consider_promotion(
        "reflexion_routing",
        candidate_ref,
        evaluation_ref,
        default_reflexion_policy(),
    )

    orchestrator = ReflexionOrchestrator()
    runtime_decision = orchestrator.evaluate_failure(_failure_card(error_code="schema_error"), {})

    assert decision.promoted is True
    assert runtime_decision is ReflexionDecision.RETURN_TO_DRAFTER


def test_reflexion_unsafe_nonhuman_route_never_promotes(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    recorder = ReflexionReplayRecorder()
    recorder.record_case(
        case_id="unsafe-1",
        card=_failure_card(error_code="security"),
        decision_outcomes={RecoverableRoutingDecision.RETURN_TO_DRAFTER.value: True},
        unsafe_for_nonhuman=True,
    )
    suite_ref = persist_benchmark_suite(
        store, recorder.write_dataset(output_dir=tmp_path / "unsafe")
    )
    candidate_ref = persist_mutation_artifact(
        store,
        ReflexionRoutingConfig(
            rules=[
                ReflexionRoutingRule(
                    error_codes=["security"],
                    decision=RecoverableRoutingDecision.RETURN_TO_DRAFTER,
                )
            ]
        ),
    )
    evaluator = ReflexionRoutingEvaluator(store=store, registry=registry)
    evaluation = evaluator.evaluate(
        candidate_ref, suite_ref, {"store": store, "registry": registry}
    )
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    decision = registry.consider_promotion(
        "reflexion_routing",
        candidate_ref,
        evaluation_ref,
        default_reflexion_policy(),
    )

    assert evaluation.guardrails["unsafe_nonhuman_route_rate_zero"] is False
    assert decision.promoted is False
