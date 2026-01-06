# src/orchestrator/workflow.py
from langgraph.graph import END, StateGraph

from src.agent.drafter import drafter_node  # <--- Импорт
from src.orchestrator.nodes import governor_node, simulator_node
from src.orchestrator.state import ExperimentState


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
    workflow.add_node("drafter", drafter_node)  # 1. Генерируем
    workflow.add_node("simulator", simulator_node)  # 2. Симулируем
    workflow.add_node("governor", governor_node)  # 3. Проверяем

    # Связи
    workflow.set_entry_point("drafter")  # Старт теперь здесь
    workflow.add_edge("drafter", "simulator")
    workflow.add_edge("simulator", "governor")

    # Условный переход
    workflow.add_conditional_edges("governor", route_governor)

    return workflow.compile()
