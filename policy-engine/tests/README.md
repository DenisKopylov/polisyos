# Policy Engine - Tests

Тестовый контур `policy-engine/tests` фиксирует архитектурные границы, контракты данных и рабочие сценарии всех ключевых слоев `polisyos`.

Актуально на **11 марта 2026**.

## Роль в системе

- Защита архитектуры: import gates, фасады API, component discovery, semver-политика.
- Контрактная совместимость: IR/ABI, migration safety, canonical serialization.
- Проверка исполнения: Foundry runtime, Scientist workflows, Runtime HTTP API.
- Feedback loop: degraded backtesting semantics, semantic data revision diff, post-deployment refutation, run compare и reissue.
- Контроль качества данных и интеграций: Fabric connectors/data plane, Lex pipelines.

## Быстрая карта покрытия

- Всего: `416` файлов `test_*.py`.
- Крупные зоны:

| Каталог | `test_*.py` | Что покрывает |
|---|---:|---|
| `tests/core` | 53 | Базовые примитивы, security, contracts/components |
| `tests/fabric` | 64 | Data fabric, connectors, provenance/trust, world/data plane, semantic historical diff |
| `tests/foundry` | 85 | Compile/execute, methods framework, calibration, determinism, execution-time overrides |
| `tests/scientist` | 83 | Workflow engine, governance passes, search/DOE, decision feedback loop |
| `tests/contract` | 18 | Cross-layer контракты, ABI diff, golden records |
| `tests/runtime` | 18 | Replay/manifest, runtime HTTP API и feedback/reissue surfaces |
| `tests/ir` | 25 | IR loaders/migrations, registry fragments, uncertainty, analytics contracts |
| `tests/lex` | 19 | Batch pipeline и norm simulator |
| `tests/integration` | 2 | Сквозной human-gate audit |
| `tests/lint` | 1 | Legacy cutover lint gate |
| `tests/performance` | 1 | Benchmark-baseline regressions |

## Архитектурная логика тестов

```text
core -> ir -> fabric -> foundry -> scientist -> runtime
```

Поперечные контуры:
- `contract/` проверяет типизированные границы между слоями.
- `lint/` и `test_arch_import_gate.py` защищают архитектурные правила.
- `integration/` и `performance/` закрывают сквозные и регрессионные риски.

## README по крупным подпапкам

- `policy-engine/tests/contract/README.md`
- `policy-engine/tests/core/README.md`
- `policy-engine/tests/core/phase0/README.md`
- `policy-engine/tests/fabric/README.md`
- `policy-engine/tests/foundry/README.md`
- `policy-engine/tests/scientist/README.md`
- `policy-engine/tests/runtime/README.md`
- `policy-engine/tests/ir/README.md`
- `policy-engine/tests/lex/README.md`
- `policy-engine/tests/integration/README.md`
- `policy-engine/tests/TESTING_POLICY.md`
- `policy-engine/tests/FIXTURE_CATALOG.md`
- `policy-engine/tests/quarantine.toml`

## Инфраструктура тестов

`tests/conftest.py`:

- добавляет `policy-engine/src` в `sys.path`;
- форсирует CPU-режим для JAX-тестов:
  - `JAX_PLATFORMS=cpu`
  - `JAX_PLATFORM_NAME=cpu`
  - `XLA_PYTHON_CLIENT_PREALLOCATE=false`
- уменьшает шум логов до `ERROR`.

В `pyproject.toml` объявлен маркер `integration`.
Phase 4 добавляет полную taxonomy/marker policy:

- primary classes: `unit`, `contract`, `property`, `integration`, `performance`;
- execution semantics: `smoke`, `slow`, `flaky`, `quarantine`;
- quarantined pytest-tests читаются из `tests/quarantine.toml` и по умолчанию не гейтят прогон;
- path-based auto-classification применяется в `tests/conftest.py`.

## Запуск

Команды выполняются из `policy-engine/`:

```bash
# полный прогон
pytest

# быстрый цикл без integration/performance/quarantine
pytest -m "not integration and not performance and not quarantine" --ignore=tests/runtime/http

# taxonomy slices
pytest -m contract
pytest -m property
pytest -m integration --ignore=tests/runtime/http
pytest -m performance
pytest tests/runtime/http -m "not quarantine"

# локальный smoke stack для backend + dashboard
uv run python tools/testing/local_integration_stack.py up
uv run python tools/testing/local_integration_stack.py smoke
```
