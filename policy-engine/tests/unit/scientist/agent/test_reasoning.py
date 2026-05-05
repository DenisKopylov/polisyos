from __future__ import annotations

from polisyos.scientist.agent.reasoning import (
    LATSAgentSearch,
    LATSConfig,
    ReasoningAction,
    ReasoningNode,
    ReasoningPolicyGate,
    ReasoningStatus,
    TreeOfThoughtConfig,
    TreeOfThoughtPlanner,
)


def _gate() -> ReasoningPolicyGate:
    return ReasoningPolicyGate(enabled=True, offline_validation_ref="sha256:" + "a" * 64)


def test_tree_of_thought_is_offline_gated_by_default() -> None:
    report = TreeOfThoughtPlanner().run(
        objective="choose policy",
        expand=lambda _node: [ReasoningAction(action_id="a", description="A")],
        evaluate=lambda _node: 1.0,
    )

    assert report.status == ReasoningStatus.OFFLINE_GATED
    assert report.gate["allowed"] is False
    assert "tree_of_thought_requires_offline_validation" in report.warnings


def test_tree_of_thought_selects_best_scored_path() -> None:
    def expand(node: ReasoningNode) -> list[ReasoningAction]:
        if node.depth == 0:
            return [
                ReasoningAction(action_id="safe", description="Safe", expected_value=0.4),
                ReasoningAction(action_id="bold", description="Bold", expected_value=0.7),
            ]
        if node.action and node.action.action_id == "bold":
            return [ReasoningAction(action_id="audit", description="Audit", expected_value=0.9)]
        return [ReasoningAction(action_id="wait", description="Wait", expected_value=0.2)]

    def evaluate(node: ReasoningNode) -> float:
        path_bonus = {"safe": 0.4, "bold": 0.7, "audit": 1.0, "wait": 0.1}
        return path_bonus[node.action.action_id] if node.action else 0.0

    report = TreeOfThoughtPlanner(
        config=TreeOfThoughtConfig(max_depth=2, beam_width=2, branching_factor=2),
        gate=_gate(),
    ).run(objective="choose policy", expand=expand, evaluate=evaluate)

    assert report.status == ReasoningStatus.COMPLETED
    assert report.best_action_path == ["bold", "audit"]
    assert report.best_score == 1.0
    assert report.metrics["node_count"] >= 4


def test_lats_mcts_prefers_high_value_action() -> None:
    actions = [
        ReasoningAction(action_id="low", description="Low", expected_value=0.1),
        ReasoningAction(action_id="high", description="High", expected_value=0.9),
    ]

    def legal_actions(node: ReasoningNode) -> list[ReasoningAction]:
        if node.depth >= 2:
            return []
        return actions

    def transition(node: ReasoningNode, action: ReasoningAction) -> dict[str, str]:
        return {"objective": f"{node.objective}/{action.action_id}"}

    def evaluate(node: ReasoningNode) -> float:
        path = node.objective
        return path.count("high") - 0.1 * path.count("low")

    report = LATSAgentSearch(
        config=LATSConfig(max_iterations=20, max_depth=2, branching_factor=2),
        gate=_gate(),
    ).run(
        objective="root",
        legal_actions=legal_actions,
        transition=transition,
        evaluate=evaluate,
    )

    assert report.status == ReasoningStatus.COMPLETED
    assert "high" in report.best_action_path
    assert report.metrics["root_visits"] == 20
