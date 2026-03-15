from enum import Enum
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# --- Enums (Словари) ---
class EntityType(str, Enum):
    """Типы агентов и объектов в системе."""

    AGENT = "agent"  # Активный агент (человек, фирма)
    RESOURCE = "resource"  # Пассивный ресурс (бюджет, зерно)
    INFRASTRUCTURE = "infrastructure"  # Дороги, больницы
    ENVIRONMENT = "environment"  # Климат, вирусная нагрузка


class OptimizationDirection(str, Enum):
    """Куда двигать метрику."""

    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"
    MAINTAIN_RANGE = "maintain_range"


class TimeFrequency(str, Enum):
    """Единицы времени для симуляции."""

    MONTH = "M"
    QUARTER = "Q"
    YEAR = "Y"

class TimeUnit(str, Enum):
    """Единицы времени в IR (человеческий формат)."""

    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class SelectorOperator(str, Enum):
    """Разрешенные операторы для TargetSelector (AST)."""
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    CONTAINS = "contains"


# --- Common Models ---
class TranslatableString(BaseModel):
    """
    Мультиязычная строка.
    LLM видит 'en' для логики, а 'ua'/'ru' используются для UI.
    """

    en: str = Field(
        ...,
        description="English text for LLM logic",
        validation_alias=AliasChoices("en", "En"),
        max_length=200,
    )
    ua: str = Field(
        ...,
        description="Ukrainian text for Reporting/UI",
        validation_alias=AliasChoices("ua", "Ua"),
        max_length=200,
    )
    ru: Optional[str] = Field(
        None,
        description="Russian text (optional)",
        validation_alias=AliasChoices("ru", "Ru"),
        max_length=200,
    )

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")
