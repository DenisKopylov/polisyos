from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import flow_nodes
from .state import ExperimentState


@dataclass(frozen=True, slots=True)
class LegacyWorkflowApp:
    """Small legacy-compatible workflow facade with `.invoke(state)`."""

    def invoke(self, state: Mapping[str, Any]) -> ExperimentState:
        current: ExperimentState = dict(state)

        current = flow_nodes.pi_decompose_node(current)

        if current.get("ir") is None:
            current = flow_nodes.drafter_node(current)
            current = flow_nodes.formalize_node(current)

        current = flow_nodes.critic_review_node(current)
        current = flow_nodes.validate_ir_node(current)

        if str(current.get("stop_after_phase", "")).lower() == "frame":
            return flow_nodes.pack_decision_node(current)

        if not current.get("pruned"):
            current = flow_nodes.compile_data_views_node(current)
            current = flow_nodes.compile_model_node(current)
            current = flow_nodes.train_agents_node(current)
            current = flow_nodes.run_sim_node(current)
            current = flow_nodes.analyze_node(current)
            current = flow_nodes.governor_node(current)

        return flow_nodes.pack_decision_node(current)


def build_workflow() -> LegacyWorkflowApp:
    return LegacyWorkflowApp()


__all__ = ["LegacyWorkflowApp", "build_workflow"]
