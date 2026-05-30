"""Deterministic active-disambiguation planning for discovery artifacts."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.foundry.methods.catalog.causal.optimal_design import (
    minimum_cost_identification,
    optimal_adjustment_set,
)
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
from polisyos.scientist.methods.discovery.aggregator import (
    EdgeConfidenceEntry,
    EdgeConfidenceMatrix,
)
from polisyos.scientist.methods.discovery.priors import GraphPriorBundle, PriorKnowledgeBundle
from polisyos.scientist.methods.discovery.schema import GraphHypothesis
from polisyos.scientist.methods.discovery.stability import BootstrapStabilityReport
from polisyos.scientist.methods.discovery.utility_judge import DownstreamUtilityReport
from polisyos.scientist.methods.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)


class DisambiguationTarget(BaseModel):
    """One unresolved ambiguity ranked for next action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str = Field(min_length=1)
    target_type: str = Field(min_length=1)
    edge_key: str | None = None
    hypothesis_id: str | None = None
    description: str = Field(min_length=1)
    priority_score: float = Field(ge=0.0, le=1.0)
    downstream_impact: float = Field(ge=0.0, le=1.0)
    ambiguity_mass: float = Field(ge=0.0, le=1.0)
    stability_gap: float = Field(ge=0.0, le=1.0)
    supporting_hypothesis_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DisambiguationAction(BaseModel):
    """Concrete deterministic follow-up action for one or more ambiguity targets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    target_ids: list[str] = Field(default_factory=list)
    recommended_interventions: list[str] = Field(default_factory=list)
    adjustment_set: list[str] = Field(default_factory=list)
    cost_estimate: float | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActiveDisambiguationConfig(BaseModel):
    """Fixed thresholds controlling deterministic next-step planning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_targets: int = Field(default=5, ge=1, le=20)
    max_actions: int = Field(default=5, ge=1, le=20)
    min_priority: float = Field(default=0.05, ge=0.0, le=1.0)
    low_margin_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    default_intervention_cost: float = Field(default=1.0, ge=0.0)
    available_intervention_costs: dict[str, float] = Field(default_factory=dict)


class ActiveDisambiguationPlannerInput(BaseModel):
    """Inputs consumed by the deterministic active-disambiguation planner."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    edge_confidence_matrix: EdgeConfidenceMatrix
    bootstrap_stability_report: BootstrapStabilityReport
    downstream_utility_report: DownstreamUtilityReport
    hypotheses: list[GraphHypothesis] = Field(default_factory=list)
    graph_prior_bundle: GraphPriorBundle | None = None
    prior_knowledge_bundle: PriorKnowledgeBundle | None = None
    causal_query: CausalQuery | None = None
    target_context: dict[str, Any] = Field(default_factory=dict)


class ActiveDisambiguationPlan(ArtifactMinimalityMixin):
    """Final active-disambiguation artifact emitted by discovery output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.ROUTING,
            ArtifactFunction.CROSS_RUN_LEARNING,
        )
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = Field(default="no_action_needed", min_length=1)
    targets: list[DisambiguationTarget] = Field(default_factory=list)
    actions: list[DisambiguationAction] = Field(default_factory=list)
    target_edge_keys: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActiveDisambiguationPlanner:
    """Build a deterministic plan to resolve high-value discovery ambiguities."""

    def __init__(
        self,
        *,
        config: ActiveDisambiguationConfig | None = None,
    ) -> None:
        self._config = config or ActiveDisambiguationConfig()

    @property
    def config(self) -> ActiveDisambiguationConfig:
        return self._config

    def plan(self, bundle: ActiveDisambiguationPlannerInput) -> ActiveDisambiguationPlan:
        targets = self._rank_targets(bundle)
        if not targets:
            return ActiveDisambiguationPlan(
                status="no_action_needed",
                notes=["No high-priority ambiguity remains after discovery aggregation."],
                metadata={"n_targets_considered": 0},
            )

        actions = self._build_actions(targets, bundle)
        if bundle.causal_query is None and any(
            target.target_type in {"disputed_edge", "low_margin_orientation", "identification_gap"}
            for target in targets
        ):
            status = "blocked_missing_query"
        elif actions and all(
            action.action_type in {"literature_followup", "expert_review"} for action in actions
        ):
            status = "degraded"
        else:
            status = "ready"

        return ActiveDisambiguationPlan(
            status=status,
            targets=targets,
            actions=actions,
            target_edge_keys=sorted({target.edge_key for target in targets if target.edge_key}),
            recommendations=[action.description for action in actions],
            notes=self._plan_notes(targets, bundle, status=status),
            metadata={
                "target_context": dict(bundle.target_context),
                "n_targets_considered": len(targets),
                "n_actions": len(actions),
            },
        )

    def _rank_targets(
        self,
        bundle: ActiveDisambiguationPlannerInput,
    ) -> list[DisambiguationTarget]:
        targets = [
            *self._targets_from_priors(bundle),
            *self._targets_from_matrix(bundle),
            *self._targets_from_utility(bundle),
            *self._targets_from_prior_knowledge(bundle),
        ]
        ranked = sorted(
            (target for target in targets if target.priority_score >= self._config.min_priority),
            key=lambda item: (
                item.priority_score,
                item.downstream_impact,
                item.ambiguity_mass,
            ),
            reverse=True,
        )
        deduped: list[DisambiguationTarget] = []
        seen: set[str] = set()
        for target in ranked:
            key = target.edge_key or target.hypothesis_id or target.target_id
            if key in seen:
                continue
            seen.add(key)
            deduped.append(target)
            if len(deduped) >= self._config.max_targets:
                break
        return deduped

    def _targets_from_priors(
        self,
        bundle: ActiveDisambiguationPlannerInput,
    ) -> list[DisambiguationTarget]:
        prior_bundle = bundle.graph_prior_bundle
        if prior_bundle is None:
            return []
        targets: list[DisambiguationTarget] = []
        for disputed in prior_bundle.disputed_edges:
            supporting_ids = sorted(
                {
                    hypothesis_id
                    for edge in disputed.candidate_edges
                    for hypothesis_id in edge.supporting_hypothesis_ids
                }
            )
            downstream_impact = self._downstream_impact(
                bundle.downstream_utility_report,
                supporting_ids,
            )
            ambiguity_mass = min(
                1.0,
                max(
                    [
                        1.0 - _finite_unit_interval(edge.orientation_confidence)
                        for edge in disputed.candidate_edges
                    ]
                    or [0.8]
                ),
            )
            stability_gap = self._stability_gap(
                bundle.bootstrap_stability_report,
                supporting_ids,
            )
            targets.append(
                DisambiguationTarget(
                    target_id=disputed.dispute_id,
                    target_type="disputed_edge",
                    edge_key=(
                        disputed.candidate_edges[0].edge_key if disputed.candidate_edges else None
                    ),
                    description=(
                        f"Resolve disputed discovery edge around {disputed.skeleton_key}."
                    ),
                    priority_score=self._priority(
                        downstream_impact=downstream_impact,
                        ambiguity_mass=ambiguity_mass,
                        stability_gap=stability_gap,
                    ),
                    downstream_impact=downstream_impact,
                    ambiguity_mass=ambiguity_mass,
                    stability_gap=stability_gap,
                    supporting_hypothesis_ids=supporting_ids,
                    notes=list(disputed.dispute_reasons) + list(disputed.notes),
                    metadata={"source": "graph_prior_bundle"},
                )
            )
        return targets

    def _targets_from_matrix(
        self,
        bundle: ActiveDisambiguationPlannerInput,
    ) -> list[DisambiguationTarget]:
        targets: list[DisambiguationTarget] = []
        for entry in bundle.edge_confidence_matrix.entries:
            margin = self._orientation_margin(entry)
            if not entry.disputed and margin > self._config.low_margin_threshold:
                continue
            ambiguity_mass = min(
                1.0,
                max(1.0 - margin, 1.0 - _finite_unit_interval(entry.orientation_confidence)),
            )
            supporting_ids = list(entry.supporting_hypothesis_ids)
            downstream_impact = self._downstream_impact(
                bundle.downstream_utility_report,
                supporting_ids,
            )
            stability_gap = self._stability_gap(
                bundle.bootstrap_stability_report,
                supporting_ids,
            )
            targets.append(
                DisambiguationTarget(
                    target_id=f"matrix::{entry.edge_key}",
                    target_type="low_margin_orientation",
                    edge_key=entry.edge_key,
                    description=f"Disambiguate orientation for {entry.edge_key}.",
                    priority_score=self._priority(
                        downstream_impact=downstream_impact,
                        ambiguity_mass=ambiguity_mass,
                        stability_gap=stability_gap,
                    ),
                    downstream_impact=downstream_impact,
                    ambiguity_mass=ambiguity_mass,
                    stability_gap=stability_gap,
                    supporting_hypothesis_ids=supporting_ids,
                    notes=list(entry.dispute_reasons),
                    metadata={
                        "source": "edge_confidence_matrix",
                        "orientation_margin": margin,
                    },
                )
            )
        return targets

    def _targets_from_utility(
        self,
        bundle: ActiveDisambiguationPlannerInput,
    ) -> list[DisambiguationTarget]:
        targets: list[DisambiguationTarget] = []
        for score in bundle.downstream_utility_report.scores[: self._config.max_targets]:
            if score.identification_status in {"identified"}:
                continue
            identifiability_score = _finite_unit_interval(score.identifiability_score)
            composite_score = _finite_unit_interval(score.composite_score)
            ambiguity_mass = 1.0 if identifiability_score <= 0.0 else 0.6
            stability_gap = self._stability_gap(
                bundle.bootstrap_stability_report,
                [score.hypothesis_id],
            )
            targets.append(
                DisambiguationTarget(
                    target_id=f"utility::{score.hypothesis_id}",
                    target_type="identification_gap",
                    hypothesis_id=score.hypothesis_id,
                    description=(
                        f"Hypothesis {score.hypothesis_id} remains {score.identification_status}."
                    ),
                    priority_score=self._priority(
                        downstream_impact=composite_score,
                        ambiguity_mass=ambiguity_mass,
                        stability_gap=stability_gap,
                    ),
                    downstream_impact=composite_score,
                    ambiguity_mass=ambiguity_mass,
                    stability_gap=stability_gap,
                    supporting_hypothesis_ids=[score.hypothesis_id],
                    notes=list(score.reasons) + list(score.warnings),
                    metadata={
                        "source": "downstream_utility_report",
                        "blocking_certificates": list(score.blocking_certificates),
                    },
                )
            )
        return targets

    def _targets_from_prior_knowledge(
        self,
        bundle: ActiveDisambiguationPlannerInput,
    ) -> list[DisambiguationTarget]:
        prior_knowledge = bundle.prior_knowledge_bundle
        if prior_knowledge is None:
            return []
        targets: list[DisambiguationTarget] = []
        for edge_key in prior_knowledge.unresolved_edges:
            targets.append(
                DisambiguationTarget(
                    target_id=f"prior::{edge_key}",
                    target_type="academic_conflict",
                    edge_key=edge_key,
                    description=f"Academic support remains unresolved for {edge_key}.",
                    priority_score=self._priority(
                        downstream_impact=self._downstream_impact(
                            bundle.downstream_utility_report,
                            [],
                        ),
                        ambiguity_mass=0.7,
                        stability_gap=0.5,
                    ),
                    downstream_impact=self._downstream_impact(
                        bundle.downstream_utility_report,
                        [],
                    ),
                    ambiguity_mass=0.7,
                    stability_gap=0.5,
                    notes=list(prior_knowledge.warnings),
                    metadata={"source": "prior_knowledge_bundle"},
                )
            )
        return targets

    def _build_actions(
        self,
        targets: list[DisambiguationTarget],
        bundle: ActiveDisambiguationPlannerInput,
    ) -> list[DisambiguationAction]:
        actions: list[DisambiguationAction] = []
        hypotheses_by_id = {
            hypothesis.hypothesis_id: hypothesis for hypothesis in bundle.hypotheses
        }
        for target in targets:
            action = self._action_for_target(target, bundle, hypotheses_by_id)
            if action is None:
                continue
            actions.append(action)
            if len(actions) >= self._config.max_actions:
                break
        return actions

    def _action_for_target(
        self,
        target: DisambiguationTarget,
        bundle: ActiveDisambiguationPlannerInput,
        hypotheses_by_id: dict[str, GraphHypothesis],
    ) -> DisambiguationAction | None:
        if target.target_type in {"disputed_edge", "low_margin_orientation", "identification_gap"}:
            action = self._try_experiment_action(target, bundle, hypotheses_by_id)
            if action is not None:
                return action
        if target.metadata.get("transport_gap"):
            return DisambiguationAction(
                action_type="collect_target_domain_data",
                title="Collect target-domain data",
                description=(
                    "Collect target-domain evidence to resolve context shift around "
                    f"{target.edge_key or target.target_id}."
                ),
                target_ids=[target.target_id],
                notes=["Transport or context gap remained unresolved after discovery priors."],
                metadata={"source_target_type": target.target_type},
            )
        if self._looks_measurement_like(target):
            return DisambiguationAction(
                action_type="measure_proxy",
                title="Measure missing proxy",
                description=(
                    "Add direct measurement or a stronger proxy for "
                    f"{target.edge_key or target.target_id}."
                ),
                target_ids=[target.target_id],
                notes=["Measurement ambiguity looked proxy-like from the target naming surface."],
                metadata={"source_target_type": target.target_type},
            )
        if target.target_type == "academic_conflict":
            return DisambiguationAction(
                action_type="literature_followup",
                title="Follow up literature conflict",
                description=(
                    "Run a targeted literature follow-up for "
                    f"{target.edge_key or target.target_id}."
                ),
                target_ids=[target.target_id],
                notes=list(target.notes),
                metadata={"source_target_type": target.target_type},
            )
        return DisambiguationAction(
            action_type="expert_review",
            title="Escalate for expert review",
            description=(
                "Request expert review for "
                f"{target.edge_key or target.hypothesis_id or target.target_id}."
            ),
            target_ids=[target.target_id],
            notes=list(target.notes),
            metadata={"source_target_type": target.target_type},
        )

    def _try_experiment_action(
        self,
        target: DisambiguationTarget,
        bundle: ActiveDisambiguationPlannerInput,
        hypotheses_by_id: dict[str, GraphHypothesis],
    ) -> DisambiguationAction | None:
        if bundle.causal_query is None:
            return None
        hypothesis = self._preferred_hypothesis(
            target,
            hypotheses_by_id,
            bundle.downstream_utility_report,
        )
        if hypothesis is None:
            return None
        graph = hypothesis.resolved_graph or hypothesis.graph
        if graph is None:
            return None
        treatment = bundle.causal_query.treatment_variable
        outcome = bundle.causal_query.outcome_variable
        if treatment not in graph.nodes or outcome not in graph.nodes:
            return None
        available = dict(self._config.available_intervention_costs) or {
            node: self._config.default_intervention_cost for node in graph.nodes if node != outcome
        }
        try:
            adjustment = optimal_adjustment_set(graph, treatment=treatment, outcome=outcome)
            experiment_plan = minimum_cost_identification(
                graph,
                treatment=treatment,
                outcome=outcome,
                available_interventions=available,
            )
        except Exception:
            experiment_plan = None
            adjustment = None
        if experiment_plan is not None:
            return DisambiguationAction(
                action_type="run_intervention",
                title="Run targeted intervention",
                description=(
                    "Execute a targeted causal design to resolve "
                    f"{target.edge_key or target.hypothesis_id or target.target_id}."
                ),
                target_ids=[target.target_id],
                recommended_interventions=list(experiment_plan.recommended_interventions),
                adjustment_set=sorted(adjustment.o_set) if adjustment is not None else [],
                cost_estimate=experiment_plan.cost_estimate,
                notes=[experiment_plan.rationale],
                metadata={"hypothesis_id": hypothesis.hypothesis_id},
            )
        fallback_type = (
            BlockingType.S_NODE_UNRESOLVED
            if target.metadata.get("transport_gap")
            else BlockingType.HEDGE_STRUCTURE
        )
        suggestions = NegativeCertificate.auto_suggest_experiments(
            fallback_type,
            missing_vars=tuple(self._variables_for_target(target, bundle.causal_query)),
        )
        if suggestions:
            return DisambiguationAction(
                action_type="literature_followup",
                title="Collect fallback evidence",
                description=suggestions[0].description
                or (f"Collect additional evidence for {target.target_id}."),
                target_ids=[target.target_id],
                recommended_interventions=list(suggestions[0].required_variables),
                notes=[
                    "Optimal design could not be constructed; using negative-certificate guidance."
                ],
                metadata={"hypothesis_id": hypothesis.hypothesis_id},
            )
        return None

    def _preferred_hypothesis(
        self,
        target: DisambiguationTarget,
        hypotheses_by_id: dict[str, GraphHypothesis],
        utility_report: DownstreamUtilityReport,
    ) -> GraphHypothesis | None:
        for hypothesis_id in target.supporting_hypothesis_ids:
            if hypothesis_id in hypotheses_by_id:
                return hypotheses_by_id[hypothesis_id]
        if target.hypothesis_id and target.hypothesis_id in hypotheses_by_id:
            return hypotheses_by_id[target.hypothesis_id]
        for score in utility_report.scores:
            if score.hypothesis_id in hypotheses_by_id:
                return hypotheses_by_id[score.hypothesis_id]
        return None

    def _priority(
        self,
        *,
        downstream_impact: float,
        ambiguity_mass: float,
        stability_gap: float,
    ) -> float:
        safe_downstream = _finite_unit_interval(downstream_impact)
        safe_ambiguity = _finite_unit_interval(ambiguity_mass)
        safe_stability = max(_finite_unit_interval(stability_gap), 0.1)
        return min(
            1.0,
            safe_downstream * safe_ambiguity * safe_stability,
        )

    @staticmethod
    def _downstream_impact(
        report: DownstreamUtilityReport,
        supporting_hypothesis_ids: list[str],
    ) -> float:
        score_map = {
            score.hypothesis_id: _finite_unit_interval(score.composite_score)
            for score in report.scores
        }
        if supporting_hypothesis_ids:
            return max(
                score_map.get(hypothesis_id, 0.0) for hypothesis_id in supporting_hypothesis_ids
            )
        return max(score_map.values(), default=0.5)

    @staticmethod
    def _stability_gap(
        report: BootstrapStabilityReport,
        supporting_hypothesis_ids: list[str],
    ) -> float:
        if not supporting_hypothesis_ids:
            return 0.5
        gaps: list[float] = []
        for hypothesis_id in supporting_hypothesis_ids:
            summary = report.summary_for(hypothesis_id)
            if summary is None or summary.mean_edge_stability is None:
                gaps.append(0.5)
                continue
            gaps.append(1.0 - _finite_unit_interval(summary.mean_edge_stability, default=0.5))
        if not gaps:
            return 0.5
        return max(0.0, min(1.0, sum(gaps) / len(gaps)))

    def _orientation_margin(self, entry: EdgeConfidenceEntry) -> float:
        supports = sorted(
            (_finite_unit_interval(value) for value in entry.orientation_support.values()),
            reverse=True,
        )
        if len(supports) < 2:
            return _finite_unit_interval(entry.orientation_confidence)
        return max(0.0, min(1.0, float(supports[0] - supports[1])))

    @staticmethod
    def _variables_for_target(target: DisambiguationTarget, causal_query: CausalQuery) -> list[str]:
        variables = [causal_query.treatment_variable, causal_query.outcome_variable]
        if target.edge_key:
            cleaned = target.edge_key.split("@lag=")[0]
            variables.extend(part.strip() for part in cleaned.split("->") if part.strip())
        return sorted({value for value in variables if value})

    @staticmethod
    def _looks_measurement_like(target: DisambiguationTarget) -> bool:
        material = (target.edge_key or target.description).lower()
        return "proxy" in material or "measure" in material or "latent" in material

    @staticmethod
    def _plan_notes(
        targets: list[DisambiguationTarget],
        bundle: ActiveDisambiguationPlannerInput,
        *,
        status: str,
    ) -> list[str]:
        notes = [f"Planner status: {status}."]
        if bundle.causal_query is None:
            notes.append(
                "Causal query missing; intervention designs could not be fully constructed."
            )
        if any(target.target_type == "academic_conflict" for target in targets):
            notes.append(
                "Academic support conflicts were surfaced from the prior-knowledge bundle."
            )
        return notes


__all__ = [
    "ActiveDisambiguationConfig",
    "ActiveDisambiguationPlan",
    "ActiveDisambiguationPlanner",
    "ActiveDisambiguationPlannerInput",
    "DisambiguationAction",
    "DisambiguationTarget",
]


def _finite_unit_interval(value: Any, *, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    if numeric <= 0.0:
        return 0.0
    if numeric >= 1.0:
        return 1.0
    return numeric
