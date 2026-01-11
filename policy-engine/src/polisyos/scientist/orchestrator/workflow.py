# polisyos/orchestrator/workflow.py
from langgraph.graph import END, StateGraph

from polisyos.scientist.kernel import Phase, advance_phase
from polisyos.scientist.orchestrator.flow_nodes import (
    analyze_node,
    compile_data_views_node,
    compile_model_node,
    draft_ir_node,
    governor_node,
    pack_decision_node,
    repair_ir_node,
    run_sim_node,
    validate_ir_node,
)
from polisyos.scientist.orchestrator.state import ExperimentState


def _route_after_validate(state: ExperimentState) -> str:
    if state.get("pruned"):
        return "pack_decision"
    feedback = state.get("feedback")
    if not feedback:
        return "compile_data_views"
    verdict = feedback.get("verdict")
    if verdict == "NEEDS_REVISION":
        return "repair_ir"
    if verdict == "REJECT":
        return "pack_decision"
    return "compile_data_views"


def _with_phase(phase: Phase, node_fn):
    def _wrapped(state: ExperimentState):
        state = advance_phase(state, phase)
        return node_fn(state)

    return _wrapped


def build_workflow():
    workflow = StateGraph(ExperimentState)

    workflow.add_node("draft_ir", _with_phase(Phase.FRAME, draft_ir_node))
    workflow.add_node("validate_ir", _with_phase(Phase.FRAME, validate_ir_node))
    workflow.add_node("repair_ir", _with_phase(Phase.FRAME, repair_ir_node))
    workflow.add_node("compile_data_views", _with_phase(Phase.PLAN, compile_data_views_node))
    workflow.add_node("compile_model", _with_phase(Phase.EXECUTE, compile_model_node))
    workflow.add_node("run_sim", _with_phase(Phase.EXECUTE, run_sim_node))
    workflow.add_node("analyze", _with_phase(Phase.EXECUTE, analyze_node))
    workflow.add_node("governor", _with_phase(Phase.POSTFLIGHT_GOV, governor_node))
    workflow.add_node("pack_decision", _with_phase(Phase.PUBLISH, pack_decision_node))

    workflow.set_entry_point("draft_ir")
    workflow.add_edge("draft_ir", "validate_ir")
    workflow.add_conditional_edges("validate_ir", _route_after_validate)
    workflow.add_edge("repair_ir", "validate_ir")
    workflow.add_edge("compile_data_views", "compile_model")
    workflow.add_edge("compile_model", "run_sim")
    workflow.add_edge("run_sim", "analyze")
    workflow.add_edge("analyze", "governor")
    workflow.add_edge("governor", "pack_decision")
    workflow.add_edge("pack_decision", END)

    return workflow.compile()
