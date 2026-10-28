"""Planning node that generates candidate policies, evaluates them, and installs a champion.

The node sits between policy formalization and Foundry compilation in the
`scientist_policy_design` DAG. It resolves an initial candidate from
`params.policy_candidate_schema`, `params.lex_policy_bundle_input`, or the
current Trinity input, runs hierarchical structure/parameter search, evaluates
candidate payloads through the compile/readiness/simulation subpipeline, and
persists a frontier report plus the selected champion Trinity bundle.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.core.contracts.runtime import CompletedExAnteComparisonRequest
from polisyos.core.contracts.trinity import TrinityBundleRef
from polisyos.data_forge.read_api.academic import SKGQuery
from polisyos.ir.trinity import TrinityBundle
from polisyos.lex import LexPolicyBundleInput
from polisyos.lex.interventions import HierarchicalPolicySearchPlan
from polisyos.pdc import WorldModelRecord
from polisyos.scientist.evidence.sources import normalize_evidence_sources_config
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    CandidateStrategyContext,
    ParetoBasisScope,
    ParetoViewAssessment,
    ParetoViewProjection,
)
from polisyos.scientist.methods.search.frontier import (
    invoke_candidate_evaluator,
    strategy_candidate_payload,
)
from polisyos.scientist.methods.search.pareto_registry import (
    ParetoRegistry,
    verify_policy_evaluation_source,
)

# isort: split
from polisyos.scientist.methods.search.controller import (
    SearchIteration,
    SearchResult,
    SearchStatus,
)
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreStatus,
    reconcile_objective_score_assessment,
    score_assessment_matches_source,
)
from polisyos.scientist.methods.search.strategies.transfer import RunFingerprint
from polisyos.scientist.methods.search.strategies.types import Evaluation
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    resolve_baseline_policy_value,
)
from polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate import (
    evaluate_counterfactual_gate,
)
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import (
    ResolveParametersNode,
)
from polisyos.scientist.nodes.builtins.causal.run_causal_readiness import (
    RunCausalReadinessNode,
)
from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationSafetyError,
    ProductionPolicyEvaluationBackend,
    build_policy_runtime_evaluation,
    load_ambiguity_certificate,
    load_causal_report,
    load_cross_graph_profile,
    load_distributional_report_for_state,
    load_governance_report,
    load_search_uncertainty,
    load_simulation_metrics,
)
from polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence import (
    CompileCrossGraphEvidenceNode,
)
from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_READINESS_BUNDLE_REF,
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_LOWERED_IR_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_POLICY_FRONTIER_REPORT_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_SBOM_REF,
    ARTIFACT_SLOT_LAYOUT_REF,
    ARTIFACT_STATE_DELTA_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    ARTIFACT_TEE_ATTESTATION_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
    ARTIFACT_TREASURY_PLAN_REF,
    INPUT_TRINITY_BUNDLE_REF,
)

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.academic import PreparedSKGRead
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.policy_design.objectives import (
    ObjectiveStack,
    PolicyEvaluationBundle,
    PolicyEvaluationVector,
    _normalize_policy_evaluation_vector,
)
from polisyos.scientist.policy_design.output import (
    PolicyFrontierEntry,
    PolicyFrontierReport,
    persist_policy_frontier_report,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.policy_design.search import (
    HierarchicalSearchConfig,
    HierarchicalSearchCoordinator,
    HierarchicalSearchResult,
    PolicySearchLevel,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_hierarchical_policy_search@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Hierarchical Policy Search",
    description="Run structure and parameter search, then install the champion candidate.",
    tags=["builtin", "planning", "policy_design", "c6c"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "params.policy_candidate_schema",
        "params.lex_policy_bundle_input",
        "params.policy_loop_id",
        "params.policy_search_config",
        "params.policy_search_candidate_transfer",
        "params.policy_search_completed_ex_ante_comparison",
        "params.hierarchical_policy_search_config",
        "params.cross_graph_evidence_config",
        "params.evidence_sources",
        "params.skg_db_path",
        "params.skg_index_dir",
        "params.target_context",
        "params.required_parameters",
        "params.domain",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
        "inputs",
        "artifacts_index",
        "reports_index",
    ],
    state_writes=[
        "params.policy_candidate_schema",
        "params.policy_search_result",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_POLICY_FRONTIER_REPORT_REF}",
    ],
    produces=[ARTIFACT_POLICY_FRONTIER_REPORT_REF],
)

_INNER_CANDIDATE_ARTIFACT_KEYS = (
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_LOWERED_IR_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_SLOT_LAYOUT_REF,
    ARTIFACT_TREASURY_PLAN_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_CAUSAL_READINESS_BUNDLE_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_STATE_DELTA_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    ARTIFACT_TEE_ATTESTATION_REF,
    ARTIFACT_SBOM_REF,
)

_POLICY_SEARCH_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_POLICY_SEARCH_EXECUTION_ERRORS = (
    ImportError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)


class _CandidateOnlyPolicyTransferIntent(BaseModel):
    """Opt-in request to discover typed history and transfer parameters as candidates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index_ref: ArtifactRef
    query_fingerprint: RunFingerprint
    max_source_runs: int = Field(default=5, ge=1, le=20, strict=True)
    max_candidates: int = Field(default=20, ge=1, le=100, strict=True)

    @field_validator("query_fingerprint", mode="before")
    @classmethod
    def _validate_query_fingerprint(cls, value: object) -> RunFingerprint:
        if isinstance(value, RunFingerprint):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("query_fingerprint must be a RunFingerprint object")
        return RunFingerprint.model_validate(value, strict=True)

    @model_validator(mode="after")
    def _validate_candidate_only_scope(self) -> _CandidateOnlyPolicyTransferIntent:
        if (self.index_ref.kind, self.index_ref.media_type) != (
            "vector_memory.bundle",
            "application/json",
        ):
            raise ValueError("candidate transfer requires a vector_memory.bundle JSON ref")
        if self.query_fingerprint.history_ref is not None:
            raise ValueError("candidate transfer query cannot assert a history_ref")
        if not self.query_fingerprint.embedding or any(
            not math.isfinite(value) for value in self.query_fingerprint.embedding
        ):
            raise ValueError("candidate transfer query requires a finite non-empty embedding")
        if not self.query_fingerprint.objective_names or len(
            set(self.query_fingerprint.objective_names)
        ) != len(self.query_fingerprint.objective_names):
            raise ValueError("candidate transfer query requires unique objective names")
        if not self.query_fingerprint.tenant_id:
            raise ValueError("candidate transfer query requires an explicit tenant identity")
        return self


class HierarchicalPolicySearchAdapter:
    """Bridge Lex policy bundles into Scientist-owned hierarchical search."""

    coordinator_fqn = "polisyos.scientist.policy_design.search.HierarchicalSearchCoordinator"

    def build_request(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None = None,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HierarchicalPolicySearchPlan:
        """Create a Scientist search-plan payload from a Trinity or Lex policy bundle."""
        resolved_candidate = self._resolve_candidate_payload(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        resolved_config = self.instantiate_search_config(search_config)
        resolved_policy_family = str(
            policy_family
            or resolved_candidate.metadata.get("policy_family")
            or resolved_candidate.candidate_id
        )
        request_metadata = {
            **dict(resolved_candidate.metadata),
            **dict(metadata or {}),
        }
        request_metadata.setdefault("policy_family", resolved_policy_family)
        return HierarchicalPolicySearchPlan(
            coordinator_fqn=self.coordinator_fqn,
            candidate_id=resolved_candidate.candidate_id,
            candidate_hash=resolved_candidate.candidate_hash(),
            policy_family=resolved_policy_family,
            search_config=resolved_config.model_dump(mode="json"),
            metadata=request_metadata,
        )

    def build_candidate(
        self,
        bundle_input: LexPolicyBundleInput | TrinityBundle | Mapping[str, Any],
        *,
        candidate_id: str | None = None,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> PolicyCandidateSchema:
        """Convert a Lex policy bundle into a policy-search candidate."""
        resolved_input = _coerce_lex_policy_bundle_input(bundle_input)
        domain = _bundle_domain(resolved_input.trinity_bundle)
        resolved_policy_family = str(
            policy_family
            or resolved_input.metadata.get("policy_family")
            or candidate_id
            or resolved_input.trinity_bundle.policy_spec.policy_id
        )
        compiled_interventions = list(resolved_input.compiled_interventions)
        temporal_sequences = list(resolved_input.temporal_sequences)
        strategic_response_bundle = resolved_input.strategic_response_bundle

        dynamic_intervention_ids = [
            sequence.dynamic_intervention_id for sequence in temporal_sequences
        ]
        strategic_intervention_kinds = {
            compiled.intervention.kind
            for compiled in compiled_interventions
            if compiled.intervention.strategic_response_expected
        }
        if strategic_response_bundle is not None:
            strategic_intervention_kinds.update(
                spec.intervention_kind
                for spec in strategic_response_bundle.expectations
                if spec.strategic_response_expected
            )

        candidate_metadata = {
            **dict(resolved_input.metadata),
            **dict(metadata or {}),
            "policy_family": resolved_policy_family,
            "jurisdiction": "UA",
            "country": "ua",
            "domain": domain,
            "dynamic_intervention_ids": dynamic_intervention_ids,
            "strategic_intervention_kinds": sorted(strategic_intervention_kinds),
            "compiled_intervention_ids": [
                compiled.intervention.intervention_id for compiled in compiled_interventions
            ],
            "sequence_ids": [sequence.sequence_id for sequence in temporal_sequences],
        }
        return PolicyCandidateSchema.from_trinity_bundle(
            resolved_input.trinity_bundle,
            candidate_id=candidate_id,
            metadata=candidate_metadata,
        )

    def build_request_from_trinity(
        self,
        bundle: TrinityBundle | Mapping[str, Any],
        *,
        candidate_id: str | None = None,
        policy_family: str | None = None,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HierarchicalPolicySearchPlan:
        """Build a hierarchical search plan directly from a Trinity payload."""
        candidate = self.build_candidate(
            bundle,
            candidate_id=candidate_id,
            policy_family=policy_family,
            metadata=metadata,
        )
        return self.build_request(
            candidate,
            search_config=search_config,
            policy_family=policy_family,
            metadata=metadata,
        )

    def instantiate_search_config(
        self,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None,
    ) -> HierarchicalSearchConfig:
        if search_config is None:
            return HierarchicalSearchConfig()
        if isinstance(search_config, HierarchicalSearchConfig):
            return search_config
        return HierarchicalSearchConfig.model_validate(search_config)

    def instantiate_coordinator(
        self,
        plan: HierarchicalPolicySearchPlan | Mapping[str, Any],
    ) -> HierarchicalSearchCoordinator:
        resolved_plan = (
            plan
            if isinstance(plan, HierarchicalPolicySearchPlan)
            else HierarchicalPolicySearchPlan.model_validate(plan)
        )
        return HierarchicalSearchCoordinator(
            config=self.instantiate_search_config(resolved_plan.search_config)
        )

    def validate_policy_design_api(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None = None,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HierarchicalSearchCoordinator:
        """Check that Scientist policy-design APIs accept the generated candidate."""
        resolved_candidate = self._resolve_candidate_payload(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        coordinator = HierarchicalSearchCoordinator(
            config=self.instantiate_search_config(search_config)
        )
        try:
            coordinator.build_parameter_search_spec(resolved_candidate)
        except ValueError as exc:
            if "No tunable policy parameters" not in str(exc):
                raise
        coordinator.build_optimizer_objective_spec(resolved_candidate)
        return coordinator

    def build_runtime_context(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        loop_id: str,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the runtime context expected by orchestration and search loops."""
        resolved_candidate = self._resolve_candidate_payload(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        request = self.build_request(
            resolved_candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        return {
            "loop_id": loop_id,
            "candidate_id": resolved_candidate.candidate_id,
            "candidate_hash": resolved_candidate.candidate_hash(),
            "policy_family": request.policy_family,
            "policy_search_plan": request.model_dump(mode="json"),
            "policy_search_context": {
                "structure_id": resolved_candidate.candidate_id,
                "policy_family": request.policy_family,
                "candidate_hash": resolved_candidate.candidate_hash(),
                "task_family": request.policy_family,
                "domain": str(request.metadata.get("domain") or resolved_candidate.candidate_id),
            },
            "ukraine_metadata": {
                "jurisdiction": request.metadata.get("jurisdiction"),
                "country": request.metadata.get("country"),
                "domain": request.metadata.get("domain"),
            },
            "dynamic_intervention_ids": list(
                request.metadata.get("dynamic_intervention_ids") or []
            ),
            "strategic_intervention_kinds": list(
                request.metadata.get("strategic_intervention_kinds") or []
            ),
            "compiled_intervention_ids": list(
                request.metadata.get("compiled_intervention_ids") or []
            ),
            "sequence_ids": list(request.metadata.get("sequence_ids") or []),
        }

    def run_search(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        loop_id: str,
        stage_b_evaluator: Any | None = None,
        stage_a_evaluator: Any | None = None,
        structure_validator: Any | None = None,
        narrative_input_builder: Any | None = None,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None = None,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        initial_context: Mapping[str, Any] | None = None,
        candidate_only_seed_evaluations: list[Evaluation] | None = None,
        source_store: Any | None = None,
    ) -> Any:
        resolved_candidate = self._resolve_candidate_payload(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        coordinator = HierarchicalSearchCoordinator(
            config=self.instantiate_search_config(search_config), source_store=source_store
        )
        runtime_context = self.build_runtime_context(
            resolved_candidate,
            loop_id=loop_id,
            policy_family=policy_family,
            metadata=metadata,
        )
        merged_context = {**runtime_context, **dict(initial_context or {})}
        try:
            coordinator.build_parameter_search_spec(resolved_candidate)
        except ValueError as exc:
            if "No tunable policy parameters" not in str(exc):
                raise
            if candidate_only_seed_evaluations:
                raise ValueError(
                    "candidate-only transfer requires tunable policy parameters"
                ) from exc
            return self._run_parameterless_search(
                coordinator,
                resolved_candidate,
                loop_id=loop_id,
                stage_b_evaluator=stage_b_evaluator,
                structure_validator=structure_validator,
                narrative_input_builder=narrative_input_builder,
                initial_context=merged_context,
            )
        return coordinator.run(
            resolved_candidate,
            loop_id=loop_id,
            stage_b_evaluator=stage_b_evaluator,
            stage_a_evaluator=stage_a_evaluator,
            structure_validator=structure_validator,
            narrative_input_builder=narrative_input_builder,
            initial_context=merged_context,
            candidate_only_seed_evaluations=candidate_only_seed_evaluations,
        )

    def _resolve_candidate_payload(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        policy_family: str | None,
        metadata: Mapping[str, Any] | None,
    ) -> PolicyCandidateSchema:
        if isinstance(candidate, PolicyCandidateSchema):
            if policy_family is None and not metadata:
                return candidate
            updated_metadata = {
                **dict(candidate.metadata),
                **dict(metadata or {}),
            }
            if policy_family is not None:
                updated_metadata["policy_family"] = policy_family
            return candidate.model_copy(update={"metadata": updated_metadata})
        return self.build_candidate(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )

    def _run_parameterless_search(
        self,
        coordinator: HierarchicalSearchCoordinator,
        candidate: PolicyCandidateSchema,
        *,
        loop_id: str,
        stage_b_evaluator: Any | None,
        structure_validator: Any | None,
        narrative_input_builder: Any | None,
        initial_context: Mapping[str, Any] | None,
    ) -> HierarchicalSearchResult:
        state = coordinator.run(
            candidate,
            loop_id=loop_id,
            stage_b_evaluator=None,
            structure_validator=structure_validator,
            narrative_input_builder=None,
            initial_context=dict(initial_context or {}),
        ).state
        accepted_structures = [item for item in state.structure_candidates if item.accepted]
        if stage_b_evaluator is not None:
            state.current_level = PolicySearchLevel.PARAMETER
            base_context = dict(initial_context or {})
            for structure in accepted_structures:
                proposal_context = CandidateStrategyContext(
                    producer="policy_design",
                    subject=structure.candidate.model_dump(mode="json", exclude_none=True),
                    policy_schema=True,
                    policy_transport=True,
                )
                candidate_payload = strategy_candidate_payload(proposal_context)
                proposal = CandidateProposal(
                    candidate_id=structure.candidate.candidate_id,
                    payload=candidate_payload,
                    strategy_context=proposal_context,
                )
                context = {
                    **base_context,
                    "loop_id": loop_id,
                    "candidate_hash": structure.candidate_hash,
                    "policy_search_context": {
                        "structure_id": structure.structure_id,
                        "policy_family": structure.policy_family,
                        "candidate_hash": structure.candidate_hash,
                        "task_family": structure.policy_family,
                        "domain": str(
                            structure.candidate.metadata.get("domain")
                            or structure.candidate.candidate_id
                        ),
                    },
                }
                stage_b_result = invoke_candidate_evaluator(
                    stage_b_evaluator, candidate_payload, context, proposal
                )
                evaluation = _coerce_policy_evaluation(stage_b_result)
                candidate_ref = _candidate_source_ref(stage_b_result.get("candidate_ref"))
                evaluation_ref = _candidate_source_ref(stage_b_result.get("policy_evaluation_ref"))
                source_verified = verify_policy_evaluation_source(
                    coordinator._source_store, proposal, evaluation, candidate_ref, evaluation_ref
                )
                source_results = stage_b_result.get("simulation_results")
                if evaluation is not None and source_verified:
                    objective_value, score_status = evaluation.legacy_scalar_proxy_for_search(
                        source_results if isinstance(source_results, dict) else None
                    )
                    score_assessment = evaluation.score_assessment
                    score_source = {
                        "policy_evaluation": evaluation.model_dump(mode="python"),
                        "simulation_results": source_results,
                    }
                else:
                    objective_value = None
                    score_status = ObjectiveScoreStatus.NOT_ESTABLISHED
                    score_assessment = None
                    score_source = source_results
                score_admission = reconcile_objective_score_assessment(
                    score_assessment,
                    score_source,
                    reported_status=score_status,
                    reported_value=objective_value,
                )
                score_status = score_admission.status
                has_usable_score = (
                    score_status is ObjectiveScoreStatus.AVAILABLE
                    and evaluation is not None
                    and evaluation.score_assessment_matches_channels(
                        source_results if isinstance(source_results, dict) else None
                    )
                    and objective_value is not None
                )
                if not has_usable_score:
                    objective_value = None
                state.parameter_search_results[structure.structure_id] = SearchResult(
                    search_id=f"{loop_id}:{structure.structure_id}",
                    status=SearchStatus.CONVERGED,
                    best_candidate=candidate_payload if has_usable_score else None,
                    best_objective=float(objective_value) if has_usable_score else math.inf,
                    iterations_completed=1,
                    history=[
                        SearchIteration(
                            iteration=0,
                            candidate=candidate_payload,
                            objective_value=(
                                float(objective_value) if objective_value is not None else None
                            ),
                            objective_details=[],
                            is_promising=has_usable_score
                            and bool(stage_b_result.get("feasible", True)),
                            stage_a_passed=True,
                            stage_b_result=stage_b_result,
                            duration_seconds=0.0,
                            policy_evaluation=evaluation,
                            score_status=score_status,
                            score_assessment=score_assessment,
                            score_admission=score_admission,
                            candidate_proposal=proposal,
                            candidate_ref=candidate_ref,
                            evaluation_ref=evaluation_ref,
                        )
                    ],
                    stopping_reason="parameter_search_not_required",
                    total_duration_seconds=0.0,
                    stage_a_evaluations=0,
                    stage_b_evaluations=1,
                    telemetry={"parameterless_candidate": True},
                )
        if narrative_input_builder is not None:
            state.current_level = PolicySearchLevel.NARRATIVE
            bundles: list[tuple[str, Any]] = []
            for structure in accepted_structures:
                result = state.parameter_search_results.get(structure.structure_id)
                bundle = narrative_input_builder(structure, result)
                if bundle is None:
                    continue
                bundles.append((structure.candidate_hash, bundle))
            state.narrative_variants = coordinator.run_narrative_search(bundles)
        state_payload = state.model_dump(mode="python") if hasattr(state, "model_dump") else state
        return HierarchicalSearchResult(state=state_payload, shared_frontier=[])


def _coerce_lex_policy_bundle_input(
    bundle_input: LexPolicyBundleInput | TrinityBundle | Mapping[str, Any],
) -> LexPolicyBundleInput:
    if isinstance(bundle_input, LexPolicyBundleInput):
        return bundle_input
    if isinstance(bundle_input, TrinityBundle):
        return LexPolicyBundleInput(trinity_bundle=bundle_input)
    if isinstance(bundle_input, Mapping) and "trinity_bundle" in bundle_input:
        return LexPolicyBundleInput.model_validate(bundle_input)
    return LexPolicyBundleInput(trinity_bundle=TrinityBundle.model_validate(bundle_input))


def _bundle_domain(bundle: TrinityBundle) -> str:
    domain = bundle.problem_frame.domain
    return str(domain.value if hasattr(domain, "value") else domain)


@dataclass(frozen=True)
class _CandidateEvaluationRecord:
    structure_id: str
    candidate: PolicyCandidateSchema
    evaluation: PolicyEvaluationVector | None
    feasible: bool
    objective_value: float | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RunHierarchicalPolicySearchNode:
    """Generate and evaluate policy candidates, then install the champion candidate.

    Upstream assumptions: policy drafting/formalization has produced either a
    typed `params.policy_candidate_schema`, a `params.lex_policy_bundle_input`,
    or an `inputs.trinity_bundle_ref`; compilation inputs and graph/evidence
    artifacts required by the inner candidate-evaluation pipeline must already be
    present in `inputs`, `artifacts_index`, and `reports_index`.

    Reads from state:
        `run_id`, policy-search params, `inputs.trinity_bundle_ref`, and the
        current `inputs`/`artifacts_index`/`reports_index` snapshots.

    Writes to state:
        `params.policy_candidate_schema`,
        `params.policy_search_result`,
        `inputs.trinity_bundle_ref`,
        `artifacts_index.policy_frontier_report_ref`.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def prepare_cache_input(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> PreparedSKGRead | None:
        """Bind the nested candidate readers to one source before outer cache lookup."""
        del ctx
        config_payload = state.params.get("cross_graph_evidence_config")
        evidence_sources = normalize_evidence_sources_config(state.params, config_payload)
        candidate_paths = {
            str(value).strip()
            for value in (
                state.params.get("skg_db_path"),
                evidence_sources.academic_db_path,
            )
            if isinstance(value, str) and value.strip()
        }
        if len(candidate_paths) != 1:
            return None
        db_path = Path(next(iter(candidate_paths)))
        index_raw = state.params.get("skg_index_dir") or evidence_sources.academic_index_dir
        index_dir = Path(str(index_raw)) if index_raw else db_path.parent
        if not index_dir.exists():
            index_dir = db_path.parent
        return SKGQuery.prepare_read(db_path=db_path, index_dir=index_dir)

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Run hierarchical search and persist the selected champion/frontier artifacts.

        Returns:
            `skip` when no candidate source exists, `fail` when the adapter or
            inner candidate evaluation raises, otherwise `ok` with the champion
            Trinity ref and optional frontier report ref.
        """
        try:
            transfer_intent = _candidate_only_transfer_intent_from_state(state)
            raw_comparison = state.params.get("policy_search_completed_ex_ante_comparison")
            comparison_request = (
                CompletedExAnteComparisonRequest.model_validate(raw_comparison)
                if "policy_search_completed_ex_ante_comparison" in state.params
                else None
            )
        except _POLICY_SEARCH_VALIDATION_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid policy_search_candidate_transfer intent: {exc}",
                ),
            )

        try:
            candidate = _resolve_search_candidate(ctx, state)
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError) as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Selected policy-search input failed owner admission: {exc}",
                    details={"input": INPUT_TRINITY_BUNDLE_REF},
                ),
            )
        if candidate is None:
            if transfer_intent is not None:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code=node_errors.ERROR_INVALID_STATE,
                        message=(
                            "policy_search_candidate_transfer requires a policy candidate "
                            "or Lex bundle input"
                        ),
                    ),
                )
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No policy candidate or Lex bundle found; skip hierarchical search.",
                    )
                ],
            )

        adapter = HierarchicalPolicySearchAdapter()
        loop_id = str(state.params.get("policy_loop_id") or f"{state.run_id}:policy_search")

        from polisyos.scientist.agent.vector_memory import UntrustedNativeVectorBundleError

        transfer_limitation: dict[str, str] | None = None
        try:
            search_config = _runtime_search_config_from_state(state)
            try:
                candidate_only_seed_evaluations = _load_candidate_only_transfer_evaluations(
                    ctx,
                    loop_id=loop_id,
                    intent=transfer_intent,
                    candidate=candidate,
                )
            except UntrustedNativeVectorBundleError as exc:
                transfer_limitation = {
                    "status": "limited",
                    "reason": exc.reason,
                    "continuation": "cold_search",
                }
                candidate_only_seed_evaluations = None
            search_result = adapter.run_search(
                candidate,
                loop_id=loop_id,
                search_config=search_config,
                initial_context={"run_id": loop_id, "workflow_run_id": state.run_id},
                candidate_only_seed_evaluations=candidate_only_seed_evaluations,
                source_store=ctx.store,
                stage_b_evaluator=lambda candidate_payload, context: _evaluate_candidate_payload(
                    ctx,
                    state,
                    candidate_payload=candidate_payload,
                    context=context,
                ),
            )
        except _POLICY_SEARCH_EXECUTION_ERRORS as exc:
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=f"Hierarchical policy search failed: {exc}",
            )
            return NodeOutcome(status="fail", state=state, error=error)

        selected_champion = _select_champion_candidate(search_result, source_store=ctx.store)
        champion = selected_champion or candidate

        champion_trinity_ref = _persist_trinity_bundle(
            ctx,
            champion.trinity_bundle,
            state=state,
        )
        frontier_ref = _persist_frontier_report(
            ctx,
            state=state,
            loop_id=loop_id,
            search_result=search_result,
            transfer_limitation=transfer_limitation,
        )

        # Search may have taken long enough for an earlier source selection to
        # be replaced or revoked. Resolve both sources at final emission.
        candidate_comparison = (
            ParetoRegistry.rank_completed_ex_ante_candidates(
                ctx=ctx, sources=comparison_request.sources
            )
            if comparison_request is not None
            else None
        )
        new_state = branch_state(
            state,
            write_paths=(
                "params.policy_candidate_schema",
                "params.policy_search_result",
                f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
                f"artifacts_index.{ARTIFACT_POLICY_FRONTIER_REPORT_REF}",
            ),
        ).state
        new_state.params["policy_candidate_schema"] = champion
        new_state.params["policy_search_result"] = {
            **search_result.model_dump(mode="json"),
            **({"transfer_limitation": transfer_limitation} if transfer_limitation else {}),
            "champion_candidate_id": (
                None if selected_champion is None else selected_champion.candidate_id
            ),
            "champion_candidate_hash": (
                None if selected_champion is None else selected_champion.candidate_hash()
            ),
            "champion_status": ("not_established" if selected_champion is None else "selected"),
            "completed_ex_ante_candidate_comparison": (
                candidate_comparison.model_dump(mode="json")
                if candidate_comparison is not None
                else None
            ),
        }
        new_state.inputs[INPUT_TRINITY_BUNDLE_REF] = champion_trinity_ref
        if frontier_ref is not None:
            new_state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF] = frontier_ref

        artifacts = [champion_trinity_ref]
        if frontier_ref is not None:
            artifacts.append(frontier_ref)
        events = (
            []
            if transfer_limitation is None
            else [
                NodeEvent(
                    level="warn",
                    code="policy_search.transfer_limited",
                    message="Transfer index had no admitted portable rows; search continued cold.",
                    attrs=transfer_limitation,
                )
            ]
        )
        return NodeOutcome(status="ok", state=new_state, artifacts=artifacts, events=events)


def _candidate_only_transfer_intent_from_state(
    state: ExperimentState,
) -> _CandidateOnlyPolicyTransferIntent | None:
    """Parse an explicitly supplied candidate-transfer request without defaulting null."""
    key = "policy_search_candidate_transfer"
    if key not in state.params:
        return None
    payload = state.params[key]
    if isinstance(payload, _CandidateOnlyPolicyTransferIntent):
        return _CandidateOnlyPolicyTransferIntent.model_validate(payload.model_dump(mode="python"))
    return _CandidateOnlyPolicyTransferIntent.model_validate(payload)


def _load_candidate_only_transfer_evaluations(
    ctx: ExecutionContext,
    *,
    loop_id: str,
    intent: _CandidateOnlyPolicyTransferIntent | None,
    candidate: PolicyCandidateSchema,
) -> list[Evaluation] | None:
    """Load index-bound V5 history candidates for current policy re-evaluation."""
    if intent is None:
        return None
    fingerprint = intent.query_fingerprint
    if fingerprint.run_id != loop_id:
        raise ValueError("candidate transfer fingerprint must identify this policy-search loop")
    selected_objectives = HierarchicalSearchCoordinator().build_optimizer_objective_spec(candidate)
    if (
        set(fingerprint.objective_names) != set(selected_objectives.objective_names)
        or fingerprint.objective_directions
        != dict(
            zip(
                selected_objectives.objective_names,
                [direction.value for direction in selected_objectives.directions],
                strict=True,
            )
        )
        or fingerprint.objective_rule_specs != selected_objectives.objective_rule_specs
    ):
        raise ValueError(
            "candidate transfer fingerprint does not match the selected objective rules"
        )
    if not ctx.run.tenant_id or fingerprint.tenant_id != ctx.run.tenant_id:
        raise ValueError("candidate transfer tenant identity does not match the current run")

    from polisyos.scientist.agent.vector_memory import VectorMemoryStore
    from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
    from polisyos.scientist.methods.search.strategies.transfer import (
        TransferLearningManager,
    )

    index = VectorMemoryStore.from_portable_artifact(ctx.store, intent.index_ref)
    manager = TransferLearningManager(ctx.store, index)
    similar_runs = manager.find_similar_runs(
        fingerprint,
        top_k=intent.max_source_runs,
    )
    if not similar_runs:
        raise ValueError("candidate transfer found no fully bound indexed history")
    bridge = WarmStartBridge(
        manager,
        max_evals=intent.max_candidates,
        top_k_runs=intent.max_source_runs,
    )
    evaluations = bridge.load_warm_start(fingerprint, similar_runs=similar_runs)
    source_fingerprints = {source.run_id: source for source in similar_runs}
    prepared: list[Evaluation] = []
    for evaluation in evaluations:
        source_run_id = str(evaluation.metadata.get("source_run_id") or "")
        source = source_fingerprints.get(source_run_id)
        if source is None or source.history_ref is None:
            continue
        history_ref = source.history_ref
        evaluation.metadata["candidate_only_transfer_source_history_ref"] = history_ref.model_dump(
            mode="json"
        )
        evaluation.metadata["candidate_only_transfer_source_binding"] = {
            "run_id": source_run_id,
            "space_hash": source.space_hash,
            "objective_names": list(source.objective_names),
            "bounds": dict(source.bounds),
            "split": source.split,
            "units": dict(source.units),
            "origin": source.origin,
            "tenant_id": source.tenant_id,
            "objective_directions": dict(source.objective_directions),
            "objective_rule_specs": dict(source.objective_rule_specs),
            "history_ref": history_ref.model_dump(mode="json"),
        }
        evaluation.metadata["candidate_only_transfer_index_ref"] = intent.index_ref.model_dump(
            mode="json"
        )
        prepared.append(evaluation)
    if not prepared:
        raise ValueError("candidate transfer history contained no addressed evaluations")
    return prepared


def _runtime_search_config_from_state(state: ExperimentState) -> object:
    raw = state.params.get("hierarchical_policy_search_config") or state.params.get(
        "policy_search_config"
    )
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        require_explicit = raw.get("require_explicit_parameter_bounds")
        legacy_shadow = raw.get("allow_legacy_shadow_inferred_bounds")
        if require_explicit is False or legacy_shadow is True:
            raise ValueError(
                "runtime state params cannot enable legacy inferred bounds; "
                "require_explicit_parameter_bounds=False and "
                "allow_legacy_shadow_inferred_bounds=True are fenced from production."
            )
        return dict(raw)
    require_explicit = getattr(raw, "require_explicit_parameter_bounds", None)
    legacy_shadow = getattr(raw, "allow_legacy_shadow_inferred_bounds", None)
    if require_explicit is False or legacy_shadow is True:
        raise ValueError(
            "runtime state params cannot enable legacy inferred bounds; "
            "legacy shadow inferred bounds are fenced from production."
        )
    return raw


def _resolve_search_candidate(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> PolicyCandidateSchema | None:
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.ir.trinity import load_trinity_bundle_artifact

    explicit = _coerce_policy_candidate(state.params.get("policy_candidate_schema"))
    lex_bundle = _coerce_lex_bundle(state.params.get("lex_policy_bundle_input"))
    adapter = HierarchicalPolicySearchAdapter()

    if explicit is not None:
        if lex_bundle is None:
            return explicit
        enriched = adapter.build_candidate(lex_bundle)
        return explicit.model_copy(
            update={
                "metadata": {
                    **dict(enriched.metadata),
                    **dict(explicit.metadata),
                }
            }
        )

    if lex_bundle is not None:
        return adapter.build_candidate(lex_bundle)

    trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is None:
        return None
    bundle = load_trinity_bundle_artifact(
        ensure_ir_artifact_store(ctx.store),
        trinity_ref,
    )
    return PolicyCandidateSchema.from_trinity_bundle(bundle)


def _evaluate_candidate_payload(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    candidate_payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    del context
    candidate = PolicyCandidateSchema.model_validate(
        _candidate_payload_without_hash(candidate_payload)
    )
    candidate_state = branch_state(
        state,
        write_paths=(
            "params.policy_candidate_schema",
            f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
            *(f"artifacts_index.{key}" for key in _INNER_CANDIDATE_ARTIFACT_KEYS),
        ),
    ).state
    candidate_state.params["policy_candidate_schema"] = candidate
    candidate_state.inputs[INPUT_TRINITY_BUNDLE_REF] = _persist_trinity_bundle(
        ctx,
        candidate.trinity_bundle,
        state=state,
    )
    for key in _INNER_CANDIDATE_ARTIFACT_KEYS:
        candidate_state.artifacts_index.pop(key, None)

    compile_outcome = CompileFoundryNode().execute(ctx, candidate_state)
    if compile_outcome.status != "ok":
        return _rejected_stage_b_result(
            candidate,
            blocked_reason="compile_foundry_failed",
            details=_node_error_payload(compile_outcome.error),
        )
    candidate_state = compile_outcome.state

    cross_graph_outcome = CompileCrossGraphEvidenceNode().execute(ctx, candidate_state)
    if cross_graph_outcome.status == "fail":
        return _rejected_stage_b_result(
            candidate,
            blocked_reason="compile_cross_graph_evidence_failed",
            details=_node_error_payload(cross_graph_outcome.error),
        )
    candidate_state = cross_graph_outcome.state

    resolve_outcome = ResolveParametersNode().execute(ctx, candidate_state)
    if resolve_outcome.status == "fail":
        return _rejected_stage_b_result(
            candidate,
            blocked_reason="resolve_parameters_failed",
            details=_node_error_payload(resolve_outcome.error),
        )
    candidate_state = resolve_outcome.state

    readiness_outcome = RunCausalReadinessNode().execute(ctx, candidate_state)
    if readiness_outcome.status == "fail":
        return _rejected_stage_b_result(
            candidate,
            blocked_reason="run_causal_readiness_failed",
            details=_node_error_payload(readiness_outcome.error),
        )
    candidate_state = readiness_outcome.state

    gate_outcome = evaluate_counterfactual_gate(ctx, candidate_state)
    candidate_state = gate_outcome.state
    gate_summary = dict(candidate_state.params.get("counterfactual_gate_summary") or {})
    if gate_outcome.status == "fail":
        return _rejected_stage_b_result(
            candidate,
            blocked_reason="counterfactual_gate_blocked",
            details=gate_summary,
        )

    manifest = getattr(ctx.run, "run_manifest", None)
    environment_ref = getattr(manifest, "environment_manifest_ref", None)
    tee_ref = getattr(manifest, "tee_attestation_ref", None)
    sbom_ref = getattr(manifest, "sbom_ref", None)
    try:
        simulation_outcome = RunSimulationNode().execute(ctx, candidate_state)
    finally:
        if manifest is not None:
            manifest.environment_manifest_ref = environment_ref
            manifest.tee_attestation_ref = tee_ref
            manifest.sbom_ref = sbom_ref
    if simulation_outcome.status != "ok":
        return _rejected_stage_b_result(
            candidate,
            blocked_reason="run_simulation_failed",
            details=_node_error_payload(simulation_outcome.error),
        )
    candidate_state = simulation_outcome.state

    simulation_metrics = load_simulation_metrics(ctx, candidate_state) or None
    try:
        evaluation_artifact = build_policy_runtime_evaluation(
            candidate,
            backend=ProductionPolicyEvaluationBackend(
                eval_safety_execution_context=ctx.eval_safety_execution_context,
                eval_safety_verifier=ctx.eval_safety_verifier,
                world_model_record=_world_model_record_from_state(candidate_state),
            ),
            fidelity="selection",
            simulation_metrics=simulation_metrics,
            uncertainty=load_search_uncertainty(ctx, candidate_state),
            distributional_report=load_distributional_report_for_state(ctx, candidate_state),
            causal_effect_report=load_causal_report(ctx, candidate_state),
            cross_graph_profile=load_cross_graph_profile(ctx, candidate_state),
            governance_report=load_governance_report(ctx, candidate_state),
            ambiguity_certificate=load_ambiguity_certificate(ctx, candidate_state),
        )
    except PolicyRuntimeEvaluationSafetyError as exc:
        return _rejected_stage_b_result(
            candidate,
            blocked_reason="eval_safety_blocked",
            details={"blocker_codes": list(exc.blocker_codes)},
        )
    evaluation = evaluation_artifact.evaluation_vector.model_copy(
        update={
            "metadata": {
                **dict(evaluation_artifact.evaluation_vector.metadata),
                "counterfactual_gate_summary": gate_summary,
                "candidate_hash": candidate.candidate_hash(),
            }
        }
    )
    simulation_results = dict(evaluation_artifact.simulation_results)
    objective_value, score_status = evaluation.legacy_scalar_proxy_for_search(simulation_results)
    candidate_ref = evaluation_ref = None
    try:
        from polisyos.core.artifacts import ensure_ir_artifact_store
        from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
            persist_policy_evaluation_vector,
        )
        from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema

        candidate_ref = persist_policy_candidate_schema(
            ensure_ir_artifact_store(ctx.store), candidate, return_selected_profile=True
        )
        evaluation_ref = persist_policy_evaluation_vector(
            ctx, candidate_ref=candidate_ref, evaluation_vector=evaluation
        )
    except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
        # The computation remains a candidate observation. Missing selected
        # source refs cannot establish rank or authority.
        candidate_ref = evaluation_ref = None
    return {
        "candidate_ref": candidate_ref.model_dump(mode="json") if candidate_ref else None,
        "policy_evaluation_ref": evaluation_ref.model_dump(mode="json") if evaluation_ref else None,
        "status": "ok",
        "feasible": bool(evaluation.feasible),
        "objective_value": objective_value,
        "objective_score_status": score_status.value,
        "simulation_results": simulation_results,
        "policy_evaluation": evaluation.model_dump(mode="json"),
        "counterfactual_gate_summary": gate_summary,
        "baseline_policy_value": resolve_baseline_policy_value(
            evaluation_artifact.simulation_results
        ),
    }


def _world_model_record_from_state(state: ExperimentState) -> WorldModelRecord | None:
    raw = state.params.get("world_model_record")
    if isinstance(raw, WorldModelRecord):
        return raw
    if isinstance(raw, Mapping):
        try:
            return WorldModelRecord.model_validate(raw)
        except ValidationError:
            return None
    return None


def _rejected_stage_b_result(
    candidate: PolicyCandidateSchema,
    *,
    blocked_reason: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evaluation = ObjectiveStack().evaluate(
        PolicyEvaluationBundle(
            candidate=candidate,
            metadata={"candidate_hash": candidate.candidate_hash()},
        )
    )
    evaluation = evaluation.model_copy(
        update={
            "feasible": False,
            "blocking_reasons": [blocked_reason],
            "metadata": {
                **dict(evaluation.metadata),
                "candidate_hash": candidate.candidate_hash(),
                "blocked_reason": blocked_reason,
                "details": dict(details or {}),
            },
        }
    )
    objective_value, score_status = evaluation.legacy_scalar_proxy_for_search({})
    return {
        "status": "rejected",
        "feasible": False,
        "objective_value": objective_value,
        "objective_score_status": score_status.value,
        "simulation_results": {},
        "policy_evaluation": evaluation.model_dump(mode="json"),
        "blocked_reason": blocked_reason,
        "details": dict(details or {}),
    }


def _candidate_source_ref(value: Any) -> ArtifactRef | None:
    if value is None:
        return None
    try:
        return ArtifactRef.model_validate(value)
    except (TypeError, ValueError):
        return None


def _select_champion_candidate(
    search_result: Any, *, source_store: Any | None = None
) -> PolicyCandidateSchema | None:
    ranked = [
        (record, rank_key)
        for record in _iter_candidate_records(search_result, source_store=source_store)
        if (rank_key := _candidate_rank_key(record)) is not None
    ]
    ranked.sort(key=lambda item: item[1], reverse=True)
    if ranked:
        return ranked[0][0].candidate
    return None


def _iter_candidate_records(
    search_result: Any, *, source_store: Any | None = None
) -> list[_CandidateEvaluationRecord]:
    records: list[_CandidateEvaluationRecord] = []
    for structure_id, result in search_result.state.parameter_search_results.items():
        for iteration in result.history:
            source_payload = getattr(iteration, "stage_b_result", None)
            source_results = (
                source_payload.get("simulation_results")
                if isinstance(source_payload, dict)
                else None
            )
            assessment = getattr(iteration, "score_assessment", None)
            evaluation = _coerce_policy_evaluation(getattr(iteration, "policy_evaluation", None))
            if not verify_policy_evaluation_source(
                source_store,
                getattr(iteration, "candidate_proposal", None),
                evaluation,
                getattr(iteration, "candidate_ref", None),
                getattr(iteration, "evaluation_ref", None),
            ):
                continue
            source_is_valid = (
                evaluation.score_assessment_matches_channels(
                    source_results if isinstance(source_results, dict) else None
                )
                if evaluation is not None
                else score_assessment_matches_source(assessment, source_results)
            )
            if (
                getattr(iteration, "score_status", None) is not ObjectiveScoreStatus.AVAILABLE
                or not source_is_valid
            ):
                continue
            candidate_payload = iteration.candidate or result.best_candidate
            if not isinstance(candidate_payload, dict):
                continue
            candidate = PolicyCandidateSchema.model_validate(
                _candidate_payload_without_hash(candidate_payload)
            )
            if evaluation is None:
                objective_value = getattr(iteration, "objective_value", None)
                if objective_value is None:
                    continue
                feasible = bool(getattr(iteration, "is_promising", False))
            else:
                feasible = bool(evaluation.feasible)
                objective_value, score_status = evaluation.legacy_scalar_proxy_for_search(
                    source_results if isinstance(source_results, dict) else None
                )
                if score_status.value != "available" or objective_value is None:
                    continue
            records.append(
                _CandidateEvaluationRecord(
                    structure_id=structure_id,
                    candidate=candidate,
                    evaluation=evaluation,
                    feasible=feasible,
                    objective_value=objective_value,
                    metadata=dict(getattr(iteration, "stage_b_result", {}) or {}),
                )
            )
    represented_hashes = {record.candidate.candidate_hash() for record in records}
    for structure in getattr(search_result.state, "structure_candidates", ()):
        if getattr(structure, "accepted", False) is not True:
            continue
        candidate = _coerce_policy_candidate(getattr(structure, "candidate", None))
        if candidate is None:
            continue
        candidate_hash = candidate.candidate_hash()
        if candidate_hash in represented_hashes:
            continue
        metadata = getattr(structure, "metadata", {})
        records.append(
            _CandidateEvaluationRecord(
                structure_id=str(
                    getattr(structure, "structure_id", None) or candidate.candidate_id
                ),
                candidate=candidate,
                evaluation=None,
                feasible=False,
                objective_value=None,
                metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
            )
        )
        represented_hashes.add(candidate_hash)
    return records


def _candidate_rank_key(
    record: _CandidateEvaluationRecord,
) -> tuple[float, float, float, int] | None:
    evaluation = record.evaluation
    if evaluation is None:
        if record.objective_value is None:
            return None
        return (1.0 if record.feasible else 0.0, -float(record.objective_value), 0.0, 0)
    policy_value = _objective_value(evaluation, "policy_value")
    welfare = _objective_value(evaluation, "welfare")
    employment = _objective_value(evaluation, "employment")
    if policy_value is None or welfare is None or employment is None:
        return None
    blocking_count = len(evaluation.blocking_reasons)
    return (
        1.0 if record.feasible else 0.0,
        policy_value,
        welfare + employment,
        -blocking_count,
    )


def _objective_value(
    evaluation: PolicyEvaluationVector | None,
    name: str,
) -> float | None:
    if evaluation is None:
        return None
    channel = evaluation.primary.get(name)
    if channel is None:
        channel = evaluation.secondary.get(name)
    return None if channel is None else float(channel.higher_is_better)


def _coerce_policy_candidate(payload: Any) -> PolicyCandidateSchema | None:
    if payload is None:
        return None
    if isinstance(payload, PolicyCandidateSchema):
        return payload
    try:
        return PolicyCandidateSchema.model_validate(payload)
    except _POLICY_SEARCH_VALIDATION_ERRORS:
        return None


def _coerce_lex_bundle(payload: Any) -> LexPolicyBundleInput | None:
    if payload is None:
        return None
    if isinstance(payload, LexPolicyBundleInput):
        return payload
    try:
        return LexPolicyBundleInput.model_validate(payload)
    except _POLICY_SEARCH_VALIDATION_ERRORS:
        return None


def _coerce_policy_evaluation(payload: Any) -> PolicyEvaluationVector | None:
    try:
        return _normalize_policy_evaluation_vector(
            payload, allow_mapping=isinstance(payload, Mapping)
        )
    except _POLICY_SEARCH_VALIDATION_ERRORS:
        return None


def _candidate_payload_without_hash(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove strategy-only envelope fields before validating a policy candidate."""
    cleaned = dict(payload)
    cleaned.pop("candidate_hash", None)
    cleaned.pop("semantic", None)
    cleaned.pop("_strategy_metadata", None)
    return cleaned


def _node_error_payload(error: NodeError | None) -> dict[str, Any]:
    if error is None:
        return {}
    return {
        "code": error.code,
        "message": error.message,
        "details": dict(error.details or {}),
    }


def _persist_trinity_bundle(
    ctx: ExecutionContext,
    bundle: TrinityBundle,
    *,
    state: ExperimentState,
) -> TrinityBundleRef:
    inputs = [input_ref_from_artifact_ref(ref, role=key) for key, ref in state.inputs.items()]
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact

    tenant_context = ctx.run.artifact_tenant_context()
    selected = persist_trinity_bundle_artifact(
        ensure_ir_artifact_store(ctx.store),
        bundle,
        inputs=inputs,
        tenant_context=tenant_context,
    )
    return TrinityBundleRef.model_validate(selected.model_dump(mode="json"))


def _persist_frontier_report(
    ctx: ExecutionContext,
    *,
    state: ExperimentState,
    loop_id: str,
    search_result: Any,
    transfer_limitation: dict[str, str] | None = None,
) -> Any | None:
    records = _iter_candidate_records(search_result, source_store=ctx.store)
    if not records:
        return None
    entries_by_hash: dict[str, PolicyFrontierEntry] = {}
    evaluation_feasibility_by_hash: dict[str, set[bool]] = {}
    missing_evaluation_hashes: set[str] = set()
    for record in records:
        candidate_hash = record.candidate.candidate_hash()
        view_membership: list[str] = []
        constraint_statuses: dict[str, str] = {}
        primary_objectives: dict[str, float] = {}
        metadata = {
            "structure_id": record.structure_id,
            **dict(record.metadata),
        }
        if record.evaluation is not None:
            evaluation_feasibility_by_hash.setdefault(candidate_hash, set()).add(
                record.evaluation.feasible
            )
            primary_objectives = {
                name: channel.value for name, channel in record.evaluation.primary.items()
            }
            constraint_statuses = {
                name: status.value for name, status in record.evaluation.constraint_statuses.items()
            }
        else:
            missing_evaluation_hashes.add(candidate_hash)
        entries_by_hash[candidate_hash] = PolicyFrontierEntry(
            candidate_hash=candidate_hash,
            candidate_id=record.candidate.candidate_id,
            policy_family=str(
                record.candidate.metadata.get("policy_family") or record.candidate.candidate_id
            ),
            view_membership=view_membership,
            primary_objectives=primary_objectives,
            constraint_statuses=constraint_statuses,
            metadata=metadata,
        )
    source_feasible_hashes = tuple(
        sorted(
            candidate_hash
            for candidate_hash, feasible_states in evaluation_feasibility_by_hash.items()
            if feasible_states == {True} and candidate_hash not in missing_evaluation_hashes
        )
    )
    eligibility_unknown_hashes = tuple(
        sorted(
            candidate_hash
            for candidate_hash in entries_by_hash
            if candidate_hash in missing_evaluation_hashes
            or len(evaluation_feasibility_by_hash[candidate_hash]) != 1
        )
    )
    projection = getattr(search_result, "pareto_projection", None)
    if projection is None:
        projection = ParetoViewProjection(
            view="global_feasible",
            assessment=ParetoViewAssessment(
                status="basis_limited",
                coverage_status="no_usable_inputs",
                basis_scope=ParetoBasisScope(scope="not_established"),
                input_count=len(source_feasible_hashes),
                assessed_count=0,
                unassessed_candidate_hashes=list(source_feasible_hashes),
            ),
            eligible_candidate_hashes=source_feasible_hashes,
            candidate_frontier_hashes=source_feasible_hashes,
            unassessed_candidate_hashes=source_feasible_hashes,
        )
    elif isinstance(projection, dict):
        projection = ParetoViewProjection.model_validate(projection)
    source_feasible = set(source_feasible_hashes)
    eligible = set(projection.eligible_candidate_hashes)
    if source_feasible != eligible or eligibility_unknown_hashes:
        # Reconcile the complete source and registry denominators. Missing,
        # conflicting, or unassessed records cannot support a global rank.
        assessment = ParetoViewAssessment.model_validate(
            {
                **projection.assessment.model_dump(mode="python"),
                "status": "denominator_limited",
            }
        )
        projection = ParetoViewProjection(
            view=projection.view,
            assessment=assessment,
            eligible_candidate_hashes=projection.eligible_candidate_hashes,
            candidate_frontier_hashes=projection.candidate_frontier_hashes,
            unassessed_candidate_hashes=projection.eligible_candidate_hashes,
        )
    ranked_hashes = set(projection.ranked_frontier_hashes)
    for candidate_hash in ranked_hashes & set(entries_by_hash):
        entries_by_hash[candidate_hash].view_membership = ["global_feasible"]
    candidate_hashes = (
        tuple(
            sorted(
                (set(projection.candidate_frontier_hashes) & source_feasible)
                | (source_feasible - eligible)
                | set(eligibility_unknown_hashes)
            )
        )
        if projection.assessment.status != "complete"
        else ()
    )
    report = PolicyFrontierReport(
        loop_id=loop_id,
        global_frontier=[
            entries_by_hash[candidate_hash]
            for candidate_hash in projection.ranked_frontier_hashes
            if candidate_hash in entries_by_hash
        ],
        candidate_frontier=[
            entries_by_hash[candidate_hash]
            for candidate_hash in candidate_hashes
            if candidate_hash in entries_by_hash
        ],
        source_feasible_candidate_hashes=source_feasible_hashes,
        eligibility_unknown_candidate_hashes=eligibility_unknown_hashes,
        view_membership={"global_feasible": list(projection.ranked_frontier_hashes)},
        view_projections={"global_feasible": projection},
        metadata={
            "source": "c6c_hierarchical_policy_search",
            "source_run_id": state.run_id,
            **({"transfer_limitation": transfer_limitation} if transfer_limitation else {}),
        },
    )
    inputs = [InputRef(artifact_id=ref.artifact_id, role=key) for key, ref in state.inputs.items()]
    return persist_policy_frontier_report(ctx.store, report, inputs=inputs)


__all__ = ["RunHierarchicalPolicySearchNode"]
