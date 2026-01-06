from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator

from src.policy_ir.types import EntityType, OptimizationDirection, TimeFrequency, TranslatableString


# --- 2.1 Entity (Сущность) ---
class PolicyEntity(BaseModel):
    """
    Абстракция любого актора или объекта.
    Поддерживает вложенность (Composite Pattern).
    """

    id: str = Field(..., pattern=r"^[a-z0-9_]+$", description="Unique slug identifier (snake_case)")
    entity_type: EntityType
    name: TranslatableString
    parent_id: Optional[str] = Field(None, description="ID родительской сущности (для иерархии)")

    # Динамическое состояние (начальные значения)
    state_variables: Dict[str, Union[float, int, bool, str]] = Field(
        default_factory=dict, description="Initial state: {'balance': 1000.0, 'health': 0.8}"
    )


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


# --- 2.2 Intervention (Вмешательство) ---
class Intervention(BaseModel):
    """
    Мера политики. Содержит Self-Healing валидаторы.
    """

    id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    name: TranslatableString

    # Селектор целей (пока строка, в будущем AST)
    target_selector: str = Field(
        ..., description="SQL-like filter: sector == 'IT' and size == 'SME'"
    )

    # Тип механизма (ссылка на Foundry)
    mechanism_type: str = Field(
        ..., description="Foundry mechanism ID: 'tax_subsidy', 'direct_grant'"
    )

    # Параметры механизма
    parameters: Dict[str, Union[float, int, str]]

    # Ограничения (бюджет, сроки)
    constraints: Dict[str, Union[float, int]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_mechanism_semantics(self) -> "Intervention":
        """
        Умная валидация: проверяем, что параметры соответствуют типу механизма.
        Это позволяет LLM 'понять' ошибку и исправить её.
        """
        mech = self.mechanism_type
        params = self.parameters

        # Пример правила из ТЗ
        if mech == "tax_subsidy":
            if "rate" not in params:
                raise ValueError(f"Mechanism '{mech}' requires parameter 'rate' (float 0..1).")
            if not (0 <= float(params["rate"]) <= 1):
                raise ValueError("Parameter 'rate' for tax_subsidy must be between 0 and 1.")

        elif mech == "direct_grant":
            if "amount" not in params:
                raise ValueError(f"Mechanism '{mech}' requires parameter 'amount'.")

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
    Корневой документ, который должна сгенерировать LLM.
    Это и есть 'Контракт'.
    """

    project_name: TranslatableString
    schema_version: str = Field("1.0.0", pattern=r"^\d+\.\d+\.\d+$")

    simulation_params: SimulationParameters

    # Списки объектов (Flat list, иерархия через parent_id)
    entities: List[PolicyEntity]
    objectives: List[Objective]
    interventions: List[Intervention]

    # Глобальные ограничения
    global_constraints: Dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_integrity(self) -> "PolicyRequestIR":
        """Проверка целостности графа и бюджетов."""
        # 1. Проверка уникальности ID сущностей
        ids = [e.id for e in self.entities]
        if len(ids) != len(set(ids)):
            raise ValueError("Entity IDs must be unique.")

        # 2. Проверка связности (родитель должен существовать)
        for e in self.entities:
            if e.parent_id and e.parent_id not in ids:
                raise ValueError(f"Entity '{e.id}' refers to non-existent parent '{e.parent_id}'.")

        return self
