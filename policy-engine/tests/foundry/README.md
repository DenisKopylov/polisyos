# Foundry Tests

`tests/foundry` покрывает simulation layer `polisyos.foundry`: компиляцию/исполнение, calibrators, methods framework и числовые инварианты.

Актуально на **10 февраля 2026**.

## Роль в системе

- Проверяет корректность runtime исполнения программ и фасадов Foundry.
- Валидирует калибровку, uncertainty propagation, deterministic behavior и no-I/O границы.
- Тестирует methods ecosystem (registry, compiler, linker, catalog registrations).
- Закрывает agent simulation, plugin и distributional analysis подсистемы.

## Снимок структуры

- `65` файлов `test_*.py`
- `66` Python-файлов
- `1` `conftest.py` (в `methods/`)
- `1` `README.md`

| Подкаталог | `test_*.py` | Зона ответственности |
|---|---:|---|
| корень `foundry/` | 34 | Runtime/compile/execute фасады, calibrators, agent steps, determinism/numerics |
| `methods/` | 28 | Methods framework + catalog/backends |
| `agent_sim/` | 1 | Monitoring визуализация/метрики |
| `analysis/` | 1 | Distributional metrics |
| `plugins/` | 1 | Plugin system |

## Ключевые модули

### Runtime/compile/execute контур

- `test_compile_facade.py`, `test_execute_facade_smoke.py`, `test_execute_input_bindings.py`
- `test_execute_requires_input_bindings_ref.py`
- `test_no_compat_facade_imports.py`, `test_no_foundry_domain_imports.py`
- `test_no_io_kernel.py`

### Calibrators и uncertainty

- `test_calibrator_mvp.py`, `test_calibrator_fidelity.py`
- `test_calibration_uncertainty_adapter.py`
- `test_uncertainty_propagation.py`

### Agent simulation и state эволюция

- `test_agent_simulation_step1.py` ... `test_agent_simulation_step6.py`
- `test_adaptive_agents.py`, `test_agent_artifact.py`
- `test_global_state.py`, `test_patch_executor.py`

### Числовая устойчивость и детерминизм

- `test_gradients.py`, `test_nan_guard.py`, `test_jit_stability.py`, `test_jit_compilation_tracker.py`
- `test_merge_determinism.py`, `test_compile_determinism.py`, `test_runtime_batch.py`
- `test_conflict_detection.py`, `test_constraints_executor.py`, `test_cost_model.py`, `test_health.py`, `test_fiscal.py`, `test_program_graph_ops.py`

### Methods framework (`foundry/methods/`)

- Core: `test_protocol.py`, `test_registry.py`, `test_compiler.py`, `test_linker.py`, `test_discovery.py`, `test_composer.py`, `test_artifacts.py`, `test_types.py`, `test_base.py`, `test_testing_infra.py`, `test_metadata_assumptions.py`, `test_components_bootstrap_adapter.py`
- Backends: `backends/test_backends.py`
- Catalog/causal: `test_did.py`, `test_rdd.py`, `test_scm.py`, `test_structural_time_series.py`, `test_hte_methods.py`, `test_protocols.py`, `test_registration.py`
- Catalog/econometrics: `test_iv.py`, `test_panel.py`, `test_timeseries.py`, `test_protocols.py`, `test_registration.py`
- Catalog/optimization: `test_methods.py`, `test_protocols.py`, `test_registration.py`

## Инфраструктура тестов

### `methods/conftest.py`

- Форсирует JAX-настройки для стабильных прогонов:
  - `JAX_PLATFORM_NAME=cpu`
  - `XLA_PYTHON_CLIENT_PREALLOCATE=false`
  - `JAX_ENABLE_X64=true`
- Предоставляет типовые fixtures для signatures/slots/units/params и testing-infra (`GoldenStore`, sample state/params).

### Optional зависимости

Часть тестов условная:

- `econml` (HTE)
- `linearmodels` (IV/panel)
- `statsmodels` (time series/STS)
- `matplotlib`, `plotly` (agent monitoring visual outputs)
- solver backend (часть optimization tests)

## Связи с другими директориями

| Здесь | Связанные директории | Назначение связи |
|---|---|---|
| `tests/foundry/` | `src/polisyos/foundry` | Основной объект тестирования |
| `tests/foundry/` | `src/polisyos/core` | Артефакты, контракты, базовые типы |
| `tests/foundry/` | `src/polisyos/ir` | Связки compile/runtime с IR объектами |

## Запуск

Команды из `policy-engine/`:

```bash
# весь foundry-контур
pytest tests/foundry -q

# methods framework
pytest tests/foundry/methods -q

# runtime/calibration
pytest tests/foundry/test_compile_facade.py -q
pytest tests/foundry/test_execute_input_bindings.py -q
pytest tests/foundry/test_calibrator_mvp.py -q

# numerics/determinism
pytest tests/foundry/test_gradients.py -q
pytest tests/foundry/test_merge_determinism.py -q
pytest tests/foundry/test_nan_guard.py -q
```
