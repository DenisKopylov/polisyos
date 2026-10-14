"""Public ir types module API."""

from enum import Enum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# --- Enums (Словари) ---
class EntityType(str, Enum):
    """Types of agents and objects in the system."""

    AGENT = "agent"  # Активный агент (человек, фирма)
    RESOURCE = "resource"  # Пассивный ресурс (бюджет, зерно)
    INFRASTRUCTURE = "infrastructure"  # Дороги, больницы
    ENVIRONMENT = "environment"  # Климат, вирусная нагрузка


class OptimizationDirection(str, Enum):
    """Direction in which to move a metric."""

    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"
    MAINTAIN_RANGE = "maintain_range"


class TimeFrequency(str, Enum):
    """Time frequencies for simulation."""

    MONTH = "M"
    QUARTER = "Q"
    YEAR = "Y"


class TimeUnit(str, Enum):
    """IR time unit in human-readable form."""

    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class SelectorOperator(str, Enum):
    """Allowed operators for TargetSelector (AST)."""

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
    """Multilingual string.

    The LLM sees 'en' for logic, while 'ua'/'ru' are used for the UI.
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
    ru: str | None = Field(
        None,
        description="Russian text (optional)",
        validation_alias=AliasChoices("ru", "Ru"),
        max_length=200,
    )

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")
