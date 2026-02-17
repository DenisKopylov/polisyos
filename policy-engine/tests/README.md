# Policy Engine - Tests

Тестовый контур `policy-engine/tests` фиксирует архитектурные границы, контракты данных и рабочие сценарии всех ключевых слоев `polisyos`.

Актуально на **17 февраля 2026**.

## Роль в системе

- Защита архитектуры: import gates, фасады API, component discovery, semver-политика.
- Контрактная совместимость: IR/ABI, migration safety, canonical serialization.
- Проверка исполнения: Foundry runtime, Scientist workflows, Runtime HTTP API.
- Контроль качества данных и интеграций: Fabric connectors/data plane, Lex pipelines.

## Быстрая карта покрытия

- Всего: `302` файлов `test_*.py`.
- Крупные зоны:

| Каталог | `test_*.py` | Что покрывает |
|---|---:|---|
| `tests/core` | 52 | Базовые примитивы, security, contracts/components |
| `tests/fabric` | 62 | Data fabric, connectors, provenance/trust, world/data plane |
| `tests/foundry` | 67 | Compile/execute, methods framework, calibration, determinism |
| `tests/scientist` | 60 | Workflow engine, governance passes, search/DOE |
| `tests/contract` | 18 | Cross-layer контракты, ABI diff, golden records |
| `tests/runtime` | 15 | Replay/manifest и runtime HTTP API |
| `tests/ir` | 10 | IR loaders/migrations, registry fragments, uncertainty |
| `tests/lex` | 9 | Batch pipeline и norm simulator |
| `tests/integration` | 1 | Сквозной human-gate audit |
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

## Инфраструктура тестов

`tests/conftest.py`:

- добавляет `policy-engine/src` в `sys.path`;
- форсирует CPU-режим для JAX-тестов:
  - `JAX_PLATFORMS=cpu`
  - `JAX_PLATFORM_NAME=cpu`
  - `XLA_PYTHON_CLIENT_PREALLOCATE=false`
- уменьшает шум логов до `ERROR`.

В `pyproject.toml` объявлен маркер `integration`.

## Запуск

Команды выполняются из `policy-engine/`:

```bash
# полный прогон
pytest

# быстрый цикл без integration
pytest -m "not integration"

# по основным зонам
pytest tests/core -q
pytest tests/fabric -q
pytest tests/foundry -q
pytest tests/scientist -q
pytest tests/runtime -q
pytest tests/contract -q

# точечные контуры
pytest tests/performance/test_overhead.py -q
pytest tests/lint/test_legacy_cutover_lint.py -q
```
