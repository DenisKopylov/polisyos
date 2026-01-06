# src/orchestrator/workflow.py
from langgraph.graph import StateGraph, END
from src.orchestrator.state import ExperimentState
from src.orchestrator.nodes import simulator_node, governor_node

def route_governor(state: ExperimentState):
    """Решает, куда идти после Губернатора."""
    verdict = state["feedback"]["verdict"]
    if verdict == "APPROVE":
        return END
    elif verdict == "REJECT":
        # В полноценной системе здесь был бы переход к "Drafter" для исправления
        # Для MVP просто заканчиваем с ошибкой
        return END
    return END

def build_workflow():
    workflow = StateGraph(ExperimentState)

    # Добавляем узлы
    workflow.add_node("simulator", simulator_node)
    workflow.add_node("governor", governor_node)

    # Связи
    workflow.set_entry_point("simulator")
    workflow.add_edge("simulator", "governor")

    # Условный переход
    workflow.add_conditional_edges(
        "governor",
        route_governor
    )

    return workflow.compile()
