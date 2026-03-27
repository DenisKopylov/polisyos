from __future__ import annotations

import math
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.contracts.scientist import PlatformMetaEvaluationReportRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.world.ids import stable_world_id_from_canon
from polisyos.scientist.doe.designs import AdversarialPlan, AdversarialStrategy
from polisyos.scientist.doe.sampling import generate_adversarial_samples
from polisyos.scientist.doe.stress_report import (
    StressTestReport,
    Vulnerability,
    VulnerabilityType,
)
from polisyos.scientist.search.sentinels import SentinelObservation, SentinelSet
from polisyos.scientist.search.stages import CorrelationTracker
from polisyos.scientist.search.controller import SearchIteration
from polisyos.scientist.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.search.stopping import (
    CompositeStoppingCriterion,
    MaxIterations,
    StoppingCondition,
    StoppingCriterion,
)
from polisyos.scientist.autotune.models import BenchmarkEvaluation, BenchmarkSplit


PLATFORM_META_EVALUATION_SCHEMA_NAME = (
    "polisyos.scientist.PlatformMetaEvaluationReport"
)


class PlatformMetaEvaluationConfig(BaseModel):
    """Fixed thresholds for platform-level adversarial audits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sentinel_pass_floor: float = Field(default=0.95, ge=0.0, le=1.0)
    max_holdout_flip_rate: float = Field(default=0.25, ge=0.0, le=1.0)
    max_hidden_holdout_degradation: float = Field(default=0.10, ge=0.0, le=1.0)
    drift_warning_threshold: float = Field(default=0.6, ge=-1.0, le=1.0)
    drift_ban_threshold: float = Field(default=0.5, ge=-1.0, le=1.0)
    expected_drift_window: int = Field(default=20, ge=2, le=200)


class PlatformAttackResult(BaseModel):
    """Result of one platform attack family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attack_type: str = Field(min_length=1)
    status: str = Field(min_length=1)
    passed: bool
    summary: str = Field(min_length=1)
    triggered_guards: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlatformMetaEvaluationReport(BaseModel):
    """Replayable report over platform self-attack results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    overall_status: str = Field(default="passed", min_length=1)
    promotion_safe: bool = True
    attack_results: list[PlatformAttackResult] = Field(default_factory=list)
    triggered_guards: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    source_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlatformMetaEvaluationInput(BaseModel):
    """Inputs required to attack the platform's own guardrails."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    sentinel_set: SentinelSet | None = None
    sentinel_observations: list[SentinelObservation] = Field(default_factory=list)
    correlation_tracker: CorrelationTracker | None = None
    selection_evaluation: BenchmarkEvaluation | None = None
    rotated_hidden_holdout_evaluations: list[BenchmarkEvaluation] = Field(default_factory=list)
    base_promotion_decision: bool | None = None
    rotated_promotion_decisions: list[bool] = Field(default_factory=list)
    observed_scheduler_mode: str | None = None
    source_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlatformMetaEvaluator:
    """Runs platform-level adversarial checks over existing guardrails."""

    def __init__(
        self,
        *,
        config: PlatformMetaEvaluationConfig | None = None,
    ) -> None:
        self._config = config or PlatformMetaEvaluationConfig()

    @property
    def config(self) -> PlatformMetaEvaluationConfig:
        return self._config

    def evaluate(
        self,
        bundle: PlatformMetaEvaluationInput,
    ) -> PlatformMetaEvaluationReport:
        attack_results = [
            self._sentinel_injection(bundle),
            self._hidden_holdout_rotation(bundle),
            self._calibration_drift_replay(bundle),
        ]
        triggered_guards = sorted(
            {
                guard
                for result in attack_results
                for guard in result.triggered_guards
            }
        )
        recommendations = _dedupe_text(
            [item for result in attack_results for item in result.recommendations]
        )
        failures = [result for result in attack_results if result.status == "failed"]
        overall_status = "failed" if failures else "passed"
        metrics = {
            "attack_count": len(attack_results),
            "failed_attack_count": len(failures),
            "skipped_attack_count": sum(
                1 for result in attack_results if result.status == "skipped"
            ),
        }
        metrics.update(
            {
                f"{result.attack_type}_status": result.status
                for result in attack_results
            }
        )
        return PlatformMetaEvaluationReport(
            overall_status=overall_status,
            promotion_safe=not failures,
            attack_results=attack_results,
            triggered_guards=triggered_guards,
            recommendations=recommendations,
            source_refs=dict(bundle.source_refs),
            metrics=metrics,
            metadata=dict(bundle.metadata),
        )

    def _sentinel_injection(
        self,
        bundle: PlatformMetaEvaluationInput,
    ) -> PlatformAttackResult:
        observations = list(bundle.sentinel_observations)
        if bundle.sentinel_set is None or not observations:
            return PlatformAttackResult(
                attack_type="sentinel_injection",
                status="skipped",
                passed=True,
                summary="Sentinel attack skipped because sentinel inputs were not provided.",
            )
        observed_pass_rate = sum(
            1 for item in observations if item.stage_a_passed
        ) / max(len(observations), 1)
        expected_floor = max(
            self._config.sentinel_pass_floor,
            float(getattr(bundle.sentinel_set, "pass_rate_floor", self._config.sentinel_pass_floor)),
        )
        alert_codes = _tracker_alert_codes(bundle.correlation_tracker)
        guard_present = "SENTINEL_FAILURE" in alert_codes or _observed_routing_mode(bundle) != "normal"
        if observed_pass_rate >= expected_floor:
            status = "passed"
            passed = True
            summary = "Sentinel pass rate remained above the configured floor."
        else:
            passed = guard_present
            status = "passed" if passed else "failed"
            summary = (
                "Sentinel pass rate fell below the configured floor and the platform "
                + ("raised the expected guard." if passed else "did not surface a guard.")
            )
        recommendations = []
        if observed_pass_rate < expected_floor and not guard_present:
            recommendations.append("Inject sentinel regression guard into calibration routing.")
        return PlatformAttackResult(
            attack_type="sentinel_injection",
            status=status,
            passed=passed,
            summary=summary,
            triggered_guards=[code for code in alert_codes if "SENTINEL" in code],
            recommendations=recommendations,
            metrics={
                "observed_pass_rate": observed_pass_rate,
                "expected_floor": expected_floor,
                "sentinel_observation_count": len(observations),
            },
        )

    def _hidden_holdout_rotation(
        self,
        bundle: PlatformMetaEvaluationInput,
    ) -> PlatformAttackResult:
        holdouts = list(bundle.rotated_hidden_holdout_evaluations)
        if bundle.selection_evaluation is None or not holdouts:
            return PlatformAttackResult(
                attack_type="hidden_holdout_rotation",
                status="skipped",
                passed=True,
                summary="Hidden holdout rotation skipped because rotated holdouts were not provided.",
            )
        selection_split = bundle.selection_evaluation.resolved_runtime_split_type()
        if selection_split is not BenchmarkSplit.SELECTION:
            return PlatformAttackResult(
                attack_type="hidden_holdout_rotation",
                status="failed",
                passed=False,
                summary=(
                    "Hidden holdout rotation received a selection evaluation with the wrong "
                    "runtime split type."
                ),
                recommendations=[
                    "Label the base evaluation as 'selection' before running rotated holdout checks."
                ],
                metrics={"observed_selection_split": selection_split.value},
            )
        invalid_rotations = [
            evaluation.resolved_runtime_split_type().value
            for evaluation in holdouts
            if evaluation.resolved_runtime_split_type()
            is not BenchmarkSplit.ROTATING_CHALLENGE
        ]
        if invalid_rotations:
            return PlatformAttackResult(
                attack_type="hidden_holdout_rotation",
                status="failed",
                passed=False,
                summary=(
                    "Rotated hidden holdout evaluations must declare the "
                    "'rotating_challenge' runtime split type."
                ),
                recommendations=[
                    "Emit rotated holdout evaluations with runtime_split_type='rotating_challenge'."
                ],
                metrics={"invalid_rotation_splits": invalid_rotations},
            )
        shared_metrics = sorted(
            set(bundle.selection_evaluation.selection_metrics)
            & {
                metric
                for evaluation in holdouts
                for metric in evaluation.holdout_metrics
            }
        )
        metric = shared_metrics[0] if shared_metrics else None
        deltas: list[float] = []
        if metric is not None:
            selection_value = float(bundle.selection_evaluation.selection_metrics[metric])
            for evaluation in holdouts:
                holdout_value = float(evaluation.holdout_metrics.get(metric, selection_value))
                delta = 0.0 if selection_value <= 0.0 else max(0.0, (selection_value - holdout_value) / selection_value)
                deltas.append(delta)
        flip_rate = 0.0
        if bundle.rotated_promotion_decisions and bundle.base_promotion_decision is not None:
            flip_rate = sum(
                1 for item in bundle.rotated_promotion_decisions if item != bundle.base_promotion_decision
            ) / len(bundle.rotated_promotion_decisions)
        elif deltas:
            flip_rate = sum(1 for item in deltas if item > self._config.max_hidden_holdout_degradation) / len(deltas)
        worst_delta = max(deltas) if deltas else 0.0
        disagreement_concentration = sum(1 for item in deltas if item > 0.0) / max(len(deltas), 1)
        passed = (
            flip_rate <= self._config.max_holdout_flip_rate
            and worst_delta <= self._config.max_hidden_holdout_degradation
        )
        return PlatformAttackResult(
            attack_type="hidden_holdout_rotation",
            status="passed" if passed else "failed",
            passed=passed,
            summary=(
                "Hidden holdout rotation stayed stable."
                if passed
                else "Rotated hidden holdouts changed promotion or degraded beyond the allowed threshold."
            ),
            recommendations=(
                []
                if passed
                else ["Refresh hidden holdout composition or demote the candidate to research-only readiness."]
            ),
            metrics={
                "promotion_flip_rate": flip_rate,
                "worst_degradation_delta": worst_delta,
                "disagreement_concentration": disagreement_concentration,
                "n_rotations": len(holdouts),
                "metric": metric,
            },
        )

    def _calibration_drift_replay(
        self,
        bundle: PlatformMetaEvaluationInput,
    ) -> PlatformAttackResult:
        tracker = bundle.correlation_tracker
        if tracker is None:
            return PlatformAttackResult(
                attack_type="calibration_drift_replay",
                status="skipped",
                passed=True,
                summary="Calibration drift replay skipped because no CorrelationTracker was provided.",
            )
        metrics = tracker.compute_metrics()
        alert_codes = _tracker_alert_codes(tracker)
        rolling_spearman = float(metrics.get("rolling_spearman_correlation", 0.0))
        routing_mode = _observed_routing_mode(bundle)
        if rolling_spearman >= self._config.drift_warning_threshold:
            passed = True
            status = "passed"
            summary = "Calibration remained healthy under the provided replay context."
        else:
            guard_present = bool(
                {"CALIBRATION_DRIFT", "PROMOTION_BAN"} & set(alert_codes)
            ) and routing_mode in {"conservative_routing", "no_promotion"}
            passed = guard_present
            status = "passed" if guard_present else "failed"
            summary = (
                "Calibration drift was detected and routing degraded as expected."
                if guard_present
                else "Calibration drift was present but the platform did not degrade routing."
            )
        recommendations = []
        if not passed:
            recommendations.append("Disable predictive VOI until paired cheap/expensive calibration is restored.")
        return PlatformAttackResult(
            attack_type="calibration_drift_replay",
            status=status,
            passed=passed,
            summary=summary,
            triggered_guards=alert_codes,
            recommendations=recommendations,
            metrics={
                "rolling_spearman_correlation": rolling_spearman,
                "routing_mode": routing_mode,
                "rolling_sample_count": metrics.get("rolling_sample_count", 0),
            },
        )


class NegatedCompositeObjective:
    """Adapts a base objective for adversarial (worst-case) search."""

    def __init__(self, base_objective: CompositeObjective):
        self._base = base_objective

    @property
    def name(self) -> str:
        return f"negated({self._base.name})"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        base = self._base.evaluate(results)
        return ObjectiveValue(
            name=self.name,
            raw_value=-base.raw_value,
            direction=OptimizationDirection.MINIMIZE,
            is_satisfied=base.is_satisfied,
        )

    def evaluate_detailed(self, results: dict[str, Any]) -> list[ObjectiveValue]:
        return self._base.evaluate_detailed(results)


class VulnerabilityFound(StoppingCriterion):
    """Stop criterion used when caller wants first critical vulnerability only."""

    def __init__(self, threshold: float):
        self._threshold = float(threshold)

    @property
    def name(self) -> str:
        return "vulnerability_found"

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> StoppingCondition:
        del state
        if not history:
            return StoppingCondition(should_stop=False)
        real_objective = -float(history[-1].get("objective_value", float("inf")))
        if real_objective <= self._threshold:
            return StoppingCondition(
                should_stop=True,
                reason=(
                    f"Vulnerability objective {real_objective:.6f} <= "
                    f"threshold {self._threshold:.6f}"
                ),
                details={
                    "objective": real_objective,
                    "threshold": self._threshold,
                },
            )
        return StoppingCondition(should_stop=False)


def run_stress_test(
    *,
    adversarial_plan: AdversarialPlan,
    base_objective: CompositeObjective,
    stage_b_evaluator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    candidate_generator: object | None = None,
    context: dict[str, Any] | None = None,
    cas: FileSystemCAS | None = None,
    decision_packet_ref: str | None = None,
) -> StressTestReport:
    runtime_context = context or {}
    param_names = [item.name for item in adversarial_plan.parameter_specs]
    initial_samples = generate_adversarial_samples(adversarial_plan)

    vulnerabilities: list[Vulnerability] = []
    worst_case_objective = float("-inf")
    worst_case_parameters: dict[str, float] = {}
    total_evaluated = 0

    for idx, sample in enumerate(initial_samples):
        parameters = {name: float(value) for name, value in zip(param_names, sample)}
        candidate = {"semantic": {"interventions": []}, **parameters}
        total_evaluated += 1
        try:
            result = stage_b_evaluator(candidate, runtime_context)
            objective = float(base_objective.evaluate(result.get("simulation_results", {})).raw_value)
        except Exception as exc:
            vulnerabilities.append(
                Vulnerability(
                    vulnerability_id=f"vuln_numerical_{idx}",
                    vulnerability_type=VulnerabilityType.NUMERICAL_INSTABILITY,
                    severity="critical",
                    parameter_values=parameters,
                    description=str(exc),
                )
            )
            if adversarial_plan.stop_on_first_vulnerability:
                break
            continue

        if objective > worst_case_objective:
            worst_case_objective = objective
            worst_case_parameters = parameters

        vuln = _detect_objective_vulnerability(
            objective=objective,
            threshold=adversarial_plan.vulnerability_threshold,
            parameters=parameters,
            vuln_id=f"vuln_objective_{idx}",
        )
        if vuln is not None:
            vulnerabilities.append(vuln)
            if adversarial_plan.stop_on_first_vulnerability:
                break

    if (
        adversarial_plan.strategy == AdversarialStrategy.SEARCH_LOOP
        and candidate_generator is not None
        and hasattr(candidate_generator, "generate")
        and total_evaluated < adversarial_plan.max_iterations
        and (not vulnerabilities or not adversarial_plan.stop_on_first_vulnerability)
    ):
        remaining = max(1, adversarial_plan.max_iterations - total_evaluated)
        stopping_criteria: list[StoppingCriterion] = [MaxIterations(remaining)]
        if (
            adversarial_plan.stop_on_first_vulnerability
            and adversarial_plan.vulnerability_threshold is not None
        ):
            stopping_criteria.append(VulnerabilityFound(adversarial_plan.vulnerability_threshold))

        stopping: StoppingCriterion
        if len(stopping_criteria) == 1:
            stopping = stopping_criteria[0]
        else:
            stopping = CompositeStoppingCriterion(stopping_criteria)

        history: list[SearchIteration] = []
        best_candidate: dict[str, Any] | None = None
        best_negated_objective = float("inf")
        for idx in range(remaining):
            candidate = candidate_generator.generate(history, best_candidate, runtime_context)  # type: ignore[attr-defined]
            result = stage_b_evaluator(candidate, runtime_context)
            objective = float(base_objective.evaluate(result.get("simulation_results", {})).raw_value)
            negated_objective = -objective
            history.append(
                SearchIteration(
                    iteration=idx,
                    candidate=dict(candidate),
                    objective_value=negated_objective,
                    objective_details=list(base_objective.evaluate_detailed(result.get("simulation_results", {}))),
                    is_promising=True,
                    stage_a_passed=True,
                    stage_b_result=result,
                    duration_seconds=0.0,
                )
            )
            total_evaluated += 1
            if negated_objective < best_negated_objective:
                best_negated_objective = negated_objective
                best_candidate = dict(candidate)
            if objective > worst_case_objective:
                worst_case_objective = objective
                worst_case_parameters = {
                    key: float(value)
                    for key, value in candidate.items()
                    if key in param_names and isinstance(value, (int, float))
                }
            if adversarial_plan.vulnerability_threshold is not None:
                vuln = _detect_objective_vulnerability(
                    objective=objective,
                    threshold=adversarial_plan.vulnerability_threshold,
                    parameters={
                        key: float(value)
                        for key, value in candidate.items()
                        if key in param_names and isinstance(value, (int, float))
                    },
                    vuln_id=f"vuln_search_{idx}",
                )
                if vuln is not None:
                    vulnerabilities.append(vuln)
                    if adversarial_plan.stop_on_first_vulnerability:
                        break
            stop_check = stopping.check(
                [{"objective_value": item.objective_value} for item in history],
                {"iteration": idx + 1, "best_objective": best_negated_objective},
            )
            if stop_check.should_stop:
                break

    vulnerabilities = _deduplicate_vulnerabilities(vulnerabilities)[: adversarial_plan.collect_top_k]
    if worst_case_objective == float("-inf"):
        worst_case_objective = float("nan")

    robustness_score = 1.0 - (len(vulnerabilities) / max(total_evaluated, 1))
    report = StressTestReport(
        report_id=stable_world_id_from_canon(
            prefix="stress.report",
            payload=_canon_safe(
                {
                    "plan": adversarial_plan.model_dump(mode="json"),
                    "total_evaluated": total_evaluated,
                    "worst_case_objective": worst_case_objective,
                }
            ),
        ),
        total_scenarios_evaluated=total_evaluated,
        worst_case_parameters=worst_case_parameters,
        worst_case_objective=worst_case_objective if math.isfinite(worst_case_objective) else None,
        vulnerabilities=vulnerabilities,
        critical_count=sum(1 for item in vulnerabilities if item.severity == "critical"),
        high_count=sum(1 for item in vulnerabilities if item.severity == "high"),
        medium_count=sum(1 for item in vulnerabilities if item.severity == "medium"),
        robustness_score=robustness_score,
        decision_packet_ref=decision_packet_ref,
        metadata={
            "strategy": adversarial_plan.strategy.value,
            "stop_on_first_vulnerability": adversarial_plan.stop_on_first_vulnerability,
        },
    )

    if cas is not None:
        ref = cas.put_json(
            report.model_dump(mode="json"),
            PutOptions(
                kind="scientist.stress_test_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        report.cas_artifact_id = str(ref.artifact_id)
    return report


def _detect_objective_vulnerability(
    *,
    objective: float,
    threshold: float | None,
    parameters: dict[str, float],
    vuln_id: str,
) -> Vulnerability | None:
    if threshold is None:
        return None
    if objective > threshold:
        return None
    return Vulnerability(
        vulnerability_id=vuln_id,
        vulnerability_type=VulnerabilityType.OBJECTIVE_COLLAPSE,
        severity="high",
        parameter_values=parameters,
        objective_value=objective,
        description=f"Objective {objective:.6f} is below threshold {threshold:.6f}",
    )


def _deduplicate_vulnerabilities(vulnerabilities: list[Vulnerability]) -> list[Vulnerability]:
    unique: dict[str, Vulnerability] = {}
    for vulnerability in vulnerabilities:
        key = stable_world_id_from_canon(
            prefix="stress.vuln",
            payload=_canon_safe(
                {
                    "type": vulnerability.vulnerability_type.value,
                    "params": vulnerability.parameter_values,
                    "description": vulnerability.description,
                    "objective_value": vulnerability.objective_value,
                }
            ),
        )
        if key not in unique:
            unique[key] = vulnerability
    return list(unique.values())


def _canon_safe(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return f"{value:.12g}"
    if isinstance(value, dict):
        return {str(key): _canon_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canon_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_canon_safe(item) for item in value]
    return value


def persist_platform_meta_evaluation_report(
    store: FileSystemCAS,
    report: PlatformMetaEvaluationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> PlatformMetaEvaluationReportRef:
    ref = store.put_json(
        report.model_dump(mode="json"),
        PutOptions(
            kind="scientist.platform_meta_evaluation_report",
            media_type="application/json",
            schema=SchemaInfo(
                name=PLATFORM_META_EVALUATION_SCHEMA_NAME,
                version=report.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return PlatformMetaEvaluationReportRef.model_validate(ref.model_dump(mode="json"))


def load_platform_meta_evaluation_report(
    store: FileSystemCAS,
    ref: PlatformMetaEvaluationReportRef | ArtifactRef,
) -> PlatformMetaEvaluationReport:
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return PlatformMetaEvaluationReport.model_validate(payload)


def _tracker_alert_codes(tracker: CorrelationTracker | None) -> list[str]:
    if tracker is None:
        return []
    return [alert.code for alert in tracker.drift_alerts()]


def _observed_routing_mode(bundle: PlatformMetaEvaluationInput) -> str:
    if bundle.observed_scheduler_mode:
        return bundle.observed_scheduler_mode
    if bundle.correlation_tracker is None:
        return "normal"
    return str(bundle.correlation_tracker.routing_mode())


def _dedupe_text(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


__all__ = [
    "NegatedCompositeObjective",
    "PlatformAttackResult",
    "PlatformMetaEvaluationConfig",
    "PlatformMetaEvaluationInput",
    "PlatformMetaEvaluationReport",
    "PlatformMetaEvaluator",
    "VulnerabilityFound",
    "load_platform_meta_evaluation_report",
    "persist_platform_meta_evaluation_report",
    "run_stress_test",
]
