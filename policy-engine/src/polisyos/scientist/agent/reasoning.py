"""Offline-gated tree reasoning policies for Scientist agent search.

The implementations in this module are intentionally dependency-light and
deterministic. They provide auditable Tree-of-Thought and LATS/MCTS-style
search traces without enabling those policies by default at runtime.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

__all__ = [
    "LATSAgentSearch",
    "LATSConfig",
    "ReasoningAction",
    "ReasoningNode",
    "ReasoningPolicyGate",
    "ReasoningSearchReport",
    "ReasoningStatus",
    "TreeOfThoughtConfig",
    "TreeOfThoughtPlanner",
]


class ReasoningStatus(StrEnum):
    """Execution status for offline-gated reasoning policies."""

    OFFLINE_GATED = "offline_gated"
    COMPLETED = "completed"
    NO_ACTIONS = "no_actions"


class ReasoningPolicyGate(BaseModel):
    """Feature gate that prevents tree reasoning from becoming default-on silently."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    offline_validation_ref: str | None = None
    default_enable_requested: bool = False
    allowed_modes: set[str] = Field(default_factory=lambda: {"tree_of_thought", "lats_mcts"})
    rationale: str = (
        "Tree reasoning is experimental until an offline trajectory evaluation "
        "artifact explicitly approves the policy."
    )

    def allows(self, mode: str) -> bool:
        """Return True only when the mode is enabled and backed by offline validation."""

        return bool(self.enabled and self.offline_validation_ref and mode in self.allowed_modes)

    def status_for(self, mode: str) -> dict[str, Any]:
        """Machine-readable gate status for reports and dashboards."""

        return {
            "mode": mode,
            "enabled": self.enabled,
            "allowed": self.allows(mode),
            "offline_validation_ref": self.offline_validation_ref,
            "default_enable_requested": self.default_enable_requested,
            "default_enable_eligible": self.allows(mode) and not self.default_enable_requested,
            "rationale": self.rationale,
        }


class ReasoningAction(BaseModel):
    """One candidate thought/action expansion."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    prior_score: float = 0.0
    expected_value: float = 0.0
    cost: float = Field(default=0.0, ge=0.0)
    risk: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def ordering_score(self) -> float:
        """Deterministic pre-evaluation ordering score."""

        return float(self.prior_score + self.expected_value - self.cost - self.risk)


class ReasoningNode(BaseModel):
    """One node in a tree reasoning trajectory."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    parent_id: str | None = None
    depth: int = Field(default=0, ge=0)
    objective: str = Field(default="", min_length=0)
    action: ReasoningAction | None = None
    score: float = 0.0
    visits: int = 0
    value_sum: float = 0.0
    state: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def value_mean(self) -> float:
        return 0.0 if self.visits <= 0 else self.value_sum / self.visits


class TreeOfThoughtConfig(BaseModel):
    """Beam-search controls for Tree-of-Thought reasoning."""

    model_config = ConfigDict(extra="forbid")

    max_depth: int = Field(default=3, ge=1, le=12)
    beam_width: int = Field(default=3, ge=1, le=32)
    branching_factor: int = Field(default=4, ge=1, le=64)
    min_score: float | None = None


class LATSConfig(BaseModel):
    """Controls for lightweight LATS / MCTS over agent actions."""

    model_config = ConfigDict(extra="forbid")

    max_iterations: int = Field(default=32, ge=1, le=4096)
    max_depth: int = Field(default=4, ge=1, le=32)
    exploration_weight: float = Field(default=1.41421356237, ge=0.0, le=10.0)
    branching_factor: int = Field(default=4, ge=1, le=64)


class ReasoningSearchReport(BaseModel):
    """Persistable trajectory report for tree reasoning experiments."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["tree_of_thought", "lats_mcts"]
    status: ReasoningStatus
    objective: str
    best_score: float | None = None
    best_node_id: str | None = None
    best_action_path: list[str] = Field(default_factory=list)
    nodes: list[ReasoningNode] = Field(default_factory=list)
    gate: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class TreeOfThoughtPlanner:
    """Deterministic beam-search Tree-of-Thought planner."""

    def __init__(
        self,
        *,
        config: TreeOfThoughtConfig | None = None,
        gate: ReasoningPolicyGate | None = None,
    ) -> None:
        self._config = config or TreeOfThoughtConfig()
        self._gate = gate or ReasoningPolicyGate()

    def run(
        self,
        *,
        objective: str,
        expand: Callable[[ReasoningNode], Sequence[ReasoningAction]],
        evaluate: Callable[[ReasoningNode], float],
    ) -> ReasoningSearchReport:
        """Run Tree-of-Thought beam search and return an auditable trace."""

        mode = "tree_of_thought"
        gate_status = self._gate.status_for(mode)
        if not gate_status["allowed"]:
            return ReasoningSearchReport(
                mode=mode,
                status=ReasoningStatus.OFFLINE_GATED,
                objective=objective,
                gate=gate_status,
                warnings=["tree_of_thought_requires_offline_validation"],
            )

        root = ReasoningNode(node_id="thought_0000", objective=objective, score=0.0)
        nodes: list[ReasoningNode] = [root]
        frontier: list[ReasoningNode] = [root]
        best = root

        for depth in range(1, self._config.max_depth + 1):
            candidates: list[ReasoningNode] = []
            for parent in frontier:
                actions = sorted(
                    expand(parent),
                    key=lambda item: (-item.ordering_score, item.action_id),
                )[: self._config.branching_factor]
                for action in actions:
                    child = ReasoningNode(
                        node_id=f"thought_{len(nodes) + len(candidates):04d}",
                        parent_id=parent.node_id,
                        depth=depth,
                        objective=parent.objective,
                        action=action,
                        state={**parent.state, "last_action": action.action_id},
                    )
                    score = _finite_score(evaluate(child))
                    if self._config.min_score is not None and score < self._config.min_score:
                        continue
                    child.score = score
                    candidates.append(child)
                    if score > best.score:
                        best = child
            if not candidates:
                break
            candidates.sort(key=lambda item: (-item.score, item.node_id))
            nodes.extend(candidates)
            frontier = candidates[: self._config.beam_width]

        status = ReasoningStatus.NO_ACTIONS if best is root else ReasoningStatus.COMPLETED
        return ReasoningSearchReport(
            mode=mode,
            status=status,
            objective=objective,
            best_score=best.score,
            best_node_id=best.node_id,
            best_action_path=_action_path(best.node_id, nodes),
            nodes=nodes,
            gate=gate_status,
            metrics={
                "node_count": len(nodes),
                "max_depth_reached": max((node.depth for node in nodes), default=0),
                "beam_width": self._config.beam_width,
            },
        )


class LATSAgentSearch:
    """Lightweight Language Agent Tree Search / MCTS over structured actions."""

    def __init__(
        self,
        *,
        config: LATSConfig | None = None,
        gate: ReasoningPolicyGate | None = None,
    ) -> None:
        self._config = config or LATSConfig()
        self._gate = gate or ReasoningPolicyGate()

    def run(
        self,
        *,
        objective: str,
        legal_actions: Callable[[ReasoningNode], Sequence[ReasoningAction]],
        transition: Callable[[ReasoningNode, ReasoningAction], Mapping[str, Any] | str],
        evaluate: Callable[[ReasoningNode], float],
    ) -> ReasoningSearchReport:
        """Run deterministic MCTS and return the selected action trajectory."""

        mode = "lats_mcts"
        gate_status = self._gate.status_for(mode)
        if not gate_status["allowed"]:
            return ReasoningSearchReport(
                mode=mode,
                status=ReasoningStatus.OFFLINE_GATED,
                objective=objective,
                gate=gate_status,
                warnings=["lats_mcts_requires_offline_validation"],
            )

        root = ReasoningNode(node_id="mcts_0000", objective=objective)
        nodes: list[ReasoningNode] = [root]
        by_parent: dict[str, list[str]] = {root.node_id: []}
        node_index: dict[str, ReasoningNode] = {root.node_id: root}

        for _ in range(self._config.max_iterations):
            leaf = self._select(root, by_parent, node_index)
            expanded = self._expand(
                leaf,
                legal_actions=legal_actions,
                transition=transition,
                nodes=nodes,
                by_parent=by_parent,
                node_index=node_index,
            )
            score = _finite_score(evaluate(expanded))
            self._backpropagate(expanded, score, node_index)

        best = max(
            nodes,
            key=lambda item: (
                item.value_mean if item.visits else item.score,
                item.visits,
                item.score,
                item.node_id,
            ),
        )
        return ReasoningSearchReport(
            mode=mode,
            status=ReasoningStatus.COMPLETED if best is not root else ReasoningStatus.NO_ACTIONS,
            objective=objective,
            best_score=best.value_mean if best.visits else best.score,
            best_node_id=best.node_id,
            best_action_path=_action_path(best.node_id, nodes),
            nodes=nodes,
            gate=gate_status,
            metrics={
                "node_count": len(nodes),
                "iterations": self._config.max_iterations,
                "root_visits": root.visits,
                "max_depth_reached": max((node.depth for node in nodes), default=0),
            },
        )

    def _select(
        self,
        root: ReasoningNode,
        by_parent: Mapping[str, list[str]],
        node_index: Mapping[str, ReasoningNode],
    ) -> ReasoningNode:
        node = root
        while node.depth < self._config.max_depth:
            children = [node_index[node_id] for node_id in by_parent.get(node.node_id, [])]
            if not children:
                return node
            unvisited = [child for child in children if child.visits <= 0]
            if unvisited:
                return sorted(unvisited, key=lambda item: item.node_id)[0]
            node = max(
                children,
                key=lambda child: (
                    child.value_mean
                    + self._config.exploration_weight
                    * math.sqrt(math.log(max(node.visits, 1)) / max(child.visits, 1)),
                    child.score,
                    child.node_id,
                ),
            )
        return node

    def _expand(
        self,
        leaf: ReasoningNode,
        *,
        legal_actions: Callable[[ReasoningNode], Sequence[ReasoningAction]],
        transition: Callable[[ReasoningNode, ReasoningAction], Mapping[str, Any] | str],
        nodes: list[ReasoningNode],
        by_parent: dict[str, list[str]],
        node_index: dict[str, ReasoningNode],
    ) -> ReasoningNode:
        if leaf.depth >= self._config.max_depth:
            return leaf
        expanded_ids = set(leaf.metadata.get("expanded_action_ids", []))
        actions = sorted(
            legal_actions(leaf),
            key=lambda item: (-item.ordering_score, item.action_id),
        )[: self._config.branching_factor]
        for action in actions:
            if action.action_id in expanded_ids:
                continue
            transition_state = transition(leaf, action)
            state = (
                {"objective": transition_state}
                if isinstance(transition_state, str)
                else dict(transition_state)
            )
            child = ReasoningNode(
                node_id=f"mcts_{len(nodes):04d}",
                parent_id=leaf.node_id,
                depth=leaf.depth + 1,
                objective=str(state.get("objective", leaf.objective)),
                action=action,
                state=state,
            )
            nodes.append(child)
            node_index[child.node_id] = child
            by_parent.setdefault(leaf.node_id, []).append(child.node_id)
            by_parent.setdefault(child.node_id, [])
            expanded_ids.add(action.action_id)
            leaf.metadata["expanded_action_ids"] = sorted(expanded_ids)
            return child
        return leaf

    def _backpropagate(
        self,
        node: ReasoningNode,
        score: float,
        node_index: Mapping[str, ReasoningNode],
    ) -> None:
        current: ReasoningNode | None = node
        while current is not None:
            current.visits += 1
            current.value_sum += score
            current.score = max(current.score, score)
            current = (
                None
                if current.parent_id is None
                else node_index.get(current.parent_id)
            )


def _action_path(node_id: str | None, nodes: Sequence[ReasoningNode]) -> list[str]:
    if node_id is None:
        return []
    index = {node.node_id: node for node in nodes}
    path: list[str] = []
    current = index.get(node_id)
    while current is not None:
        if current.action is not None:
            path.append(current.action.action_id)
        current = None if current.parent_id is None else index.get(current.parent_id)
    return list(reversed(path))


def _finite_score(value: float) -> float:
    score = float(value)
    if not math.isfinite(score):
        return -1.0e12
    return score
