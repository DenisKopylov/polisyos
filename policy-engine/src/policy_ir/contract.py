from datetime import datetime
from typing import Dict, List, Literal, Optional, Union, Any

from pydantic import BaseModel, Field, model_validator, field_validator

from src.policy_ir.types import (
    EntityType,
    OptimizationDirection,
    SelectorOperator,
    TimeFrequency,
    TranslatableString,
)


# --- 2.1 Entity (Плоская структура) ---
class PolicyEntity(BaseModel):
    """
    Сущность в плоском списке (Adjacency List).
    Иерархия строится через parent_id.
    """
    id: str = Field(..., pattern=r"^[a-z0-9_]+$", description="Unique slug (snake_case)")
    entity_type: EntityType
    name: TranslatableString
    parent_id: Optional[str] = Field(None, description="ID родителя. Должен существовать в списке.")

    # Динамическое состояние
    state_variables: Dict[str, Union[float, int, bool, str]] = Field(
        default_factory=dict, description="Initial state: {'balance': 1000.0}"
    )


# --- 2.2 Target Selector (AST) ---
class SelectorPredicate(BaseModel):
    """Атомарное условие: field op value"""
    field: str = Field(..., description="Атрибут сущности, напр. 'sector'")
    operator: SelectorOperator
    value: Union[str, int, float, bool, List[str], List[int]]

class TargetSelector(BaseModel):
    """
    Структурированный фильтр целей.
    Заменяет строку "sector == 'IT'".
    Поддерживает логику AND/OR.
    """
    logic: Literal["AND", "OR"] = Field("AND", description="Логический оператор для списка условий")
    predicates: List[SelectorPredicate] = Field(..., min_length=1)

    def to_human_readable(self) -> str:
        """Для удобства отладки/лога."""
        parts = [f"{p.field} {p.operator.value} {p.value}" for p in self.predicates]
        joiner = " AND " if self.logic == "AND" else " OR "
        return f"({joiner.join(parts)})"


# --- 2.3 Metric / Objective (Цель) ---
class Objective(BaseModel):
    metric_name: str = Field(
        ..., description="Name of the metric to optimize (e.g. 'gdp', 'unemployment')"
    )
    direction: OptimizationDirection
    threshold: Optional[float] = Field(
        None, description="Target value boundary if direction is RANGE"
    )
    priority_weight: float = Field(default=1.0, ge=0.0, le=10.0)


# --- 2.3 Intervention ---
class Intervention(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    name: TranslatableString

    # Безопасный AST селектор
    target_selector: TargetSelector

    mechanism_type: str = Field(..., description="Ссылка на механизм в Foundry")
    parameters: Dict[str, Any]
    constraints: Dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mechanism_params(self) -> "Intervention":
        # Пример простейшей валидации (в будущем здесь будет связь с Registry)
        if self.mechanism_type == "tax_subsidy" and "rate" not in self.parameters:
             raise ValueError("Mechanism 'tax_subsidy' requires 'rate' parameter")
        return self


# --- Корневой документ (Root) ---
class SimulationParameters(BaseModel):
    """Технические параметры симуляции."""

    scope_years: int = Field(..., ge=1, le=50)
    time_frequency: TimeFrequency = TimeFrequency.MONTH
    start_date: str = "2024-01-01"
    random_seed: int = 42


class PolicyRequestIR(BaseModel):
    """
    Корневой артефакт.
    Содержит версионирование и глобальную валидацию графа.
    """
    project_name: TranslatableString

    # Версионирование контракта (MUST have)
    schema_version: str = Field("1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    simulation_params: SimulationParameters

    entities: List[PolicyEntity]
    interventions: List[Intervention]
    objectives: List[Objective]

    global_constraints: Dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_topology(self) -> "PolicyRequestIR":
        """
        Проверка графа сущностей:
        1. Все parent_id существуют.
        2. Нет циклов (A -> B -> A).
        """
        entity_ids = {e.id for e in self.entities}

        # 1. Проверка существования родителей
        adjacency = {e.id: [] for e in self.entities}
        for e in self.entities:
            if e.parent_id:
                if e.parent_id not in entity_ids:
                    raise ValueError(f"Entity '{e.id}' refers to unknown parent '{e.parent_id}'")
                adjacency[e.parent_id].append(e.id) # Строим граф сверху вниз

        # 2. Проверка на циклы (DFS)
        visited = set()
        recursion_stack = set()

        def detect_cycle(node_id):
            visited.add(node_id)
            recursion_stack.add(node_id)

            for neighbor in adjacency[node_id]:
                if neighbor not in visited:
                    if detect_cycle(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    return True

            recursion_stack.remove(node_id)
            return False

        for e in self.entities:
            if e.id not in visited:
                if detect_cycle(e.id):
                    raise ValueError(f"Cycle detected in entity hierarchy involving '{e.id}'")

        return self
