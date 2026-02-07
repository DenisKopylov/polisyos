# Calibration — градиентная калибровка параметров

Автоматическая калибровка параметров экономических моделей на реальных данных через дифференцируемую оптимизацию (Adam/optax) с constraint penalties, prior regularization и Laplace-approximation uncertainty.

**8 модулей** | **JAX autodiff** | **Bijector-constrained** | **Hessian uncertainty**

## Pipeline

```
CalibratorInputs → preflight (fetch, align, normalize targets)
                 → compile_program (ProgramGraph → StaticBundle)
                 → bijectors (constrained → unconstrained space)
                 → JIT optimization loop (Adam + GradNorm + constraint penalty)
                 → Hessian uncertainty (Laplace approximation)
                 → CalibrationReport + UncertaintyEnvelopes
```

## Calibrator (`calibrator.py`)

Основной класс `Calibrator.run()` — полный pipeline калибровки:

1. **Resolve** — загрузка bundle, targets, constraints, trainable groups
2. **Bijectors** — трансформация в unconstrained пространство
3. **JIT loop** — `optax.adam` с:
   - GradNorm adaptive weight balancing для multi-target loss
   - Constraint penalty (inequality/equality)
   - Prior penalty (regularization)
   - Early stopping с patience
   - Non-finite gradient detection
4. **Hessian** (опционально) — Laplace approximation: ковариационная матрица, condition number, rank deficiency, non-identifiability warnings
5. **Report** — `CalibrationReport` с fit metrics, series comparisons, uncertainty envelopes

`CalibratorInputs` — входные данные: config, program_graph, exec_plan, base_state, registries, parameter_loader, constraints, controls, target_fetcher.

`CalibrationMetricsCollector` — batched OTel-метрики: step duration, loss, grad_norm.

## Pure Executor (`pure_executor.py`)

Side-effect-free исполнение для калибровки — компилирует ProgramGraph в `StaticBundle` для `jax.lax.scan`:

- **compile_program()** — ProgramGraph + ExecPlan → StaticBundle. Парсинг selectors, fidelity modes (relaxed/discrete/hard), temperature injection, trainable parameter discovery
- **StaticBundle** — все статические данные для чистого исполнения (nodes, registries, trainables)
- **apply_trainable_values()** / **extract_trainable_values()** — обновление/извлечение trainable params через `eqx.tree_at`
- **apply_nodes()** — single-step: механизмы → selector masks → merge (SUM/OVERRIDE/PRIORITY/ERROR)
- **run_pure_scan()** — полная симуляция через `jax.lax.scan` → final state + metric traces

## Bijectors (`bijectors.py`)

Дифференцируемые трансформации для constraint handling:

| Bounds | Bijection | Mapping |
|---|---|---|
| Без ограничений | identity | R → R |
| Только lower | `lower + softplus(u)` | R → [lower, +∞) |
| Только upper | `upper - softplus(u)` | R → (−∞, upper] |
| Lower + upper | sigmoid с temperature=0.5 | R → [lower, upper] |

`to_unconstrained()` / `from_unconstrained()` — batch-операции над вектором параметров.

## Loss Functions (`loss.py`)

- `compute_base_loss()` — MSE или Huber loss с relative normalization
- `loss_components()` — декомпозиция на per-target компоненты с weights
- `unified_loss()` — single-call total + per-target loss

## Preflight (`preflight.py`)

Подготовка данных перед калибровкой:

- `fetch_targets()` — загрузка target data из Fabric (UDF engine или custom fetcher)
- `prepare_targets()` — нормализация, resampling (linear interpolation/forward-fill), alignment по длине
- `resolve_steps()` — определение количества шагов калибровки
- `_compute_scale()` — scale для auto-normalization (mean/std/max/p95)

## Report (`report.py`)

Pydantic-модели результатов:

- **CalibrationReport** — calibrated_params, total_loss, per_target_loss, loss_history, grad_norm_history, series_comparison, fit_quality, uncertainties, uncertainty_envelopes, diagnostics
- **CalibrationFitQuality** — per_target и aggregate: MSE, RMSE, MAE, R², N
- **CalibrationUncertainty** — Laplace: params, covariance, correlation, std, damping, hessian_rank, hessian_condition, non_identifiable
- `put_calibration_config()` / `put_calibration_report()` — CAS persistence

## Uncertainty Adapter (`uncertainty_adapter.py`)

Конвертация Hessian-uncertainty в `UncertaintyEnvelope`:

- `envelope_from_calibration_param()` — Normal envelope с z-score CI из std
- `envelopes_from_calibration()` — envelopes для всех параметров в отчете

## Зависимости

- **core/observability** — метрики, трейсинг калибровки
- **core/contracts/foundry** — ProgramGraph, ExecPlan
- **core/artifacts** — CAS persistence отчетов
- **ir/calibration** — CalibrationConfig, targets, TargetLossConfig, trainable params
- **ir/uncertainty** — UncertaintyEnvelope, DistributionFamily
- **foundry/merge_engine** — MergeEngine для apply_nodes
- **foundry/registry** — создание механизмов из спецификаций
- **foundry/domain/state** — GlobalState

## Структура

```
calibration/
├── __init__.py              # Public API
├── calibrator.py            # Calibrator.run() — полный pipeline
├── pure_executor.py         # StaticBundle, compile_program, run_pure_scan
├── bijectors.py             # Differentiable parameter constraints
├── loss.py                  # MSE/Huber loss с per-target decomposition
├── preflight.py             # Target fetching, normalization, alignment
├── report.py                # CalibrationReport, FitQuality, Uncertainty
└── uncertainty_adapter.py   # Hessian → UncertaintyEnvelope conversion
```
