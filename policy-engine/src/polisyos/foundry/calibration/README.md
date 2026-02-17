# Calibration (`polisyos.foundry.calibration`)

`calibration` — подсистема data-driven калибровки параметров Foundry-моделей на эмпирических target-данных.

Актуально по коду на 2026-02-17.

## Роль в системе

Калибровка работает поверх уже собранного `ProgramGraph` + `ExecPlan` и подбирает trainable параметры механизмов, чтобы симуляция лучше совпадала с заданными целями.

## Pipeline

```text
CalibrationConfig + ProgramGraph/ExecPlan + base_state + registries
        |
        v
preflight (fetch/align targets)
        |
        v
compile_program -> StaticBundle (pure execution)
        |
        v
bijectors (constrained <-> unconstrained)
        |
        v
optimization loop (optax + penalties + adaptive weighting + early stop)
        |
        v
optional Hessian/Laplace uncertainty
        |
        v
CalibrationReport (+ optional uncertainty envelopes)
```

## Ключевые модули

- `calibrator.py`
  - `Calibrator.run()` — основной pipeline.
  - Поддерживает MSE/Huber лоссы, target weights, GradNorm balancing, prior/constraint penalties, early stopping.
  - Опционально считает Hessian/Laplace uncertainty и встраивает результат в отчёт.

- `pure_executor.py`
  - `compile_program()` строит `StaticBundle` без CAS IO внутри оптимизационного цикла.
  - `run_pure_scan()` выполняет чистый JAX scan.
  - `extract_trainable_values()` / `apply_trainable_values()` управляют trainable параметрами.

- `preflight.py`
  - `fetch_targets`, `prepare_targets`, `resolve_steps`.
  - Нормализация/ресемплинг target-рядов, согласование тайм-оси.

- `loss.py`
  - Базовые target losses и агрегирование по целям.

- `bijectors.py`
  - Дифференцируемые преобразования constrained параметров.

- `report.py`
  - `CalibrationReport`, fit metrics, uncertainty блоки и CAS persistence helpers.

- `uncertainty_adapter.py`
  - Конвертация калибровочных uncertainty-оценок в `UncertaintyEnvelope`.

## Входы и выходы

Входы (`CalibratorInputs`):
- `CalibrationConfig`, `ProgramGraph`, `ExecPlan`, `base_state`;
- registries (`mechanism`, `slot`, `merge`, optional selector/constraint);
- `parameter_loader` + источник target-данных (UDF engine или custom fetcher).

Выход:
- `CalibrationReport` с параметрами, историей loss/grad, fit quality и диагностикой;
- при успешной Hessian-оценке: covariance/correlation/std и derived uncertainty envelopes.

## Связь с другими директориями

`calibration` зависит от:
- `core/contracts/foundry`, `core/artifacts/*`, `core/observability/*`;
- `ir/analytics/calibration`, `ir/analytics/uncertainty`, `ir/analytics/data_views`;
- `foundry/registry`, `foundry/merge_engine`, `foundry/contracts/state`.

Используется в сценариях подстройки policy-параметров и uncertainty-оценки после симуляции.

## Текущее состояние и ограничения

- Базовый оптимизатор — `optax.adam` (с optional gradient clipping path).
- Калибровка требует дифференцируемый execution path и согласованные shape-и.
- Hessian/Laplace шаг может быть пропущен (нефинитный Hessian, слишком много параметров, плохая обусловленность).
- При включенном constraint penalty обязательны корректные `constraint_registry` + значения ограничений.
