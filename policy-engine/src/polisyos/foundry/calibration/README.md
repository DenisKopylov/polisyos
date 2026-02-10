# Calibration (`polisyos.foundry.calibration`)

`calibration` - подсистема градиентной калибровки параметров Foundry-моделей на эмпирических целях.

Актуально по коду на 2026-02-10.

## Роль в системе

Калибровка работает поверх уже скомпилированной программы (`ProgramGraph` + `ExecPlan`) и подбирает trainable-параметры так, чтобы симуляция согласовывалась с target-данными.

## Pipeline

```
CalibrationConfig + ProgramGraph/ExecPlan + base_state + registries
        |
        v
preflight (fetch/normalize/align targets)
        |
        v
compile_program -> StaticBundle (pure execution)
        |
        v
bijectors (constrained <-> unconstrained params)
        |
        v
optimization loop (Adam + GradNorm balancing + penalties + early stop)
        |
        v
optional Hessian/Laplace uncertainty
        |
        v
CalibrationReport (+ optional UncertaintyEnvelopes)
```

## Ключевые модули

- `calibrator.py`
  - `Calibrator.run()` - основной pipeline.
  - Поддерживает target losses, adaptive weights (GradNorm), constraint penalties, prior penalties, early stopping, optional Hessian stage.

- `pure_executor.py`
  - `compile_program()` собирает `StaticBundle` без CAS-зависимостей внутри цикла оптимизации.
  - `run_pure_scan()` выполняет симуляцию через `jax.lax.scan`.
  - `apply_trainable_values()`/`extract_trainable_values()` управляют trainable-параметрами.

- `preflight.py`
  - загрузка/подготовка target-рядов (`fetch_targets`, `prepare_targets`, `resolve_steps`).

- `loss.py`
  - базовые и агрегированные target loss-функции (MSE/Huber, per-target decomposition).

- `bijectors.py`
  - дифференцируемые преобразования для bounded параметров.

- `report.py`
  - контракты `CalibrationReport`, fit metrics, uncertainty-блоки и CAS persistence helpers.

- `uncertainty_adapter.py`
  - конвертация результатов калибровки в `UncertaintyEnvelope`.

## Входы и выходы

Входы (`CalibratorInputs`):
- `CalibrationConfig`, `ProgramGraph`, `ExecPlan`, `base_state`;
- registries (`mechanism`, `slot`, `merge`, optional selector/constraint);
- parameter loader, target source (UDF engine или custom fetcher).

Выход:
- `CalibrationReport` с калиброванными параметрами, историей loss/grad и диагностикой.
- При успешной Hessian-оценке: covariance/correlation/std + envelope-представление.

## Связь с другими директориями

`calibration` зависит от:
- `core/contracts/foundry` и `core/artifacts/*`;
- `ir/analytics/calibration`, `ir/analytics/uncertainty`, `ir/analytics/data_views`;
- `foundry/registry`, `foundry/merge_engine`, `foundry/contracts/state`.

Используется в сценариях симуляции/оценки, где требуется data-driven подстройка параметров и uncertainty-оценка.

## Текущее состояние и ограничения

- Оптимизация реализована через `optax.adam`.
- Калибровка предполагает дифференцируемый путь исполнения и стабильные shape-и.
- Hessian/Laplace шаг может быть пропущен (например, при слишком большом числе параметров или non-finite Hessian).
- Если включен constraint penalty, обязательны согласованные `constraint_registry` и значения ограничений.
