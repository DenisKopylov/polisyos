"""Public search adversarial module API."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any, Protocol, TypeGuard, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import ArtifactStore
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.scientist import PlatformMetaEvaluationReportRef
from polisyos.ir.world.ids import stable_world_id_from_canon
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.methods.doe.designs import (
    _ADVERSARIAL_PLAN_ARTIFACT_KIND,
    _ADVERSARIAL_PLAN_SCHEMA_NAME,
    _ADVERSARIAL_PLAN_SCHEMA_VERSION,
    AdversarialPlan,
    AdversarialStrategy,
)
from polisyos.scientist.methods.doe.sampling import generate_adversarial_samples
from polisyos.scientist.methods.doe.stress_report import (
    _STRESS_OBJECTIVE_SOURCE_ARTIFACT_KIND,
    _STRESS_OBJECTIVE_SOURCE_SCHEMA_NAME,
    _STRESS_OBJECTIVE_SOURCE_SCHEMA_VERSION,
    _STRESS_OUTCOME_BASIS_ADVERSARIAL_SCHEMA_VERSION,
    _STRESS_OUTCOME_BASIS_ARTIFACT_KIND,
    _STRESS_OUTCOME_BASIS_SCHEMA_NAME,
    _STRESS_OUTCOME_BASIS_SCHEMA_VERSION,
    _STRESS_TEST_REPORT_ARTIFACT_KIND,
    _STRESS_TEST_REPORT_SCHEMA_NAME,
    StressObjectiveEvidence,
    StressOutcomeBasis,
    StressOutcomeRecord,
    StressScoreComponent,
    StressTestReport,
    Vulnerability,
    VulnerabilityType,
    _canon_safe,
    _deduplicate_vulnerabilities,
    _detect_objective_vulnerability,
    _is_objective_vulnerable,
    _objective_badness,
    resolve_stress_score_components,
)
from polisyos.scientist.methods.search.contracts import SearchIteration
from polisyos.scientist.methods.search.objective import (
    BaseObjective,
    CompositeObjective,
    ObjectiveScoreStatus,
    ObjectiveValue,
    OptimizationDirection,
    configured_objective_rule_spec,
    objective_value_matches_rule,
)
from polisyos.scientist.methods.search.sentinels import SentinelObservation, SentinelSet
from polisyos.scientist.methods.search.stages import CorrelationTracker
from polisyos.scientist.methods.search.stopping import (
    CompositeStoppingCriterion,
    MaxIterations,
    StoppingCondition,
    StoppingCriterion,
)


@runtime_checkable
class _DirectionProvider(Protocol):
    """Structural direction contract for direct and legacy objective adapters."""

    @property
    def direction(self) -> OptimizationDirection: ...


class _CandidateGenerator(Protocol):
    """Legacy ask-loop generator contract used for adaptive stress continuation."""

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        runtime_context: dict[str, Any],
        /,
    ) -> dict[str, Any]: ...


def _has_candidate_generator(value: object) -> TypeGuard[_CandidateGenerator]:
    """Narrow the legacy hasattr gate without changing its runtime admission predicate."""
    return hasattr(value, "generate")


PLATFORM_META_EVALUATION_SCHEMA_NAME = "polisyos.scientist.PlatformMetaEvaluationReport"


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
            {guard for result in attack_results for guard in result.triggered_guards}
        )
        recommendations = _dedupe_text(
            [item for result in attack_results for item in result.recommendations]
        )
        failures = [result for result in attack_results if result.status == "failed"]
        overall_status = "failed" if failures else "passed"
        metrics: dict[str, int | str] = {
            "attack_count": len(attack_results),
            "failed_attack_count": len(failures),
            "skipped_attack_count": sum(
                1 for result in attack_results if result.status == "skipped"
            ),
        }
        metrics.update({f"{result.attack_type}_status": result.status for result in attack_results})
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
        observed_pass_rate = sum(1 for item in observations if item.stage_a_passed) / max(
            len(observations), 1
        )
        expected_floor = max(
            self._config.sentinel_pass_floor,
            float(
                getattr(bundle.sentinel_set, "pass_rate_floor", self._config.sentinel_pass_floor)
            ),
        )
        alert_codes = _tracker_alert_codes(bundle.correlation_tracker)
        guard_present = (
            "SENTINEL_FAILURE" in alert_codes or _observed_routing_mode(bundle) != "normal"
        )
        if observed_pass_rate >= expected_floor:
            status = "passed"
            passed = True
            summary = "Sentinel pass rate remained above the configured floor."
        else:
            passed = guard_present
            status = "passed" if passed else "failed"
            summary = "Sentinel pass rate fell below the configured floor and the platform " + (
                "raised the expected guard." if passed else "did not surface a guard."
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
            if evaluation.resolved_runtime_split_type() is not BenchmarkSplit.ROTATING_CHALLENGE
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
            & {metric for evaluation in holdouts for metric in evaluation.holdout_metrics}
        )
        metric = shared_metrics[0] if shared_metrics else None
        deltas: list[float] = []
        if metric is not None:
            selection_value = float(bundle.selection_evaluation.selection_metrics[metric])
            for evaluation in holdouts:
                holdout_value = float(evaluation.holdout_metrics.get(metric, selection_value))
                delta = (
                    0.0
                    if selection_value <= 0.0
                    else max(0.0, (selection_value - holdout_value) / selection_value)
                )
                deltas.append(delta)
        flip_rate = 0.0
        if bundle.rotated_promotion_decisions and bundle.base_promotion_decision is not None:
            flip_rate = sum(
                1
                for item in bundle.rotated_promotion_decisions
                if item != bundle.base_promotion_decision
            ) / len(bundle.rotated_promotion_decisions)
        elif deltas:
            flip_rate = sum(
                1 for item in deltas if item > self._config.max_hidden_holdout_degradation
            ) / len(deltas)
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
                else [
                    "Refresh hidden holdout composition or demote the candidate to research-only readiness."
                ]
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
            recommendations.append(
                "Disable predictive VOI until paired cheap/expensive calibration is restored."
            )
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

    def __init__(
        self,
        threshold: float,
        direction: OptimizationDirection = OptimizationDirection.MINIMIZE,
    ):
        self._threshold = float(threshold)
        self._direction = direction

    @property
    def name(self) -> str:
        return "vulnerability_found"

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> StoppingCondition:
        del state
        if not history:
            return StoppingCondition(should_stop=False)
        raw_objective = float(history[-1].get("objective_value", float("nan")))
        if _is_objective_vulnerable(
            raw_objective,
            threshold=self._threshold,
            direction=self._direction,
        ):
            return StoppingCondition(
                should_stop=True,
                reason=(
                    f"Vulnerability objective {raw_objective:.6f} violates "
                    f"threshold {self._threshold:.6f}"
                ),
                details={
                    "objective": raw_objective,
                    "badness": _objective_badness(raw_objective, self._direction),
                    "direction": self._direction.value,
                    "threshold": self._threshold,
                },
            )
        return StoppingCondition(should_stop=False)


class StressObjectiveDirectionError(ValueError):
    """Refuse stress evaluation when the raw objective direction is not typed."""

    code = "stress_objective_direction_not_established"


def _admit_adversarial_directions(
    base_objective: object,
) -> tuple[OptimizationDirection, OptimizationDirection]:
    """Freeze typed raw and compatibility directions at one pre-work intake."""
    try:
        direction = cast("_DirectionProvider", base_objective).direction
    except (AttributeError, TypeError, ValueError) as exc:
        raise StressObjectiveDirectionError("stress_objective_direction_not_established") from exc
    if type(direction) is not OptimizationDirection:
        raise StressObjectiveDirectionError("stress_objective_direction_not_established")
    if isinstance(base_objective, CompositeObjective) and not all(
        isinstance(item, BaseObjective) for item in base_objective.objectives
    ):
        # Existing duck-composite compatibility is not selected-intent authority.
        return OptimizationDirection.MAXIMIZE, direction
    return direction, direction


def _resolve_adversarial_direction(base_objective: object) -> OptimizationDirection:
    """Admit the raw direction before stress evaluation or plateau comparison."""
    return _admit_adversarial_directions(base_objective)[0]


def _is_worse_objective(
    candidate: float,
    incumbent: float,
    direction: OptimizationDirection,
) -> bool:
    """Return whether ``candidate`` has greater canonical adversarial badness."""
    candidate_badness = _objective_badness(candidate, direction)
    if not math.isfinite(candidate_badness):
        return False
    incumbent_badness = _objective_badness(incumbent, direction)
    return not math.isfinite(incumbent_badness) or candidate_badness > incumbent_badness


def _evaluate_stress_result(
    *,
    base_objective: CompositeObjective,
    result: object,
) -> tuple[dict[str, Any], float, list[ObjectiveValue], ObjectiveValue]:
    """Validate one evaluator result before it enters stress-search state."""
    if not isinstance(result, dict):
        raise TypeError("stage_b_result_missing_or_not_mapping")
    simulation_results = result.get("simulation_results")
    if not isinstance(simulation_results, dict):
        raise TypeError("stage_b_simulation_results_missing_or_not_mapping")

    evaluated = base_objective.evaluate(simulation_results)
    objective = float(evaluated.raw_value)
    if not math.isfinite(objective):
        if evaluated.score_status in {
            ObjectiveScoreStatus.UNAVAILABLE,
            ObjectiveScoreStatus.NOT_ESTABLISHED,
        }:
            assessment = evaluated.score_assessment
            reason = (
                assessment.limitation
                if assessment is not None and assessment.limitation
                else evaluated.score_status.value
            )
            raise _ObjectiveScoreUnavailable(evaluated.score_status, reason)
        raise ValueError("objective_value_missing_non_numeric_or_non_finite")

    details = list(base_objective.evaluate_detailed(simulation_results))
    if any(not math.isfinite(float(item.raw_value)) for item in details):
        raise ValueError("objective_detail_missing_non_numeric_or_non_finite")
    return result, objective, details, evaluated


class _ObjectiveScoreUnavailable(ValueError):
    """Carry typed unavailable score state without mislabeling it numerical failure."""

    def __init__(self, status: ObjectiveScoreStatus, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _persist_stress_objective_evidence(
    *,
    cas: FileSystemCAS,
    result: dict[str, Any],
    objective: ObjectiveValue,
    selected_rule_spec: str | None,
    expected_name: str,
    expected_direction: OptimizationDirection,
) -> tuple[StressObjectiveEvidence | None, ObjectiveScoreStatus, str | None]:
    """Persist a qualifying exact source and assessment, or retain a typed refusal."""
    if selected_rule_spec is None:
        return (
            None,
            ObjectiveScoreStatus.NOT_ESTABLISHED,
            "selected_objective_rule_not_recomputable",
        )
    if objective.score_status is not ObjectiveScoreStatus.AVAILABLE:
        assessment = objective.score_assessment
        return (
            None,
            objective.score_status,
            None if assessment is None else assessment.limitation,
        )
    if not objective_value_matches_rule(
        objective,
        result["simulation_results"],
        expected_name=expected_name,
        expected_direction=expected_direction,
        expected_rule_spec=selected_rule_spec,
    ):
        return None, ObjectiveScoreStatus.INVALID, "selected_objective_source_replay_mismatch"
    assessment = objective.score_assessment
    if assessment is None:
        return None, ObjectiveScoreStatus.NOT_ESTABLISHED, "selected_objective_assessment_missing"
    try:
        source_ref = cas.put_json(
            result["simulation_results"],
            PutOptions(
                kind=_STRESS_OBJECTIVE_SOURCE_ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name=_STRESS_OBJECTIVE_SOURCE_SCHEMA_NAME,
                    version=_STRESS_OBJECTIVE_SOURCE_SCHEMA_VERSION,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        evidence = StressObjectiveEvidence(
            objective_name=expected_name,
            objective_direction=expected_direction.value,
            objective_rule_spec=selected_rule_spec,
            score_assessment=assessment.to_payload(),
            source_ref=source_ref,
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        return (
            None,
            ObjectiveScoreStatus.NOT_ESTABLISHED,
            "objective_source_persistence_not_established",
        )
    return evidence, ObjectiveScoreStatus.AVAILABLE, None


def _merge_objective_score_status(
    current: ObjectiveScoreStatus, observed: ObjectiveScoreStatus
) -> ObjectiveScoreStatus:
    """Keep the most limiting per-occurrence score status for the complete run."""
    priority = {
        ObjectiveScoreStatus.AVAILABLE: 0,
        ObjectiveScoreStatus.NOT_ESTABLISHED: 1,
        ObjectiveScoreStatus.UNAVAILABLE: 2,
        ObjectiveScoreStatus.INVALID: 3,
    }
    return observed if priority[observed] > priority[current] else current


def _numerical_vulnerability(
    *,
    vulnerability_id: str,
    parameters: dict[str, float],
    error: Exception,
) -> Vulnerability:
    """Represent an evaluator failure as a typed critical stress finding."""
    return Vulnerability(
        vulnerability_id=vulnerability_id,
        vulnerability_type=VulnerabilityType.NUMERICAL_INSTABILITY,
        severity="critical",
        parameter_values=parameters,
        description=f"Objective evaluation was not admitted: {error}",
    )


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
    """Run stress test."""
    objective_direction, source_objective_direction = _admit_adversarial_directions(base_objective)
    runtime_context = context or {}
    param_names = [item.name for item in adversarial_plan.parameter_specs]
    initial_samples = generate_adversarial_samples(adversarial_plan)
    selected_rule_spec = configured_objective_rule_spec(base_objective)
    expected_objective_name = getattr(base_objective, "name", "")
    candidate_ref: ArtifactRef | None = None
    if cas is not None:
        raw_candidate_ref = runtime_context.get("policy_candidate_ref")
        if isinstance(raw_candidate_ref, ArtifactRef):
            candidate_ref = raw_candidate_ref
        elif isinstance(raw_candidate_ref, dict):
            try:
                candidate_ref = ArtifactRef.model_validate(raw_candidate_ref)
            except Exception:
                candidate_ref = None
    capture_objective_sources = (
        cas is not None
        and candidate_ref is not None
        and candidate_ref.manifest_profile_sha256 is not None
    )

    vulnerabilities: list[Vulnerability] = []
    outcome_records: list[StressOutcomeRecord] = []
    objective_score_status = (
        ObjectiveScoreStatus.NOT_ESTABLISHED
        if not capture_objective_sources or selected_rule_spec is None
        else ObjectiveScoreStatus.AVAILABLE
    )
    objective_score_reason = (
        "selected_objective_rule_not_recomputable"
        if selected_rule_spec is None
        else "persisted_objective_source_capture_required"
    )
    objective_evidence_complete = capture_objective_sources and selected_rule_spec is not None
    unavailable_evaluation_count = 0
    adaptive_continuation = False
    worst_case_objective = float("nan")
    worst_case_parameters: dict[str, float] = {}
    total_evaluated = 0
    invalid_evaluation_count = 0
    evaluation_unverified = False

    for idx, sample in enumerate(initial_samples):
        parameters = {name: float(value) for name, value in zip(param_names, sample)}
        candidate = {"semantic": {"interventions": []}, **parameters}
        total_evaluated += 1
        try:
            result, objective, _, objective_value = _evaluate_stress_result(
                base_objective=base_objective,
                result=stage_b_evaluator(candidate, runtime_context),
            )
            objective_evidence = None
            if capture_objective_sources and cas is not None:
                objective_evidence, observed_status, reason = _persist_stress_objective_evidence(
                    cas=cas,
                    result=result,
                    objective=objective_value,
                    selected_rule_spec=selected_rule_spec,
                    expected_name=expected_objective_name,
                    expected_direction=source_objective_direction,
                )
                objective_score_status = _merge_objective_score_status(
                    objective_score_status, observed_status
                )
                if objective_evidence is None:
                    objective_evidence_complete = False
                    objective_score_reason = reason or observed_status.value
        except Exception as exc:
            if isinstance(exc, _ObjectiveScoreUnavailable):
                unavailable_evaluation_count += 1
                objective_score_status = _merge_objective_score_status(
                    objective_score_status, exc.status
                )
                objective_score_reason = exc.reason
                objective_evidence_complete = False
                evaluation_unverified = True
                outcome_records.append(
                    StressOutcomeRecord(
                        occurrence_index=len(outcome_records),
                        scenario_id=f"initial:{idx}",
                        status="skipped",
                        parameter_values=parameters,
                        reason_code=f"objective_score_{exc.status.value}",
                    )
                )
                continue
            invalid_evaluation_count += 1
            objective_score_status = _merge_objective_score_status(
                objective_score_status, ObjectiveScoreStatus.INVALID
            )
            objective_score_reason = "objective_evaluation_invalid_or_failed"
            objective_evidence_complete = False
            evaluation_unverified = True
            vulnerability = _numerical_vulnerability(
                vulnerability_id=f"vuln_numerical_{idx}",
                parameters=parameters,
                error=exc,
            )
            vulnerabilities.append(vulnerability)
            outcome_records.append(
                StressOutcomeRecord(
                    occurrence_index=len(outcome_records),
                    scenario_id=f"initial:{idx}",
                    status="invalid",
                    parameter_values=parameters,
                    vulnerabilities=[vulnerability],
                    reason_code="evaluator_exception_or_nonfinite_objective",
                )
            )
            if adversarial_plan.stop_on_first_vulnerability:
                break
            continue

        if _is_worse_objective(objective, worst_case_objective, objective_direction):
            worst_case_objective = objective
            worst_case_parameters = parameters

        vuln = _detect_objective_vulnerability(
            objective=objective,
            threshold=adversarial_plan.vulnerability_threshold,
            direction=objective_direction,
            parameters=parameters,
            vuln_id=f"vuln_objective_{idx}",
        )
        scenario_vulnerabilities = [] if vuln is None else [vuln]
        if vuln is not None:
            vulnerabilities.append(vuln)
        outcome_records.append(
            StressOutcomeRecord(
                occurrence_index=len(outcome_records),
                scenario_id=f"initial:{idx}",
                status="failed" if scenario_vulnerabilities else "passed",
                parameter_values=parameters,
                vulnerabilities=scenario_vulnerabilities,
                objective_evidence=objective_evidence,
            )
        )
        if vuln is not None and adversarial_plan.stop_on_first_vulnerability:
            break

    if (
        adversarial_plan.strategy == AdversarialStrategy.SEARCH_LOOP
        and candidate_generator is not None
        and _has_candidate_generator(candidate_generator)
        and total_evaluated < adversarial_plan.max_iterations
        and (not vulnerabilities or not adversarial_plan.stop_on_first_vulnerability)
        and not evaluation_unverified
    ):
        adaptive_continuation = True
        remaining = max(1, adversarial_plan.max_iterations - total_evaluated)
        stopping_criteria: list[StoppingCriterion] = [MaxIterations(remaining)]
        if (
            adversarial_plan.stop_on_first_vulnerability
            and adversarial_plan.vulnerability_threshold is not None
        ):
            stopping_criteria.append(
                VulnerabilityFound(
                    adversarial_plan.vulnerability_threshold,
                    direction=objective_direction,
                )
            )

        stopping: StoppingCriterion
        if len(stopping_criteria) == 1:
            stopping = stopping_criteria[0]
        else:
            stopping = CompositeStoppingCriterion(stopping_criteria)

        history: list[SearchIteration] = []
        best_candidate: dict[str, Any] | None = None
        best_search_objective = float("nan")
        for idx in range(remaining):
            candidate = candidate_generator.generate(history, best_candidate, runtime_context)
            candidate_parameters = {
                key: float(value)
                for key, value in candidate.items()
                if key in param_names and isinstance(value, (int, float))
            }
            total_evaluated += 1
            try:
                result, objective, objective_details, objective_value = _evaluate_stress_result(
                    base_objective=base_objective,
                    result=stage_b_evaluator(candidate, runtime_context),
                )
                objective_evidence = None
                if capture_objective_sources and cas is not None:
                    objective_evidence, observed_status, reason = (
                        _persist_stress_objective_evidence(
                            cas=cas,
                            result=result,
                            objective=objective_value,
                            selected_rule_spec=selected_rule_spec,
                            expected_name=expected_objective_name,
                            expected_direction=source_objective_direction,
                        )
                    )
                    objective_score_status = _merge_objective_score_status(
                        objective_score_status, observed_status
                    )
                    if objective_evidence is None:
                        objective_evidence_complete = False
                        objective_score_reason = reason or observed_status.value
            except Exception as exc:
                if isinstance(exc, _ObjectiveScoreUnavailable):
                    unavailable_evaluation_count += 1
                    objective_score_status = _merge_objective_score_status(
                        objective_score_status, exc.status
                    )
                    objective_score_reason = exc.reason
                    objective_evidence_complete = False
                    evaluation_unverified = True
                    outcome_records.append(
                        StressOutcomeRecord(
                            occurrence_index=len(outcome_records),
                            scenario_id=f"adaptive:{idx}",
                            status="skipped",
                            parameter_values=candidate_parameters,
                            reason_code=f"objective_score_{exc.status.value}",
                        )
                    )
                    break
                invalid_evaluation_count += 1
                objective_score_status = _merge_objective_score_status(
                    objective_score_status, ObjectiveScoreStatus.INVALID
                )
                objective_score_reason = "objective_evaluation_invalid_or_failed"
                objective_evidence_complete = False
                evaluation_unverified = True
                vulnerability = _numerical_vulnerability(
                    vulnerability_id=f"vuln_numerical_search_{idx}",
                    parameters=candidate_parameters,
                    error=exc,
                )
                vulnerabilities.append(vulnerability)
                outcome_records.append(
                    StressOutcomeRecord(
                        occurrence_index=len(outcome_records),
                        scenario_id=f"adaptive:{idx}",
                        status="invalid",
                        parameter_values=candidate_parameters,
                        vulnerabilities=[vulnerability],
                        reason_code="evaluator_exception_or_nonfinite_objective",
                    )
                )
                break
            history.append(
                SearchIteration(
                    iteration=idx,
                    candidate=dict(candidate),
                    objective_value=objective,
                    objective_details=objective_details,
                    is_promising=True,
                    stage_a_passed=True,
                    stage_b_result=result,
                    duration_seconds=0.0,
                )
            )
            if _is_worse_objective(objective, best_search_objective, objective_direction):
                best_search_objective = objective
                best_candidate = dict(candidate)
            if _is_worse_objective(objective, worst_case_objective, objective_direction):
                worst_case_objective = objective
                worst_case_parameters = candidate_parameters
            scenario_vulnerabilities = []
            if adversarial_plan.vulnerability_threshold is not None:
                vuln = _detect_objective_vulnerability(
                    objective=objective,
                    threshold=adversarial_plan.vulnerability_threshold,
                    direction=objective_direction,
                    parameters=candidate_parameters,
                    vuln_id=f"vuln_search_{idx}",
                )
                if vuln is not None:
                    vulnerabilities.append(vuln)
                    scenario_vulnerabilities.append(vuln)
                    if adversarial_plan.stop_on_first_vulnerability:
                        outcome_records.append(
                            StressOutcomeRecord(
                                occurrence_index=len(outcome_records),
                                scenario_id=f"adaptive:{idx}",
                                status="failed",
                                parameter_values=candidate_parameters,
                                vulnerabilities=scenario_vulnerabilities,
                                objective_evidence=objective_evidence,
                            )
                        )
                        break
            if not (outcome_records and outcome_records[-1].scenario_id == f"adaptive:{idx}"):
                outcome_records.append(
                    StressOutcomeRecord(
                        occurrence_index=len(outcome_records),
                        scenario_id=f"adaptive:{idx}",
                        status="failed" if scenario_vulnerabilities else "passed",
                        parameter_values=candidate_parameters,
                        vulnerabilities=scenario_vulnerabilities,
                        objective_evidence=objective_evidence,
                    )
                )
            stop_check = stopping.check(
                [{"objective_value": item.objective_value} for item in history],
                {"iteration": idx + 1, "best_objective": best_search_objective},
            )
            if stop_check.should_stop:
                break

    observed_vulnerabilities = list(vulnerabilities)
    unique_vulnerabilities = _deduplicate_vulnerabilities(observed_vulnerabilities)
    vulnerabilities = unique_vulnerabilities[: adversarial_plan.collect_top_k]
    if not math.isfinite(worst_case_objective):
        worst_case_objective = float("nan")

    evaluation_status = "unverified" if evaluation_unverified else None
    score_status = (
        "invalid" if objective_score_status is ObjectiveScoreStatus.INVALID else "unbound"
    )
    if (
        objective_score_reason == "persisted_objective_source_capture_required"
        and not capture_objective_sources
    ):
        objective_score_reason = "persisted_candidate_and_objective_source_capture_required"
    robustness_score = None
    report = StressTestReport(
        report_id=stable_world_id_from_canon(
            prefix="stress.report",
            payload=_canon_safe(
                {
                    "plan": adversarial_plan.model_dump(mode="json"),
                    "total_evaluated": total_evaluated,
                    "worst_case_objective": worst_case_objective,
                    "invalid_evaluation_count": invalid_evaluation_count,
                    "evaluation_status": evaluation_status,
                }
            ),
        ),
        total_scenarios_evaluated=total_evaluated,
        worst_case_parameters=worst_case_parameters,
        worst_case_objective=worst_case_objective if math.isfinite(worst_case_objective) else None,
        vulnerabilities=vulnerabilities,
        critical_count=sum(1 for item in observed_vulnerabilities if item.severity == "critical"),
        high_count=sum(1 for item in observed_vulnerabilities if item.severity == "high"),
        medium_count=sum(1 for item in observed_vulnerabilities if item.severity == "medium"),
        robustness_score=None,
        score_profile="finite_binary_scenario_v1",
        score_status=score_status,
        score_reason=objective_score_reason,
        set_adequacy_status=evaluation_status,
        decision_packet_ref=decision_packet_ref,
        metadata={
            "strategy": adversarial_plan.strategy.value,
            "stop_on_first_vulnerability": adversarial_plan.stop_on_first_vulnerability,
            "objective_direction": objective_direction.value,
            "source_objective_direction": source_objective_direction.value,
            "evaluation_status": evaluation_status or "verified",
            "objective_score_admission_status": objective_score_status.value,
            "objective_score_admission_reason": objective_score_reason,
            "objective_unavailable_evaluation_count": unavailable_evaluation_count,
            "invalid_evaluation_count": invalid_evaluation_count,
            "valid_evaluation_count": total_evaluated - invalid_evaluation_count,
            "observed_vulnerability_count": len(observed_vulnerabilities),
            "unique_vulnerability_count": len(unique_vulnerabilities),
            "presented_vulnerability_count": len(vulnerabilities),
        },
    )

    if cas is not None and candidate_ref is not None:
        plan_ref = cas.put_json(
            adversarial_plan.model_dump(mode="json"),
            PutOptions(
                kind=_ADVERSARIAL_PLAN_ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name=_ADVERSARIAL_PLAN_SCHEMA_NAME,
                    version=_ADVERSARIAL_PLAN_SCHEMA_VERSION,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        report = report.model_copy(update={"adversarial_plan_ref": str(plan_ref.artifact_id)})
        complete_objective_evidence = (
            objective_score_status is ObjectiveScoreStatus.AVAILABLE
            and objective_evidence_complete
            and bool(outcome_records)
            and all(
                outcome.status not in {"passed", "failed"} or outcome.objective_evidence is not None
                for outcome in outcome_records
            )
        )
        if complete_objective_evidence:
            expected_count = total_evaluated if adaptive_continuation else len(initial_samples)
            source_id = f"adversarial_plan:{plan_ref.artifact_id}"
            basis = StressOutcomeBasis(
                schema_version=_STRESS_OUTCOME_BASIS_ADVERSARIAL_SCHEMA_VERSION,
                source_kind="adversarial_plan",
                source_id=source_id,
                expected_count=expected_count,
                expected_scenario_ids=[f"initial:{i}" for i in range(expected_count)],
                outcomes=outcome_records,
                complete=(
                    not adaptive_continuation
                    and len(outcome_records) == expected_count
                    and all(item.status in {"passed", "failed"} for item in outcome_records)
                ),
                adaptive_continuation=adaptive_continuation,
                plan_ref=plan_ref,
                candidate_ref=candidate_ref,
            )
            objective_source_inputs = [
                input_ref_from_artifact_ref(
                    outcome.objective_evidence.source_ref,
                    role=f"objective_source:{outcome.occurrence_index}",
                )
                for outcome in outcome_records
                if outcome.objective_evidence is not None
            ]
            basis_ref = cas.put_json(
                basis.model_dump(mode="json"),
                PutOptions(
                    kind=_STRESS_OUTCOME_BASIS_ARTIFACT_KIND,
                    media_type="application/json",
                    schema=SchemaInfo(
                        name=_STRESS_OUTCOME_BASIS_SCHEMA_NAME,
                        version=_STRESS_OUTCOME_BASIS_ADVERSARIAL_SCHEMA_VERSION,
                    ),
                    inputs=[
                        input_ref_from_artifact_ref(plan_ref, role="adversarial_plan"),
                        input_ref_from_artifact_ref(candidate_ref, role="candidate"),
                        *objective_source_inputs,
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            component = StressScoreComponent(
                component_id=source_id,
                score_profile="finite_binary_scenario_v1",
                outcome_basis_ref=basis_ref,
            )
            resolution = resolve_stress_score_components(
                cas, [component], expected_candidate_ref=candidate_ref
            )
            report = report.model_copy(
                update={
                    "score_components": [component],
                    "score_status": resolution.status,
                    "score_reason": resolution.reason_code,
                    "score_predicate_status": resolution.predicate_status,
                    "score_profile": resolution.score_profile or "finite_binary_scenario_v1",
                    "robustness_score": resolution.robustness_score,
                    "total_scenarios_evaluated": resolution.total_scenarios_evaluated,
                    "critical_count": resolution.critical_count,
                    "high_count": resolution.high_count,
                    "medium_count": resolution.medium_count,
                }
            )
        elif objective_score_status is not ObjectiveScoreStatus.INVALID:
            report = report.model_copy(
                update={
                    "score_status": "unbound",
                    "score_reason": objective_score_reason
                    or "objective_source_evidence_incomplete",
                    "robustness_score": None,
                }
            )
        ref = cas.put_json(
            report.model_dump(mode="json"),
            PutOptions(
                kind=_STRESS_TEST_REPORT_ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=_STRESS_TEST_REPORT_SCHEMA_NAME, version="1.1"),
                inputs=(
                    [
                        input_ref_from_artifact_ref(
                            item.outcome_basis_ref, role="stress_outcome_basis"
                        )
                        for item in report.score_components
                    ]
                    + [input_ref_from_artifact_ref(candidate_ref, role="candidate")]
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        report.cas_artifact_id = str(ref.artifact_id)
        report._cas_artifact_ref = ref
    return report


def persist_platform_meta_evaluation_report(
    store: ArtifactStore,
    report: PlatformMetaEvaluationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> PlatformMetaEvaluationReportRef:
    """Persist the platform meta-evaluation report produced by adversarial runtime review."""
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
        return_selected_profile=True,
    )
    return PlatformMetaEvaluationReportRef.model_validate(ref.model_dump(mode="json"))


def load_platform_meta_evaluation_report(
    store: ArtifactStore,
    ref: PlatformMetaEvaluationReportRef | ArtifactRef,
) -> PlatformMetaEvaluationReport:
    """Load platform meta evaluation report."""
    from polisyos.core.artifacts import load_core_json_artifact

    payload = load_core_json_artifact(store, ref)
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
    "StressObjectiveDirectionError",
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
