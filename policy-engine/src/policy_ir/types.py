from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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


# --- Common Models ---
class TranslatableString(BaseModel):
    """
    Мультиязычная строка.
    LLM видит 'en' для логики, а 'ua'/'ru' используются для UI.
    """

    en: str = Field(..., description="English text for LLM logic")
    ua: str = Field(..., description="Ukrainian text for Reporting/UI")
    ru: Optional[str] = Field(None, description="Russian text (optional)")

    model_config = ConfigDict(frozen=True)  # Делаем неизменяемым
