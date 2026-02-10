# Policy Engine — Tests

Тестовый контур `policy-engine/tests` проверяет архитектурные границы, контракты и поведение всех ключевых слоёв `polisyos`.

Актуально на **10 февраля 2026**.

## Роль в системе

- Защищает слоистую архитектуру и публичные API (`import gate`, фасады, component discovery).
- Проверяет контрактную совместимость (IR/ABI/миграции) и целостность артефактов.
- Валидирует вычислительные и оркестрационные контуры (Fabric, Foundry, Scientist, Runtime).
- Фиксирует регрессии производительности и технические cutover-инварианты.

## Архитектурное покрытие

Базовый стек покрывается зеркально структуре исходного кода:

```text
core -> runtime -> ir -> fabric -> foundry -> scientist
```

Дополнительно проверяются:

- `contract/`: cross-layer контракты и ABI-совместимость.
- `lint/`: архитектурные и migration-гейты через линтеры.
- `performance/`: benchmark-baseline регрессии.
- `integration/`: сквозные сценарии уровня runtime/governance.

## Снимок структуры

По текущему дереву:

- `270` файлов `test_*.py`
- `283` Python-файла в каталоге тестов (включая `conftest.py` и утилиты)
- `9` файлов `conftest.py`
- `7` файлов `README.md`

| Каталог | `test_*.py` | Основная зона ответственности |
|---|---:|---|
| корень `tests/` | 6 | Архитектурные гейты, фасады API, component/packs discovery, semver/bridge |
| `contract/` | 18 | Контракты Trinity/IR, ABI diff, миграции, SLO и gate models |
| `core/` | 51 | Phase0 primitives, security, component contracts, базовые registry/pipeline проверки |
| `fabric/` | 46 | Data fabric: catalog, connectors, provenance, trust, world/materialization, claims/scholar |
| `foundry/` | 65 | Simulation engine, methods framework, calibration, agent simulation, determinism/numerics |
| `scientist/` | 58 | Orchestration, governance passes, search/DOE, engine workflow, decision artifacts |
| `runtime/` | 10 | Replay/completeness, runtime HTTP API, run timeline/debug/artifact inspection |
| `ir/` | 10 | Loaders, registry fragments, uncertainty, policy portfolio/query contracts |
| `lex/` | 3 | Симулятор норм: diff/mutator/engine |
| `integration/` | 1 | Human-gate audit и trace-события (`GATE_REQUESTED`, `GATE_DECIDED`) |
| `lint/` | 1 | Legacy cutover lint gate |
| `performance/` | 1 | Baseline-бенчмарки для simulation/CAS/calibration |

## Особенности модулей

### Корневые гейты (`tests/test_*.py`)

- `test_arch_import_gate.py` запускает `tools/lint/lint_imports.py` с `import_policy.toml` и `import_exceptions.toml`.
- `test_public_api_facades.py` требует curated `__all__` и запрещает `from ... import *` в корневых фасадах `src/polisyos/*`.
- `test_components_*` и `test_packs_discovery.py` проверяют entry-point/dev-scan discovery, bridge в method registry и semver-политику компонентов.

### Runtime HTTP (`tests/runtime/http/`)

- Покрываются endpoints: runs, timeline, nodes, lineage, artifact inspector, debug.
- Есть security-ветка с tenant/cell/authz проверками (`test_runtime_api_authz.py`).
- Тесты защищают контракт: `source_kind == "core_run"` и отсутствие legacy-source в payload/OpenAPI.

### Fabric/Foundry/Scientist

- Самые объёмные зоны (`fabric`, `foundry`, `scientist`) покрывают data ingestion, simulation, orchestration и governance.
- Для подробностей сохранены отдельные README:
  - `policy-engine/tests/fabric/README.md`
  - `policy-engine/tests/foundry/README.md`
  - `policy-engine/tests/scientist/README.md`

### Контрактный и базовый слой

- `contract/` фиксирует стабильность схем и ABI, включая golden-record проверки.
- `core/phase0/` концентрируется на CAS, signing, canonical JSON, observability и run-context.
- Подробные справки:
  - `policy-engine/tests/contract/README.md`
  - `policy-engine/tests/core/phase0/README.md`

## Связь с другими директориями проекта

| Здесь | Связанный код/ресурс | Как связаны |
|---|---|---|
| `tests/core/`, `tests/contract/`, `tests/ir/` | `policy-engine/src/polisyos/core`, `policy-engine/src/polisyos/ir` | Контракты, артефакты, загрузка/миграции IR |
| `tests/fabric/` | `policy-engine/src/polisyos/fabric`, `policy-engine/src/polisyos/scholar`, `policy-engine/src/polisyos/lex` | Data pipelines, trust/provenance, world query, scholar/lex интеграции |
| `tests/foundry/` | `policy-engine/src/polisyos/foundry` | Runtime исполнения, методы, calibration, numerical invariants |
| `tests/scientist/` | `policy-engine/src/polisyos/scientist`, `policy-engine/src/polisyos/runtime` | Engine workflows, governance passes, search, packet/report artifacts |
| `tests/test_arch_import_gate.py`, `tests/lint/` | `policy-engine/tools/lint/*`, `policy-engine/import_policy.toml` | Линт-гейты архитектуры и cutover-правил |
| `tests/test_packs_discovery.py` | `policy-engine/src/polisyos/packs/*` | Проверка discovery пакетов через dev-scan и entry points |

## Тестовая инфраструктура

### Глобальная конфигурация

`policy-engine/tests/conftest.py`:

- добавляет `policy-engine/src` в `sys.path`;
- форсирует CPU для JAX-тестов (`JAX_PLATFORMS=cpu`, `XLA_PYTHON_CLIENT_PREALLOCATE=false`);
- снижает шум логов до уровня `ERROR`.

### Специализированные `conftest.py`

- `policy-engine/tests/contract/conftest.py`
- `policy-engine/tests/core/phase0/conftest.py`
- `policy-engine/tests/fabric/connectors/conftest.py`
- `policy-engine/tests/foundry/methods/conftest.py`
- `policy-engine/tests/runtime/http/conftest.py`
- `policy-engine/tests/scientist/conftest.py`
- `policy-engine/tests/scientist/search/conftest.py`
- `policy-engine/tests/scientist/search/strategies/conftest.py`

### Маркеры и optional зависимости

- В `pyproject.toml` объявлен маркер: `integration`.
- Часть тестов помечена `@pytest.mark.integration` (например, `scientist/integration`, connector reference integration).
- Некоторые сценарии условные и `skip`-ятся без optional библиотек (`fastapi`, `PyJWT`, `aiohttp`, `duckdb`, `kuzu`, `linearmodels`, `statsmodels`, `econml` и др.).
- Для части scientist integration-тестов требуется `POLISYOS_RUN_INTEGRATION=1`.

## Запуск

Команды выполняются из `policy-engine/`.

```bash
# весь тестовый контур
pytest

# быстрый цикл без integration-маркера
pytest -m "not integration"

# по слоям
pytest tests/contract -q
pytest tests/fabric -q
pytest tests/foundry -q
pytest tests/scientist -q
pytest tests/runtime -q

# integration-подмножество scientist
POLISYOS_RUN_INTEGRATION=1 pytest tests/scientist/integration -q

# performance baseline checks
pytest tests/performance/test_overhead.py -q
```
