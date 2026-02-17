# Foundry Tests

`tests/foundry` покрывает simulation layer `polisyos.foundry`: compile/execute контур, methods ecosystem, calibrators и числовые инварианты.

Актуально на **17 февраля 2026**.

## Состав

- `67` файлов `test_*.py`
- `1` `README.md`
- `1` `conftest.py` (в `methods/`)

## Структура

| Подкаталог | `test_*.py` | Что покрывает |
|---|---:|---|
| `foundry/` (корень) | 36 | compile/execute фасады, determinism, numerics, agent simulation steps |
| `foundry/methods/` | 28 | registry/protocol/compiler/linker + catalog/backends |
| `foundry/agent_sim/` | 1 | monitoring visual outputs |
| `foundry/analysis/` | 1 | distributional analysis |
| `foundry/plugins/` | 1 | plugin system |

## Ключевые зоны

- Runtime контур: `test_compile_facade.py`, `test_execute_*`, `test_runtime_batch.py`.
- Safety boundaries: `test_no_io_kernel.py`, `test_no_compat_facade_imports.py`, `test_no_foundry_domain_imports.py`.
- Calibration/uncertainty: `test_calibrator_*.py`, `test_calibration_uncertainty_adapter.py`, `test_uncertainty_propagation.py`.
- Determinism/numerics: `test_compile_determinism.py`, `test_merge_determinism.py`, `test_nan_guard.py`, `test_jit_*`, `test_gradients.py`.
- Agent workflow: `test_agent_simulation_step1.py` ... `test_agent_simulation_step6.py`, `test_patch_executor.py`, `test_global_state.py`.

## Связи с кодом

- `policy-engine/src/polisyos/foundry`
- `policy-engine/src/polisyos/core`
- `policy-engine/src/polisyos/ir`

## Запуск

```bash
pytest tests/foundry -q
pytest tests/foundry/methods -q

# горячие проверки
pytest tests/foundry/test_execute_input_bindings.py -q
pytest tests/foundry/test_calibrator_mvp.py -q
pytest tests/foundry/test_merge_determinism.py -q
```
