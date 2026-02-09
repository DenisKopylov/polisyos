from .decision_card import DecisionCard, IssuesSummary, KeyMetric
from .agent_factory import AgentStack, build_agent_stack, resolve_critic_agent

__all__ = [
    "AgentStack",
    "DecisionCard",
    "IssuesSummary",
    "KeyMetric",
    "build_agent_stack",
    "build_workflow",
    "LegacyWorkflowApp",
    "resolve_critic_agent",
]


def __getattr__(name: str):
    if name == "build_workflow":
        from .workflow import build_workflow

        return build_workflow
    if name == "LegacyWorkflowApp":
        from .workflow import LegacyWorkflowApp

        return LegacyWorkflowApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
