# Calibration (`polisyos.foundry.calibration`)

`calibration` — подсистема data-driven калибровки trainable параметров Foundry-моделей по эмпирическим целям.

Актуально по коду на 2026-03-03.

## Роль в системе

Калибровка работает поверх уже построенных `ProgramGraph` и `ExecPlan`, подбирая параметры механизмов так, чтобы симуляция лучше совпадала с target-данными.

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
to_unconstrained / bijectors / trainable groups
        |
        v
optimization loop (optax, penalties, GradNorm, early stop)
        |
        v
optional Hessian/Laplace uncertainty
        |
        v
CalibrationReport (+ optional uncertainty envelopes)
```

## Ключевые модули

- `calibrator.py`: `Calibrator.run()`, оптимизационный цикл и сбор диагностик/метрик.
- `pure_executor.py`: `compile_program`, `run_pure_scan`, управление trainable handles без CAS IO в loop.
- `preflight.py`: fetch/normalize/align целевых рядов, ресемплинг и согласование временной оси.
- `loss.py`: target losses, веса, относительная нормализация и aggregation.
- `bijectors.py`: constrained/unconstrained преобразования параметров.
- `report.py`: `CalibrationReport` и CAS persistence (`put_calibration_report`).
- `uncertainty_adapter.py`: конвертация Hessian/Laplace результата в `UncertaintyEnvelope`.

## Входы и выходы

Входы (`CalibratorInputs`):

- `CalibrationConfig`, `ProgramGraph`, `ExecPlan`, `base_state`;
- registries (`mechanism`, `slot`, `merge`, optional selector/constraint);
- `parameter_loader` и источник target-данных (UDF engine или custom fetcher).

Выход:

- `CalibrationReport` с параметрами, history loss/grad, fit quality и diagnostics;
- при успешной Hessian-оценке: covariance/correlation/std и derived uncertainty envelopes.

## Связь с другими директориями

`calibration` зависит от:

- `foundry/registry`, `foundry/merge_engine`, `foundry/contracts/state`;
- `core/artifacts/*`, `core/observability/*`, `core/contracts/foundry`;
- `ir/analytics/calibration`, `ir/analytics/uncertainty`, `ir/analytics/data_views`.

Используется в сценариях подстройки policy-параметров и uncertainty-оценки после симуляции.

## Текущее состояние и ограничения

- Базовый оптимизатор: `optax.adam` (с optional gradient clipping chain).
- Корректность зависит от дифференцируемости execution path и согласованных shape-ов.
- Hessian/Laplace шаг может быть пропущен при плохой обусловленности или слишком большом числе параметров.
- При включенном constraint penalty обязателен валидный `constraint_registry` и значения ограничений.
