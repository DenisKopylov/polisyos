from datetime import datetime
from typing import Dict, List, Optional, Union, Any

from pydantic import BaseModel, Field, model_validator, field_validator, ConfigDict

from src.policy_ir.types import (
    EntityType,
    OptimizationDirection,
    SelectorOperator,
    TimeFrequency,
    TimeUnit,
    TranslatableString,
)
from src.policy_ir.mechanism_spec import get_mechanism_spec
from src.policy_ir.units import UNIT_REGISTRY

# --- Limits (Anti-runaway) ---
MAX_ENTITIES = 500
MAX_INTERVENTIONS = 200
MAX_OBJECTIVES = 50
MAX_SHOCKS = 100
MAX_ID_LEN = 64
MAX_SELECTOR_FIELD_LEN = 64
MAX_STRING_LEN = 500
MAX_DEPTH = 4
MAX_CHILDREN = 200


def _get_param_value(params: Dict[str, Any], path: str) -> Any:
    current = params
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _validate_nested_specs(params: Dict[str, Any], spec) -> None:
    for key, nested_spec in spec.nested_params.items():
        nested_value = params.get(key)
        if not isinstance(nested_value, dict):
            raise ValueError(f"Mechanism '{spec.name}' param '{key}' must be object")
        missing = nested_spec.required_params - set(nested_value.keys())
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(
                f"Mechanism '{spec.name}.{key}' requires params: {missing_list}"
            )
        for nested_key, (min_val, max_val) in nested_spec.param_ranges.items():
            value = _get_param_value(nested_value, nested_key)
            if value is None:
                continue
            if isinstance(value, (int, float)):
                if value < min_val or value > max_val:
                    raise ValueError(
                        f"Mechanism '{spec.name}.{key}' param '{nested_key}' "
                        f"out of range [{min_val}, {max_val}]"
                    )
        for nested_key, unit in nested_spec.param_units.items():
            if unit not in UNIT_REGISTRY:
                raise ValueError(
                    f"Mechanism '{spec.name}.{key}' param '{nested_key}' "
                    f"uses unknown unit '{unit}'"
                )

# --- 2.1 Entity (Плоская структура) ---
class PolicyEntity(BaseModel):
    """
    Сущность в плоском списке (Adjacency List).
    Иерархия строится через parent_id.
    """
    id: str = Field(
        ...,
        pattern=r"^[a-z0-9_]+$",
        max_length=MAX_ID_LEN,
        description="Unique slug (snake_case)",
    )
    entity_type: EntityType
    name: TranslatableString
    parent_id: Optional[str] = Field(
        None,
        description="ID родителя. Должен существовать в списке.",
        max_length=MAX_ID_LEN,
    )

    # Динамическое состояние
    state_variables: Dict[str, Union[float, int, bool, str]] = Field(
        default_factory=dict, description="Initial state: {'balance': 1000.0}"
    )


# --- 2.2 Target Selector (AST) ---
class SelectorPredicate(BaseModel):
    """Атомарное условие: field op value"""
    field: str = Field(
        ...,
        description="Атрибут сущности, напр. 'sector'",
        max_length=MAX_SELECTOR_FIELD_LEN,
    )
    operator: SelectorOperator
    value: Union[str, int, float, bool, List[str], List[int], List[float], List[bool]]
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_operator_value(self) -> "SelectorPredicate":
        if self.operator == SelectorOperator.BETWEEN:
            if not isinstance(self.value, list) or len(self.value) != 2:
                raise ValueError("Operator 'between' requires a list of two values")
        if self.operator == SelectorOperator.CONTAINS:
            if not isinstance(self.value, (str, list)):
                raise ValueError("Operator 'contains' requires string or list value")
        return self

class TargetSelector(BaseModel):
    """
    Структурированный фильтр целей.
    Заменяет строку "sector == 'IT'".
    Поддерживает композицию all_of/any_of/not.
    """
    all_of: List[SelectorPredicate] = Field(default_factory=list)
    any_of: List[SelectorPredicate] = Field(default_factory=list)
    not_: Optional["TargetSelector"] = Field(None, alias="not")
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    def to_human_readable(self) -> str:
        """Для удобства отладки/лога."""
        parts = []
        if self.all_of:
            parts.append(
                " AND ".join([f"{p.field} {p.operator.value} {p.value}" for p in self.all_of])
            )
        if self.any_of:
            parts.append(
                " OR ".join([f"{p.field} {p.operator.value} {p.value}" for p in self.any_of])
            )
        if self.not_:
            parts.append(f"NOT {self.not_.to_human_readable()}")
        return f"({' AND '.join(parts)})"

    @model_validator(mode="after")
    def validate_non_empty(self) -> "TargetSelector":
        if not self.all_of and not self.any_of and not self.not_:
            raise ValueError("TargetSelector must define at least one of all_of/any_of/not")
        return self


# --- 2.3 Metric / Objective (Цель) ---
class Objective(BaseModel):
    metric_name: str = Field(
        ...,
        description="Name of the metric to optimize (e.g. 'gdp', 'unemployment')",
        max_length=MAX_STRING_LEN,
    )
    direction: OptimizationDirection
    threshold: Optional[float] = Field(
        None, description="Target value boundary if direction is RANGE"
    )
    priority_weight: float = Field(default=1.0, ge=0.0, le=10.0)


# --- 2.3 Intervention ---
class Intervention(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9_]+$", max_length=MAX_ID_LEN)
    name: TranslatableString

    # Безопасный AST селектор
    target_selector: TargetSelector

    mechanism_type: str = Field(
        ...,
        description="Ссылка на механизм в Foundry",
        max_length=MAX_STRING_LEN,
    )
    parameters: Dict[str, Any]
    constraints: Dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mechanism_params(self) -> "Intervention":
        spec = get_mechanism_spec(self.mechanism_type)
        missing = spec.required_params - set(self.parameters.keys())
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(
                f"Mechanism '{self.mechanism_type}' requires params: {missing_list}"
            )
        for key, (min_val, max_val) in spec.param_ranges.items():
            value = _get_param_value(self.parameters, key)
            if value is None:
                continue
            if isinstance(value, (int, float)):
                if value < min_val or value > max_val:
                    raise ValueError(
                        f"Mechanism '{self.mechanism_type}' param '{key}' "
                        f"out of range [{min_val}, {max_val}]"
                    )
        for key, unit in spec.param_units.items():
            if unit not in UNIT_REGISTRY:
                raise ValueError(
                    f"Mechanism '{self.mechanism_type}' param '{key}' "
                    f"uses unknown unit '{unit}'"
                )
        _validate_nested_specs(self.parameters, spec)
        return self


# --- Корневой документ (Root) ---
class SimulationParameters(BaseModel):
    """Технические параметры симуляции."""

    scope_years: int = Field(..., ge=1, le=50)
    time_frequency: TimeFrequency = TimeFrequency.MONTH
    start_date: str = "2024-01-01"
    random_seed: int = 42


class GeneratorInfo(BaseModel):
    name: str = Field(..., max_length=MAX_STRING_LEN, description="Component name")
    version: str = Field(..., max_length=MAX_STRING_LEN, description="Component version")


class Shock(BaseModel):
    """Внешний шок/событие."""

    id: str = Field(..., pattern=r"^[a-z0-9_]+$", max_length=MAX_ID_LEN)
    name: TranslatableString
    description: Optional[TranslatableString] = None
    magnitude: Optional[float] = None
    at_step: Optional[int] = Field(None, ge=0)


class Timeline(BaseModel):
    start_year: int = Field(..., ge=1900, le=2100)
    end_year: int = Field(..., ge=1900, le=2100)

    @model_validator(mode="after")
    def validate_range(self) -> "Timeline":
        if self.end_year < self.start_year:
            raise ValueError("timeline.end_year must be >= timeline.start_year")
        return self


class Scenarios(BaseModel):
    random_seed: int = Field(..., description="Deterministic seed for scenarios")
    shocks: List[Shock] = Field(default_factory=list)
    timeline: Timeline


class PolicyRequestIR(BaseModel):
    """
    Корневой артефакт.
    Содержит версионирование и глобальную валидацию графа.
    """
    project_name: TranslatableString

    # Версионирование контракта (MUST have)
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    generator: GeneratorInfo

    # Единицы измерения
    currency: str = Field("USD", pattern=r"^[A-Z]{3}$")
    time_unit: TimeUnit = TimeUnit.YEAR
    price_base_year: Optional[int] = Field(None, ge=1900, le=2100)

    simulation_params: SimulationParameters
    scenarios: Scenarios

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
        3. Нет превышения глубины/числа детей.
        4. Все узлы достижимы от корней.
        """
        if len(self.entities) > MAX_ENTITIES:
            raise ValueError(f"Too many entities: {len(self.entities)} > {MAX_ENTITIES}")
        if len(self.interventions) > MAX_INTERVENTIONS:
            raise ValueError(
                f"Too many interventions: {len(self.interventions)} > {MAX_INTERVENTIONS}"
            )
        if len(self.objectives) > MAX_OBJECTIVES:
            raise ValueError(
                f"Too many objectives: {len(self.objectives)} > {MAX_OBJECTIVES}"
            )
        if len(self.scenarios.shocks) > MAX_SHOCKS:
            raise ValueError(f"Too many shocks: {len(self.scenarios.shocks)} > {MAX_SHOCKS}")

        entity_ids = {e.id for e in self.entities}

        # 1. Проверка существования родителей
        adjacency = {e.id: [] for e in self.entities}
        for e in self.entities:
            if e.parent_id:
                if e.parent_id not in entity_ids:
                    raise ValueError(f"Entity '{e.id}' refers to unknown parent '{e.parent_id}'")
                adjacency[e.parent_id].append(e.id)  # Строим граф сверху вниз

        # 1.1 Ограничение числа детей
        for parent_id, children in adjacency.items():
            if len(children) > MAX_CHILDREN:
                raise ValueError(
                    f"Entity '{parent_id}' has too many children: {len(children)} > {MAX_CHILDREN}"
                )

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

        # 3. Проверка глубины и достижимости
        roots = [e.id for e in self.entities if not e.parent_id]
        if not roots:
            raise ValueError("At least one root entity is required (parent_id=None).")

        reachable = set()
        max_depth_found = 0
        stack = [(root, 1) for root in roots]
        while stack:
            node_id, depth = stack.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            max_depth_found = max(max_depth_found, depth)
            for child in adjacency.get(node_id, []):
                stack.append((child, depth + 1))

        if max_depth_found > MAX_DEPTH:
            raise ValueError(f"Entity tree depth {max_depth_found} exceeds MAX_DEPTH {MAX_DEPTH}")

        if reachable != entity_ids:
            missing = entity_ids - reachable
            raise ValueError(f"Some entities are not reachable from roots: {sorted(missing)}")

        return self

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        # Зафиксируем формат MAJOR.MINOR
        return v


TargetSelector.model_rebuild()
