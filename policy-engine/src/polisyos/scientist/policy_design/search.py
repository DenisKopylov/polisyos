"""Hierarchical policy search over structure, parameters, and narrative."""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import ArtifactRef
from polisyos.ir.governance.policy_spec import PolicySearchLevel
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    CandidateStrategyContext,
    EvaluationBundle,
    ParetoViewProjection,
)
from polisyos.scientist.methods.search.controller import (
    SearchIteration,
    SearchResult,
    SearchStatus,
)
from polisyos.scientist.methods.search.frontier import (
    candidate_payloads_equal,
    funnel_prior_ticket_id,
    invoke_candidate_evaluator,
    materialize_candidate_proposal,
    policy_candidate_hash,
    strategy_candidate_payload,
)
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonRegistry,
    LessonTrustLevel,
)
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreStatus,
    ObjectiveValue,
    OptimizationDirection,
    _evaluation_matches_selected_objectives,
    _unestablished_score_assessment,
    objective_value_matches_rule,
)
from polisyos.scientist.methods.search.pareto_registry import (
    ParetoRegistry,
    ParetoView,
    verify_policy_evaluation_source,
)
from polisyos.scientist.methods.search.stopping import MaxIterations
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.codec import _get_path, _set_path
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.transfer import RunFingerprint
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    ParameterBounds,
    ParameterType,
)
from polisyos.scientist.methods.search.transfer_context import resolve_transfer_context
from polisyos.scientist.orchestration.llm.factory import create_traced_gateway_client
from polisyos.scientist.policy_design.critic import (
    ConstraintCritic,
    ConstraintCriticInput,
)
from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveDirection,
    ObjectiveStack,
    PolicyEvaluationBundle,
    PolicyEvaluationVector,
    _normalize_policy_evaluation_vector,
    _policy_vector_channel_assessment,
    _policy_vector_channel_rule_spec,
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
    require_explicit_parameter_bounds: bool = True
    allow_legacy_shadow_inferred_bounds: bool = False


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
    objective_rule_specs: dict[str, str]
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
    pareto_projection: ParetoViewProjection | None = None


# SearchResult is a dataclass whose deferred annotation includes ParetoViewProjection.
# Resolve the containing Pydantic models after the imported contracts are available so
# coordinator construction does not fail lazily on its first runtime result.
HierarchicalSearchState.model_rebuild()
HierarchicalSearchResult.model_rebuild()


class Phase2BoundsApplicability(BaseModel):
    """Search-owned applicability result for explicit Phase-2 parameter bounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    result_id: str
    invocation_id: str
    status: str
    checked_preconditions: list[dict[str, Any]] = Field(default_factory=list)
    failed_preconditions: list[dict[str, Any]] = Field(default_factory=list)
    repair_options: list[dict[str, Any]] = Field(default_factory=list)


class Phase2BoundsBlocker(BaseModel):
    """Search-owned blocker for missing or invalid Phase-2 lex bounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocker_id: str
    workspace_id: str
    blocked_port: str
    missing_input: str
    reason: str
    frontier_snapshot_ref: str
    applicability_result_ref: str
    repair_options: list[dict[str, Any]] = Field(default_factory=list)
    producer_missing_label: str = "producer_missing"


class Phase2ParameterBoundsResult(BaseModel):
    """Applicability plus frontier provenance for Phase-2 parameter search bounds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applicability: Phase2BoundsApplicability
    blocker: Phase2BoundsBlocker | None = None
    frontier_payload: dict[str, Any]


@dataclass(slots=True)
class PolicyParameterCodec:
    """Policy parameter codec public type."""

    parameter_paths: dict[str, str]
    template_values: dict[str, Any]

    def encode(self, candidate: dict[str, Any]) -> dict[str, Any]:
        encoded: dict[str, Any] = {}
        for name, path in self.parameter_paths.items():
            value = _get_path(candidate, path)
            exemplar = self.template_values.get(name)
            if isinstance(value, dict) and isinstance(
                exemplar, (MoneyValue, RateValue, CountValue, DurationValue)
            ):
                value = type(exemplar).model_validate(value)
            encoded[name] = _normalize_value_like(value)
        return encoded

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
        source_store: Any | None = None,
        lesson_registry: LessonRegistry | None = None,
        translator_worker: PolicyTranslatorWorker | None = None,
        translator_compliance: TranslatorCompliancePass | None = None,
        constraint_critic: ConstraintCritic | None = None,
        config: HierarchicalSearchConfig | None = None,
    ) -> None:
        self._pareto_registry = pareto_registry
        self._source_store = source_store
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
                    update={
                        "accepted": False,
                        "rejection_reason": "structure_validator_rejected",
                    }
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
        parameter_specs = {
            parameter.param_id: parameter
            for parameter in candidate.trinity_bundle.policy_spec.parameters
        }
        bounds: list[ParameterBounds] = []
        parameter_paths: dict[str, str] = {}
        template_values: dict[str, Any] = {}

        for parameter in candidate.trinity_bundle.policy_spec.parameters:
            if not parameter.tunable:
                continue
            default = _normalize_value_like(parameter.default_value)
            lower = (
                None if parameter.min_value is None else _normalize_value_like(parameter.min_value)
            )
            upper = (
                None if parameter.max_value is None else _normalize_value_like(parameter.max_value)
            )
            dtype = _parameter_type(parameter.default_value)
            if self._config.require_explicit_parameter_bounds:
                phase2_bounds = derive_phase2_parameter_bounds(
                    workspace_id=str(
                        candidate.metadata.get("workspace_id") or candidate.candidate_id
                    ),
                    invocation_id=f"invoke-{parameter.param_id}",
                    default=default,
                    lower=lower,
                    upper=upper,
                )
                if phase2_bounds.blocker is not None:
                    raise ValueError(phase2_bounds.blocker.reason)
                bounds.append(
                    ParameterBounds.explicit(
                        name=parameter.param_id,
                        lower=lower,
                        upper=upper,
                        dtype=dtype,
                    )
                )
            else:
                if not self._config.allow_legacy_shadow_inferred_bounds:
                    raise ValueError(
                        "Inferred lex bounds are legacy-shadow/candidate-only; "
                        "set allow_legacy_shadow_inferred_bounds=True for compatibility."
                    )
                derived_lower, derived_upper = _derive_bounds(default, lower, upper)
                bounds.append(
                    ParameterBounds(
                        name=parameter.param_id,
                        lower=derived_lower,
                        upper=derived_upper,
                        dtype=dtype,
                    )
                )
            index = intervention_indexes[parameter.intervention_id]
            parameter_paths[parameter.param_id] = (
                f"trinity_bundle.policy_spec.interventions.{index}.params.{parameter.param_path}"
            )
            template_values[parameter.param_id] = parameter.default_value

        for index, entry in enumerate(candidate.parameter_schedule):
            parameter = parameter_specs[entry.param_id]
            if not parameter.tunable:
                continue
            default = _normalize_value_like(entry.scheduled_value)
            lower = (
                None if parameter.min_value is None else _normalize_value_like(parameter.min_value)
            )
            upper = (
                None if parameter.max_value is None else _normalize_value_like(parameter.max_value)
            )
            dtype = _parameter_type(entry.scheduled_value)
            if self._config.require_explicit_parameter_bounds:
                phase2_bounds = derive_phase2_parameter_bounds(
                    workspace_id=str(
                        candidate.metadata.get("workspace_id") or candidate.candidate_id
                    ),
                    invocation_id=f"invoke-schedule-{entry.entry_id}",
                    default=default,
                    lower=lower,
                    upper=upper,
                )
                if phase2_bounds.blocker is not None:
                    raise ValueError(phase2_bounds.blocker.reason)
                bounds.append(
                    ParameterBounds.explicit(
                        name=f"schedule::{entry.entry_id}",
                        lower=lower,
                        upper=upper,
                        dtype=dtype,
                    )
                )
            else:
                if not self._config.allow_legacy_shadow_inferred_bounds:
                    raise ValueError(
                        "Inferred schedule bounds are legacy-shadow/candidate-only; "
                        "set allow_legacy_shadow_inferred_bounds=True for compatibility."
                    )
                lower, upper = _derive_bounds(default, lower, upper)
                bounds.append(
                    ParameterBounds(
                        name=f"schedule::{entry.entry_id}",
                        lower=lower,
                        upper=upper,
                        dtype=dtype,
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
        grouped_channels = [
            *(("primary", channel) for channel in template.primary.values()),
            *(("secondary", channel) for channel in template.secondary.values()),
            *(("penalties", channel) for channel in template.penalties.values()),
        ]
        channels_by_name: dict[str, tuple[str, Any]] = {}
        for group, channel in grouped_channels:
            existing = channels_by_name.get(channel.name)
            if existing is not None and _policy_vector_channel_rule_spec(
                existing[1], existing[0]
            ) != _policy_vector_channel_rule_spec(channel, group):
                raise ValueError(
                    f"selected policy objective {channel.name!r} has ambiguous channel rules"
                )
            channels_by_name.setdefault(channel.name, (group, channel))
        objective_names = list(channels_by_name)
        directions = [_to_search_direction(channels_by_name[name][1]) for name in objective_names]
        objective_rule_specs = {
            name: _policy_vector_channel_rule_spec(channel, group)
            for name, (group, channel) in channels_by_name.items()
        }
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
            objective_rule_specs=objective_rule_specs,
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
        candidate_only_seed_evaluations: list[Evaluation] | None = None,
    ) -> SearchResult:
        spec = self.build_parameter_search_spec(structure.candidate)
        objective_spec = self.build_optimizer_objective_spec(structure.candidate)
        codec = PolicyParameterCodec(spec.parameter_paths, spec.template_values)
        strategy = MOBayesianOptimizer(
            spec.search_space,
            objective_names=objective_spec.objective_names,
            directions=objective_spec.directions,
            objective_rule_specs=objective_spec.objective_rule_specs,
        )
        adapter = StrategyAdapter(
            strategy,
            spec.search_space,
            codec=codec,
            canonical_template=structure.candidate,
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
        effective_stage_a = stage_a_evaluator or _always_pass_stage_a
        (
            transfer_initials,
            transfer_report,
            transfer_stage_a_count,
            transfer_stage_b_count,
        ) = _reevaluate_candidate_only_transfer_seeds(
            candidate_only_seed_evaluations or [],
            spec=spec,
            objective_spec=objective_spec,
            codec=codec,
            context=context,
            stage_a_evaluator=effective_stage_a,
            stage_b_evaluator=stage_b_evaluator,
            constraint_critic=self._constraint_critic,
            source_store=self._source_store,
        )
        initial_evaluations.extend(transfer_initials)
        result = _run_blueprint_parameter_search(
            loop_id=loop_id,
            adapter=adapter,
            max_iterations=self._config.max_parameter_iterations,
            stage_b_evaluator=stage_b_evaluator,
            stage_a_evaluator=effective_stage_a,
            context=context,
            initial_evaluations=initial_evaluations,
            source_store=self._source_store,
        )
        result.stage_a_evaluations += transfer_stage_a_count
        result.stage_b_evaluations += transfer_stage_b_count
        if candidate_only_seed_evaluations is not None:
            result.telemetry["candidate_only_transfer"] = transfer_report
        result.telemetry["optimizer_objectives"] = list(objective_spec.objective_names)
        result.telemetry["frontier_projection_names"] = list(
            objective_spec.frontier_projection_names
        )
        result.telemetry["constraint_names"] = sorted(objective_spec.constraint_extractors)
        if seed_bundle is not None:
            result.telemetry["frontier_seed_count"] = len(seed_bundle.entries)
            result.telemetry["frontier_scope_refusals"] = [
                refusal.model_dump(mode="json") for refusal in seed_bundle.scope_refusals
            ]
            result.telemetry["seed_domains"] = list(seed_bundle.seed_domains)
            result.telemetry["cross_domain_seed_count"] = seed_bundle.cross_domain_seed_count
        if self._pareto_registry is not None:
            for iteration in result.history:
                if iteration.policy_evaluation is None:
                    continue
                if iteration.iteration < 0 and not iteration.current_policy_reevaluation:
                    continue
                self._pareto_registry.update(
                    loop_id,
                    candidate_hash=policy_candidate_hash(
                        iteration.candidate_proposal or iteration.candidate
                    ),
                    evaluation=iteration.policy_evaluation,
                    candidate_id=iteration.policy_evaluation.candidate_id,
                    candidate_ref=iteration.candidate_ref,
                    evaluation_ref=iteration.evaluation_ref,
                    policy_family=structure.policy_family,
                    seed_payload=dict(iteration.candidate),
                    candidate_proposal=iteration.candidate_proposal,
                    task_family=transfer_context.task_family,
                    domain=transfer_context.domain,
                    transfer_context=transfer_context,
                    metadata={
                        "structure_id": structure.structure_id,
                        "parent_structure_hash": structure.metadata.get("parent_structure_hash"),
                    },
                )
            result.pareto_front = self._pareto_registry.as_legacy_frontier_payload(
                loop_id, transfer_context=transfer_context
            )
            result.pareto_projection = self._pareto_registry.get_snapshot(
                loop_id, transfer_context=transfer_context
            ).project_view(ParetoView.GLOBAL_FEASIBLE)
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
        candidate_only_seed_evaluations: list[Evaluation] | None = None,
    ) -> HierarchicalSearchResult:
        if candidate_only_seed_evaluations and stage_b_evaluator is None:
            raise ValueError("candidate-only transfer requires a policy Stage B evaluator")
        transfer_context = resolve_transfer_context(
            candidate=candidate,
            context=initial_context or {},
            run_id=loop_id,
        )
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
                    candidate_only_seed_evaluations=candidate_only_seed_evaluations,
                )

        if candidate_only_seed_evaluations:
            admitted = sum(
                int(result.telemetry.get("candidate_only_transfer", {}).get("accepted_count", 0))
                for result in state.parameter_search_results.values()
            )
            if admitted == 0:
                raise ValueError(
                    "candidate-only transfer requested but no source candidate passed "
                    "policy validation and Stage A/Stage B re-evaluation"
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

        shared_frontier: list[dict[str, Any]] = []
        pareto_projection = None
        if self._pareto_registry is not None:
            shared_frontier = self._pareto_registry.as_legacy_frontier_payload(
                loop_id, transfer_context=transfer_context
            )
            pareto_projection = self._pareto_registry.get_snapshot(
                loop_id, transfer_context=transfer_context
            ).project_view(ParetoView.GLOBAL_FEASIBLE)
        return HierarchicalSearchResult(
            state=state,
            shared_frontier=shared_frontier,
            pareto_projection=pareto_projection,
        )

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
            candidate=candidate, fallback_run_id=candidate.candidate_id
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
                proposal = entry.candidate_proposal
                source = (
                    proposal.strategy_context.subject
                    if proposal is not None
                    and proposal.strategy_context is not None
                    and proposal.strategy_context.policy_schema
                    else entry.seed_payload
                )
                seeded_candidate = PolicyCandidateSchema.model_validate(source)
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
        gateway_available = client is not None
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
            seeds.append(
                StructureCandidate(
                    structure_id=f"{candidate.candidate_id}_hybrid_{index}",
                    candidate=self._with_policy_family(hybrid_candidate, policy_family),
                    candidate_hash=candidate_hash,
                    policy_family=policy_family,
                    source="hybrid_seed_deterministic",
                    metadata={
                        "parent_structure_hash": candidate.candidate_hash(),
                        "hybrid_gateway_available": gateway_available,
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


def _optional_artifact_ref(value: Any) -> ArtifactRef | None:
    if value is None:
        return None
    try:
        return ArtifactRef.model_validate(value)
    except (TypeError, ValueError):
        return None


def _run_blueprint_parameter_search(
    *,
    loop_id: str,
    adapter: StrategyAdapter,
    max_iterations: int,
    stage_b_evaluator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    stage_a_evaluator: Callable[[dict[str, Any], dict[str, Any]], tuple[float, bool]],
    context: dict[str, Any],
    initial_evaluations: list[dict[str, Any]],
    source_store: Any | None = None,
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
        source_payload = warm_start.get("stage_b_result")
        source_results = (
            source_payload.get("simulation_results") if isinstance(source_payload, dict) else None
        )
        policy_evaluation = _coerce_policy_evaluation(source_payload)
        warm_metadata = warm_start.get("metadata")
        proposal_data = warm_start.get("candidate_proposal")
        proposal = (
            CandidateProposal.model_validate(proposal_data) if proposal_data is not None else None
        )
        warm_candidate = dict(warm_start.get("candidate", {}))
        if proposal is not None and not candidate_payloads_equal(
            materialize_candidate_proposal(proposal), warm_candidate
        ):
            raise ValueError("warm_start_candidate_subject_mismatch")
        warm_candidate_ref = _optional_artifact_ref(warm_start.get("candidate_ref"))
        warm_evaluation_ref = _optional_artifact_ref(warm_start.get("evaluation_ref"))
        source_verified = verify_policy_evaluation_source(
            source_store, proposal, policy_evaluation, warm_candidate_ref, warm_evaluation_ref
        )
        seed_only = (
            isinstance(warm_metadata, dict) and warm_metadata.get("seed_only") is True
        ) or not source_verified
        objective_value: float | None = None
        score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
        score_assessment = None
        objective_details: list[ObjectiveValue] = []
        rank_key = None
        if policy_evaluation is not None and not seed_only:
            objective_value, score_status = policy_evaluation.legacy_scalar_proxy_for_search(
                source_results if isinstance(source_results, dict) else None
            )
            score_assessment = policy_evaluation.score_assessment
            rank_key = _policy_rank_key(
                policy_evaluation,
                source_results if isinstance(source_results, dict) else None,
            )
            objective_details = policy_evaluation.as_legacy_objectives(
                source_results if isinstance(source_results, dict) else None
            )
        record = SearchIteration(
            iteration=-1,
            candidate=warm_candidate,
            objective_value=(
                objective_value
                if score_status is ObjectiveScoreStatus.AVAILABLE
                else None
                if seed_only
                else warm_start.get("objective_value")
            ),
            objective_details=objective_details,
            is_promising=not seed_only and bool(warm_start.get("is_promising", False)),
            stage_a_passed=True,
            stage_b_result=source_payload,
            duration_seconds=0.0,
            policy_evaluation=policy_evaluation,
            score_status=score_status,
            score_assessment=score_assessment,
            candidate_proposal=proposal,
            candidate_ref=warm_candidate_ref,
            evaluation_ref=warm_evaluation_ref,
            current_policy_reevaluation=(
                warm_start.get("current_policy_reevaluation") is True and source_verified
            ),
        )
        history.append(record)
        if rank_key is not None:
            if best_rank_key is None or rank_key > best_rank_key:
                best_rank_key = rank_key
                best_candidate = dict(record.candidate)
                best_objective = _diagnostic_policy_score(
                    policy_evaluation,
                    source_results if isinstance(source_results, dict) else None,
                )

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

        proposal = adapter.generate_proposal(history, best_candidate, context)
        candidate = materialize_candidate_proposal(proposal)
        iter_start = datetime.now(UTC)
        stage_a_count += 1
        stage_a_result = invoke_candidate_evaluator(
            stage_a_evaluator, copy.deepcopy(candidate), context, proposal
        )
        if isinstance(stage_a_result, EvaluationBundle):
            stage_a_passed = stage_a_result.stage_a_passed
            stage_a_ticket = funnel_prior_ticket_id(
                stage_a_evaluator, stage_b_evaluator, stage_a_result
            )
        else:
            _, stage_a_passed = stage_a_result
            stage_a_ticket = None
        stage_b_result: dict[str, Any] | None = None
        policy_evaluation: PolicyEvaluationVector | None = None
        objective_value: float | None = None
        score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
        score_assessment = None
        objective_details: list[Any] = []
        is_promising = False
        candidate_ref: ArtifactRef | None = None
        evaluation_ref: ArtifactRef | None = None
        source_verified = False
        if stage_a_passed:
            stage_b_count += 1
            stage_b_result = invoke_candidate_evaluator(
                stage_b_evaluator,
                copy.deepcopy(candidate),
                context,
                proposal,
                prior_ticket_id=stage_a_ticket,
            )
            policy_evaluation = _coerce_policy_evaluation(stage_b_result)
            try:
                policy_candidate_hash(
                    proposal,
                    metadata_hash=(
                        policy_evaluation.metadata.get("candidate_hash")
                        if policy_evaluation
                        else None
                    ),
                    explicit_hash=(
                        stage_b_result.get("candidate_hash")
                        if isinstance(stage_b_result, dict)
                        else None
                    ),
                )
            except (TypeError, ValueError):
                policy_evaluation = None
                score_status = ObjectiveScoreStatus.INVALID
                stage_b_result = {**(stage_b_result or {}), "candidate_identity_error": "mismatch"}
            if policy_evaluation is not None:
                candidate_ref = _optional_artifact_ref(stage_b_result.get("candidate_ref"))
                evaluation_ref = _optional_artifact_ref(stage_b_result.get("policy_evaluation_ref"))
                source_verified = verify_policy_evaluation_source(
                    source_store, proposal, policy_evaluation, candidate_ref, evaluation_ref
                )
            if policy_evaluation is not None and source_verified:
                objective_details = policy_evaluation.as_legacy_objectives(
                    stage_b_result.get("simulation_results")
                    if isinstance(stage_b_result.get("simulation_results"), dict)
                    else None
                )
                source_results = stage_b_result.get("simulation_results")
                score_assessment = policy_evaluation.score_assessment
                objective_value, score_status = policy_evaluation.legacy_scalar_proxy_for_search(
                    source_results if isinstance(source_results, dict) else None
                )
                rank_key = _policy_rank_key(
                    policy_evaluation,
                    source_results if isinstance(source_results, dict) else None,
                )
                if rank_key is not None and (best_rank_key is None or rank_key > best_rank_key):
                    best_rank_key = rank_key
                    best_candidate = dict(candidate)
                    diagnostic_score = _diagnostic_policy_score(
                        policy_evaluation,
                        source_results if isinstance(source_results, dict) else None,
                    )
                    if diagnostic_score is not None:
                        best_objective = diagnostic_score
            is_promising = (
                policy_evaluation is not None
                and source_verified
                and bool(stage_b_result)
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
                score_status=score_status,
                score_assessment=score_assessment,
                candidate_proposal=proposal,
                candidate_ref=candidate_ref,
                evaluation_ref=evaluation_ref,
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
    if isinstance(stage_b_result, dict):
        raw = stage_b_result.get("policy_evaluation", stage_b_result)
    else:
        raw = stage_b_result
    try:
        return _normalize_policy_evaluation_vector(raw, allow_mapping=isinstance(raw, dict))
    except (TypeError, ValueError):
        return None


def _optimizer_objectives_for_iteration(
    iteration: SearchIteration,
    spec: OptimizerObjectiveSpec,
) -> list[ObjectiveValue]:
    if iteration.policy_evaluation is None:
        return list(iteration.objective_details)
    return _optimizer_objectives_from_policy_evaluation(
        iteration.policy_evaluation, spec, iteration.stage_b_result
    )


def _optimizer_objectives_from_policy_evaluation(
    evaluation: PolicyEvaluationVector,
    spec: OptimizerObjectiveSpec,
    source: Any = None,
) -> list[ObjectiveValue]:
    infeasibility_penalty = _constraint_penalty(evaluation, spec)
    values: list[ObjectiveValue] = []
    groups = ("primary", "secondary", "penalties")
    for name, direction in zip(spec.objective_names, spec.directions, strict=True):
        expected_rule_spec = spec.objective_rule_specs.get(name)
        if expected_rule_spec is None:
            continue
        try:
            rule = json.loads(expected_rule_spec)
            group = rule["group"]
        except (KeyError, TypeError, ValueError):
            continue
        if group not in groups or rule.get("name") != name:
            continue
        channels = getattr(evaluation, group)
        channel = channels.get(name)
        if channel is None:
            continue
        raw_value = float(channel.value)
        assessment = _policy_vector_channel_assessment(channel, group, source)
        source_is_selected = (
            assessment.rule_spec == expected_rule_spec
            and objective_value_matches_rule(
                ObjectiveValue(
                    name=name,
                    raw_value=raw_value,
                    direction=direction,
                    weight=float(channel.weight),
                    is_satisfied=bool(channel.satisfied is not False),
                    threshold=channel.threshold,
                    score_status=ObjectiveScoreStatus.AVAILABLE,
                    score_assessment=assessment,
                ),
                source,
                expected_name=name,
                expected_direction=direction,
                expected_rule_spec=expected_rule_spec,
            )
        )
        if infeasibility_penalty > 0.0:
            if direction is OptimizationDirection.MAXIMIZE:
                raw_value -= infeasibility_penalty
            else:
                raw_value += infeasibility_penalty
            source_is_selected = False
        values.append(
            ObjectiveValue(
                name=name,
                raw_value=raw_value,
                direction=direction,
                weight=float(channel.weight),
                is_satisfied=bool(channel.satisfied is not False),
                threshold=channel.threshold,
                score_status=(
                    ObjectiveScoreStatus.AVAILABLE
                    if source_is_selected
                    else ObjectiveScoreStatus.NOT_ESTABLISHED
                ),
                score_assessment=(
                    assessment
                    if source_is_selected
                    else _unestablished_score_assessment(
                        "selected_policy_objective_rule_not_reconciled"
                    )
                ),
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


def _policy_rank_key(
    evaluation: PolicyEvaluationVector,
    source_results: dict[str, Any] | None = None,
) -> tuple[Any, ...] | None:
    objectives = evaluation.frontier_objectives("global_feasible", source_results)
    if not {"policy_value", "employment"}.issubset(objectives):
        return None
    return (
        1 if evaluation.feasible else 0,
        float(objectives["policy_value"]),
        float(objectives["employment"]),
        -float(len(evaluation.blocking_reasons)),
    )


def _diagnostic_policy_score(
    evaluation: PolicyEvaluationVector,
    source_results: dict[str, Any] | None = None,
) -> float | None:
    score, status = evaluation.legacy_scalar_proxy_for_search(source_results)
    return score if status is ObjectiveScoreStatus.AVAILABLE else None


def _history_record(iteration: SearchIteration) -> dict[str, Any]:
    """Expose only source-reconciled objective scores to stopping criteria."""
    record = {
        "iteration": iteration.iteration,
        "score_status": iteration.score_status.value,
        "is_promising": iteration.is_promising,
        "stage_a_passed": iteration.stage_a_passed,
    }
    policy_evaluation = iteration.policy_evaluation
    stage_b_result = iteration.stage_b_result
    source_results = (
        stage_b_result.get("simulation_results") if isinstance(stage_b_result, dict) else None
    )
    if (
        iteration.score_status is ObjectiveScoreStatus.AVAILABLE
        and policy_evaluation is not None
        and iteration.score_assessment is not None
        and iteration.score_assessment == policy_evaluation.score_assessment
        and policy_evaluation.score_assessment_matches_channels(
            source_results if isinstance(source_results, dict) else None
        )
    ):
        record["objective_value"] = iteration.score_assessment.value
    return record


def _reevaluate_candidate_only_transfer_seeds(
    evaluations: list[Evaluation],
    *,
    spec: ParameterSearchSpec,
    objective_spec: OptimizerObjectiveSpec,
    codec: PolicyParameterCodec,
    context: dict[str, Any],
    stage_a_evaluator: Callable[[dict[str, Any], dict[str, Any]], tuple[float, bool]],
    stage_b_evaluator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    constraint_critic: ConstraintCritic,
    source_store: Any | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], int, int]:
    """Turn exact-space V5 rows into policy candidates, never into policy scores."""
    from polisyos.scientist.methods.autotune.models import BayesianSourceProfile

    accepted: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "requested_count": len(evaluations),
        "considered_count": 0,
        "accepted_count": 0,
        "rejected_by_reason": {},
        "source_reported_profile_kind_counts": {},
        "accepted_sources": [],
        "generic_source_objectives_used": False,
        "generic_source_scalar_used_as_policy_objective": False,
        "source_scalar_may_order_candidate_proposals": True,
        "candidate_policy_stage_b_recomputed": True,
        "candidate_policy_constraint_critic_applied": True,
        "source_profile_attestation": "producer_reported_not_independently_recomputed",
    }
    stage_a_count = 0
    stage_b_count = 0

    def reject(reason: str) -> None:
        reasons = report["rejected_by_reason"]
        reasons[reason] = int(reasons.get(reason, 0)) + 1

    expected_space = spec.search_space.sobol_space_fingerprint()
    selected_directions = {
        name: direction
        for name, direction in zip(
            objective_spec.objective_names, objective_spec.directions, strict=True
        )
    }
    for evaluation in evaluations:
        report["considered_count"] += 1
        if not _evaluation_matches_selected_objectives(
            evaluation,
            objective_names=objective_spec.objective_names,
            objective_directions=selected_directions,
            objective_rule_specs=objective_spec.objective_rule_specs,
        ):
            reject("source_selected_objective_basis_not_reconciled")
            continue
        source_metadata = evaluation.metadata
        history_payload = source_metadata.get("candidate_only_transfer_source_history_ref")
        binding_payload = source_metadata.get("candidate_only_transfer_source_binding")
        index_payload = source_metadata.get("candidate_only_transfer_index_ref")
        try:
            history_ref = ArtifactRef.model_validate(history_payload)
            index_ref = ArtifactRef.model_validate(index_payload)
            if not isinstance(binding_payload, dict):
                raise TypeError("source binding must be an object")
            source_binding = RunFingerprint.model_validate({**binding_payload, "embedding": []})
        except (TypeError, ValueError):
            reject("source_history_or_index_ref_invalid")
            continue
        if (history_ref.kind, history_ref.media_type) != (
            "search.transfer.history",
            "application/json",
        ) or (index_ref.kind, index_ref.media_type) != (
            "vector_memory.bundle",
            "application/json",
        ):
            reject("source_history_or_index_ref_kind_mismatch")
            continue
        profile_payload = source_metadata.get("warm_start_compatibility")
        try:
            profile = BayesianSourceProfile.model_validate(profile_payload)
        except (TypeError, ValueError):
            reject("source_profile_missing_or_invalid")
            continue
        profile_kinds = report["source_reported_profile_kind_counts"]
        profile_kinds[profile.profile_kind] = int(profile_kinds.get(profile.profile_kind, 0)) + 1
        if source_binding.history_ref != history_ref or source_binding.run_id != str(
            source_metadata.get("source_run_id") or ""
        ):
            reject("source_index_binding_history_mismatch")
            continue
        expected_directions = {
            name: direction.value for name, direction in selected_directions.items()
        }
        if (
            source_binding.objective_names != objective_spec.objective_names
            or source_binding.objective_directions != expected_directions
            or source_binding.objective_rule_specs != objective_spec.objective_rule_specs
        ):
            reject("source_selected_objective_binding_mismatch")
            continue
        if (
            profile.search_space_fingerprint != expected_space
            or profile.search_space_fingerprint != source_binding.space_hash
        ):
            reject("source_profile_search_space_mismatch")
            continue
        params = evaluation.params
        invalid_params = _candidate_only_parameter_error(params, spec.search_space)
        if invalid_params is not None:
            reject(invalid_params)
            continue
        try:
            candidate_payload = codec.decode(
                dict(params),
                template=spec.candidate.as_search_payload(),
            )
            candidate_payload.pop("candidate_hash", None)
            policy_candidate = PolicyCandidateSchema.model_validate(candidate_payload)
        except (TypeError, ValueError):
            reject("source_parameters_do_not_form_policy_candidate")
            continue
        candidate_context = CandidateStrategyContext(
            producer="policy_design",
            subject=policy_candidate.model_dump(mode="json", exclude_none=True),
            policy_schema=True,
            policy_transport=True,
        )
        candidate_payload = strategy_candidate_payload(candidate_context)
        proposal = CandidateProposal(
            candidate_id=policy_candidate.candidate_id,
            payload=candidate_payload,
            strategy_context=candidate_context,
        )
        candidate_hash = policy_candidate_hash(proposal)
        critique = constraint_critic.evaluate(ConstraintCriticInput(candidate=policy_candidate))
        stage_a_count += 1
        if not critique.passed:
            reject("policy_constraint_critic_rejected")
            continue
        stage_a_result = invoke_candidate_evaluator(
            stage_a_evaluator, copy.deepcopy(candidate_payload), dict(context), proposal
        )
        if isinstance(stage_a_result, EvaluationBundle):
            stage_a_passed = stage_a_result.stage_a_passed
            stage_a_ticket = funnel_prior_ticket_id(
                stage_a_evaluator, stage_b_evaluator, stage_a_result
            )
        else:
            _, stage_a_passed = stage_a_result
            stage_a_ticket = None
        if not stage_a_passed:
            reject("policy_stage_a_rejected")
            continue
        stage_b_count += 1
        transfer_record = {
            "source_run_id": str(source_metadata.get("source_run_id") or ""),
            "source_candidate_id": evaluation.candidate_id,
            "source_history_ref": history_ref.model_dump(mode="json"),
            "source_index_ref": index_ref.model_dump(mode="json"),
            "source_run_binding": binding_payload,
            "source_profile": profile.model_dump(mode="json", exclude_none=True),
            "source_profile_attestation": "producer_reported_not_independently_recomputed",
            "source_profile_kind": profile.profile_kind,
            "source_proposal_source": profile.proposal_source,
            "source_warm_start_eligible": profile.warm_start_eligible,
            "candidate_hash": candidate_hash,
            "generic_source_objectives_used": False,
            "generic_source_scalar_used_as_policy_objective": False,
            "evaluation_basis": "current_policy_constraint_critic_and_stage_b",
            "source_scalar_may_order_candidate_proposals": True,
        }
        stage_context = {
            **dict(context),
            "candidate_only_transfer": transfer_record,
        }
        stage_b_result = invoke_candidate_evaluator(
            stage_b_evaluator,
            copy.deepcopy(candidate_payload),
            stage_context,
            proposal,
            prior_ticket_id=stage_a_ticket,
        )
        if not isinstance(stage_b_result, dict) or stage_b_result.get("status") != "ok":
            reject("policy_stage_b_did_not_complete")
            continue
        policy_evaluation = _coerce_policy_evaluation(stage_b_result)
        if (
            policy_evaluation is None
            or policy_evaluation.metadata.get("candidate_hash") != candidate_hash
        ):
            reject("policy_stage_b_vector_not_bound_to_candidate")
            continue
        candidate_ref = _optional_artifact_ref(stage_b_result.get("candidate_ref"))
        evaluation_ref = _optional_artifact_ref(stage_b_result.get("policy_evaluation_ref"))
        if not verify_policy_evaluation_source(
            source_store, proposal, policy_evaluation, candidate_ref, evaluation_ref
        ):
            reject("policy_stage_b_source_unverified")
            continue
        current_stage_b_result = {
            **stage_b_result,
            "policy_evaluation": policy_evaluation.model_dump(mode="json"),
            "candidate_only_transfer": transfer_record,
        }
        accepted.append(
            {
                "candidate": candidate_payload,
                "candidate_proposal": proposal.model_dump(mode="json"),
                "current_policy_reevaluation": True,
                "candidate_ref": candidate_ref.model_dump(mode="json") if candidate_ref else None,
                "evaluation_ref": evaluation_ref.model_dump(mode="json")
                if evaluation_ref
                else None,
                "stage_b_result": current_stage_b_result,
                "objective_value": _diagnostic_policy_score(
                    policy_evaluation,
                    stage_b_result.get("simulation_results")
                    if isinstance(stage_b_result.get("simulation_results"), dict)
                    else None,
                ),
                "is_promising": policy_evaluation.feasible,
            }
        )
        report["accepted_sources"].append(
            {
                "source_run_id": transfer_record["source_run_id"],
                "source_candidate_id": evaluation.candidate_id,
                "source_history_ref": transfer_record["source_history_ref"],
                "source_profile_kind": profile.profile_kind,
                "source_warm_start_eligible": profile.warm_start_eligible,
                "candidate_hash": candidate_hash,
            }
        )
    report["accepted_count"] = len(accepted)
    report["policy_stage_a_evaluations"] = stage_a_count
    report["policy_stage_b_evaluations"] = stage_b_count
    return accepted, report, stage_a_count, stage_b_count


def _candidate_only_parameter_error(
    params: dict[str, Any],
    search_space: SearchSpace,
) -> str | None:
    """Reject incomplete, clipped, or type-coerced transferred parameters."""
    if set(params) != {bound.name for bound in search_space.bounds}:
        return "source_parameter_set_mismatch"
    for bound in search_space.bounds:
        value = params[bound.name]
        if bound.dtype is ParameterType.CATEGORICAL:
            if bound.categories is None or value not in bound.categories:
                return "source_parameter_category_mismatch"
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "source_parameter_type_mismatch"
        numeric = float(value)
        if not math.isfinite(numeric):
            return "source_parameter_non_finite"
        if numeric < bound.lower or numeric > bound.upper:
            return "source_parameter_out_of_bounds"
        if bound.dtype is ParameterType.INTEGER and not numeric.is_integer():
            return "source_parameter_integer_mismatch"
    return None


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


def derive_phase2_parameter_bounds(
    *,
    workspace_id: str,
    invocation_id: str,
    default: float | int,
    lower: float | int | None,
    upper: float | int | None,
) -> Phase2ParameterBoundsResult:
    """Return the GY Phase-2 fail-closed bounds gate result for real search paths."""

    del default
    failed: list[dict[str, Any]] = []
    lower_value = None if lower is None else float(lower)
    upper_value = None if upper is None else float(upper)
    if lower_value is None:
        failed.append(_phase2_failed_bound("lower_bound", "bounds.lower"))
    elif not math.isfinite(lower_value):
        failed.append(_phase2_failed_bound("lower_bound", "bounds.lower", "non_finite_bound"))
    if upper_value is None:
        failed.append(_phase2_failed_bound("upper_bound", "bounds.upper"))
    elif not math.isfinite(upper_value):
        failed.append(_phase2_failed_bound("upper_bound", "bounds.upper", "non_finite_bound"))
    if lower_value is not None and upper_value is not None and lower_value > upper_value:
        failed.append(
            {
                "predicate_id": "phase2.lex_bounds.ordered",
                "input_path": "bounds",
                "reason": "lower_bound_exceeds_upper_bound",
                "severity": "hard",
            }
        )
    applicability = Phase2BoundsApplicability(
        result_id="applicability-lex-bounds",
        invocation_id=invocation_id,
        status="repair_required" if failed else "applicable",
        checked_preconditions=[
            {
                "predicate_id": "phase2.lex_bounds.present",
                "status": "failed" if failed else "passed",
                "lower_observed": lower_value,
                "upper_observed": upper_value,
                "rule_version": "policyos.gy.phase2.spine_repair.v1",
            }
        ],
        failed_preconditions=failed,
        repair_options=[
            {
                "operation_class": "REFINE",
                "reason": "Provide finite lower and upper bounds for lex search.",
            }
        ]
        if failed
        else [],
    )
    blocker = None
    if failed:
        first = failed[0]
        blocker = Phase2BoundsBlocker(
            blocker_id=f"blocker-{_slug(str(first['reason']))}",
            workspace_id=workspace_id,
            blocked_port=str(first.get("input_path") or "bounds"),
            missing_input=str(first.get("missing_input") or first.get("reason")),
            reason="Lex search bounds are missing or invalid; no default zero may be used.",
            frontier_snapshot_ref="frontier-lex-bounds",
            applicability_result_ref=applicability.result_id,
            repair_options=applicability.repair_options,
        )
    return Phase2ParameterBoundsResult(
        applicability=applicability,
        blocker=blocker,
        frontier_payload={
            "rule_version": "policyos.gy.phase2.spine_repair.v1",
            "bounded_frontier": not failed,
            "bounds": {"lower": lower_value, "upper": upper_value},
            "frontier_provenance": {
                "source": "scientist.policy_design.search",
                "exhaustive": False,
                "authority_disposition": "frontier_only_not_producer_evidence",
            },
        },
    )


def _phase2_failed_bound(
    missing_input: str,
    input_path: str,
    reason: str = "missing_bound",
) -> dict[str, Any]:
    return {
        "predicate_id": f"phase2.lex_bounds.{_slug(missing_input)}",
        "input_path": input_path,
        "missing_input": missing_input,
        "reason": reason,
        "severity": "hard",
    }


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


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
    "derive_phase2_parameter_bounds",
]
