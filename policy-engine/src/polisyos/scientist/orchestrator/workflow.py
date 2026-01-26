# polisyos/orchestrator/workflow.py
from langgraph.graph import END, StateGraph

from polisyos.scientist.kernel import Phase, advance_phase
from polisyos.scientist.agent.reflexion import ReflexionDecision
from polisyos.scientist.orchestrator.flow_nodes import (
    analyze_node,
    compile_data_views_node,
    compile_model_node,
    critic_review_node,
    drafter_node,
    formalize_node,
    governor_node,
    pack_decision_node,
    pi_decompose_node,
    reflexion_node,
    repair_ir_node,
    run_sim_node,
    train_agents_node,
    validate_ir_node,
)
from polisyos.scientist.orchestrator.state import ExperimentState


def _route_after_pi(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    if state.get("ir") is not None:
        return "validate_ir"
    if not state.get("problem_frame"):
        return "pack_decision"
    return "drafter"


def _route_after_drafter(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    if not state.get("draft_result"):
        return "pack_decision"
    return "formalize"


def _route_after_formalize(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    if not state.get("ir"):
        return "reflexion"
    return "critic_review"


def _route_after_critic(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    critique = state.get("critique_report")
    if not critique:
        return "validate_ir"
    verdict = critique.get("verdict") if isinstance(critique, dict) else getattr(critique, "verdict", None)
    if verdict == "APPROVE":
        return "validate_ir"
    if verdict in {"NEEDS_REVISION", "REJECT"}:
        return "reflexion"
    return "pack_decision"


def _route_after_validate(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    if state.get("stop_after_phase") == "frame":
        return "pack_decision"
    feedback = state.get("feedback")
    if not feedback:
        return "compile_data_views"
    verdict = feedback.get("verdict")
    if verdict == "NEEDS_REVISION":
        return "reflexion"
    if verdict == "REJECT":
        return "pack_decision"
    return "compile_data_views"


def _route_after_compile(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    feedback = state.get("feedback")
    if not feedback:
        return "train_agents"
    verdict = feedback.get("verdict")
    if verdict == "NEEDS_REVISION":
        return "reflexion"
    if verdict == "REJECT":
        return "pack_decision"
    return "train_agents"


def _route_after_run_sim(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    feedback = state.get("feedback")
    if not feedback:
        return "analyze"
    verdict = feedback.get("verdict")
    if verdict == "NEEDS_REVISION":
        # If simulation produced a *constraint/policy* verdict, we should stop and pack the decision
        # rather than immediately burning additional sim budget on auto-repair loops.
        # Runtime/infra failures remain eligible for repair.
        issues = feedback.get("issues") or []
        if any(isinstance(issue, dict) and issue.get("error_type") == "constraint" for issue in issues):
            return "pack_decision"
        return "reflexion"
    if verdict == "REJECT":
        return "pack_decision"
    return "analyze"


def _route_after_train_agents(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    feedback = state.get("feedback")
    if not feedback:
        return "run_sim"
    verdict = feedback.get("verdict")
    if verdict == "NEEDS_REVISION":
        return "reflexion"
    if verdict == "REJECT":
        return "pack_decision"
    return "run_sim"


def _route_after_governor(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    feedback = state.get("feedback")
    if not feedback:
        return "pack_decision"
    verdict = feedback.get("verdict")
    if verdict == "NEEDS_REVISION":
        issues = feedback.get("issues") or []
        has_fatal = any(
            isinstance(issue, dict) and issue.get("severity") == "fatal" for issue in issues
        )
        if not has_fatal:
            return "reflexion"
    return "pack_decision"


def _route_after_reflexion(state: ExperimentState) -> str:
    decision = state.get("reflexion_decision")
    if decision == ReflexionDecision.RETURN_TO_FORMALIZER.value:
        return "repair_ir"
    if decision == ReflexionDecision.RETURN_TO_DRAFTER.value:
        return "drafter"
    return "pack_decision"


def _with_phase(phase: Phase, node_fn):
    def _wrapped(state: ExperimentState):
        state = advance_phase(state, phase)
        return node_fn(state)

    return _wrapped


def build_workflow():
    workflow = StateGraph(ExperimentState)

    workflow.add_node("pi_decompose", _with_phase(Phase.FRAME, pi_decompose_node))
    workflow.add_node("drafter", _with_phase(Phase.FRAME, drafter_node))
    workflow.add_node("formalize", _with_phase(Phase.FRAME, formalize_node))
    workflow.add_node("critic_review", _with_phase(Phase.FRAME, critic_review_node))
    workflow.add_node("repair_ir", _with_phase(Phase.FRAME, repair_ir_node))
    workflow.add_node("reflexion", _with_phase(Phase.REFLEXION, reflexion_node))
    workflow.add_node("validate_ir", _with_phase(Phase.FRAME, validate_ir_node))
    workflow.add_node("compile_data_views", _with_phase(Phase.PLAN, compile_data_views_node))
    workflow.add_node("compile_model", _with_phase(Phase.EXECUTE, compile_model_node))
    workflow.add_node("train_agents", _with_phase(Phase.EXECUTE, train_agents_node))
    workflow.add_node("run_sim", _with_phase(Phase.EXECUTE, run_sim_node))
    workflow.add_node("analyze", _with_phase(Phase.EXECUTE, analyze_node))
    workflow.add_node("governor", _with_phase(Phase.POSTFLIGHT_GOV, governor_node))
    workflow.add_node("pack_decision", _with_phase(Phase.DECIDE, pack_decision_node))

    workflow.set_entry_point("pi_decompose")
    workflow.add_conditional_edges("pi_decompose", _route_after_pi)
    workflow.add_conditional_edges("drafter", _route_after_drafter)
    workflow.add_conditional_edges("formalize", _route_after_formalize)
    workflow.add_conditional_edges("critic_review", _route_after_critic)
    workflow.add_edge("repair_ir", "critic_review")
    workflow.add_conditional_edges("validate_ir", _route_after_validate)
    workflow.add_edge("compile_data_views", "compile_model")
    workflow.add_conditional_edges("compile_model", _route_after_compile)
    workflow.add_conditional_edges("train_agents", _route_after_train_agents)
    workflow.add_conditional_edges("run_sim", _route_after_run_sim)
    workflow.add_edge("analyze", "governor")
    workflow.add_conditional_edges("governor", _route_after_governor)
    workflow.add_conditional_edges("reflexion", _route_after_reflexion)
    workflow.add_edge("pack_decision", END)

    return workflow.compile()
