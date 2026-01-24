# Calibration Module (Калибровка моделей)

## Обзор

Модуль `calibration` предоставляет инструменты для автоматической калибровки параметров экономических моделей на реальных данных. Модуль использует градиентную оптимизацию для подбора параметров механизмов, обеспечивая соответствие моделируемых показателей реальным данным.

## Архитектура

Модуль состоит из следующих компонентов:

### 1. Core Calibration (Основная калибровка)
- **`calibrator.py`** - Основной класс `Calibrator` для оптимизации параметров
- **`pure_executor.py`** - Чистый JAX executor без side effects для калибровки

### 2. Функции потерь и биекции
- **`loss.py`** - Функции потерь (MSE, Huber, weighted loss)
- **`bijectors.py`** - Биекции для ограничения параметров (sigmoid, softplus)

### 3. Подготовка и анализ
- **`preflight.py`** - Подготовка данных и конфигурации
- **`report.py`** - Отчёты калибровки с метриками качества

## Основные концепции

### Calibrator (Калибратор)

Основной класс для выполнения калибровки:

```python
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs

@dataclass
class CalibratorInputs:
    config: CalibrationConfig              # Конфигурация калибровки
    program_graph: ProgramGraph           # Скомпилированная политика
    exec_plan: ExecPlan                   # План исполнения
    base_state: GlobalState               # Начальное состояние экономики
    mechanism_registry: MechanismTypeRegistry
    slot_registry: SlotRegistry
    merge_registry: MergeRuleRegistry
    raw_targets: Mapping[str, object]     # Реальные данные для сравнения

# Запуск калибровки
calibrator = Calibrator()
report = calibrator.calibrate(inputs)
```

### CalibrationConfig (Конфигурация калибровки)

```python
from polisyos.ir.calibration import CalibrationConfig, CalibrationTarget

config = CalibrationConfig(
    trainable_params=[                           # Параметры для оптимизации
        TrainableParamRef(
            path="tax_mechanism.rate",          # Путь к параметру
            lower=0.0, upper=0.5,               # Ограничения
            prior_mean=0.2, prior_std=0.05      # Априорное распределение
        )
    ],
    targets=[                                   # Цели калибровки
        CalibrationTarget(
            name="gdp",
            data_source="real_gdp_data",        # Источник данных
            time_window=(0, 120),               # Временное окно
            loss_config=LossConfig(
                loss_type="mse",                # Тип потери
                scale=1.0,                      # Масштаб
                weight=1.0                      # Вес
            )
        )
    ],
    optimizer=OptimizerConfig(                   # Оптимизатор
        algorithm="adam",
        learning_rate=0.01,
        max_steps=1000
    )
)
```

## Процесс калибровки

### 1. Подготовка (Preflight)

```python
from polisyos.foundry.calibration.preflight import fetch_targets, prepare_targets

# Загрузка целевых данных
targets = fetch_targets(
    target_configs=config.targets,
    target_fetcher=data_fetcher,
    raw_targets=inputs.raw_targets
)

# Подготовка данных для оптимизации
prepared_targets = prepare_targets(
    targets=targets,
    steps=resolve_steps(config.targets)
)
```

### 2. Компиляция оптимизируемой функции

```python
from polisyos.foundry.calibration.pure_executor import compile_program

# Компиляция программы для калибровки
static_bundle = compile_program(
    program_graph=inputs.program_graph,
    exec_plan=inputs.exec_plan,
    mechanism_registry=inputs.mechanism_registry,
    slot_registry=inputs.slot_registry,
    merge_registry=inputs.merge_registry
)
```

### 3. Оптимизация параметров

```python
from polisyos.foundry.calibration.calibrator import _run_optimization

# Запуск оптимизации
optimization_result = _run_optimization(
    objective_fn=lambda params: compute_loss(params, static_bundle),
    initial_params=initial_param_values,
    bijectors=param_bijectors,
    optimizer_config=config.optimizer,
    constraints=constraint_handles
)
```

### 4. Анализ результатов

```python
from polisyos.foundry.calibration.report import CalibrationReport

# Создание отчёта
report = CalibrationReport(
    calibrated_params=optimization_result.final_params,
    total_loss=optimization_result.final_loss,
    per_target_loss=per_target_losses,
    series_comparison=time_series_comparisons,
    fit_quality=compute_fit_quality(),
    uncertainties=estimate_uncertainties()
)
```

## Функции потерь

### Типы потерь

```python
from polisyos.foundry.calibration.loss import loss_components, compute_base_loss

# Вычисление потерь по нескольким целям
total_loss, per_target_loss, per_target_base = loss_components(
    predicted=predicted_values,     # Предсказанные значения [n_targets, n_steps]
    targets=real_values,           # Реальные значения [n_targets, n_steps]
    configs=target_configs,         # Конфигурации потерь
    scales=target_scales,          # Масштабы для относительных ошибок
    weights=target_weights         # Веса целей
)
```

### Поддерживаемые типы потерь

- **MSE (Mean Squared Error)**: Квадратичная ошибка
- **Huber Loss**: Робастная квадратичная ошибка
- **Weighted Loss**: Взвешенные потери с учётом важности целей

```python
@dataclass
class LossConfig:
    loss_type: str = "mse"          # "mse", "huber", "weighted"
    delta: float = 1.0             # Параметр для Huber loss
    scale: float = 1.0             # Масштаб ошибки
    weight: float = 1.0            # Вес цели
    relative: bool = False         # Относительная ошибка
```

## Биекции параметров

### Ограничение параметров

Для обеспечения физической корректности параметров используются биекции:

```python
from polisyos.foundry.calibration.bijectors import make_bijector, to_unconstrained, from_unconstrained

# Создание биекции для параметра [0, 1] (например, налоговая ставка)
tax_rate_bijector = make_bijector(lower=0.0, upper=1.0)

# Преобразование в unconstrained пространство для оптимизации
unconstrained = to_unconstrained([0.2], [tax_rate_bijector])  # [0.2] -> логарифм

# Обратное преобразование
constrained = from_unconstrained(unconstrained, [tax_rate_bijector])  # логарифм -> [0.2]
```

### Поддерживаемые биекции

- **`sigmoid`**: Для параметров в диапазоне (0, 1)
- **`softplus`**: Для положительных параметров (0, ∞)
- **`identity`**: Для неограниченных параметров (-∞, ∞)
- **`exp`**: Для строго положительных параметров (0, ∞)

## Отчёт калибровки

### Структура отчёта

```python
@dataclass
class CalibrationReport:
    calibrated_params: dict[str, float]                    # Калиброванные параметры
    total_loss: float                                       # Общая потеря
    per_target_loss: dict[str, float]                       # Потери по целям
    series_comparison: dict[str, CalibrationSeriesComparison]  # Сравнение рядов
    fit_quality: CalibrationFitQuality                      # Метрики качества
    uncertainties: CalibrationUncertainty                   # Оценки неопределённости
```

### Метрики качества подгонки

```python
@dataclass
class CalibrationFitQuality:
    r_squared: float                    # Коэффициент детерминации
    rmse: float                        # Root Mean Square Error
    mae: float                         # Mean Absolute Error
    mape: float                        # Mean Absolute Percentage Error
    max_error: float                   # Максимальная ошибка
    correlation: float                 # Корреляция модель/данные
```

### Сравнение временных рядов

```python
@dataclass
class CalibrationSeriesComparison:
    time: list[int]                    # Временные метки
    real: list[float]                  # Реальные значения
    model: list[float]                 # Модельные значения
    residuals: list[float]             # Остатки (real - model)
    relative_errors: list[float]       # Относительные ошибки
```

## Оптимизаторы

### Поддерживаемые алгоритмы

```python
@dataclass
class OptimizerConfig:
    algorithm: str = "adam"           # "adam", "lbfgs", "sgd"
    learning_rate: float = 0.01       # Скорость обучения
    max_steps: int = 1000             # Максимальное число шагов
    tolerance: float = 1e-6           # Критерий остановки
    patience: int = 50                # Терпение для early stopping
```

#### Adam (рекомендуемый)
```python
optimizer_config = OptimizerConfig(
    algorithm="adam",
    learning_rate=0.01,
    max_steps=1000
)
```

#### L-BFGS (для точной оптимизации)
```python
optimizer_config = OptimizerConfig(
    algorithm="lbfgs",
    learning_rate=1.0,        # Для L-BFGS обычно 1.0
    max_steps=500,
    tolerance=1e-9
)
```

## Примеры использования

### Базовая калибровка налоговой ставки

```python
from polisyos.foundry.calibration import Calibrator, CalibratorInputs
from polisyos.ir.calibration import CalibrationConfig, CalibrationTarget, TrainableParamRef

# Конфигурация калибровки
config = CalibrationConfig(
    trainable_params=[
        TrainableParamRef(
            path="tax_mechanism.rate",
            lower=0.0,
            upper=0.4,
            prior_mean=0.2,
            prior_std=0.05
        )
    ],
    targets=[
        CalibrationTarget(
            name="gdp_growth",
            data_source="world_bank_gdp",
            time_window=(0, 60),
            loss_config=LossConfig(loss_type="mse", weight=1.0)
        ),
        CalibrationTarget(
            name="unemployment",
            data_source="bls_unemployment",
            time_window=(0, 60),
            loss_config=LossConfig(loss_type="huber", delta=0.5, weight=0.8)
        )
    ],
    optimizer=OptimizerConfig(
        algorithm="adam",
        learning_rate=0.005,
        max_steps=500
    )
)

# Входные данные
inputs = CalibratorInputs(
    config=config,
    program_graph=compiled_policy.program_graph,
    exec_plan=compiled_policy.exec_plan,
    base_state=initial_economy_state,
    mechanism_registry=mechanism_registry,
    slot_registry=slot_registry,
    merge_registry=merge_registry,
    raw_targets={"gdp_growth": real_gdp_data, "unemployment": real_unemp_data}
)

# Запуск калибровки
calibrator = Calibrator()
report = calibrator.calibrate(inputs)

print(f"Калиброванная ставка налога: {report.calibrated_params['tax_mechanism.rate']:.3f}")
print(f"Общая потеря: {report.total_loss:.6f}")
print(f"R² для GDP: {report.fit_quality.r_squared:.3f}")
```

### Многоцелевая калибровка

```python
# Калибровка нескольких параметров одновременно
config = CalibrationConfig(
    trainable_params=[
        TrainableParamRef(path="labor_market.friction", lower=0.01, upper=0.5),
        TrainableParamRef(path="consumption.propensity", lower=0.5, upper=0.95),
        TrainableParamRef(path="investment.rate", lower=0.1, upper=0.4),
    ],
    targets=[
        CalibrationTarget(name="gdp", weight=1.0),
        CalibrationTarget(name="investment", weight=0.8),
        CalibrationTarget(name="consumption", weight=0.6),
        CalibrationTarget(name="employment", weight=0.9),
    ],
    optimizer=OptimizerConfig(algorithm="adam", learning_rate=0.001, max_steps=2000)
)
```

### Анализ результатов калибровки

```python
# Анализ качества подгонки
print("=== Метрики качества ===")
for target_name, comparison in report.series_comparison.items():
    corr = np.corrcoef(comparison.real, comparison.model)[0, 1]
    rmse = np.sqrt(np.mean(np.square(comparison.residuals)))
    print(f"{target_name}:")
    print(f"  Корреляция: {corr:.3f}")
    print(f"  RMSE: {rmse:.4f}")
    print(f"  Макс. ошибка: {max(abs(r) for r in comparison.residuals):.4f}")

# Проверка ограничений параметров
print("\n=== Калиброванные параметры ===")
for param_path, value in report.calibrated_params.items():
    param_ref = next(p for p in config.trainable_params if p.path == param_path)
    in_bounds = param_ref.lower <= value <= param_ref.upper
    print(f"{param_path}: {value:.4f} {'✓' if in_bounds else '⚠'}")
```

## Продвинутые возможности

### Ограничения и зависимости параметров

```python
# Параметры с зависимостями
config = CalibrationConfig(
    trainable_params=[
        TrainableParamRef(path="tax.income_rate", lower=0.0, upper=0.5),
        TrainableParamRef(path="tax.corporate_rate", lower=0.0, upper=0.4),
    ],
    constraints=[
        ConstraintConfig(
            type="inequality",
            expression="tax.income_rate >= tax.corporate_rate",
            description="Ставка корпоративного налога не выше подоходного"
        )
    ]
)
```

### Байесовская калибровка

```python
# Калибровка с учётом априорных распределений
config = CalibrationConfig(
    trainable_params=[
        TrainableParamRef(
            path="elasticity.labor_supply",
            lower=0.1, upper=2.0,
            prior_mean=0.5,      # Априорное среднее
            prior_std=0.2        # Априорное стандартное отклонение
        )
    ],
    use_bayesian=True,           # Байесовский подход
    n_mcmc_samples=1000          # Число MCMC сэмплов
)
```

### Временные ряды и сезонность

```python
# Калибровка с учётом сезонных эффектов
targets = [
    CalibrationTarget(
        name="seasonal_gdp",
        data_source="quarterly_gdp",
        time_window=(0, 40),      # 10 лет квартальных данных
        seasonal_adjustment=True, # Учёт сезонности
        loss_config=LossConfig(loss_type="mse")
    )
]
```

## Диагностика и отладка

### Проверка градиентов

```python
from polisyos.foundry.calibration.calibrator import _check_gradients

# Проверка корректности градиентов
gradient_report = _check_gradients(
    objective_fn=lambda params: compute_loss(params, static_bundle),
    params=initial_params,
    bijectors=param_bijectors
)

if gradient_report.has_issues:
    print("Проблемы с градиентами:")
    for issue in gradient_report.issues:
        print(f"  - {issue}")
```

### Визуализация процесса калибровки

```python
# Сохранение истории оптимизации
history = calibrator.optimize_with_history(inputs)

# Визуализация сходимости
plt.figure(figsize=(12, 4))

plt.subplot(1, 3, 1)
plt.plot(history.losses)
plt.title('Loss over time')
plt.yscale('log')

plt.subplot(1, 3, 2)
for i, param_name in enumerate(history.param_names):
    plt.plot(history.param_values[:, i], label=param_name)
plt.title('Parameter values')
plt.legend()

plt.subplot(1, 3, 3)
plt.plot(history.grad_norms)
plt.title('Gradient norms')
plt.yscale('log')

plt.tight_layout()
plt.show()
```

## Производительность

### Оптимизации

- **JIT-компиляция**: Все вычисления компилируются для максимальной скорости
- **Векторизация**: Параллельная обработка батчей
- **Кеширование**: Переиспользование вычислений между итерациями
- **Чистые функции**: Отсутствие side effects для надёжной оптимизации

### Масштабирование

```python
# Калибровка на GPU с большими батчами
config = CalibrationConfig(
    optimizer=OptimizerConfig(
        algorithm="adam",
        learning_rate=0.01,
        max_steps=2000,
        batch_size=32,           # Размер батча для векторизации
        use_jit=True            # JIT-компиляция
    ),
    parallel_evaluation=True,   # Параллельная оценка
    n_workers=4                # Число worker'ов
)
```

## Интеграция с другими модулями

- **`scientist/`**: Вызов калибровки из экспериментов
- **`foundry.compiler`**: Компиляция политик для калибровки
- **`foundry.runtime`**: Исполнение калиброванных политик
- **`core.artifacts`**: Сохранение результатов калибровки

---

Модуль `calibration` предоставляет полный фреймворк для автоматической калибровки экономических моделей на реальных данных с использованием современных методов оптимизации и анализа качества подгонки.