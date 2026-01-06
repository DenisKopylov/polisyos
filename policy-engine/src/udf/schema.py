from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DataViewType(str, Enum):
    PANEL = "panel"  # Таблица (Время x Сущность x Метрики)
    SNAPSHOT = "snapshot"  # Срез всех агентов в конкретный момент
    NETWORK = "network"  # <--- Теперь активно


class AccessTier(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"


class DataFilter(BaseModel):
    """Фильтр для выборки данных."""

    # Например: column="is_employed", op="==", value=True
    column: str
    op: str = Field(..., pattern=r"^(==|!=|>|<|>=|<=)$")
    value: str | int | float | bool


class DataViewRequest(BaseModel):
    """
    Запрос на выгрузку данных.
    LLM заполняет эту структуру, чтобы 'посмотреть' на мир.
    """

    request_id: str
    run_id: str  # <--- НОВОЕ ПОЛЕ: Обязательно фильтруем по ID запуска
    view_type: DataViewType

    # Что выбираем (проекция)
    metrics: List[str] = Field(..., description="List of columns to select: ['income', 'gdp']")

    # Фильтры (WHERE)
    filters: List[DataFilter] = Field(default_factory=list)

    # Временное окно (для PANEL)
    step_start: Optional[int] = None
    step_end: Optional[int] = None

    # Группировка (для агрегации, например 'mean')
    aggregation: str = Field("mean", pattern=r"^(mean|sum|count|min|max)$")

    # Уровень доступа (PII protection)
    access_tier: AccessTier = AccessTier.INTERNAL

    # --- НОВЫЕ ПОЛЯ ДЛЯ ГРАФА ---
    # Для выборки "Кто связан с X на глубину N"
    ego_node_id: Optional[str] = Field(None, description="Center node for network query")
    hop_depth: int = Field(1, ge=1, le=5, description="Search depth")
    relation_types: Optional[List[str]] = None
