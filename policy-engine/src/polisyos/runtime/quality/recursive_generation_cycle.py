"""Thin depth-N router over canonical recursion and generation-cycle owners."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import (
    CompositionCertificate,
    SearchTerminalKind,
    SearchTerminalState,
    SubDesignContract,
    gy_content_hash,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    RecursiveDesignGraph,
    compose_subdesigns,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    GenerationCycleRun,
    generation_cycle_terminal_state,
    validate_generation_cycle_run,
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
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from polisyos.scientist import BudgetState

RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION = (
    "policyos.runtime.recursive_generation_cycle.v1"
)
RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF = (
    "polisyos.runtime.quality.recursive_generation_cycle."
    "RecursiveGenerationCycleController"
)
_LEGACY_RECURSIVE_FIXTURE_SYMBOLS = frozenset(
    {
        "run_recursive_case",
        "coupling_graph_for_subdesigns",
        "_recursive_case_child_fixtures",
    }
)
_DEFAULT_RECURSIVE_ROUTE_SYMBOL = "build_default_recursive_generation_cycle_controller"


def _joint_simulation_is_unsupported(result: JointSimulationResult) -> bool:
    """Return whether N5 emitted no supported trajectory for composition."""

    return (
        result.receipt.calibration_status in {"unsupported_coupling_gated", "no_run"}
        or not result.trajectories
        or any(decision.decision != "selected" for decision in result.engine_decisions)
    )


class RecursiveGenerationCycleError(ValueError):
    """Fail-closed depth-N routing error."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


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


class RecursiveCycleNode(_StrictModel):
    """One replay-visible node routed through existing depth owners."""

    node_ref: str = Field(min_length=1)
    parent_ref: str | None = None
    depth: int = Field(ge=0)
    child_refs: tuple[str, ...] = ()
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cycle_run: GenerationCycleRun | None = None
    joint_simulation: JointSimulationResult | None = None
    composition_certificate: CompositionCertificate | None = None
    terminal: SearchTerminalState

    @model_validator(mode="after")
    def _only_leaves_run_n6(self) -> RecursiveCycleNode:
        if self.child_refs and self.cycle_run is not None:
            raise ValueError("recursive_internal_node_cannot_run_leaf_cycle")
        if not self.child_refs and self.cycle_run is None:
            raise ValueError("recursive_leaf_requires_generation_cycle")
        if not self.child_refs and (
            self.joint_simulation is not None
            or self.composition_certificate is not None
        ):
            raise ValueError("recursive_leaf_cannot_mint_parent_evidence")
        if len(self.child_refs) < 2 and (
            self.joint_simulation is not None
            or self.composition_certificate is not None
        ):
            raise ValueError("recursive_unary_parent_cannot_mint_coupled_evidence")
        if (
            self.composition_certificate is not None
            and self.joint_simulation is None
        ):
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
            or {
                (node.node_ref, child_ref)
                for node in self.nodes
                for child_ref in node.child_refs
            }
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
            elif (
                node.joint_simulation is not None
                and node.composition_certificate is not None
            ):
                expected_terminal = _fold_composed_terminal(
                    children=routed_children,
                    joint_simulation=node.joint_simulation,
                    certificate=node.composition_certificate,
                )
            elif node.joint_simulation is not None:
                expected_terminal = _blocked_parent_terminal(
                    "unsupported_coupling_gated"
                )
            else:
                expected_terminal = node.terminal
            if node.terminal != expected_terminal:
                raise ValueError("recursive_run_parent_terminal_not_owner_derived")
        payload = self.model_dump(
            mode="json",
            exclude={"content_hash", "leaf_nodes"},
        )
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("recursive_generation_cycle_content_hash_mismatch")
        return self


CycleControllerFactory = Callable[[str, DesignProblem], GenerationCycleController]


class DepthNStrangleReceipt(_StrictModel):
    """Live caller census proving the fixed GY-G recursive fixture is gone."""

    status: Literal["strangled", "drift"]
    default_controller: str
    predecessor_symbols: tuple[str, ...]
    production_fixture_callers: tuple[str, ...]
    production_default_routes: tuple[str, ...]
    verified_by: str = (
        "polisyos.runtime.quality.recursive_generation_cycle."
        "recompute_depth_n_strangle_receipt"
    )


def recompute_depth_n_strangle_receipt(
    repo_root: Path | None = None,
) -> DepthNStrangleReceipt:
    """Census executable source for surviving GY-G fixture definitions or calls."""

    root = (repo_root or Path.cwd()).resolve()
    source_root = root / "src/polisyos"
    callers: list[str] = []
    default_routes: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            callers.append(f"{path.relative_to(root)}:parse_error:{type(exc).__name__}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name in _LEGACY_RECURSIVE_FIXTURE_SYMBOLS
            ):
                callers.append(
                    f"{path.relative_to(root)}:{node.lineno}:definition:{node.name}"
                )
            if not isinstance(node, ast.Call):
                continue
            symbol = None
            if isinstance(node.func, ast.Name):
                symbol = node.func.id
            elif isinstance(node.func, ast.Attribute):
                symbol = node.func.attr
            if symbol in _LEGACY_RECURSIVE_FIXTURE_SYMBOLS:
                callers.append(
                    f"{path.relative_to(root)}:{node.lineno}:call:{symbol}"
                )
            if symbol == _DEFAULT_RECURSIVE_ROUTE_SYMBOL:
                default_routes.append(
                    f"{path.relative_to(root)}:{node.lineno}:call:{symbol}"
                )
    ordered = tuple(sorted(set(callers)))
    routes = tuple(sorted(set(default_routes)))
    return DepthNStrangleReceipt(
        status="strangled" if not ordered and routes else "drift",
        default_controller=(
            RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF if routes else "unresolved"
        ),
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
                unsupported_simulation
                or SearchTerminalKind.RECURSIVE_BLOCKED in kinds
            ),
            poor_recall=SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED in kinds,
            human_decision_required=SearchTerminalKind.HUMAN_DECISION_REQUIRED in kinds,
            acquisition_required=SearchTerminalKind.ACQUISITION_REQUIRED in kinds,
            budget_exhausted_kind=(
                "recursive"
                if SearchTerminalKind.BUDGET_EXHAUSTED in kinds
                else None
            ),
            frontier_stable=SearchTerminalKind.FRONTIER_STABLE in kinds,
            positive_terminal=positive_terminal,
        )
    )
    blockers = [
        blocker
        for child in children
        for blocker in child.terminal.blocking_obligations
    ]
    blockers.extend(
        obligation.obligation_id
        for obligation in certificate.unresolved_obligations
    )
    blockers.extend(joint_simulation.feedback_classification.support_blockers)
    acquisition_children = tuple(
        child
        for child in children
        if child.terminal.kind is SearchTerminalKind.ACQUISITION_REQUIRED
    )
    costed_plan = None
    data_need_spec = None
    if (
        decision.kind is SearchTerminalKind.ACQUISITION_REQUIRED
        and len(acquisition_children) == 1
    ):
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
    if len(graph.module_refs) != len(set(graph.module_refs)) or set(
        graph.module_refs
    ) != set(child_refs):
        return "recursive_coupling_child_denominator_mismatch"
    if any(
        edge.source_module_ref not in child_refs
        or edge.target_module_ref not in child_refs
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
    repo_root: Path | None = None,
    model_id: str | None = None,
) -> RecursiveGenerationCycleController:
    """Build the production router whose leaves are canonical N6 controllers."""

    return RecursiveGenerationCycleController(
        repo_root=repo_root,
        model_id=model_id,
    )


class RecursiveGenerationCycleController:
    """Route a recursive design graph and delegate every engine decision."""

    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        model_id: str | None = None,
    ) -> None:
        self._repo_root = (repo_root or Path.cwd()).resolve()
        self._leaf_model_id = model_id
        self._cycle_controller_factory: CycleControllerFactory | None = None
        self._authority_scope: Literal["production", "contract_testing"] = "production"
        self._joint_simulation_controller = JointSimulationHorizonController()

    @classmethod
    def for_contract_testing(
        cls,
        *,
        cycle_controller_factory: CycleControllerFactory,
        repo_root: Path | None = None,
    ) -> RecursiveGenerationCycleController:
        """Build a visibly non-production router over canonical scripted N6 owners."""

        controller = cls(repo_root=repo_root)
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
        joint_simulation_requests_by_node: Mapping[
            str, JointSimulationRequest
        ] | None = None,
        subdesign_contracts_by_node: Mapping[
            str, tuple[SubDesignContract, ...]
        ] | None = None,
        cycle_substrate_contexts_by_node: Mapping[
            str, CycleSubstrateContext
        ] | None = None,
    ) -> RecursiveGenerationCycleRun:
        """Run N6 at leaves and conservatively route terminals toward the root."""

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
                    controller = GenerationCycleController(
                        repo_root=self._repo_root,
                        model_id=self._leaf_model_id,
                        cycle_substrate_context=context,
                    )
                else:
                    controller = self._cycle_controller_factory(node_ref, problem)
                if not isinstance(controller, GenerationCycleController):
                    raise RecursiveGenerationCycleError(
                        "recursive_leaf_controller_not_canonical"
                    )
                if (
                    context is not None
                    and controller._cycle_substrate_context is not context
                ):
                    raise RecursiveGenerationCycleError(
                        "recursive_contract_testing_context_not_consumed"
                    )
                cycle_run = await controller.run(
                    problem,
                    budget_state=budget_state,
                    min_cycles=recursive_budget.min_cycles_per_leaf,
                    max_cycles=recursive_budget.max_cycles_per_leaf,
                )
                if cycle_run.design_problem_ref != problem_ref:
                    raise RecursiveGenerationCycleError(
                        "recursive_leaf_problem_binding_mismatch"
                    )
                issues = validate_generation_cycle_run(cycle_run)
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
                return result

            routed_children = tuple([await route(child_ref) for child_ref in child_refs])
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
                        terminal=_blocked_parent_terminal(
                            "observed_coupling_evidence_missing"
                        ),
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
                        terminal=_blocked_parent_terminal(
                            "subdesign_contract_denominator_missing"
                        ),
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
                joint_simulation = self._joint_simulation_controller.run(request)
                if _joint_simulation_is_unsupported(joint_simulation):
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        joint_simulation=joint_simulation,
                        terminal=_blocked_parent_terminal(
                            "unsupported_coupling_gated"
                        ),
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

        root = await route(recursive_graph.root_design_ref)
        ordered_nodes = tuple(node_results[node_ref] for node_ref in node_refs)
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
            "nodes": tuple(node.model_dump(mode="json") for node in ordered_nodes),
            "terminal": root.terminal.model_dump(mode="json"),
        }
        return RecursiveGenerationCycleRun.model_validate(
            {**payload, "content_hash": gy_content_hash(payload)}
        )


__all__ = [
    "RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF",
    "RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION",
    "DepthNStrangleReceipt",
    "RecursiveCycleBudget",
    "RecursiveCycleNode",
    "RecursiveGenerationCycleController",
    "RecursiveGenerationCycleError",
    "RecursiveGenerationCycleRun",
    "build_default_recursive_generation_cycle_controller",
    "recompute_depth_n_strangle_receipt",
]
