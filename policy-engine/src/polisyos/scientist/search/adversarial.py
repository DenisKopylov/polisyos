from __future__ import annotations

import math
from typing import Any, Callable

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir.world.ids import stable_world_id_from_canon
from polisyos.scientist.doe.designs import AdversarialPlan, AdversarialStrategy
from polisyos.scientist.doe.sampling import generate_adversarial_samples
from polisyos.scientist.doe.stress_report import (
    StressTestReport,
    Vulnerability,
    VulnerabilityType,
)
from polisyos.scientist.search.controller import SearchConfig, SearchController
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

        controller = SearchController(
            config=SearchConfig(
                stopping=stopping,
                objective=NegatedCompositeObjective(base_objective),
                enable_stage_a=False,
            ),
            candidate_generator=candidate_generator,  # type: ignore[arg-type]
            stage_a_evaluator=lambda candidate, ctx: (0.0, True),
            stage_b_evaluator=stage_b_evaluator,
        )
        search_result = controller.run(initial_context=runtime_context)
        total_evaluated += int(search_result.iterations_completed)

        if search_result.best_candidate is not None and search_result.best_objective is not None:
            candidate_objective = -float(search_result.best_objective)
            if candidate_objective > worst_case_objective:
                worst_case_objective = candidate_objective
                worst_case_parameters = {
                    key: float(value)
                    for key, value in search_result.best_candidate.items()
                    if key in param_names and isinstance(value, (int, float))
                }

        if adversarial_plan.vulnerability_threshold is not None:
            for idx, item in enumerate(search_result.history):
                objective = -float(item.objective_value)
                params = {
                    key: float(value)
                    for key, value in item.candidate.items()
                    if key in param_names and isinstance(value, (int, float))
                }
                vuln = _detect_objective_vulnerability(
                    objective=objective,
                    threshold=adversarial_plan.vulnerability_threshold,
                    parameters=params,
                    vuln_id=f"vuln_search_{idx}",
                )
                if vuln is None:
                    continue
                vulnerabilities.append(vuln)
                if adversarial_plan.stop_on_first_vulnerability:
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
