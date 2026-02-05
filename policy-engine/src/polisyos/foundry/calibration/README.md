# Calibration Module (Калибровка моделей)

Модуль `calibration` предоставляет инструменты для автоматической калибровки параметров экономических моделей на реальных данных с использованием градиентной оптимизации.

## Архитектура (актуально на 2026-02-05)

### Core компоненты
- **`calibrator.py`** - Основной класс `Calibrator` для оптимизации параметров
- **`pure_executor.py`** - Чистый JAX executor без side effects

### Функции потерь и биекции
- **`loss.py`** - Функции потерь (MSE, Huber, weighted loss)
- **`bijectors.py`** - Биекции для ограничения параметров (sigmoid, softplus, exp)
- **`preflight.py`** - Подготовка данных и конфигурации перед калибровкой
- **`pure_executor.py`** - Чистый JAX executor без side effects для калибровки

### Подготовка и анализ
- **`preflight.py`** - Подготовка данных и конфигурации
- **`report.py`** - Отчёты калибровки с метриками качества

## Основные концепции

### Calibrator (Калибратор)

```python
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs

@dataclass
class CalibratorInputs:
    config: CalibrationConfig              # Конфигурация калибровки
    program_graph: ProgramGraph           # Скомпилированная политика
    exec_plan: ExecPlan                   # План исполнения
    base_state: GlobalState               # Начальное состояние экономики
    raw_targets: Mapping[str, object]     # Реальные данные

calibrator = Calibrator(inputs)
report = calibrator.run()
```

### CalibrationConfig

```python
from polisyos.ir.calibration import CalibrationConfig, CalibrationTarget

config = CalibrationConfig(
    trainable_params=[TrainableParamRef(path="tax_mechanism.rate", lower=0.0, upper=0.5)],
    targets=[CalibrationTarget(name="gdp", data_source="real_gdp_data", time_window=(0, 120))],
    optimizer=OptimizerConfig(algorithm="adam", learning_rate=0.01, max_steps=1000)
)
```

## Процесс калибровки

1. **Preflight**: Загрузка и подготовка целевых данных
2. **Компиляция**: Создание оптимизируемой функции с автодифференцированием
3. **Оптимизация**: Градиентный спуск с биекциями для ограниченных параметров
4. **Анализ**: Метрики качества и оценки неопределённости

## Функции потерь и биекции

### Функции потерь

```python
from polisyos.foundry.calibration.loss import loss_components

total_loss, per_target_loss, per_target_base = loss_components(
    predicted=predicted_values, targets=real_values,
    configs=target_configs, scales=target_scales, weights=target_weights
)
```

Поддержка: **MSE**, **Huber Loss**, **Weighted Loss**

### Биекции параметров

Ограничение параметров для физической корректности:

```python
from polisyos.foundry.calibration.bijectors import make_bijector, to_unconstrained, from_unconstrained

bijector = make_bijector(lower=0.0, upper=1.0)  # Для [0,1] параметров
unconstrained = to_unconstrained([0.2], [bijector])
constrained = from_unconstrained(unconstrained, [bijector])
```

Поддержка: **sigmoid** (0,1), **softplus** (0,∞), **identity** (-∞,∞), **exp** (0,∞)

## Отчёт калибровки

```python
@dataclass
class CalibrationReport:
    calibrated_params: dict[str, float]                    # Калиброванные параметры
    total_loss: float                                       # Общая потеря
    per_target_loss: dict[str, float]                       # Потери по целям
    series_comparison: dict[str, CalibrationSeriesComparison]  # Сравнение рядов
    fit_quality: CalibrationFitQuality                      # Метрики качества (R², RMSE, MAE, etc.)
    uncertainties: CalibrationUncertainty                   # Оценки неопределённости
```

## Оптимизаторы

```python
@dataclass
class OptimizerConfig:
    algorithm: str = "adam"           # "adam", "lbfgs", "sgd"
    learning_rate: float = 0.01       # Скорость обучения
    max_steps: int = 1000             # Максимальное число шагов
```

**Adam** (рекомендуемый), **L-BFGS** (для точной оптимизации), **SGD**

## Примеры использования

### Базовая калибровка

```python
from polisyos.foundry.calibration import Calibrator, CalibratorInputs

config = CalibrationConfig(
    trainable_params=[TrainableParamRef(path="tax_mechanism.rate", lower=0.0, upper=0.4)],
    targets=[CalibrationTarget(name="gdp_growth", data_source="world_bank_gdp")],
    optimizer=OptimizerConfig(algorithm="adam", learning_rate=0.005, max_steps=500)
)

inputs = CalibratorInputs(config=config, program_graph=program_graph, exec_plan=exec_plan,
                         base_state=initial_state, raw_targets=real_data)

calibrator = Calibrator(inputs)
report = calibrator.run()

print(f"Калиброванная ставка: {report.calibrated_params['tax_mechanism.rate']:.3f}")
print(f"R²: {report.fit_quality.r_squared:.3f}")
```

### Многоцелевая калибровка

Калибровка нескольких параметров одновременно с весами целей для баланса оптимизации.

## Продвинутые возможности

- **Ограничения параметров**: Зависимости между параметрами
- **Байесовская калибровка**: С учётом априорных распределений
- **Временные ряды**: Сезонная корректировка и анализ

## Производительность

- **JIT-компиляция**: Максимальная скорость вычислений
- **Векторизация**: Параллельная обработка батчей
- **GPU поддержка**: Масштабирование на GPU

## Интеграция

- **`scientist/`**: Вызов калибровки из экспериментов
- **`foundry.compiler`**: Компиляция политик
- **`foundry.runtime`**: Исполнение калиброванных политик
- **`core.artifacts`**: Сохранение результатов

---

Модуль `calibration` - полный фреймворк для калибровки экономических моделей на реальных данных.