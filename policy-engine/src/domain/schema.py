from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AgentType(str, Enum):
    WORKER = "worker"
    ENTREPRENEUR = "entrepreneur"
    RETIREE = "retiree"


class RegionProfile(BaseModel):
    """Параметры региона для инициализации популяции."""

    region_id: int
    avg_income: float = Field(..., ge=0)
    unemployment_rate: float = Field(..., ge=0, le=1.0)
    tech_level: float = Field(default=1.0, ge=0.5, description="Уровень цифровизации бизнеса")

    model_config = ConfigDict(frozen=True)  # Делаем объект неизменяемым (хорошо для JAX)


class SimulationConfig(BaseModel):
    """Глобальные настройки симуляции."""

    n_agents: int = Field(..., gt=0, description="Количество агентов в популяции")
    n_steps: int = Field(default=12, gt=0, description="Горизонт планирования (месяцев)")
    seed: int = 42
