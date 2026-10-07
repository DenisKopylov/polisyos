"""Thin depth-N router over canonical recursion and generation-cycle owners."""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from typing import TYPE_CHECKING, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ModelWrapValidatorHandler,
    PrivateAttr,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from polisyos.core.artifacts import ArtifactRef as CASArtifactRef  # noqa: TC001
from polisyos.pdc import (
    CompositionCertificate,
    EvalSafetyAdmissionChallenge,
    SearchTerminalKind,
    SearchTerminalState,
    SubDesignContract,
    evaluation_safety_consumer_admission_is_verified,
    gy_artifact_self_identity_projection,
    gy_content_hash,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    RecursiveDesignGraph,
    compose_subdesigns,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.evaluation_modes import (
    ExecutionIntentBand,
    execution_intent_band_for_mode,
    resolve_evaluation_mode,
    resolve_execution_intent_band,
)
from polisyos.runtime.quality.evaluation_safety import EvaluationExecutionContext
from polisyos.runtime.quality.generation_cycle import (
    FOUNDRY_VALUE_PORT_EVALUATOR_ID,
    FoundryValuePort,
    GenerationCycleController,
    GenerationCycleError,
    GenerationCycleRun,
    N4GenerationPort,
    generation_cycle_terminal_state,
    persist_joint_simulation_result,
    validate_generation_cycle_candidate_run,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationHorizonController,
    JointSimulationRequest,
    JointSimulationResult,
    SimulationProofReceipt,
)
from polisyos.runtime.quality.workspace.loop import (
    SearchExitDecisionInputs,
    select_search_terminal,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core import contracts as core_contracts
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextHandoff,
    )
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from polisyos.runtime.quality.evaluation_safety import EvalSafetyVerifierPort
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from polisyos.scientist import BudgetState

RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION = "policyos.runtime.recursive_generation_cycle.v1"
RECURSIVE_GENERATION_CYCLE_PARTIAL_V2_SCHEMA_VERSION = (
    "policyos.runtime.recursive_generation_cycle.partial.v2"
)
ExecutionIntent = Literal[
    "candidate_only",
    "simulate_only",
    "retrospective",
    "measurement_audit",
    "sandbox_pilot",
    "field_pilot",
    "deployment",
]
RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF = (
    "polisyos.runtime.quality.recursive_generation_cycle.RecursiveGenerationCycleController"
)
# These are the complete set of ref-less v1 recursive-run identities currently
# tracked in the repository.  A self-computed hash is integrity evidence only;
# it is not permission to reopen pre-CAS numeric evidence.
_AUTHENTIC_LEGACY_RECURSIVE_V1_CONTENT_HASHES = frozenset(
    {
        "sha256:b72e66af7330f57830ca9c70c348051e53b858e02a5b82893988855823c7a3c1",
        "sha256:13647b6958aac56b004faded5752b31cc7d53fde67c9476f1f899051b4edab50",
        "sha256:47cf94dbe46aa90e9a0a9b3208459f4687a0ea1c651ef5d8dbce8a738db09f6d",
        "sha256:17a29992ae4ce1720290a40e1a7651bf5949176e718520824d74b80c2b8a2328",
        "sha256:23ad1413786ccf1e3c1d13c09d33a9df87bb3a18c798570be245206c352d72ec",
        "sha256:027db04a69e899eb80c911de9df7432d31fa8afd480baf0dae8f49ca62362137",
        "sha256:d6ddaacf81d9cc4c48b049c4070149026d1fd8e07a118890a5abc1745c952535",
    }
)
_LEGACY_RECURSIVE_V1_CONTEXT: ContextVar[bool] = ContextVar(
    "polisyos_legacy_recursive_v1_context",
    default=False,
)
_LEGACY_RECURSIVE_FIXTURE_SYMBOLS = frozenset(
    {
        "run_recursive_case",
        "coupling_graph_for_subdesigns",
        "_recursive_case_child_fixtures",
    }
)
_DEFAULT_RECURSIVE_ROUTE_SYMBOL = "build_default_recursive_generation_cycle_controller"


def _is_authenticated_legacy_v1(value: object) -> bool:
    """Return whether value is one exact tracked pre-CAS recursive artifact."""

    if not isinstance(value, Mapping):
        return False
    if value.get("schema_version") != RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION:
        return False
    raw_nodes = value.get("nodes")
    if not isinstance(raw_nodes, (list, tuple)) or not raw_nodes:
        return False
    if any(not isinstance(node, Mapping) for node in raw_nodes):
        return False
    if any("joint_simulation_ref" in node for node in raw_nodes):
        return False
    raw_content_hash = value.get("content_hash")
    if raw_content_hash not in _AUTHENTIC_LEGACY_RECURSIVE_V1_CONTENT_HASHES:
        return False
    legacy_payload = {key: item for key, item in value.items() if key != "content_hash"}
    return gy_content_hash(legacy_payload) == raw_content_hash


def _joint_simulation_is_unsupported(result: JointSimulationResult) -> bool:
    """Return whether N5 emitted no supported trajectory for composition."""

    return (
        result.receipt.calibration_status in {"unsupported_coupling_gated", "no_run"}
        or not result.trajectories
        or not any(decision.decision == "selected" for decision in result.engine_decisions)
    )


class RecursiveGenerationCycleError(ValueError):
    """Fail-closed depth-N routing error."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _RecursiveBudgetStopError(Exception):
    """Unwind the router after an owner-issued leaf budget terminal."""

    def __init__(
        self,
        budget_stop_node_ref: str,
        frontier_node_refs: tuple[str, ...] = (),
    ) -> None:
        self.budget_stop_node_ref = budget_stop_node_ref
        self.frontier_node_refs = frontier_node_refs
        super().__init__("recursive_child_budget_exhausted")


class _StrictModel(BaseModel):
    """Strict immutable base for public depth-N artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RecursiveCycleBudget(_StrictModel):
    """Explicit recursion and leaf-cycle limits owned by the thin router."""

    max_depth: int = Field(ge=0, le=99)
    max_nodes: int = Field(ge=1, le=100)
    min_cycles_per_leaf: int = Field(ge=1)
    max_cycles_per_leaf: int = Field(ge=1)

    @model_validator(mode="after")
    def _cycle_range_is_coherent(self) -> RecursiveCycleBudget:
        if self.min_cycles_per_leaf > self.max_cycles_per_leaf:
            raise ValueError("recursive_cycle_budget_range_incoherent")
        return self


def _legacy_supplied_field_tree(value: object, payload: object) -> object:
    """Preserve supplied v1 fields, including JSON-normalized map keys."""

    if isinstance(value, BaseModel) and isinstance(payload, dict):
        fields_by_key = {
            key: name
            for name, field in type(value).model_fields.items()
            for key in (name, field.alias, field.serialization_alias)
            if isinstance(key, str)
        }
        return {
            key: _legacy_supplied_field_tree(getattr(value, fields_by_key[key]), item)
            for key, item in payload.items()
            if key in fields_by_key and fields_by_key[key] in value.model_fields_set
        }
    if isinstance(value, Mapping) and isinstance(payload, dict):
        return {
            key: _legacy_supplied_field_tree(
                next(
                    (
                        original_value
                        for original_key, original_value in value.items()
                        if original_key == key or str(original_key) == key
                    ),
                    item,
                ),
                item,
            )
            for key, item in payload.items()
        }
    if isinstance(value, (tuple, list)) and isinstance(payload, (tuple, list)):
        return [
            _legacy_supplied_field_tree(original, item)
            for original, item in zip(value, payload, strict=True)
        ]
    return payload


class RecursiveCycleNode(_StrictModel):
    """One replay-visible node routed through existing depth owners."""

    node_ref: str = Field(min_length=1)
    parent_ref: str | None = None
    depth: int = Field(ge=0)
    child_refs: tuple[str, ...] = ()
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cycle_run: GenerationCycleRun | None = None
    joint_simulation: JointSimulationResult | None = None
    joint_simulation_ref: CASArtifactRef | None = None
    composition_certificate: CompositionCertificate | None = None
    terminal: SearchTerminalState
    _legacy_v1_missing_joint_simulation_ref: bool = PrivateAttr(default=False)

    @field_validator("cycle_run", mode="before")
    @classmethod
    def _load_persisted_leaf_run(cls, value: object) -> object:
        """Route a serialized leaf through the canonical persisted N6 reader."""

        if isinstance(value, Mapping):
            return GenerationCycleRun.from_persisted_payload(value)
        return value

    @model_validator(mode="after")
    def _only_leaves_run_n6(self) -> RecursiveCycleNode:
        legacy_v1 = _LEGACY_RECURSIVE_V1_CONTEXT.get()
        if legacy_v1:
            object.__setattr__(self, "_legacy_v1_missing_joint_simulation_ref", True)
        if self.joint_simulation is None and self.joint_simulation_ref is not None:
            raise ValueError("recursive_simulation_ref_without_result")
        if (
            self.joint_simulation is not None
            and self.joint_simulation_ref is None
            and not legacy_v1
        ):
            raise ValueError("recursive_simulation_result_requires_cas_ref")
        if self.joint_simulation_ref is not None and (
            self.joint_simulation_ref.kind != "polisyos.runtime.joint_simulation_result"
            or self.joint_simulation_ref.media_type != "application/json"
        ):
            raise ValueError("recursive_simulation_ref_contract_mismatch")
        if self.child_refs and self.cycle_run is not None:
            raise ValueError("recursive_internal_node_cannot_run_leaf_cycle")
        if not self.child_refs and self.cycle_run is None:
            raise ValueError("recursive_leaf_requires_generation_cycle")
        if not self.child_refs and (
            self.joint_simulation is not None or self.composition_certificate is not None
        ):
            raise ValueError("recursive_leaf_cannot_mint_parent_evidence")
        if len(self.child_refs) < 2 and (
            self.joint_simulation is not None or self.composition_certificate is not None
        ):
            raise ValueError("recursive_unary_parent_cannot_mint_coupled_evidence")
        if self.composition_certificate is not None and self.joint_simulation is None:
            raise ValueError("recursive_composition_requires_joint_simulation")
        if self.composition_certificate is not None and (
            self.composition_certificate.parent_workspace_id != self.node_ref
            or self.composition_certificate.target_policy_program_ref != self.node_ref
        ):
            raise ValueError("recursive_composition_parent_binding_mismatch")
        if self.joint_simulation is not None:
            unsupported = _joint_simulation_is_unsupported(self.joint_simulation)
            if unsupported and self.composition_certificate is not None:
                raise ValueError("recursive_unsupported_n5_cannot_mint_composition")
            if not unsupported and self.composition_certificate is None:
                raise ValueError("recursive_supported_n5_requires_composition")
        return self

    @model_serializer(mode="wrap")
    def _serialize_without_legacy_or_empty_simulation_ref(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        """Keep v1 identity bytes stable while omitting empty ref defaults."""

        payload = handler(self)
        if self._legacy_v1_missing_joint_simulation_ref:
            supplied = _legacy_supplied_field_tree(self, payload)
            if not isinstance(supplied, dict):
                raise TypeError("historical_recursive_payload_invalid")
            payload = supplied
        if self.joint_simulation_ref is None:
            payload.pop("joint_simulation_ref", None)
        return payload


class RecursiveGenerationCycleRun(_StrictModel):
    """Content-bound depth-N run emitted by the thin recursive router."""

    schema_version: str = RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    controller_ref: str = RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF
    authority_scope: Literal["production", "contract_testing"] = "production"
    recursive_graph: RecursiveDesignGraph
    recursive_graph_ref: str = Field(min_length=1)
    recursive_graph_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    root_node_ref: str = Field(min_length=1)
    root_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    recursive_budget: RecursiveCycleBudget
    observed_max_depth: int = Field(ge=0)
    nodes: tuple[RecursiveCycleNode, ...] = Field(min_length=1)
    terminal: SearchTerminalState
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="wrap")
    @classmethod
    def _admit_authenticated_legacy_v1(
        cls,
        value: object,
        handler: ModelWrapValidatorHandler,
    ) -> RecursiveGenerationCycleRun:
        """Scope legacy ref omission to exact tracked identities during validation."""

        token = _LEGACY_RECURSIVE_V1_CONTEXT.set(_is_authenticated_legacy_v1(value))
        try:
            return handler(value)
        finally:
            _LEGACY_RECURSIVE_V1_CONTEXT.reset(token)

    @property
    def leaf_nodes(self) -> tuple[RecursiveCycleNode, ...]:
        """Return nodes whose real N6 leaf runs produced terminal evidence."""

        return tuple(node for node in self.nodes if not node.child_refs)

    @property
    def joint_simulation_receipts(self) -> tuple[SimulationProofReceipt, ...]:
        """Return only receipts emitted live by the canonical N5 owner."""

        return tuple(
            node.joint_simulation.receipt
            for node in self.nodes
            if node.joint_simulation is not None
        )

    @model_validator(mode="after")
    def _verify_content_binding(self) -> RecursiveGenerationCycleRun:
        if (
            self.recursive_graph_ref != self.recursive_graph.graph_ref
            or self.recursive_graph_content_hash
            != gy_content_hash(self.recursive_graph.model_dump(mode="json"))
        ):
            raise ValueError("recursive_run_graph_binding_mismatch")
        by_ref = {node.node_ref: node for node in self.nodes}
        if len(by_ref) != len(self.nodes):
            raise ValueError("recursive_run_duplicate_node")
        root = by_ref.get(self.root_node_ref)
        if root is None or root.parent_ref is not None or root.depth != 0:
            raise ValueError("recursive_run_root_incoherent")
        if self.root_design_problem_ref != root.design_problem_ref:
            raise ValueError("recursive_run_root_problem_mismatch")
        if (
            self.root_node_ref != self.recursive_graph.root_design_ref
            or set(by_ref) != set(self.recursive_graph.node_refs)
            or {(node.node_ref, child_ref) for node in self.nodes for child_ref in node.child_refs}
            != set(self.recursive_graph.parent_child_edges)
        ):
            raise ValueError("recursive_run_graph_topology_mismatch")
        if self.terminal != root.terminal:
            raise ValueError("recursive_run_terminal_not_root_derived")
        if self.observed_max_depth != max(node.depth for node in self.nodes):
            raise ValueError("recursive_run_observed_depth_incoherent")
        if (
            len(self.nodes) > self.recursive_budget.max_nodes
            or self.observed_max_depth > self.recursive_budget.max_depth
        ):
            raise ValueError("recursive_run_budget_incoherent")
        for node in sorted(self.nodes, key=lambda item: item.depth, reverse=True):
            if len(node.child_refs) != len(set(node.child_refs)):
                raise ValueError("recursive_run_duplicate_child")
            for child_ref in node.child_refs:
                child = by_ref.get(child_ref)
                if (
                    child is None
                    or child.parent_ref != node.node_ref
                    or child.depth != node.depth + 1
                ):
                    raise ValueError("recursive_run_topology_incoherent")
            if node.node_ref != self.root_node_ref:
                parent = by_ref.get(node.parent_ref or "")
                if parent is None or node.node_ref not in parent.child_refs:
                    raise ValueError("recursive_run_topology_incoherent")
            if (
                node.cycle_run is not None
                and node.cycle_run.design_problem_ref != node.design_problem_ref
            ):
                raise ValueError("recursive_run_leaf_problem_mismatch")
            if node.cycle_run is not None:
                if node.terminal != generation_cycle_terminal_state(node.cycle_run):
                    raise ValueError("recursive_run_leaf_terminal_not_owner_derived")
                continue
            routed_children = tuple(by_ref[child_ref] for child_ref in node.child_refs)
            if len(routed_children) == 1:
                expected_terminal = _fold_unary_terminal(routed_children[0])
            elif node.joint_simulation is not None and node.composition_certificate is not None:
                expected_terminal = _fold_composed_terminal(
                    children=routed_children,
                    joint_simulation=node.joint_simulation,
                    certificate=node.composition_certificate,
                )
            elif node.joint_simulation is not None:
                expected_terminal = _blocked_parent_terminal("unsupported_coupling_gated")
            else:
                expected_terminal = node.terminal
            if node.terminal != expected_terminal:
                raise ValueError("recursive_run_parent_terminal_not_owner_derived")
        payload = gy_artifact_self_identity_projection(self)
        payload.pop("leaf_nodes", None)
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("recursive_generation_cycle_content_hash_mismatch")
        return self


class RecursiveCyclePendingNode(_StrictModel):
    """A graph member not executed before the recursive budget stop."""

    node_ref: str = Field(min_length=1)
    parent_ref: str | None = None
    depth: int = Field(ge=0)
    child_refs: tuple[str, ...] = ()
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RecursiveGenerationCyclePartialRunV2(_StrictModel):
    """Content-bound checkpoint preserving completed work and its pending frontier.

    This artifact represents traversal stopped by a real N6 child budget terminal.
    It deliberately has no root terminal: a partial graph cannot be projected as a
    completed design outcome or as epistemic abstention.
    """

    schema_version: Literal[
        "policyos.runtime.recursive_generation_cycle.partial.v2"
    ] = RECURSIVE_GENERATION_CYCLE_PARTIAL_V2_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    controller_ref: str = RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF
    authority_scope: Literal["production", "contract_testing"] = "production"
    recursive_graph: RecursiveDesignGraph
    recursive_graph_ref: str = Field(min_length=1)
    recursive_graph_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    root_node_ref: str = Field(min_length=1)
    root_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    recursive_budget: RecursiveCycleBudget
    observed_max_depth: int = Field(ge=0)
    nodes: tuple[RecursiveCycleNode | RecursiveCyclePendingNode, ...] = Field(min_length=1)
    traversal_status: Literal["budget_stopped"] = "budget_stopped"
    traversal_stop_reason: Literal["child_budget_exhausted"] = "child_budget_exhausted"
    budget_stop_node_ref: str = Field(min_length=1)
    frontier_node_refs: tuple[str, ...] = ()
    terminal: None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @property
    def leaf_nodes(self) -> tuple[RecursiveCycleNode, ...]:
        """Return only leaves whose canonical N6 runs actually completed."""

        return tuple(
            node
            for node in self.nodes
            if isinstance(node, RecursiveCycleNode) and not node.child_refs
        )

    @property
    def pending_node_refs(self) -> tuple[str, ...]:
        """Return graph members with no execution result."""

        return tuple(
            node.node_ref
            for node in self.nodes
            if isinstance(node, RecursiveCyclePendingNode)
        )

    @model_validator(mode="after")
    def _verify_partial_checkpoint(self) -> RecursiveGenerationCyclePartialRunV2:
        if (
            self.recursive_graph_ref != self.recursive_graph.graph_ref
            or self.recursive_graph_content_hash
            != gy_content_hash(self.recursive_graph.model_dump(mode="json"))
        ):
            raise ValueError("recursive_run_graph_binding_mismatch")

        node_refs = tuple(self.recursive_graph.node_refs)
        by_ref = {node.node_ref: node for node in self.nodes}
        if len(by_ref) != len(self.nodes) or set(by_ref) != set(node_refs):
            raise ValueError("recursive_partial_graph_denominator_mismatch")
        children_by_ref: dict[str, list[str]] = {ref: [] for ref in node_refs}
        parent_by_ref: dict[str, str] = {}
        for parent_ref, child_ref in self.recursive_graph.parent_child_edges:
            if parent_ref not in children_by_ref or child_ref not in children_by_ref:
                raise ValueError("recursive_run_graph_topology_mismatch")
            if child_ref in parent_by_ref:
                raise ValueError("recursive_run_graph_topology_mismatch")
            children_by_ref[parent_ref].append(child_ref)
            parent_by_ref[child_ref] = parent_ref
        if set(parent_by_ref) != set(node_refs) - {self.root_node_ref}:
            raise ValueError("recursive_run_graph_topology_mismatch")

        root = by_ref.get(self.root_node_ref)
        if (
            self.root_node_ref != self.recursive_graph.root_design_ref
            or not isinstance(root, RecursiveCyclePendingNode)
            or root.parent_ref is not None
            or root.depth != 0
            or root.design_problem_ref != self.root_design_problem_ref
            or self.terminal is not None
        ):
            raise ValueError("recursive_partial_root_not_pending")

        depths: dict[str, int] = {}

        def visit(node_ref: str, depth: int) -> None:
            if node_ref in depths or depth > self.recursive_budget.max_depth:
                raise ValueError("recursive_partial_graph_topology_incoherent")
            depths[node_ref] = depth
            for child_ref in children_by_ref[node_ref]:
                visit(child_ref, depth + 1)

        visit(self.root_node_ref, 0)
        if (
            set(depths) != set(node_refs)
            or len(node_refs) > self.recursive_budget.max_nodes
            or self.observed_max_depth != max(depths.values())
        ):
            raise ValueError("recursive_partial_graph_budget_incoherent")

        for node_ref in node_refs:
            node = by_ref[node_ref]
            expected_parent = parent_by_ref.get(node_ref)
            expected_children = tuple(children_by_ref[node_ref])
            if (
                node.parent_ref != expected_parent
                or node.depth != depths[node_ref]
                or node.child_refs != expected_children
            ):
                raise ValueError("recursive_partial_node_topology_mismatch")
            if isinstance(node, RecursiveCyclePendingNode):
                continue
            if (
                node.cycle_run is not None
                and node.cycle_run.design_problem_ref != node.design_problem_ref
            ):
                raise ValueError("recursive_run_leaf_problem_mismatch")
            if node.cycle_run is not None:
                if node.terminal != generation_cycle_terminal_state(node.cycle_run):
                    raise ValueError("recursive_run_leaf_terminal_not_owner_derived")
                continue
            routed_children = tuple(by_ref[child_ref] for child_ref in node.child_refs)
            if any(not isinstance(child, RecursiveCycleNode) for child in routed_children):
                raise ValueError("recursive_partial_completed_parent_has_pending_child")
            if len(routed_children) == 1:
                expected_terminal = _fold_unary_terminal(routed_children[0])
            elif node.joint_simulation is not None and node.composition_certificate is not None:
                expected_terminal = _fold_composed_terminal(
                    children=routed_children,
                    joint_simulation=node.joint_simulation,
                    certificate=node.composition_certificate,
                )
            elif node.joint_simulation is not None:
                expected_terminal = _blocked_parent_terminal("unsupported_coupling_gated")
            else:
                expected_terminal = _fold_uncomposed_partial_parent_terminal(node.terminal)
            if node.terminal != expected_terminal:
                raise ValueError("recursive_run_parent_terminal_not_owner_derived")

        budget_stop = by_ref.get(self.budget_stop_node_ref)
        if (
            not isinstance(budget_stop, RecursiveCycleNode)
            or budget_stop.child_refs
            or budget_stop.cycle_run is None
            or budget_stop.terminal.kind is not SearchTerminalKind.BUDGET_EXHAUSTED
        ):
            raise ValueError("recursive_partial_budget_stop_not_owner_derived")

        pending_refs = {
            node_ref
            for node_ref, node in by_ref.items()
            if isinstance(node, RecursiveCyclePendingNode)
        }
        if len(self.frontier_node_refs) != len(set(self.frontier_node_refs)):
            raise ValueError("recursive_partial_frontier_duplicate")
        frontier_refs = set(self.frontier_node_refs)
        if not frontier_refs.issubset(pending_refs):
            raise ValueError("recursive_partial_frontier_not_pending")
        stop_ancestors: set[str] = set()
        current_parent = parent_by_ref.get(self.budget_stop_node_ref)
        while current_parent is not None:
            stop_ancestors.add(current_parent)
            current_parent = parent_by_ref.get(current_parent)
        frontier_subtrees: set[str] = set()

        def collect_frontier_subtree(node_ref: str) -> None:
            if node_ref in frontier_subtrees:
                return
            frontier_subtrees.add(node_ref)
            for child_ref in children_by_ref[node_ref]:
                collect_frontier_subtree(child_ref)

        for frontier_ref in frontier_refs:
            if parent_by_ref.get(frontier_ref) not in stop_ancestors:
                raise ValueError("recursive_partial_frontier_not_sibling_of_stop_path")
            collect_frontier_subtree(frontier_ref)
        if pending_refs != stop_ancestors | frontier_subtrees:
            raise ValueError("recursive_partial_frontier_denominator_mismatch")

        payload = gy_artifact_self_identity_projection(self)
        payload.pop("leaf_nodes", None)
        payload.pop("pending_node_refs", None)
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("recursive_generation_cycle_content_hash_mismatch")
        return self


def _build_budget_stopped_recursive_run_v2(
    *,
    recursive_graph: RecursiveDesignGraph,
    problems_by_node: Mapping[str, DesignProblem],
    completed_nodes_by_ref: Mapping[str, RecursiveCycleNode],
    children_by_node: Mapping[str, list[str]],
    parent_by_node: Mapping[str, str],
    depths: Mapping[str, int],
    recursive_budget: RecursiveCycleBudget,
    budget_stop_node_ref: str,
    frontier_node_refs: tuple[str, ...],
    authority_scope: Literal["production", "contract_testing"],
) -> RecursiveGenerationCyclePartialRunV2:
    """Seal actual routed children and graph-only pending nodes in one checkpoint."""

    nodes: list[RecursiveCycleNode | RecursiveCyclePendingNode] = []
    for node_ref in recursive_graph.node_refs:
        completed = completed_nodes_by_ref.get(node_ref)
        if completed is not None:
            nodes.append(completed)
        else:
            nodes.append(
                RecursiveCyclePendingNode(
                    node_ref=node_ref,
                    parent_ref=parent_by_node.get(node_ref),
                    depth=depths[node_ref],
                    child_refs=tuple(children_by_node[node_ref]),
                    design_problem_ref=_problem_ref(problems_by_node[node_ref]),
                )
            )
    node_payloads = [node.model_dump(mode="json") for node in nodes]
    payload: dict[str, object] = {
        "schema_version": RECURSIVE_GENERATION_CYCLE_PARTIAL_V2_SCHEMA_VERSION,
        "run_id": f"recursive:{recursive_graph.graph_id}",
        "controller_ref": RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF,
        "authority_scope": authority_scope,
        "recursive_graph": recursive_graph.model_dump(mode="json"),
        "recursive_graph_ref": recursive_graph.graph_ref,
        "recursive_graph_content_hash": gy_content_hash(
            recursive_graph.model_dump(mode="json")
        ),
        "root_node_ref": recursive_graph.root_design_ref,
        "root_design_problem_ref": _problem_ref(
            problems_by_node[recursive_graph.root_design_ref]
        ),
        "recursive_budget": recursive_budget.model_dump(mode="json"),
        "observed_max_depth": max(depths.values()),
        "nodes": node_payloads,
        "traversal_status": "budget_stopped",
        "traversal_stop_reason": "child_budget_exhausted",
        "budget_stop_node_ref": budget_stop_node_ref,
        "frontier_node_refs": list(frontier_node_refs),
        "terminal": None,
    }
    return RecursiveGenerationCyclePartialRunV2.model_validate(
        {
            **payload,
            "nodes": tuple(nodes),
            "content_hash": gy_content_hash(payload),
        }
    )


CycleControllerFactory = Callable[[str, DesignProblem], GenerationCycleController]


class DepthNStrangleReceipt(_StrictModel):
    """Live, source-bound caller census for the depth-N recursive route.

    A caller census is positive evidence only when the controlled source slice
    was present and parsed successfully. Missing source or a parse failure is
    therefore represented separately from a real prohibited caller; both are
    non-positive outcomes, but they require different remediation.
    """

    status: Literal["strangled", "drift", "not_established"]
    source_state: Literal[
        "available",
        "missing",
        "parse_error",
        "read_error",
        "not_established",
    ]
    source_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    parse_errors: tuple[str, ...] = ()
    default_controller: str
    predecessor_symbols: tuple[str, ...]
    production_fixture_callers: tuple[str, ...]
    production_default_routes: tuple[str, ...]
    verified_by: str = (
        "polisyos.runtime.quality.recursive_generation_cycle.recompute_depth_n_strangle_receipt"
    )


def recompute_depth_n_strangle_receipt(
    repo_root: Path | None = None,
) -> DepthNStrangleReceipt:
    """Census the controlled source slice and surviving fixture callers.

    The receipt binds successful results to the bytes of ``src/polisyos``
    Python files. It deliberately withholds a source hash when the slice is
    absent, unreadable, or contains syntax errors, because a partial census is
    not evidence that the legacy caller is gone.
    """

    if repo_root is None:
        return DepthNStrangleReceipt(
            status="not_established",
            source_state="not_established",
            source_content_hash=None,
            parse_errors=(),
            default_controller="unresolved",
            predecessor_symbols=tuple(sorted(_LEGACY_RECURSIVE_FIXTURE_SYMBOLS)),
            production_fixture_callers=(),
            production_default_routes=(),
        )
    root = repo_root.resolve()
    source_root = root / "src/polisyos"
    callers: list[str] = []
    default_routes: list[str] = []
    parse_errors: list[str] = []
    source_files: dict[str, str] = {}
    if not source_root.is_dir():
        return DepthNStrangleReceipt(
            status="not_established",
            source_state="missing",
            source_content_hash=None,
            parse_errors=(),
            default_controller="unresolved",
            predecessor_symbols=tuple(sorted(_LEGACY_RECURSIVE_FIXTURE_SYMBOLS)),
            production_fixture_callers=(),
            production_default_routes=(),
        )

    for path in sorted(source_root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
            source_files[relative] = "sha256:" + hashlib.sha256(raw).hexdigest()
            tree = ast.parse(raw.decode("utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            parse_errors.append(f"{relative}:parse_error:{type(exc).__name__}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name in _LEGACY_RECURSIVE_FIXTURE_SYMBOLS
            ):
                callers.append(f"{path.relative_to(root)}:{node.lineno}:definition:{node.name}")
            if not isinstance(node, ast.Call):
                continue
            symbol = None
            if isinstance(node.func, ast.Name):
                symbol = node.func.id
            elif isinstance(node.func, ast.Attribute):
                symbol = node.func.attr
            if symbol in _LEGACY_RECURSIVE_FIXTURE_SYMBOLS:
                callers.append(f"{path.relative_to(root)}:{node.lineno}:call:{symbol}")
            if symbol == _DEFAULT_RECURSIVE_ROUTE_SYMBOL:
                default_routes.append(f"{path.relative_to(root)}:{node.lineno}:call:{symbol}")
    ordered = tuple(sorted(set(callers)))
    routes = tuple(sorted(set(default_routes)))
    ordered_parse_errors = tuple(sorted(set(parse_errors)))
    if ordered_parse_errors:
        source_state: Literal["available", "missing", "parse_error", "read_error"] = (
            "read_error"
            if any(item.rsplit(":", 1)[-1] == "OSError" for item in ordered_parse_errors)
            else "parse_error"
        )
        source_content_hash = None
        status: Literal["strangled", "drift", "not_established"] = "not_established"
    else:
        source_state = "available"
        source_content_hash = gy_content_hash(
            {
                "scope": "src/polisyos",
                "files": dict(sorted(source_files.items())),
            }
        )
        status = "drift" if ordered or not routes else "strangled"
    return DepthNStrangleReceipt(
        status=status,
        source_state=source_state,
        source_content_hash=source_content_hash,
        parse_errors=ordered_parse_errors,
        default_controller=(RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF if routes else "unresolved"),
        predecessor_symbols=tuple(sorted(_LEGACY_RECURSIVE_FIXTURE_SYMBOLS)),
        production_fixture_callers=ordered,
        production_default_routes=routes,
    )


def _problem_ref(problem: DesignProblem) -> str:
    return gy_content_hash(problem.model_dump(mode="json"))


def _leaf_terminal(run: GenerationCycleRun) -> SearchTerminalState:
    return generation_cycle_terminal_state(run)


def _fold_unary_terminal(child: RecursiveCycleNode) -> SearchTerminalState:
    return SearchTerminalState(
        kind=child.terminal.kind,
        reason="Unary recursive parent routed its child terminal without widening authority.",
        blocking_obligations=list(child.terminal.blocking_obligations),
        budget_kind=child.terminal.budget_kind,
        costed_plan=child.terminal.costed_plan,
        data_need_spec=child.terminal.data_need_spec,
    )


def _fold_composed_terminal(
    *,
    children: tuple[RecursiveCycleNode, ...],
    joint_simulation: JointSimulationResult,
    certificate: CompositionCertificate,
) -> SearchTerminalState:
    kinds = {child.terminal.kind for child in children}
    unsupported_simulation = _joint_simulation_is_unsupported(joint_simulation)
    positive_terminal = SearchTerminalKind.GROUNDED_ADMISSIBLE
    if SearchTerminalKind.GROUNDED_ABSTENTION in kinds:
        positive_terminal = SearchTerminalKind.GROUNDED_ABSTENTION
    elif SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE in kinds:
        positive_terminal = SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE
    decision = select_search_terminal(
        SearchExitDecisionInputs(
            spec_gap=SearchTerminalKind.A_SPEC_GAP in kinds,
            tool_failure=SearchTerminalKind.TOOL_FAILURE in kinds,
            composition_invalid=(
                certificate.verdict == "not_composable"
                or SearchTerminalKind.COMPOSITION_INVALID in kinds
            ),
            recursive_blocked=(
                unsupported_simulation or SearchTerminalKind.RECURSIVE_BLOCKED in kinds
            ),
            poor_recall=SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED in kinds,
            human_decision_required=SearchTerminalKind.HUMAN_DECISION_REQUIRED in kinds,
            acquisition_required=SearchTerminalKind.ACQUISITION_REQUIRED in kinds,
            budget_exhausted_kind=(
                "recursive" if SearchTerminalKind.BUDGET_EXHAUSTED in kinds else None
            ),
            frontier_stable=SearchTerminalKind.FRONTIER_STABLE in kinds,
            positive_terminal=positive_terminal,
        )
    )
    blockers = [blocker for child in children for blocker in child.terminal.blocking_obligations]
    blockers.extend(obligation.obligation_id for obligation in certificate.unresolved_obligations)
    blockers.extend(joint_simulation.feedback_classification.support_blockers)
    acquisition_children = tuple(
        child
        for child in children
        if child.terminal.kind is SearchTerminalKind.ACQUISITION_REQUIRED
    )
    costed_plan = None
    data_need_spec = None
    if decision.kind is SearchTerminalKind.ACQUISITION_REQUIRED and len(acquisition_children) == 1:
        costed_plan = acquisition_children[0].terminal.costed_plan
        data_need_spec = acquisition_children[0].terminal.data_need_spec
    return SearchTerminalState(
        kind=decision.kind,
        reason=decision.reason,
        blocking_obligations=list(dict.fromkeys(blockers)),
        budget_kind=decision.budget_kind,
        costed_plan=costed_plan,
        data_need_spec=data_need_spec,
    )


def _blocked_parent_terminal(reason: str) -> SearchTerminalState:
    return SearchTerminalState(
        kind=SearchTerminalKind.RECURSIVE_BLOCKED,
        reason="Recursive parent lacks owner-proven coupling/composition inputs.",
        blocking_obligations=[reason],
    )


_PARTIAL_UNCOMPOSED_PARENT_DIAGNOSTIC_CODES = frozenset(
    {
        "observed_coupling_evidence_missing",
        "subdesign_contract_denominator_missing",
        "recursive_coupling_design_ref_mismatch",
        "recursive_coupling_child_denominator_mismatch",
        "recursive_coupling_edge_unresolved",
        "recursive_subdesign_denominator_mismatch",
        "recursive_subdesign_terminal_binding_mismatch",
        "recursive_n5_atom_problem_binding_mismatch",
        "recursive_n5_outcome_problem_binding_mismatch",
    }
)


def _fold_uncomposed_partial_parent_terminal(
    terminal: SearchTerminalState,
) -> SearchTerminalState:
    """Admit only conservative blocked shape for bounded uncomposed parents.

    The blocker codes are router diagnostics, not recomputed facts about the
    source coupling graph or subdesign contracts. V2 does not persist enough
    owner evidence to re-establish those predicates, so this helper preserves
    only a blocked terminal with no acquisition, budget, or positive authority
    fields; all other terminal shapes are refused.
    """

    if (
        terminal.kind is not SearchTerminalKind.RECURSIVE_BLOCKED
        or len(terminal.blocking_obligations) != 1
        or terminal.blocking_obligations[0]
        not in _PARTIAL_UNCOMPOSED_PARENT_DIAGNOSTIC_CODES
    ):
        raise ValueError("recursive_partial_parent_not_conservatively_blocked")
    expected = _blocked_parent_terminal(terminal.blocking_obligations[0])
    if terminal != expected:
        raise ValueError("recursive_partial_parent_terminal_not_owner_derived")
    return expected


def _composition_claims_for_problem(
    problem: DesignProblem,
    *,
    target_policy_program_ref: str,
) -> tuple[dict[str, object], ...]:
    """Project parent intent as candidate-only claims for the composition owner."""

    problem_ref = _problem_ref(problem)
    return tuple(
        {
            "claim_ref": (
                f"claim://design-problem/{problem_ref.removeprefix('sha256:')}/"
                f"objective/{objective.objective_id}"
            ),
            "claim_text": objective.description,
            "outcome_variable": problem.outcome_of_interest.target_variable,
            "target_policy_program_ref": target_policy_program_ref,
            "grounding_refs": (),
        }
        for objective in problem.objectives
    )


def _branch_binding_issue(
    *,
    node_ref: str,
    problem_ref: str,
    problem: DesignProblem,
    child_refs: tuple[str, ...],
    routed_children: tuple[RecursiveCycleNode, ...],
    request: JointSimulationRequest,
    subdesigns: tuple[SubDesignContract, ...],
) -> str | None:
    """Resolve branch identities before N5 or composition can emit evidence."""

    graph = request.coupling_graph
    if graph is None:
        return "observed_coupling_evidence_missing"
    if graph.design_ref != node_ref:
        return "recursive_coupling_design_ref_mismatch"
    if len(graph.module_refs) != len(set(graph.module_refs)) or set(graph.module_refs) != set(
        child_refs
    ):
        return "recursive_coupling_child_denominator_mismatch"
    if any(
        edge.source_module_ref not in child_refs or edge.target_module_ref not in child_refs
        for edge in graph.interaction_edges
    ):
        return "recursive_coupling_edge_unresolved"
    by_workspace = {subdesign.workspace_id: subdesign for subdesign in subdesigns}
    if len(by_workspace) != len(subdesigns) or set(by_workspace) != set(child_refs):
        return "recursive_subdesign_denominator_mismatch"
    routed_by_ref = {child.node_ref: child for child in routed_children}
    for child_ref in child_refs:
        subdesign = by_workspace[child_ref]
        routed = routed_by_ref[child_ref]
        if (
            subdesign.parent_workspace_id != node_ref
            or subdesign.search_exit.workspace_id != child_ref
            or subdesign.search_exit.terminal_state != routed.terminal
        ):
            return "recursive_subdesign_terminal_binding_mismatch"
    if any(atom.problem_frame_ref != problem_ref for atom in request.intervention_atoms):
        return "recursive_n5_atom_problem_binding_mismatch"
    if problem.outcome_of_interest.target_variable not in request.selected_outcomes:
        return "recursive_n5_outcome_problem_binding_mismatch"
    return None


def build_default_recursive_generation_cycle_controller(
    *,
    promotion_runtime: PromotionRuntime,
    eval_safety_verifier: EvalSafetyVerifierPort | None = None,
    repo_root: Path | None = None,
    model_id: str | None = None,
) -> RecursiveGenerationCycleController:
    """Build the production router from one container-owned promotion runtime."""

    return RecursiveGenerationCycleController(
        repo_root=repo_root,
        model_id=model_id,
        promotion_runtime=promotion_runtime,
        eval_safety_verifier=eval_safety_verifier,
    )


class RecursiveGenerationCycleController:
    """Route a recursive design graph and delegate every engine decision."""

    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        model_id: str | None = None,
        promotion_runtime: PromotionRuntime | None = None,
        artifact_store: ArtifactStore | None = None,
        eval_safety_verifier: EvalSafetyVerifierPort | None = None,
        epoch_subject_authority: core_contracts.EpochValidityPreN9SubjectAuthority | None = None,
        epoch_validity_gate: core_contracts.EpochValidityAuthorityGate | None = None,
        epoch_n9_evidence_resolver: core_contracts.EpochValidityN9EvidenceResolver | None = None,
    ) -> None:
        if promotion_runtime is not None and any(
            dependency is not None
            for dependency in (
                epoch_subject_authority,
                epoch_validity_gate,
                epoch_n9_evidence_resolver,
            )
        ):
            raise ValueError("recursive_epoch_dependencies_must_be_runtime_derived")
        if promotion_runtime is not None:
            if artifact_store is not None and artifact_store is not promotion_runtime.store:
                raise ValueError("recursive_artifact_store_owner_mismatch")
            artifact_store = promotion_runtime.store
        self._repo_root = repo_root.resolve() if repo_root is not None else None
        self._leaf_model_id = model_id
        self._promotion_runtime = promotion_runtime
        self._artifact_store = artifact_store
        self._eval_safety_verifier = eval_safety_verifier
        self._epoch_subject_authority = epoch_subject_authority or getattr(
            promotion_runtime, "epoch_subject_authority", None
        )
        self._epoch_validity_gate = epoch_validity_gate or getattr(
            promotion_runtime, "epoch_validity_gate", None
        )
        self._epoch_n9_evidence_resolver = epoch_n9_evidence_resolver or getattr(
            promotion_runtime, "epoch_n9_evidence_resolver", None
        )
        self._cycle_controller_factory: CycleControllerFactory | None = None
        self._authority_scope: Literal["production", "contract_testing"] = "production"
        self._joint_simulation_controller = JointSimulationHorizonController()

    @classmethod
    def for_contract_testing(
        cls,
        *,
        cycle_controller_factory: CycleControllerFactory,
        repo_root: Path | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> RecursiveGenerationCycleController:
        """Build a visibly non-production router over canonical scripted N6 owners."""

        controller = cls(repo_root=repo_root, artifact_store=artifact_store)
        controller._cycle_controller_factory = cycle_controller_factory
        controller._authority_scope = "contract_testing"
        return controller

    async def run(
        self,
        recursive_graph: RecursiveDesignGraph,
        *,
        problems_by_node: Mapping[str, DesignProblem],
        budget_state: BudgetState,
        recursive_budget: RecursiveCycleBudget,
        joint_simulation_requests_by_node: Mapping[str, JointSimulationRequest] | None = None,
        subdesign_contracts_by_node: Mapping[str, tuple[SubDesignContract, ...]] | None = None,
        cycle_substrate_contexts_by_node: Mapping[str, CycleSubstrateContext] | None = None,
        candidate_simulation_handoffs_by_node: Mapping[
            str, CandidateSimulationContextHandoff
        ] | None = None,
        candidate_simulation_currentness_resolvers_by_node: Mapping[
            str, Callable[[], bool]
        ] | None = None,
        candidate_simulation_context_resolvers_by_node: Mapping[
            str, Callable[[DesignProblem], object]
        ]
        | None = None,
        n4_generation_ports_by_node: Mapping[str, N4GenerationPort] | None = None,
        evaluation_contexts_by_node: Mapping[str, EvaluationExecutionContext] | None = None,
        execution_intents_by_node: Mapping[str, ExecutionIntent] | None = None,
    ) -> RecursiveGenerationCycleRun | RecursiveGenerationCyclePartialRunV2:
        """Run N6 at leaves and preserve a checkpoint on child budget exhaustion."""

        if self._authority_scope == "production" and (
            self._promotion_runtime is None
            or self._epoch_subject_authority is None
            or self._epoch_validity_gate is None
            or self._epoch_n9_evidence_resolver is None
        ):
            raise RecursiveGenerationCycleError("recursive_epoch_owner_not_established")

        node_refs = tuple(recursive_graph.node_refs)
        if len(node_refs) != len(set(node_refs)):
            raise RecursiveGenerationCycleError("recursive_graph_duplicate_node")
        if recursive_graph.root_design_ref not in node_refs:
            raise RecursiveGenerationCycleError("recursive_graph_root_missing")
        if len(node_refs) > recursive_budget.max_nodes:
            raise RecursiveGenerationCycleError("recursive_node_budget_exhausted")
        if set(problems_by_node) != set(node_refs):
            raise RecursiveGenerationCycleError("recursive_problem_denominator_mismatch")

        children: dict[str, list[str]] = {node_ref: [] for node_ref in node_refs}
        parent_by_node: dict[str, str] = {}
        for parent_ref, child_ref in recursive_graph.parent_child_edges:
            if parent_ref not in children or child_ref not in children:
                raise RecursiveGenerationCycleError("recursive_graph_edge_unresolved")
            if child_ref == recursive_graph.root_design_ref:
                raise RecursiveGenerationCycleError("recursive_graph_root_has_parent")
            if child_ref in parent_by_node:
                raise RecursiveGenerationCycleError("recursive_graph_multiple_parents")
            children[parent_ref].append(child_ref)
            parent_by_node[child_ref] = parent_ref
        if set(parent_by_node) != set(node_refs) - {recursive_graph.root_design_ref}:
            raise RecursiveGenerationCycleError("recursive_graph_unreachable_node")

        depths: dict[str, int] = {}
        active: set[str] = set()

        def visit(node_ref: str, depth: int) -> None:
            if node_ref in active:
                raise RecursiveGenerationCycleError("recursive_graph_cycle_detected")
            if node_ref in depths:
                return
            if depth > recursive_budget.max_depth:
                raise RecursiveGenerationCycleError("recursive_depth_budget_exhausted")
            active.add(node_ref)
            depths[node_ref] = depth
            for child_ref in children[node_ref]:
                visit(child_ref, depth + 1)
            active.remove(node_ref)

        visit(recursive_graph.root_design_ref, 0)
        if set(depths) != set(node_refs):
            raise RecursiveGenerationCycleError("recursive_graph_unreachable_node")
        leaf_refs = {node_ref for node_ref, child_refs in children.items() if not child_refs}
        if candidate_simulation_handoffs_by_node is not None:
            from polisyos.runtime.quality.candidate_simulation import (
                CandidateSimulationContextHandoff,
            )
            from polisyos.runtime.quality.cycle_substrate import (
                cycle_job_design_problem_ref,
            )

            if not set(candidate_simulation_handoffs_by_node).issubset(leaf_refs):
                raise RecursiveGenerationCycleError(
                    "recursive_candidate_simulation_handoff_not_leaf"
                )
            for node_ref, handoff in candidate_simulation_handoffs_by_node.items():
                if type(handoff) is not CandidateSimulationContextHandoff:
                    raise RecursiveGenerationCycleError(
                        "recursive_candidate_simulation_handoff_untyped"
                    )
                if (
                    handoff.context.design_problem_ref
                    != cycle_job_design_problem_ref(problems_by_node[node_ref])
                    or (cycle_substrate_contexts_by_node or {}).get(node_ref)
                    != handoff.context
                ):
                    raise RecursiveGenerationCycleError(
                        "recursive_candidate_simulation_handoff_binding_mismatch"
                    )
        if set(candidate_simulation_currentness_resolvers_by_node or {}) != set(
            candidate_simulation_handoffs_by_node or {}
        ):
            raise RecursiveGenerationCycleError(
                "recursive_candidate_simulation_currentness_denominator_mismatch"
            )
        if candidate_simulation_context_resolvers_by_node is not None:
            context_resolver_refs = set(candidate_simulation_context_resolvers_by_node)
            if not context_resolver_refs.issubset(leaf_refs):
                raise RecursiveGenerationCycleError(
                    "recursive_candidate_simulation_context_resolver_not_leaf"
                )
            if any(
                not callable(resolver)
                for resolver in candidate_simulation_context_resolvers_by_node.values()
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_candidate_simulation_context_resolver_not_callable"
                )
            if not context_resolver_refs.issubset(set(candidate_simulation_handoffs_by_node or {})):
                raise RecursiveGenerationCycleError(
                    "recursive_candidate_simulation_context_resolver_without_handoff"
                )
            if context_resolver_refs and self._cycle_controller_factory is not None:
                raise RecursiveGenerationCycleError(
                    "recursive_candidate_simulation_factory_bypass_forbidden"
                )
        if candidate_simulation_handoffs_by_node and self._cycle_controller_factory is not None:
            raise RecursiveGenerationCycleError(
                "recursive_candidate_simulation_factory_bypass_forbidden"
            )
        if execution_intents_by_node is not None:
            if set(execution_intents_by_node) != leaf_refs:
                raise RecursiveGenerationCycleError(
                    "recursive_execution_intent_denominator_mismatch"
                )
            if any(
                execution_intent_band_for_mode(intent)
                is ExecutionIntentBand.NOT_ESTABLISHED
                for intent in execution_intents_by_node.values()
            ):
                raise RecursiveGenerationCycleError("recursive_execution_intent_not_canonical")
            if self._cycle_controller_factory is not None and any(
                execution_intent_band_for_mode(intent)
                is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                for intent in execution_intents_by_node.values()
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_eval_safety_custom_factory_context_not_consumed"
                )
        if evaluation_contexts_by_node is not None:
            supplied_context_refs = set(evaluation_contexts_by_node)
            required_eval_safety_refs = (
                leaf_refs
                if execution_intents_by_node is None
                else {
                    node_ref
                    for node_ref, intent in execution_intents_by_node.items()
                    if execution_intent_band_for_mode(intent)
                    is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                }
            )
            if (
                not supplied_context_refs.issubset(leaf_refs)
                or not required_eval_safety_refs.issubset(supplied_context_refs)
                or (execution_intents_by_node is None and supplied_context_refs != leaf_refs)
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_eval_safety_context_denominator_mismatch"
                )
            if self._cycle_controller_factory is not None and any(
                isinstance(context, EvaluationExecutionContext)
                and execution_intent_band_for_mode(context.evaluation_mode)
                is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                for context in evaluation_contexts_by_node.values()
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_eval_safety_custom_factory_context_not_consumed"
                )
        if self._cycle_controller_factory is None:
            candidate_band_only = bool(execution_intents_by_node) and all(
                execution_intent_band_for_mode(intent)
                in {
                    ExecutionIntentBand.CANDIDATE_ONLY,
                    ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT,
                }
                for intent in execution_intents_by_node.values()
            )
            if (
                evaluation_contexts_by_node is None
                and cycle_substrate_contexts_by_node is None
                and not candidate_band_only
            ):
                missing_owner_code = (
                    "recursive_data_trust_owner_not_established"
                    if execution_intents_by_node is not None
                    and not any(
                        execution_intent_band_for_mode(intent)
                        is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                        for intent in execution_intents_by_node.values()
                    )
                    and any(
                        execution_intent_band_for_mode(intent)
                        is ExecutionIntentBand.DATA_TRUST_REQUIRED
                        for intent in execution_intents_by_node.values()
                    )
                    else "recursive_eval_safety_context_not_established"
                )
                raise RecursiveGenerationCycleError(missing_owner_code)
            if evaluation_contexts_by_node is not None and any(
                not isinstance(context, EvaluationExecutionContext)
                for context in evaluation_contexts_by_node.values()
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_eval_safety_context_not_canonical"
                )
            for node_ref, intent in (execution_intents_by_node or {}).items():
                context = (evaluation_contexts_by_node or {}).get(node_ref)
                intent_band = execution_intent_band_for_mode(intent)
                if intent_band in {
                    ExecutionIntentBand.CANDIDATE_ONLY,
                    ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT,
                }:
                    if (
                        intent_band is ExecutionIntentBand.CANDIDATE_ONLY
                        and context is not None
                    ):
                        raise RecursiveGenerationCycleError(
                            "recursive_candidate_intent_has_eval_safety_context"
                        )
                    if context is None:
                        continue
                if context is None:
                    if intent_band is ExecutionIntentBand.DATA_TRUST_REQUIRED:
                        raise RecursiveGenerationCycleError(
                            "recursive_data_trust_owner_not_established"
                        )
                    raise RecursiveGenerationCycleError(
                        "recursive_eval_safety_context_denominator_mismatch"
                    )
                if context.evaluation_mode != intent:
                    code = (
                        "recursive_eval_safety_execution_mode_mismatch"
                        if intent_band is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                        else "recursive_execution_intent_context_mode_mismatch"
                    )
                    raise RecursiveGenerationCycleError(code)
            protected_node_refs = (
                {
                    node_ref
                    for node_ref, intent in execution_intents_by_node.items()
                    if execution_intent_band_for_mode(intent)
                    is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                }
                if execution_intents_by_node is not None
                else {
                    node_ref
                    for node_ref, context in (evaluation_contexts_by_node or {}).items()
                    if execution_intent_band_for_mode(context.evaluation_mode)
                    is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                }
            )
            for node_ref in protected_node_refs:
                context = (evaluation_contexts_by_node or {}).get(node_ref)
                if context is None or context.design_problem_ref != _problem_ref(
                    problems_by_node[node_ref]
                ):
                    raise RecursiveGenerationCycleError(
                        "recursive_eval_safety_design_problem_mismatch"
                    )
                verifier = self._eval_safety_verifier
                if verifier is None:
                    raise RecursiveGenerationCycleError(
                        "recursive_eval_safety_context_not_current"
                    )
                challenge = EvalSafetyAdmissionChallenge.fresh(
                    consumer_component_id=FOUNDRY_VALUE_PORT_EVALUATOR_ID
                )
                try:
                    admission = verifier.require_admission(context, challenge)
                except Exception as exc:
                    raise RecursiveGenerationCycleError(
                        "recursive_eval_safety_context_not_current",
                        type(exc).__name__,
                    ) from exc
                if (
                    not evaluation_safety_consumer_admission_is_verified(
                        admission,
                        context,
                        challenge,
                    )
                    or bool(admission.blocker_codes)
                    or context.eval_safety_certificate_ref is None
                    or context.eval_safety_revision_head_ref is None
                    or admission.certificate_ref != context.eval_safety_certificate_ref
                    or admission.current_revision_head_ref
                    != context.eval_safety_revision_head_ref
                ):
                    raise RecursiveGenerationCycleError(
                        "recursive_eval_safety_context_not_current"
                    )

        def effective_intent_band(node_ref: str) -> ExecutionIntentBand:
            explicit_intent = (execution_intents_by_node or {}).get(node_ref)
            if explicit_intent is not None:
                return execution_intent_band_for_mode(explicit_intent)
            evaluation_context = (evaluation_contexts_by_node or {}).get(node_ref)
            if isinstance(evaluation_context, EvaluationExecutionContext):
                return execution_intent_band_for_mode(
                    evaluation_context.evaluation_mode
                )
            if (
                self._authority_scope == "contract_testing"
                and type(self) is RecursiveGenerationCycleController
            ):
                return resolve_execution_intent_band(
                    attempt_present=False,
                    mode_resolution=resolve_evaluation_mode(None),
                )
            return ExecutionIntentBand.NOT_ESTABLISHED

        intent_bands_by_leaf = {
            node_ref: effective_intent_band(node_ref) for node_ref in leaf_refs
        }
        if self._authority_scope == "production" and any(
            band is ExecutionIntentBand.NOT_ESTABLISHED
            for band in intent_bands_by_leaf.values()
        ):
            raise RecursiveGenerationCycleError(
                "recursive_execution_intent_not_established"
            )

        if n4_generation_ports_by_node is not None:
            if self._cycle_controller_factory is not None:
                raise RecursiveGenerationCycleError(
                    "recursive_n4_port_and_controller_factory_conflict"
                )
            if set(n4_generation_ports_by_node) != leaf_refs:
                raise RecursiveGenerationCycleError("recursive_n4_port_denominator_mismatch")
            if any(
                not isinstance(port, N4GenerationPort)
                for port in n4_generation_ports_by_node.values()
            ):
                raise RecursiveGenerationCycleError("recursive_n4_port_not_canonical")

        node_results: dict[str, RecursiveCycleNode] = {}

        async def route(node_ref: str) -> RecursiveCycleNode:
            problem = problems_by_node[node_ref]
            problem_ref = _problem_ref(problem)
            child_refs = tuple(children[node_ref])
            if not child_refs:
                context = (cycle_substrate_contexts_by_node or {}).get(node_ref)
                if context is not None:
                    from polisyos.runtime.quality.cycle_substrate import (
                        revalidate_cycle_substrate_context,
                    )

                    revalidate_cycle_substrate_context(context)
                    if context.design_problem_ref != problem_ref:
                        raise RecursiveGenerationCycleError(
                            "recursive_leaf_context_problem_mismatch"
                        )
                if self._cycle_controller_factory is None:
                    evaluation_context = (evaluation_contexts_by_node or {}).get(node_ref)
                    if (
                        evaluation_context is not None
                        and evaluation_context.design_problem_ref != problem_ref
                    ):
                        raise RecursiveGenerationCycleError(
                            "recursive_eval_safety_design_problem_mismatch"
                        )
                    value_port = (
                        FoundryValuePort(
                            evaluation_context=evaluation_context,
                            eval_safety_verifier=self._eval_safety_verifier,
                            repo_root=self._repo_root,
                            cycle_substrate_context=context,
                        )
                        if evaluation_context is not None
                        else None
                    )
                    controller = GenerationCycleController(
                        generation_port=(n4_generation_ports_by_node or {}).get(node_ref),
                        value_port=value_port,
                        eval_safety_verifier=self._eval_safety_verifier,
                        repo_root=self._repo_root,
                        model_id=self._leaf_model_id,
                        cycle_substrate_context=context,
                        candidate_simulation_handoff=(
                            candidate_simulation_handoffs_by_node or {}
                        ).get(node_ref),
                        candidate_simulation_currentness_resolver=(
                            candidate_simulation_currentness_resolvers_by_node or {}
                        ).get(node_ref),
                        candidate_simulation_context_resolver=(
                            candidate_simulation_context_resolvers_by_node or {}
                        ).get(node_ref),
                        promotion_runtime=self._promotion_runtime,
                        artifact_store=self._artifact_store,
                    )
                else:
                    controller = self._cycle_controller_factory(node_ref, problem)
                if not isinstance(controller, GenerationCycleController):
                    raise RecursiveGenerationCycleError("recursive_leaf_controller_not_canonical")
                if (
                    self._authority_scope == "contract_testing"
                    and execution_intents_by_node is None
                    and (evaluation_contexts_by_node or {}).get(node_ref) is None
                ):
                    from polisyos.runtime.quality.promotion_sequence import (
                        CanonicalN9PromotionPort,
                    )

                    if (
                        type(self) is not RecursiveGenerationCycleController
                        or type(controller) is not GenerationCycleController
                        or controller._authority_scope != "production"
                        or controller._promotion_runtime is not None
                        or type(controller._promotion_port) is not CanonicalN9PromotionPort
                        or "run" in vars(controller)
                        or "_promote_completed_generation" in vars(controller)
                        or "deployment_identity_refusal" in vars(controller._promotion_port)
                    ):
                        raise RecursiveGenerationCycleError(
                            "recursive_contract_testing_candidate_n9_owner_not_established"
                        )
                if context is not None and controller._cycle_substrate_context is not context:
                    raise RecursiveGenerationCycleError(
                        "recursive_contract_testing_context_not_consumed"
                    )
                cycle_run = await controller.run(
                    problem,
                    budget_state=budget_state,
                    min_cycles=recursive_budget.min_cycles_per_leaf,
                    max_cycles=recursive_budget.max_cycles_per_leaf,
                    stable_design_problem_ref=problem_ref,
                )
                if cycle_run.design_problem_ref != problem_ref:
                    raise RecursiveGenerationCycleError("recursive_leaf_problem_binding_mismatch")
                # N6 currentness governs authority, not whether a computed leaf
                # can continue as candidate input to recursion. Protected
                # authority consumers keep the strict validator at their owner.
                issues = validate_generation_cycle_candidate_run(cycle_run)
                if issues:
                    raise RecursiveGenerationCycleError(
                        "recursive_leaf_generation_cycle_invalid",
                        str(issues),
                    )
                result = RecursiveCycleNode(
                    node_ref=node_ref,
                    parent_ref=parent_by_node.get(node_ref),
                    depth=depths[node_ref],
                    design_problem_ref=problem_ref,
                    cycle_run=cycle_run,
                    terminal=_leaf_terminal(cycle_run),
                )
                node_results[node_ref] = result
                if (
                    result.terminal.kind is SearchTerminalKind.BUDGET_EXHAUSTED
                    and node_ref != recursive_graph.root_design_ref
                ):
                    # Preserve this canonical N6 run, then unwind before the
                    # router can visit a sibling or start ancestor composition.
                    raise _RecursiveBudgetStopError(node_ref)
                return result

            routed_children_list: list[RecursiveCycleNode] = []
            for child_index, child_ref in enumerate(child_refs):
                try:
                    routed_child = await route(child_ref)
                except _RecursiveBudgetStopError as stop:
                    frontier_node_refs = (
                        *stop.frontier_node_refs,
                        *child_refs[child_index + 1 :],
                    )
                    raise _RecursiveBudgetStopError(
                        stop.budget_stop_node_ref,
                        frontier_node_refs,
                    ) from None
                routed_children_list.append(routed_child)
            routed_children = tuple(routed_children_list)
            if len(routed_children) != 1:
                request = (joint_simulation_requests_by_node or {}).get(node_ref)
                subdesigns = (subdesign_contracts_by_node or {}).get(node_ref)
                if request is None or request.coupling_graph is None:
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        terminal=_blocked_parent_terminal("observed_coupling_evidence_missing"),
                    )
                    node_results[node_ref] = result
                    return result
                if subdesigns is None or len(subdesigns) != len(child_refs):
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        terminal=_blocked_parent_terminal("subdesign_contract_denominator_missing"),
                    )
                    node_results[node_ref] = result
                    return result
                binding_issue = _branch_binding_issue(
                    node_ref=node_ref,
                    problem_ref=problem_ref,
                    problem=problem,
                    child_refs=child_refs,
                    routed_children=routed_children,
                    request=request,
                    subdesigns=subdesigns,
                )
                if binding_issue is not None:
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        terminal=_blocked_parent_terminal(binding_issue),
                    )
                    node_results[node_ref] = result
                    return result
                if self._artifact_store is None:
                    raise RecursiveGenerationCycleError(
                        "recursive_n5_runtime_store_not_established",
                        "The parent N5 run cannot start without its runtime-owned result store.",
                    )
                joint_simulation = self._joint_simulation_controller.run(request)
                try:
                    joint_simulation_ref = persist_joint_simulation_result(
                        joint_simulation,
                        store=self._artifact_store,
                    )
                except GenerationCycleError as exc:
                    raise RecursiveGenerationCycleError(
                        "recursive_n5_result_persistence_failed",
                        str(exc),
                    ) from exc
                if _joint_simulation_is_unsupported(joint_simulation):
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        joint_simulation=joint_simulation,
                        joint_simulation_ref=joint_simulation_ref,
                        terminal=_blocked_parent_terminal("unsupported_coupling_gated"),
                    )
                    node_results[node_ref] = result
                    return result
                certificate = compose_subdesigns(
                    subdesigns=subdesigns,
                    claims=_composition_claims_for_problem(
                        problem,
                        target_policy_program_ref=node_ref,
                    ),
                    graph=request.coupling_graph,
                    parent_workspace_id=node_ref,
                    rule_version_ref=recursive_graph.rule_version_ref,
                )
                result = RecursiveCycleNode(
                    node_ref=node_ref,
                    parent_ref=parent_by_node.get(node_ref),
                    depth=depths[node_ref],
                    child_refs=child_refs,
                    design_problem_ref=problem_ref,
                    joint_simulation=joint_simulation,
                    joint_simulation_ref=joint_simulation_ref,
                    composition_certificate=certificate,
                    terminal=_fold_composed_terminal(
                        children=routed_children,
                        joint_simulation=joint_simulation,
                        certificate=certificate,
                    ),
                )
                node_results[node_ref] = result
                return result
            result = RecursiveCycleNode(
                node_ref=node_ref,
                parent_ref=parent_by_node.get(node_ref),
                depth=depths[node_ref],
                child_refs=child_refs,
                design_problem_ref=problem_ref,
                terminal=_fold_unary_terminal(routed_children[0]),
            )
            node_results[node_ref] = result
            return result

        try:
            root = await route(recursive_graph.root_design_ref)
        except _RecursiveBudgetStopError as stop:
            return _build_budget_stopped_recursive_run_v2(
                recursive_graph=recursive_graph,
                problems_by_node=problems_by_node,
                completed_nodes_by_ref=node_results,
                children_by_node=children,
                parent_by_node=parent_by_node,
                depths=depths,
                recursive_budget=recursive_budget,
                budget_stop_node_ref=stop.budget_stop_node_ref,
                frontier_node_refs=stop.frontier_node_refs,
                authority_scope=self._authority_scope,
            )
        ordered_nodes = tuple(node_results[node_ref] for node_ref in node_refs)
        node_payloads = tuple(node.model_dump(mode="json") for node in ordered_nodes)
        payload = {
            "schema_version": RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
            "run_id": f"recursive:{recursive_graph.graph_id}",
            "controller_ref": RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF,
            "authority_scope": self._authority_scope,
            "recursive_graph": recursive_graph.model_dump(mode="json"),
            "recursive_graph_ref": recursive_graph.graph_ref,
            "recursive_graph_content_hash": gy_content_hash(
                recursive_graph.model_dump(mode="json")
            ),
            "root_node_ref": recursive_graph.root_design_ref,
            "root_design_problem_ref": _problem_ref(
                problems_by_node[recursive_graph.root_design_ref]
            ),
            "recursive_budget": recursive_budget.model_dump(mode="json"),
            "observed_max_depth": max(depths.values()),
            "nodes": node_payloads,
            "terminal": root.terminal.model_dump(mode="json"),
        }
        return RecursiveGenerationCycleRun.model_validate(
            {
                **payload,
                # Keep the already-validated leaf objects on the live route.
                # Their SimulationPortObservation carries the exact owner WMR
                # as an internal provenance handle excluded from JSON output.
                "nodes": ordered_nodes,
                "content_hash": gy_content_hash(payload),
            }
        )


__all__ = [
    "RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF",
    "RECURSIVE_GENERATION_CYCLE_PARTIAL_V2_SCHEMA_VERSION",
    "RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION",
    "DepthNStrangleReceipt",
    "RecursiveCycleBudget",
    "RecursiveCycleNode",
    "RecursiveCyclePendingNode",
    "RecursiveGenerationCycleController",
    "RecursiveGenerationCycleError",
    "RecursiveGenerationCyclePartialRunV2",
    "RecursiveGenerationCycleRun",
    "build_default_recursive_generation_cycle_controller",
    "recompute_depth_n_strangle_receipt",
]
