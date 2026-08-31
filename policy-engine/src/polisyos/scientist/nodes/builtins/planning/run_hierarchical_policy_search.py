"""Planning node that generates candidate policies, evaluates them, and installs a champion.

The node sits between policy formalization and Foundry compilation in the
`scientist_policy_design` DAG. It resolves an initial candidate from
`params.policy_candidate_schema`, `params.lex_policy_bundle_input`, or the
current Trinity input, runs hierarchical structure/parameter search, evaluates
candidate payloads through the compile/readiness/simulation subpipeline, and
persists a frontier report plus the selected champion Trinity bundle.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.trinity import TrinityBundleRef
from polisyos.ir.trinity import TrinityBundle
from polisyos.lex.intervention_artifacts import LexPolicyBundleInput
from polisyos.lex.interventions import HierarchicalPolicySearchPlan
from polisyos.pdc import WorldModelRecord
from polisyos.scientist.methods.search.controller import (
    SearchIteration,
    SearchResult,
    SearchStatus,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    resolve_baseline_policy_value,
)
from polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate import (
    evaluate_counterfactual_gate,
)
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.nodes.builtins.causal.run_causal_readiness import RunCausalReadinessNode
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
        "params.hierarchical_policy_search_config",
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
_POLICY_SEARCH_EXECUTION_ERRORS = (RuntimeError, TypeError, ValueError, ValidationError)


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
    ) -> Any:
        resolved_candidate = self._resolve_candidate_payload(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        coordinator = HierarchicalSearchCoordinator(
            config=self.instantiate_search_config(search_config)
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
                candidate_payload = structure.candidate.as_search_payload()
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
                stage_b_result = stage_b_evaluator(candidate_payload, context)
                state.parameter_search_results[structure.structure_id] = SearchResult(
                    search_id=f"{loop_id}:{structure.structure_id}",
                    status=SearchStatus.CONVERGED,
                    best_candidate=candidate_payload,
                    best_objective=float(stage_b_result.get("objective_value", 0.0)),
                    iterations_completed=1,
                    history=[
                        SearchIteration(
                            iteration=0,
                            candidate=candidate_payload,
                            objective_value=float(stage_b_result.get("objective_value", 0.0)),
                            objective_details=[],
                            is_promising=bool(stage_b_result.get("feasible", True)),
                            stage_a_passed=True,
                            stage_b_result=stage_b_result,
                            duration_seconds=0.0,
                            policy_evaluation=stage_b_result.get("policy_evaluation"),
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
    objective_value: float
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

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Run hierarchical search and persist the selected champion/frontier artifacts.

        Returns:
            `skip` when no candidate source exists, `fail` when the adapter or
            inner candidate evaluation raises, otherwise `ok` with the champion
            Trinity ref and optional frontier report ref.
        """
        candidate = _resolve_search_candidate(ctx, state)
        if candidate is None:
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

        try:
            search_config = _runtime_search_config_from_state(state)
            search_result = adapter.run_search(
                candidate,
                loop_id=loop_id,
                search_config=search_config,
                initial_context={"run_id": state.run_id},
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

        champion = _select_champion_candidate(candidate, search_result)
        if champion is None:
            champion = candidate

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
            "champion_candidate_id": champion.candidate_id,
            "champion_candidate_hash": champion.candidate_hash(),
        }
        new_state.inputs[INPUT_TRINITY_BUNDLE_REF] = champion_trinity_ref
        if frontier_ref is not None:
            new_state.artifacts_index[ARTIFACT_POLICY_FRONTIER_REPORT_REF] = frontier_ref

        artifacts = [champion_trinity_ref]
        if frontier_ref is not None:
            artifacts.append(frontier_ref)
        return NodeOutcome(status="ok", state=new_state, artifacts=artifacts)


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
    payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
    bundle = TrinityBundle.model_validate(payload)
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
    return {
        "status": "ok",
        "feasible": bool(evaluation.feasible),
        "objective_value": float(evaluation.legacy_scalar_proxy),
        "simulation_results": dict(evaluation_artifact.simulation_results),
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
    return {
        "status": "rejected",
        "feasible": False,
        "objective_value": float(evaluation.legacy_scalar_proxy),
        "simulation_results": {},
        "policy_evaluation": evaluation.model_dump(mode="json"),
        "blocked_reason": blocked_reason,
        "details": dict(details or {}),
    }


def _select_champion_candidate(
    fallback_candidate: PolicyCandidateSchema,
    search_result: Any,
) -> PolicyCandidateSchema | None:
    ranked = sorted(
        _iter_candidate_records(search_result),
        key=_candidate_rank_key,
        reverse=True,
    )
    if ranked:
        return ranked[0].candidate
    structure_candidates = [
        item.candidate for item in search_result.state.structure_candidates if item.accepted
    ]
    if structure_candidates:
        return structure_candidates[0]
    return fallback_candidate


def _iter_candidate_records(search_result: Any) -> list[_CandidateEvaluationRecord]:
    records: list[_CandidateEvaluationRecord] = []
    structure_map = {
        item.structure_id: item.candidate for item in search_result.state.structure_candidates
    }
    for structure_id, result in search_result.state.parameter_search_results.items():
        for iteration in result.history:
            evaluation = _coerce_policy_evaluation(getattr(iteration, "policy_evaluation", None))
            candidate_payload = iteration.candidate or result.best_candidate
            if not isinstance(candidate_payload, dict):
                continue
            candidate = PolicyCandidateSchema.model_validate(
                _candidate_payload_without_hash(candidate_payload)
            )
            if evaluation is None:
                feasible = bool(getattr(iteration, "is_promising", False))
                objective_value = float(getattr(iteration, "objective_value", 0.0))
            else:
                feasible = bool(evaluation.feasible)
                objective_value = float(evaluation.legacy_scalar_proxy)
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
    if records:
        return records
    for structure_id, candidate in structure_map.items():
        records.append(
            _CandidateEvaluationRecord(
                structure_id=structure_id,
                candidate=candidate,
                evaluation=None,
                feasible=True,
                objective_value=0.0,
                metadata={},
            )
        )
    return records


def _candidate_rank_key(record: _CandidateEvaluationRecord) -> tuple[float, float, float, int]:
    evaluation = record.evaluation
    policy_value = _objective_value(evaluation, "policy_value")
    welfare = _objective_value(evaluation, "welfare")
    employment = _objective_value(evaluation, "employment")
    blocking_count = 0 if evaluation is None else len(evaluation.blocking_reasons)
    return (
        1.0 if record.feasible else 0.0,
        policy_value,
        welfare + employment,
        -blocking_count,
    )


def _objective_value(
    evaluation: PolicyEvaluationVector | None,
    name: str,
) -> float:
    if evaluation is None:
        return 0.0
    channel = evaluation.primary.get(name)
    if channel is None:
        channel = evaluation.secondary.get(name)
    return 0.0 if channel is None else float(channel.higher_is_better)


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
    if payload is None:
        return None
    if isinstance(payload, PolicyEvaluationVector):
        return payload
    try:
        return PolicyEvaluationVector.model_validate(payload)
    except _POLICY_SEARCH_VALIDATION_ERRORS:
        return None


def _candidate_payload_without_hash(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    cleaned.pop("candidate_hash", None)
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
    inputs = [InputRef(artifact_id=ref.artifact_id, role=key) for key, ref in state.inputs.items()]
    artifact = ctx.store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.TrinityBundle",
                version=str(bundle.schema_version),
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return TrinityBundleRef.model_validate(artifact.model_dump(mode="json"))


def _persist_frontier_report(
    ctx: ExecutionContext,
    *,
    state: ExperimentState,
    loop_id: str,
    search_result: Any,
) -> Any | None:
    records = _iter_candidate_records(search_result)
    if not records:
        return None
    entries: list[PolicyFrontierEntry] = []
    feasible_hashes: list[str] = []
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
            if record.evaluation.feasible:
                view_membership.append("global_feasible")
                feasible_hashes.append(candidate_hash)
            primary_objectives = {
                name: channel.value for name, channel in record.evaluation.primary.items()
            }
            constraint_statuses = {
                name: status.value for name, status in record.evaluation.constraint_statuses.items()
            }
        entries.append(
            PolicyFrontierEntry(
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
        )
    report = PolicyFrontierReport(
        loop_id=loop_id,
        global_frontier=entries,
        view_membership={"global_feasible": feasible_hashes},
        metadata={"source": "c6c_hierarchical_policy_search"},
    )
    inputs = [InputRef(artifact_id=ref.artifact_id, role=key) for key, ref in state.inputs.items()]
    return persist_policy_frontier_report(ctx.store, report, inputs=inputs)


__all__ = ["RunHierarchicalPolicySearchNode"]
