"""
Базовые схемы данных для Policy Engine.
Использует Pydantic для валидации и типизации данных.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PolicyModel(BaseModel):
    """Базовая модель политики"""

    id: str = Field(..., description="Уникальный идентификатор политики")
    name: str = Field(..., description="Название политики")
    description: str | None = Field(None, description="Описание политики")

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Метаданные политики
    tags: list[str] = Field(default_factory=list, description="Теги для категоризации")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные")

    class Config:
        """Конфигурация Pydantic"""

        json_encoders = {datetime: lambda v: v.isoformat()}


class SimulationParameters(BaseModel):
    """Параметры симуляции политики"""

    time_steps: int = Field(..., gt=0, description="Количество временных шагов")
    population_size: int = Field(..., gt=0, description="Размер популяции для симуляции")

    # Параметры моделирования
    random_seed: int | None = Field(None, description="Seed для воспроизводимости")
    confidence_level: float = Field(0.95, ge=0, le=1, description="Уровень доверия для интервалов")

    # Опциональные параметры
    parallel_computation: bool = Field(True, description="Использовать параллельные вычисления")
    save_intermediate: bool = Field(False, description="Сохранять промежуточные результаты")


class SimulationResult(BaseModel):
    """Результаты симуляции политики"""

    policy_id: str = Field(..., description="ID политики")
    parameters: SimulationParameters

    # Результаты
    outcomes: dict[str, list[float]] = Field(..., description="Результаты по метрикам")
    statistics: dict[str, dict[str, float]] = Field(..., description="Статистики по результатам")

    # Метаданные выполнения
    execution_time: float = Field(..., gt=0, description="Время выполнения в секундах")
    completed_at: datetime = Field(default_factory=datetime.now)


# Пример использования
if __name__ == "__main__":
    from loguru import logger

    # Создаем тестовую политику
    policy = PolicyModel(
        id="test-policy-001",
        name="Тестовая политика",
        description="Пример политики для демонстрации",
        tags=["test", "demo"],
    )

    logger.info("✅ Policy Model создана:")
    logger.info(policy.model_dump_json(indent=2))

    # Создаем параметры симуляции
    params = SimulationParameters(
        time_steps=100,
        population_size=1000,
        random_seed=42,
        confidence_level=0.95,
        parallel_computation=True,
        save_intermediate=False,
    )

    logger.info("✅ Simulation Parameters созданы:")
    logger.info(params.model_dump_json(indent=2))
