from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from polisyos.ir.types import TimeFrequency


class TargetAlignConfig(BaseModel):
    """Настройки выравнивания исторического ряда под шаг симуляции."""

    frequency: Optional[TimeFrequency] = Field(
        None, description="Частота симуляции/ресемплинга (если нужно переопределить)."
    )
    method: str = Field(
        "linear",
        description="Метод интерполяции/ресемплинга (linear|ffill).",
        pattern=r"^(linear|ffill)$",
    )
    fill_value: Optional[float] = Field(
        None, description="Чем заполнить пропуски (если None — использовать крайние значения/интерполяцию)."
    )

    model_config = ConfigDict(extra="forbid")


class TargetLossConfig(BaseModel):
    """Параметры расчёта ошибки по таргету."""

    kind: str = Field("mse", description="mse|huber (MVP поддерживает mse).")
    relative: bool = Field(
        True, description="Использовать относительную нормализацию ошибки (делить на масштаб ряда)."
    )
    epsilon: float = Field(1e-8, description="Стабилизация при нулевом масштабе.")
    weight: float = Field(1.0, ge=0.0, description="Вес компоненты в общей потере.")

    model_config = ConfigDict(extra="forbid")


class CalibrationTarget(BaseModel):
    """Связка наблюдаемого ряда Fabric с метрикой симуляции."""

    target_id: str = Field(..., max_length=128, description="Идентификатор таргета (уникален).")
    model_metric_path: str = Field(
        ..., max_length=256, description="state_path или slot_id для извлечения метрики из состояния/трейса."
    )
    fabric_query: dict[str, Any] | None = Field(
        None,
        description="Запрос/спецификация к Fabric/UDF. В preflight должен быть разрешён в массив значений.",
    )
    align: TargetAlignConfig = Field(default_factory=TargetAlignConfig)
    loss: TargetLossConfig = Field(default_factory=TargetLossConfig)

    model_config = ConfigDict(extra="forbid")


class TrainableParamRef(BaseModel):
    """Ссылка на параметр механизма, который нужно калибровать."""

    param_id: str = Field(..., max_length=128)
    node_id: Optional[str] = Field(
        None, description="node_id в ProgramGraph (если известен конкретный узел).", max_length=128
    )
    mechanism_type: Optional[str] = Field(
        None, description="Тип механизма, если trainable определяется на типовом уровне.", max_length=128
    )
    selector: Optional[str] = Field(
        None,
        description="Опциональная текстовая селекция/маска, если параметр применяется к подмножеству.",
        max_length=256,
    )

    model_config = ConfigDict(extra="forbid")


class CalibrationConfig(BaseModel):
    """Корневой контракт калибрации."""

    schema_version: str = Field("0.1", pattern=r"^\\d+\\.\\d+$")
    targets: List[CalibrationTarget] = Field(default_factory=list)
    trainables: List[TrainableParamRef] = Field(
        default_factory=list,
        description="Необязательный явный список параметров; если пусто — использовать ParamSpec.trainable.",
    )
    max_steps: int = Field(200, ge=1, description="Лимит итераций оптимизации (MVP).")
    learning_rate: float = Field(1e-2, gt=0.0, description="Начальный lr для optax.Adam.")
    seed: int = Field(0, description="PRNG seed для детерминизма.")

    model_config = ConfigDict(extra="forbid")
