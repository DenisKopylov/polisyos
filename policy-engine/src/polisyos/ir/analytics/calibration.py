"""Public analytics calibration module API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from polisyos.ir.model_layer.types import TimeFrequency
else:
    from polisyos.ir.model_layer.types import TimeFrequency


class TargetAlignConfig(BaseModel):
    """Настройки выравнивания исторического ряда под шаг симуляции."""

    frequency: TimeFrequency | None = Field(
        None, description="Частота симуляции/ресемплинга (если нужно переопределить)."
    )
    time_column: str | None = Field(
        None, description="Название колонки времени в результатах Fabric (если есть)."
    )
    method: str = Field(
        "linear",
        description="Метод интерполяции/ресемплинга (linear|ffill).",
        pattern=r"^(linear|ffill)$",
    )
    fill_value: float | None = Field(
        None,
        description="Чем заполнить пропуски (если None — использовать крайние значения/интерполяцию).",
    )
    steps: int | None = Field(
        None, ge=1, description="Явное количество шагов симуляции для данного таргета."
    )

    model_config = ConfigDict(extra="forbid")


class TargetLossConfig(BaseModel):
    """Параметры расчёта ошибки по таргету."""

    kind: str = Field("mse", description="mse|huber (MVP поддерживает mse).")
    relative: bool = Field(
        True, description="Использовать относительную нормализацию ошибки (делить на масштаб ряда)."
    )
    scale: str = Field(
        "mean_abs",
        description="Стратегия масштаба ряда (mean_abs|std|max|p95|none).",
        pattern=r"^(mean_abs|std|max|p95|none)$",
    )
    epsilon: float = Field(1e-8, description="Стабилизация при нулевом масштабе.")
    weight: float = Field(1.0, ge=0.0, description="Вес компоненты в общей потере.")

    model_config = ConfigDict(extra="forbid")


class GradNormConfig(BaseModel):
    """Настройки GradNorm (выравнивание норм градиентов по таргетам)."""

    enabled: bool = False
    alpha: float = Field(1.0, ge=0.0, description="Степень выравнивания скорости обучения.")
    lr: float = Field(0.1, ge=0.0, description="Скорость адаптации весов.")
    min_weight: float = Field(0.1, gt=0.0)
    max_weight: float = Field(10.0, gt=0.0)
    epsilon: float = Field(1e-8, gt=0.0)
    update_every: int = Field(1, ge=1, description="Частота обновления весов (в шагах).")

    model_config = ConfigDict(extra="forbid")


class HessianConfig(BaseModel):
    """Настройки оценки неопределённости через Hessian."""

    enabled: bool = True
    damping: float = Field(1e-6, ge=0.0, description="Диагональный сдвиг λ для H + λI.")
    rank_tol: float = Field(1e-6, gt=0.0, description="Порог для оценки ранга Hessian.")
    condition_warn: float = Field(
        1e8, gt=0.0, description="Порог кондиционирования для диагностики."
    )
    std_warn: float = Field(
        1e6, gt=0.0, description="Порог STD для диагностики неидентифицируемости."
    )
    max_params: int | None = Field(
        None, ge=1, description="Ограничение на количество параметров для расчёта Hessian."
    )

    model_config = ConfigDict(extra="forbid")


class ConstraintLossConfig(BaseModel):
    """Настройки штрафов по ограничениям."""

    enabled: bool = False
    constraint_ids: list[str] = Field(
        default_factory=list, description="Если пусто — использовать все ограничения из registry."
    )
    mode: str = Field("trajectory", pattern=r"^(trajectory|final)$")
    reduction: str = Field("mean", pattern=r"^(mean|max)$")
    weight: float = Field(1.0, ge=0.0)
    epsilon: float = Field(1e-8, gt=0.0)

    model_config = ConfigDict(extra="forbid")


class PriorLossConfig(BaseModel):
    """Настройки Gaussian priors по trainable параметрам."""

    enabled: bool = False
    weight: float = Field(1.0, ge=0.0)
    epsilon: float = Field(1e-8, gt=0.0)

    model_config = ConfigDict(extra="forbid")


class FidelityConfig(BaseModel):
    """Настройки режима исполнения для калибрации."""

    mode: str = Field(
        "relaxed",
        description="Режим исполнения (relaxed|discrete).",
        pattern=r"^(relaxed|discrete)$",
    )
    temperature: float = Field(1.0, gt=0.0, description="Температура сглаживания (softmax/gumbel).")
    force_override: bool = Field(
        True, description="Принудительно перезаписывать fidelity в параметрах механизма."
    )

    model_config = ConfigDict(extra="forbid")


class CalibrationTarget(BaseModel):
    """Bind one observed Fabric series to the simulation metric being calibrated.

    Calibration runners align the Fabric series using ``align``, evaluate the
    target-specific loss configured in ``loss``, and optionally restrict which
    trainable parameters should respond to this target.
    """

    target_id: str = Field(..., max_length=128, description="Идентификатор таргета (уникален).")
    model_metric_path: str = Field(
        ...,
        max_length=256,
        description="state_path или slot_id для извлечения метрики из состояния/трейса.",
    )
    fabric_query: dict[str, Any] | None = Field(
        None,
        description="Запрос/спецификация к Fabric/UDF. В preflight должен быть разрешён в массив значений.",
    )
    fabric_metric: str | None = Field(
        None,
        description=(
            "Колонка/метрика из результата Fabric "
            "(если не задано — использовать target_id или единственную метрику)."
        ),
        max_length=128,
    )
    align: TargetAlignConfig = Field(default_factory=TargetAlignConfig)
    loss: TargetLossConfig = Field(default_factory=TargetLossConfig)
    trainables: list[TrainableParamRef] = Field(
        default_factory=list,
        description="Опциональная карта параметров, связанных с этим таргетом.",
    )
    aggregation: str = Field(
        "none",
        description="Агрегация метрики для векторных слотов (none|mean|sum|min|max).",
        pattern=r"^(none|mean|sum|min|max)$",
    )

    model_config = ConfigDict(extra="forbid")


class TrainableParamRef(BaseModel):
    """Ссылка на параметр механизма, который нужно калибровать."""

    param_id: str = Field(..., max_length=128)
    node_id: str | None = Field(
        None, description="node_id в ProgramGraph (если известен конкретный узел).", max_length=128
    )
    mechanism_type: str | None = Field(
        None,
        description="Тип механизма, если trainable определяется на типовом уровне.",
        max_length=128,
    )
    selector: Any | None = Field(
        None,
        description="Опциональная селекция/маска (SelectorExpr или строковый ключ).",
    )
    tie_id: str | None = Field(
        None,
        description="Идентификатор группы для связки параметров (shared/tied).",
        max_length=128,
    )

    model_config = ConfigDict(extra="forbid")


class MultiStartConfig(BaseModel):
    """Configuration for multi-start optimization."""

    n_starts: int = Field(5, ge=1, description="Number of optimization starts.")
    perturbation_scale: float = Field(
        0.1, gt=0.0, description="Scale for initial parameter perturbation."
    )
    selection: str = Field(
        "best_loss",
        pattern=r"^(best_loss|best_identifiability)$",
        description="Selection criterion: best_loss or best_identifiability.",
    )
    condition_threshold: float = Field(
        1e8, gt=0.0, description="Max acceptable Hessian condition number for best_loss selection."
    )

    model_config = ConfigDict(extra="forbid")


class CalibrationConfig(BaseModel):
    """Configure a full calibration run over targets, trainables, and penalties.

    This is the root calibration contract passed into optimization runners. It
    defines the observed targets, trainable parameter set, loss regularizers,
    fidelity mode, multi-start/Hessian behavior, and deterministic seeding.
    """

    schema_version: str = Field("0.1", pattern=r"^\\d+\\.\\d+$")
    targets: list[CalibrationTarget] = Field(default_factory=list)
    trainables: list[TrainableParamRef] = Field(
        default_factory=list,
        description="Необязательный явный список параметров; если пусто — использовать ParamSpec.trainable.",
    )
    steps: int | None = Field(
        None,
        ge=1,
        description="Явное число шагов симуляции для калибровки (если нужно переопределить).",
    )
    time_axis: list[float] | None = Field(
        None, description="Явная ось времени для ресемплинга таргетов."
    )
    max_steps: int = Field(200, ge=1, description="Лимит итераций оптимизации (MVP).")
    learning_rate: float = Field(1e-2, gt=0.0, description="Начальный lr для optax.Adam.")
    clip_grad_norm: float | None = Field(
        None, gt=0.0, description="Глобальный клиппинг нормы градиента."
    )
    early_stop_patience: int = Field(0, ge=0, description="Patience для early stopping.")
    early_stop_min_delta: float = Field(
        0.0, ge=0.0, description="Мин. улучшение для сброса patience."
    )
    early_stop_min_steps: int = Field(0, ge=0, description="Минимум шагов до early stopping.")
    seed_strategy: str = Field(
        "fixed",
        description="Стратегия использования seed (fixed|step).",
        pattern=r"^(fixed|step)$",
    )
    grad_norm: GradNormConfig = Field(default_factory=GradNormConfig)
    hessian: HessianConfig = Field(default_factory=HessianConfig)
    multi_start: MultiStartConfig | None = Field(
        None, description="Multi-start optimization config; None = single run."
    )
    constraint_loss: ConstraintLossConfig = Field(default_factory=ConstraintLossConfig)
    prior_loss: PriorLossConfig = Field(default_factory=PriorLossConfig)
    fidelity: FidelityConfig = Field(default_factory=FidelityConfig)
    constraint_values: dict[str, float] | None = Field(
        None, description="Значения ограничений по constraint_id."
    )
    literature_priors: dict[str, dict[str, Any]] | None = Field(
        None,
        description=(
            "Prior distributions from academic literature (ScholarKnowledgeGraph). "
            "Maps param_id → {prior_mean, prior_std, n_studies, best_design}. "
            "Used when TrainableHandle has no explicit prior and prior_loss is enabled."
        ),
    )
    seed: int = Field(0, description="PRNG seed для детерминизма.")

    model_config = ConfigDict(extra="forbid")
