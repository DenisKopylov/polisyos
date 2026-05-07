"""Hierarchical policy search over structure, parameters, and narrative."""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client
from polisyos.scientist.policy_design.critic import ConstraintCritic, ConstraintCriticInput
from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveDirection,
    ObjectiveStack,
    PolicyEvaluationBundle,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.schema import (
    MonitoringSignalSpec,
    PolicyAssumptionSpec,
    PolicyCandidateSchema,
    TransportAssumptionSpec,
)
from polisyos.scientist.policy_design.translator import (
    PolicyTranslatorWorker,
    TranslatorCompliancePass,
    TranslatorInputBundle,
)
from polisyos.scientist.methods.search.controller import SearchIteration, SearchResult, SearchStatus
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonRegistry,
    LessonTrustLevel,
)
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.codec import _get_path, _set_path
from polisyos.scientist.methods.search.strategies.multi_objective import MOBayesianOptimizer
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds, ParameterType
from polisyos.scientist.methods.search.transfer_context import resolve_transfer_context


class PolicySearchLevel(str, Enum):
    """Policy search level public type."""

    STRUCTURE = "structure"
    PARAMETER = "parameter"
    NARRATIVE = "narrative"


class HierarchicalSearchConfig(BaseModel):
    """Controls the breadth, LLM budget, and seed policy of the structure-to-narrative search loop."""

    model_config = ConfigDict(extra="forbid")

    max_structure_candidates: int = Field(default=8, ge=1, le=64)
    max_parameter_iterations: int = Field(default=12, ge=1, le=200)
    narrative_top_k: int = Field(default=3, ge=1, le=10)
    enable_hybrid_seeds: bool = True
    max_hybrid_seeds: int = Field(default=2, ge=0, le=10)
    llm_model_name: str = "gpt-5.4"
    llm_provider_hint: str | None = None
    random_seed: int = Field(default=42, ge=0)


class StructureCandidate(BaseModel):
    """Structure candidate public type."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    structure_id: str = Field(min_length=1)
    candidate: PolicyCandidateSchema
    candidate_hash: str = Field(min_length=1)
    policy_family: str = Field(min_length=1)
    source: str = Field(min_length=1)
    accepted: bool = True
    rejection_reason: str | None = None
    mutation_hints: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParameterSearchSpec(BaseModel):
    """Parameter-search bundle for one structure candidate, including codec paths and search space."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    structure_id: str = Field(min_length=1)
    candidate: PolicyCandidateSchema
    parameter_paths: dict[str, str] = Field(default_factory=dict)
    template_values: dict[str, Any] = Field(default_factory=dict)
    search_space: SearchSpace
    policy_family: str = Field(min_length=1)


@dataclass(slots=True)
class OptimizerObjectiveSpec:
    """Objective mapping that tells the optimizer which signals define the shared frontier."""

    objective_names: list[str]
    directions: list[OptimizationDirection]
    frontier_projection_names: list[str]
    constraint_extractors: dict[str, Callable[[PolicyEvaluationVector], float]]


class NarrativeVariant(BaseModel):
    """Narrative variant public type."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    variant_id: str = Field(min_length=1)
    candidate_hash: str = Field(min_length=1)
    brief: Any
    compliance_result: Any
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class HierarchicalSearchState(BaseModel):
    """Mutable snapshot of the structure, parameter, and narrative stages for one search run."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    current_level: PolicySearchLevel = PolicySearchLevel.STRUCTURE
    structure_candidates: list[StructureCandidate] = Field(default_factory=list)
    parameter_search_results: dict[str, SearchResult] = Field(default_factory=dict)
    narrative_variants: list[NarrativeVariant] = Field(default_factory=list)
    lessons_created: list[LessonCard] = Field(default_factory=list)


class HierarchicalSearchResult(BaseModel):
    """Final coordinator output containing the stage state and published shared frontier."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    state: HierarchicalSearchState
    shared_frontier: list[dict[str, Any]] = Field(default_factory=list)


@dataclass(slots=True)
class PolicyParameterCodec:
    """Policy parameter codec public type."""

    parameter_paths: dict[str, str]
    template_values: dict[str, Any]

    def encode(self, candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            name: _normalize_value_like(_get_path(candidate, path))
            for name, path in self.parameter_paths.items()
        }

    def decode(
        self,
        params: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del context
        output = copy.deepcopy(template or {})
        for name, value in params.items():
            path = self.parameter_paths[name]
            exemplar = self.template_values.get(name)
            _set_path(output, path, _restore_value_like(value, exemplar))
        return output


class HierarchicalSearchCoordinator:
    """Additive structure -> parameter -> narrative policy search."""

    def __init__(
        self,
        *,
        pareto_registry: ParetoRegistry | None = None,
        lesson_registry: LessonRegistry | None = None,
        translator_worker: PolicyTranslatorWorker | None = None,
        translator_compliance: TranslatorCompliancePass | None = None,
        constraint_critic: ConstraintCritic | None = None,
        config: HierarchicalSearchConfig | None = None,
    ) -> None:
        self._pareto_registry = pareto_registry
        self._lesson_registry = lesson_registry
        self._translator_worker = translator_worker or PolicyTranslatorWorker()
        self._translator_compliance = translator_compliance or TranslatorCompliancePass()
        self._constraint_critic = constraint_critic or ConstraintCritic()
        self._config = config or HierarchicalSearchConfig()

    def generate_structure_candidates(
        self,
        candidate: PolicyCandidateSchema,
        *,
        structure_validator: Callable[[PolicyCandidateSchema], bool] | None = None,
    ) -> list[StructureCandidate]:
        seeds: list[StructureCandidate] = []
        base_family = str(candidate.metadata.get("policy_family") or candidate.candidate_id)
        seeds.append(
            StructureCandidate(
                structure_id=f"{candidate.candidate_id}_base",
                candidate=self._with_policy_family(candidate, base_family),
                candidate_hash=candidate.candidate_hash(),
                policy_family=base_family,
                source="deterministic_base",
            )
        )

        for variant in candidate.fallback_variants:
            variant_candidate = candidate.model_copy(
                update={
                    "candidate_id": f"{candidate.candidate_id}_{variant.variant_id}",
                    "trinity_bundle": variant.trinity_bundle,
                    "metadata": {
                        **candidate.metadata,
                        "policy_family": base_family,
                        "parent_candidate_hash": candidate.candidate_hash(),
                    },
                }
            )
            seeds.append(
                StructureCandidate(
                    structure_id=f"{candidate.candidate_id}_{variant.variant_id}",
                    candidate=variant_candidate,
                    candidate_hash=variant_candidate.candidate_hash(),
                    policy_family=base_family,
                    source="fallback_variant",
                )
            )

        seeds.extend(self._transfer_seed_candidates(candidate, base_family))
        seeds.extend(self._rollout_mutation_seeds(candidate, base_family))
        if self._config.enable_hybrid_seeds:
            seeds.extend(self._hybrid_seed_candidates(candidate, base_family))

        accepted: list[StructureCandidate] = []
        seen_hashes: set[str] = set()
        for seed in seeds[: self._config.max_structure_candidates]:
            if seed.candidate_hash in seen_hashes:
                continue
            seen_hashes.add(seed.candidate_hash)
            critique = self._constraint_critic.evaluate(
                ConstraintCriticInput(candidate=seed.candidate)
            )
            if structure_validator is not None and not structure_validator(seed.candidate):
                seed = seed.model_copy(
                    update={"accepted": False, "rejection_reason": "structure_validator_rejected"}
                )
            elif not critique.passed:
                seed = seed.model_copy(
                    update={
                        "accepted": False,
                        "rejection_reason": "constraint_critic_blocked",
                        "mutation_hints": critique.mutation_hints,
                    }
                )
            else:
                seed = seed.model_copy(update={"mutation_hints": critique.mutation_hints})
            accepted.append(seed)
        return accepted

    def build_parameter_search_spec(self, candidate: PolicyCandidateSchema) -> ParameterSearchSpec:
        intervention_indexes = {
            intervention.intervention_id: index
            for index, intervention in enumerate(candidate.trinity_bundle.policy_spec.interventions)
        }
        bounds: list[ParameterBounds] = []
        parameter_paths: dict[str, str] = {}
        template_values: dict[str, Any] = {}

        for parameter in candidate.trinity_bundle.policy_spec.parameters:
            if not parameter.tunable:
                continue
            default = _normalize_value_like(parameter.default_value)
            lower = _normalize_value_like(parameter.min_value)
            upper = _normalize_value_like(parameter.max_value)
            lower, upper = _derive_bounds(default, lower, upper)
            dtype = _parameter_type(parameter.default_value)
            bounds.append(
                ParameterBounds(
                    name=parameter.param_id,
                    lower=lower,
                    upper=upper,
                    dtype=dtype,
                )
            )
            index = intervention_indexes[parameter.intervention_id]
            parameter_paths[parameter.param_id] = (
                f"trinity_bundle.policy_spec.interventions.{index}.params.{parameter.param_path}"
            )
            template_values[parameter.param_id] = parameter.default_value

        for index, entry in enumerate(candidate.parameter_schedule):
            default = _normalize_value_like(entry.scheduled_value)
            lower, upper = _derive_bounds(default, None, None)
            bounds.append(
                ParameterBounds(
                    name=f"schedule::{entry.entry_id}",
                    lower=lower,
                    upper=upper,
                    dtype=_parameter_type(entry.scheduled_value),
                )
            )
            parameter_paths[f"schedule::{entry.entry_id}"] = (
                f"parameter_schedule.{index}.scheduled_value"
            )
            template_values[f"schedule::{entry.entry_id}"] = entry.scheduled_value

        if not bounds:
            raise ValueError("No tunable policy parameters available for parameter search")

        return ParameterSearchSpec(
            structure_id=candidate.candidate_id,
            candidate=candidate,
            parameter_paths=parameter_paths,
            template_values=template_values,
            search_space=SearchSpace(bounds=bounds),
            policy_family=str(candidate.metadata.get("policy_family") or candidate.candidate_id),
        )

    def build_optimizer_objective_spec(
        self,
        candidate: PolicyCandidateSchema,
    ) -> OptimizerObjectiveSpec:
        template = ObjectiveStack().evaluate(PolicyEvaluationBundle(candidate=candidate))
        channels = [
            *template.primary.values(),
            *template.secondary.values(),
            *template.penalties.values(),
        ]
        objective_names = list(dict.fromkeys(channel.name for channel in channels))
        directions = [_to_search_direction(template.channel(name)) for name in objective_names]
        frontier_projection_names = list(
            dict.fromkeys(template.frontier_objectives("global_feasible").keys())
        )
        constraint_extractors = {
            name: (
                lambda evaluation, constraint_name=name: float(
                    evaluation.hard_constraints.get(constraint_name).value
                    if evaluation.hard_constraints.get(constraint_name) is not None
                    else 1.0
                )
            )
            for name in template.hard_constraints
        }
        return OptimizerObjectiveSpec(
            objective_names=objective_names,
            directions=directions,
            frontier_projection_names=frontier_projection_names,
            constraint_extractors=constraint_extractors,
        )

    def run_parameter_search(
        self,
        structure: StructureCandidate,
        *,
        loop_id: str,
        stage_b_evaluator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        stage_a_evaluator: Callable[[dict[str, Any], dict[str, Any]], tuple[float, bool]]
        | None = None,
        initial_context: dict[str, Any] | None = None,
    ) -> SearchResult:
        spec = self.build_parameter_search_spec(structure.candidate)
        objective_spec = self.build_optimizer_objective_spec(structure.candidate)
        codec = PolicyParameterCodec(spec.parameter_paths, spec.template_values)
        strategy = MOBayesianOptimizer(
            spec.search_space,
            objective_names=objective_spec.objective_names,
            directions=objective_spec.directions,
        )
        adapter = StrategyAdapter(
            strategy,
            spec.search_space,
            codec=codec,
            objective_extractor=lambda iteration: _optimizer_objectives_for_iteration(
                iteration,
                objective_spec,
            ),
        )
        context = dict(initial_context or {})
        transfer_context = resolve_transfer_context(
            candidate=structure.candidate,
            context=context,
            run_id=loop_id,
        )
        seed_bundle = None
        initial_evaluations: list[dict[str, Any]] = []
        if self._pareto_registry is not None:
            max_seeds = max(1, self._config.max_hybrid_seeds + 1)
            seed_bundle = self._pareto_registry.get_seed_bundle(
                transfer_context,
                max_seeds=max_seeds,
            )
            initial_evaluations = self._pareto_registry.build_warm_start_evaluations(
                transfer_context,
                max_seeds=max_seeds,
            )
        context.setdefault("candidate_template", structure.candidate.as_search_payload())
        context.setdefault("transfer_context", transfer_context)
        context.setdefault(
            "policy_search_context",
            {
                "structure_id": structure.structure_id,
                "policy_family": structure.policy_family,
                "candidate_hash": structure.candidate_hash,
                "parent_structure_hash": structure.metadata.get("parent_structure_hash"),
                "task_family": transfer_context.task_family,
                "domain": transfer_context.domain,
            },
        )
        context.setdefault("loop_id", loop_id)
        result = _run_blueprint_parameter_search(
            loop_id=loop_id,
            adapter=adapter,
            max_iterations=self._config.max_parameter_iterations,
            stage_b_evaluator=stage_b_evaluator,
            stage_a_evaluator=stage_a_evaluator or _always_pass_stage_a,
            context=context,
            initial_evaluations=initial_evaluations,
        )
        result.telemetry["optimizer_objectives"] = list(objective_spec.objective_names)
        result.telemetry["frontier_projection_names"] = list(
            objective_spec.frontier_projection_names
        )
        result.telemetry["constraint_names"] = sorted(objective_spec.constraint_extractors)
        if seed_bundle is not None:
            result.telemetry["frontier_seed_count"] = len(seed_bundle.entries)
            result.telemetry["seed_domains"] = list(seed_bundle.seed_domains)
            result.telemetry["cross_domain_seed_count"] = seed_bundle.cross_domain_seed_count
        if self._pareto_registry is not None:
            for iteration in result.history:
                if iteration.policy_evaluation is None:
                    continue
                self._pareto_registry.update(
                    loop_id,
                    candidate_hash=str(
                        iteration.policy_evaluation.metadata.get("candidate_hash")
                        or structure.candidate_hash
                    ),
                    evaluation=iteration.policy_evaluation,
                    candidate_id=iteration.policy_evaluation.candidate_id,
                    policy_family=structure.policy_family,
                    seed_payload=dict(iteration.candidate),
                    task_family=transfer_context.task_family,
                    domain=transfer_context.domain,
                    transfer_context=transfer_context,
                    metadata={
                        "structure_id": structure.structure_id,
                        "parent_structure_hash": structure.metadata.get("parent_structure_hash"),
                    },
                )
            result.pareto_front = self._pareto_registry.as_legacy_frontier_payload(loop_id)
        return result

    def run_narrative_search(
        self,
        bundles: list[tuple[str, TranslatorInputBundle]],
    ) -> list[NarrativeVariant]:
        variants: list[NarrativeVariant] = []
        for index, (candidate_hash, bundle) in enumerate(
            bundles[: self._config.narrative_top_k],
            start=1,
        ):
            brief = self._translator_worker.translate(bundle)
            compliance = self._translator_compliance.evaluate(
                brief,
                dossier=bundle.dossier,
                readiness_contract=bundle.readiness_contract,
                constraint_report=bundle.constraint_report,
                subgroup_report=bundle.subgroup_report,
                uncertainty_report=bundle.uncertainty_report,
            )
            variants.append(
                NarrativeVariant(
                    variant_id=f"{candidate_hash}_narrative_{index}",
                    candidate_hash=candidate_hash,
                    brief=brief,
                    compliance_result=compliance,
                    score=_score_narrative_variant(brief, compliance),
                    metadata={
                        "readiness_level": brief.readiness_level,
                        "compliance_passed": compliance.passed,
                    },
                )
            )
        variants.sort(key=lambda item: item.score, reverse=True)
        return variants

    def run(
        self,
        candidate: PolicyCandidateSchema,
        *,
        loop_id: str,
        stage_b_evaluator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
        stage_a_evaluator: Callable[[dict[str, Any], dict[str, Any]], tuple[float, bool]]
        | None = None,
        structure_validator: Callable[[PolicyCandidateSchema], bool] | None = None,
        narrative_input_builder: Callable[
            [StructureCandidate, SearchResult | None], TranslatorInputBundle | None
        ]
        | None = None,
        initial_context: dict[str, Any] | None = None,
    ) -> HierarchicalSearchResult:
        state = HierarchicalSearchState(current_level=PolicySearchLevel.STRUCTURE)
        structures = self.generate_structure_candidates(
            candidate,
            structure_validator=structure_validator,
        )
        state.structure_candidates = structures
        state.lessons_created.extend(self._record_rejection_lessons(structures, loop_id))

        accepted = [item for item in structures if item.accepted]
        if stage_b_evaluator is not None:
            state.current_level = PolicySearchLevel.PARAMETER
            for structure in accepted:
                state.parameter_search_results[structure.structure_id] = self.run_parameter_search(
                    structure,
                    loop_id=loop_id,
                    stage_b_evaluator=stage_b_evaluator,
                    stage_a_evaluator=stage_a_evaluator,
                    initial_context=initial_context,
                )

        if narrative_input_builder is not None:
            state.current_level = PolicySearchLevel.NARRATIVE
            bundles: list[tuple[str, TranslatorInputBundle]] = []
            for structure in accepted:
                result = state.parameter_search_results.get(structure.structure_id)
                bundle = narrative_input_builder(structure, result)
                if bundle is None:
                    continue
                bundles.append((structure.candidate_hash, bundle))
            state.narrative_variants = self.run_narrative_search(bundles)

        shared_frontier = (
            self._pareto_registry.as_legacy_frontier_payload(loop_id)
            if self._pareto_registry is not None
            else []
        )
        return HierarchicalSearchResult(state=state, shared_frontier=shared_frontier)

    def _rollout_mutation_seeds(
        self,
        candidate: PolicyCandidateSchema,
        policy_family: str,
    ) -> list[StructureCandidate]:
        if len(candidate.rollout_plan) < 2:
            return []
        reordered = [
            step.model_copy(update={"order": index})
            for index, step in enumerate(reversed(candidate.rollout_plan))
        ]
        try:
            mutated = candidate.model_copy(
                update={
                    "candidate_id": f"{candidate.candidate_id}_rollout_reverse",
                    "rollout_plan": reordered,
                    "metadata": {
                        **candidate.metadata,
                        "policy_family": policy_family,
                        "parent_structure_hash": candidate.candidate_hash(),
                    },
                }
            )
        except Exception:
            return []
        return [
            StructureCandidate(
                structure_id=f"{candidate.candidate_id}_rollout_reverse",
                candidate=mutated,
                candidate_hash=mutated.candidate_hash(),
                policy_family=policy_family,
                source="rollout_mutation",
                metadata={"parent_structure_hash": candidate.candidate_hash()},
            )
        ]

    def _transfer_seed_candidates(
        self,
        candidate: PolicyCandidateSchema,
        policy_family: str,
    ) -> list[StructureCandidate]:
        if self._pareto_registry is None:
            return []
        target_context = resolve_transfer_context(
            candidate=candidate, run_id=candidate.candidate_id
        )
        bundle = self._pareto_registry.get_seed_bundle(
            target_context,
            max_seeds=max(1, self._config.max_hybrid_seeds),
        )
        seeds: list[StructureCandidate] = []
        for index, entry in enumerate(bundle.entries, start=1):
            if not entry.seed_payload:
                continue
            try:
                seeded_candidate = PolicyCandidateSchema.model_validate(entry.seed_payload)
            except Exception:
                continue
            seeded_candidate = seeded_candidate.model_copy(
                update={
                    "metadata": {
                        **seeded_candidate.metadata,
                        "policy_family": policy_family,
                        "transfer_seed_domain": entry.domain,
                        "transfer_seed_weight": entry.provenance_weight,
                        "parent_structure_hash": candidate.candidate_hash(),
                    }
                }
            )
            seeds.append(
                StructureCandidate(
                    structure_id=f"{candidate.candidate_id}_transfer_seed_{index}",
                    candidate=seeded_candidate,
                    candidate_hash=seeded_candidate.candidate_hash(),
                    policy_family=policy_family,
                    source="transfer_seed",
                    metadata={
                        "transfer_seed_domain": entry.domain,
                        "transfer_provenance_weight": entry.provenance_weight,
                        "parent_structure_hash": candidate.candidate_hash(),
                    },
                )
            )
        return seeds

    def _hybrid_seed_candidates(
        self,
        candidate: PolicyCandidateSchema,
        policy_family: str,
    ) -> list[StructureCandidate]:
        if self._config.max_hybrid_seeds <= 0:
            return []
        client = create_traced_gateway_client(
            model_name=self._config.llm_model_name,
            provider_hint=self._config.llm_provider_hint,
            run_id=f"{candidate.candidate_id}_hybrid_seed",
        )
        degraded = client is None
        candidates: list[PolicyCandidateSchema] = []

        monitoring_seed = self._build_monitoring_hybrid_seed(candidate)
        if monitoring_seed is not None:
            candidates.append(monitoring_seed)
        transport_seed = self._build_transport_hybrid_seed(candidate)
        if transport_seed is not None:
            candidates.append(transport_seed)
        evidence_seed = self._build_evidence_hybrid_seed(candidate)
        if evidence_seed is not None:
            candidates.append(evidence_seed)

        seeds: list[StructureCandidate] = []
        seen_hashes: set[str] = set()
        for index, hybrid_candidate in enumerate(candidates, start=1):
            candidate_hash = hybrid_candidate.candidate_hash()
            if candidate_hash == candidate.candidate_hash() or candidate_hash in seen_hashes:
                continue
            seen_hashes.add(candidate_hash)
            source = "hybrid_seed_llm_assisted" if not degraded else "hybrid_seed_degraded"
            seeds.append(
                StructureCandidate(
                    structure_id=f"{candidate.candidate_id}_hybrid_{index}",
                    candidate=self._with_policy_family(hybrid_candidate, policy_family),
                    candidate_hash=candidate_hash,
                    policy_family=policy_family,
                    source=source,
                    metadata={
                        "parent_structure_hash": candidate.candidate_hash(),
                        "hybrid_gateway_available": not degraded,
                        "hybrid_degraded_reason": (None if not degraded else "gateway_unavailable"),
                    },
                )
            )
            if len(seeds) >= self._config.max_hybrid_seeds:
                break
        return seeds

    def _build_monitoring_hybrid_seed(
        self,
        candidate: PolicyCandidateSchema,
    ) -> PolicyCandidateSchema | None:
        bundle = candidate.trinity_bundle
        known_metric_ids = {signal.metric_id for signal in candidate.monitoring_plan}
        metric_id = None
        intervention_id = None
        if bundle.problem_frame.kpis:
            metric_id = bundle.problem_frame.kpis[0].metric_id
        elif bundle.problem_frame.objectives:
            metric_id = bundle.problem_frame.objectives[0].metric_id
        if bundle.policy_spec.interventions:
            intervention_id = bundle.policy_spec.interventions[0].intervention_id
        if metric_id is None or metric_id in known_metric_ids:
            return None
        monitoring_signal = MonitoringSignalSpec(
            monitoring_id=f"monitor_hybrid_{candidate.candidate_id}",
            metric_id=metric_id,
            intervention_id=intervention_id,
            notes=["Hybrid seed added monitoring coverage for an untracked policy metric."],
        )
        return candidate.model_copy(
            update={
                "candidate_id": f"{candidate.candidate_id}_hybrid_monitoring",
                "monitoring_plan": [*candidate.monitoring_plan, monitoring_signal],
                "metadata": {
                    **candidate.metadata,
                    "hybrid_seed_type": "monitoring_expansion",
                },
            }
        )

    def _build_transport_hybrid_seed(
        self,
        candidate: PolicyCandidateSchema,
    ) -> PolicyCandidateSchema | None:
        if candidate.transport_assumptions:
            return None
        domain = str(candidate.metadata.get("domain") or candidate.candidate_id)
        assumption = TransportAssumptionSpec(
            transport_id=f"transport_hybrid_{candidate.candidate_id}",
            description="Policy effects transport from the observed sample to the declared target population.",
            source_context=domain,
            target_context=str(candidate.target_population.geography or domain),
            compatible_population_tags=list(candidate.target_population.compatible_transport_tags),
            caveats=[
                "Hybrid seed surfaces transport assumptions explicitly for later judge review."
            ],
        )
        return candidate.model_copy(
            update={
                "candidate_id": f"{candidate.candidate_id}_hybrid_transport",
                "transport_assumptions": [assumption],
                "metadata": {
                    **candidate.metadata,
                    "hybrid_seed_type": "transport_surface",
                },
            }
        )

    def _build_evidence_hybrid_seed(
        self,
        candidate: PolicyCandidateSchema,
    ) -> PolicyCandidateSchema | None:
        if candidate.evidence_assumptions:
            return None
        model_assumptions = list(candidate.trinity_bundle.model_spec.assumptions)
        if not model_assumptions:
            return None
        source = model_assumptions[0]
        assumption = PolicyAssumptionSpec(
            assumption_id=f"evidence_hybrid_{candidate.candidate_id}",
            description=source.description,
            source_assumption_id=source.assumption_id,
            notes=[
                "Hybrid seed promotes model assumption into surfaced policy evidence assumption."
            ],
        )
        return candidate.model_copy(
            update={
                "candidate_id": f"{candidate.candidate_id}_hybrid_evidence",
                "evidence_assumptions": [assumption],
                "metadata": {
                    **candidate.metadata,
                    "hybrid_seed_type": "evidence_surface",
                },
            }
        )

    def _with_policy_family(
        self,
        candidate: PolicyCandidateSchema,
        policy_family: str,
    ) -> PolicyCandidateSchema:
        return candidate.model_copy(
            update={"metadata": {**candidate.metadata, "policy_family": policy_family}}
        )

    def _record_rejection_lessons(
        self,
        structures: list[StructureCandidate],
        loop_id: str,
    ) -> list[LessonCard]:
        if self._lesson_registry is None:
            return []
        lessons: list[LessonCard] = []
        transfer_context = resolve_transfer_context(
            candidate=structures[0].candidate if structures else None,
            run_id=loop_id,
        )
        for structure in structures:
            if structure.accepted:
                continue
            lesson = LessonCard(
                kind=LessonKind.FAILURE,
                summary=(
                    f"Structure candidate '{structure.structure_id}' was rejected: "
                    f"{structure.rejection_reason or 'unknown'}."
                ),
                failure_type=structure.rejection_reason or "structure_rejected",
                stage_name="hierarchical_structure_search",
                fidelity_level=1,
                candidate_hash=structure.candidate_hash,
                source_run_id=loop_id,
                confidence=0.8,
                trust_level=LessonTrustLevel.LOCAL,
                tags=["policy_mode", "hierarchical_search"],
                mutation_hints=list(structure.mutation_hints),
                metadata={"structure_id": structure.structure_id},
            )
            self._lesson_registry.record_local(lesson, context=transfer_context)
            lessons.append(lesson)
        return lessons


def _run_blueprint_parameter_search(
    *,
    loop_id: str,
    adapter: StrategyAdapter,
    max_iterations: int,
    stage_b_evaluator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    stage_a_evaluator: Callable[[dict[str, Any], dict[str, Any]], tuple[float, bool]],
    context: dict[str, Any],
    initial_evaluations: list[dict[str, Any]],
) -> SearchResult:
    start = datetime.now(UTC)
    stopping = MaxIterations(max_iterations)
    stopping.reset()
    history: list[SearchIteration] = []
    best_candidate: dict[str, Any] | None = None
    best_objective = float("inf")
    best_rank_key: tuple[Any, ...] | None = None
    stage_a_count = 0
    stage_b_count = 0
    telemetry: dict[str, Any] = {"runtime": "blueprint_parameter_search"}

    for warm_start in initial_evaluations:
        policy_evaluation = _coerce_policy_evaluation(warm_start.get("stage_b_result"))
        objective_details = (
            policy_evaluation.as_legacy_objectives() if policy_evaluation is not None else []
        )
        record = SearchIteration(
            iteration=-1,
            candidate=dict(warm_start.get("candidate", {})),
            objective_value=float(warm_start.get("objective_value", float("inf"))),
            objective_details=objective_details,
            is_promising=bool(warm_start.get("is_promising", False)),
            stage_a_passed=True,
            stage_b_result=warm_start.get("stage_b_result"),
            duration_seconds=0.0,
            policy_evaluation=policy_evaluation,
        )
        history.append(record)
        if policy_evaluation is not None:
            rank_key = _policy_rank_key(policy_evaluation)
            if best_rank_key is None or rank_key > best_rank_key:
                best_rank_key = rank_key
                best_candidate = dict(record.candidate)
                best_objective = _diagnostic_policy_score(policy_evaluation)

    stopping_reason: str | None = None
    iteration = 0
    while iteration < max_iterations:
        stop_check = stopping.check(
            [_history_record(item) for item in history if item.iteration >= 0],
            {"iteration": iteration, "best_objective": best_objective},
        )
        if stop_check.should_stop:
            stopping_reason = stop_check.reason
            break

        candidate = adapter.generate(history, best_candidate, context)
        iter_start = datetime.now(UTC)
        stage_a_count += 1
        _, stage_a_passed = stage_a_evaluator(candidate, context)
        stage_b_result: dict[str, Any] | None = None
        policy_evaluation: PolicyEvaluationVector | None = None
        objective_value = float("inf")
        objective_details: list[Any] = []
        is_promising = False
        if stage_a_passed:
            stage_b_count += 1
            stage_b_result = stage_b_evaluator(candidate, context)
            policy_evaluation = _coerce_policy_evaluation(stage_b_result)
            if policy_evaluation is not None:
                objective_value = _diagnostic_policy_score(policy_evaluation)
                objective_details = policy_evaluation.as_legacy_objectives()
                rank_key = _policy_rank_key(policy_evaluation)
                if best_rank_key is None or rank_key > best_rank_key:
                    best_rank_key = rank_key
                    best_candidate = dict(candidate)
                    best_objective = objective_value
            else:
                objective_value = float((stage_b_result or {}).get("objective_value", float("inf")))
            is_promising = (
                bool(stage_b_result)
                and str((stage_b_result or {}).get("feedback", {}).get("verdict", "")).upper()
                == "APPROVE"
            )

        history.append(
            SearchIteration(
                iteration=iteration,
                candidate=dict(candidate),
                objective_value=objective_value,
                objective_details=objective_details,
                is_promising=is_promising,
                stage_a_passed=stage_a_passed,
                stage_b_result=stage_b_result,
                duration_seconds=(datetime.now(UTC) - iter_start).total_seconds(),
                policy_evaluation=policy_evaluation,
            )
        )
        iteration += 1

    if stopping_reason is None:
        stopping_reason = f"Maximum iterations ({max_iterations}) reached"

    return SearchResult(
        search_id=loop_id,
        status=SearchStatus.STOPPED,
        best_candidate=best_candidate,
        best_objective=best_objective,
        iterations_completed=iteration,
        history=history,
        stopping_reason=stopping_reason,
        total_duration_seconds=(datetime.now(UTC) - start).total_seconds(),
        stage_a_evaluations=stage_a_count,
        stage_b_evaluations=stage_b_count,
        telemetry=telemetry,
    )


def _coerce_policy_evaluation(stage_b_result: Any) -> PolicyEvaluationVector | None:
    if isinstance(stage_b_result, PolicyEvaluationVector):
        return stage_b_result
    if isinstance(stage_b_result, dict):
        raw = stage_b_result.get("policy_evaluation", stage_b_result)
        if isinstance(raw, PolicyEvaluationVector):
            return raw
        if isinstance(raw, dict):
            try:
                return PolicyEvaluationVector.model_validate(raw)
            except Exception:
                return None
    return None


def _optimizer_objectives_for_iteration(
    iteration: SearchIteration,
    spec: OptimizerObjectiveSpec,
) -> list[ObjectiveValue]:
    if iteration.policy_evaluation is None:
        return list(iteration.objective_details)
    return _optimizer_objectives_from_policy_evaluation(iteration.policy_evaluation, spec)


def _optimizer_objectives_from_policy_evaluation(
    evaluation: PolicyEvaluationVector,
    spec: OptimizerObjectiveSpec,
) -> list[ObjectiveValue]:
    infeasibility_penalty = _constraint_penalty(evaluation, spec)
    values: list[ObjectiveValue] = []
    for name, direction in zip(spec.objective_names, spec.directions, strict=False):
        channel = evaluation.channel(name)
        raw_value = float(channel.value) if channel is not None else 0.0
        if infeasibility_penalty > 0.0:
            if direction is OptimizationDirection.MAXIMIZE:
                raw_value -= infeasibility_penalty
            else:
                raw_value += infeasibility_penalty
        values.append(
            ObjectiveValue(
                name=name,
                raw_value=raw_value,
                direction=direction,
                weight=float(channel.weight) if channel is not None else 1.0,
                is_satisfied=True if channel is None else bool(channel.satisfied is not False),
                threshold=channel.threshold if channel is not None else None,
            )
        )
    return values


def _constraint_penalty(
    evaluation: PolicyEvaluationVector,
    spec: OptimizerObjectiveSpec,
) -> float:
    penalty = 0.0
    for name, extractor in spec.constraint_extractors.items():
        channel = evaluation.hard_constraints.get(name)
        if channel is None:
            penalty += 25.0
            continue
        raw_value = abs(float(extractor(evaluation)))
        if channel.status is ConstraintStatus.VIOLATED:
            penalty += 100.0 + raw_value
        elif channel.status is ConstraintStatus.NEAR_BINDING:
            penalty += 10.0 + (0.1 * raw_value)
    if not evaluation.feasible:
        penalty += 250.0 + (25.0 * float(len(evaluation.blocking_reasons)))
    return penalty


def _to_search_direction(channel: Any) -> OptimizationDirection:
    if channel is not None and channel.direction is ObjectiveDirection.MINIMIZE:
        return OptimizationDirection.MINIMIZE
    return OptimizationDirection.MAXIMIZE


def _policy_rank_key(evaluation: PolicyEvaluationVector) -> tuple[Any, ...]:
    objectives = evaluation.frontier_objectives("global_feasible")
    return (
        1 if evaluation.feasible else 0,
        float(objectives.get("policy_value", 0.0)),
        float(objectives.get("employment", 0.0)),
        float(objectives.get("welfare", 0.0)),
        -float(len(evaluation.blocking_reasons)),
    )


def _diagnostic_policy_score(evaluation: PolicyEvaluationVector) -> float:
    objectives = evaluation.frontier_objectives("global_feasible")
    if not objectives:
        return float("inf")
    score = -sum(float(value) for value in objectives.values())
    if not evaluation.feasible:
        score += 1_000_000.0 + (1000.0 * float(len(evaluation.blocking_reasons)))
    return float(score)


def _history_record(iteration: SearchIteration) -> dict[str, Any]:
    return {
        "iteration": iteration.iteration,
        "objective_value": iteration.objective_value,
        "is_promising": iteration.is_promising,
        "stage_a_passed": iteration.stage_a_passed,
    }


def _always_pass_stage_a(candidate: dict[str, Any], context: dict[str, Any]) -> tuple[float, bool]:
    del candidate, context
    return 0.0, True


def _normalize_value_like(value: Any) -> float | int:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, MoneyValue):
        return float(value.amount)
    if isinstance(value, RateValue):
        return float(value.as_ratio())
    if isinstance(value, CountValue):
        return int(value.value)
    if isinstance(value, DurationValue):
        return float(value.value)
    return float(value)


def _restore_value_like(value: Any, exemplar: Any) -> Any:
    if exemplar is None:
        return value
    if isinstance(exemplar, Decimal):
        return Decimal(str(value))
    if isinstance(exemplar, int) and not isinstance(exemplar, bool):
        return int(round(float(value)))
    if isinstance(exemplar, float):
        return float(value)
    if isinstance(exemplar, MoneyValue):
        return exemplar.model_copy(update={"amount": Decimal(str(value))})
    if isinstance(exemplar, RateValue):
        if exemplar.base == "percent":
            return exemplar.model_copy(update={"value": float(value) * 100.0})
        return exemplar.model_copy(update={"value": float(value)})
    if isinstance(exemplar, CountValue):
        return exemplar.model_copy(update={"value": int(round(float(value)))})
    if isinstance(exemplar, DurationValue):
        return exemplar.model_copy(update={"value": float(value)})
    return value


def _parameter_type(value: Any) -> ParameterType:
    if isinstance(value, (int, CountValue)) and not isinstance(value, bool):
        return ParameterType.INTEGER
    return ParameterType.CONTINUOUS


def _derive_bounds(
    default: float | int,
    lower: float | int | None,
    upper: float | int | None,
) -> tuple[float, float]:
    if lower is not None and upper is not None:
        return float(lower), float(upper)
    base = float(default)
    if base == 0.0:
        return (
            float(lower if lower is not None else -1.0),
            float(upper if upper is not None else 1.0),
        )
    span = abs(base) * 0.2
    derived_lower = float(lower if lower is not None else base - span)
    derived_upper = float(upper if upper is not None else base + span)
    if derived_lower == derived_upper:
        derived_upper = derived_lower + 1.0
    if derived_lower > derived_upper:
        derived_lower, derived_upper = derived_upper, derived_lower
    return derived_lower, derived_upper


def _score_narrative_variant(brief: Any, compliance: Any) -> float:
    base = 1.0 if getattr(compliance, "passed", False) else 0.0
    action_score = min(len(getattr(brief, "recommended_actions", [])), 3) / 10.0
    tradeoff_score = min(len(getattr(brief, "tradeoffs", [])), 4) / 10.0
    summary_length = len(str(getattr(brief, "executive_summary", "")))
    readability_bonus = 0.1 if 80 <= summary_length <= 400 else 0.0
    return base + action_score + tradeoff_score + readability_bonus


__all__ = [
    "HierarchicalSearchConfig",
    "HierarchicalSearchCoordinator",
    "HierarchicalSearchResult",
    "HierarchicalSearchState",
    "NarrativeVariant",
    "ParameterSearchSpec",
    "PolicyParameterCodec",
    "PolicySearchLevel",
    "StructureCandidate",
]
