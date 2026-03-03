# polisyos.ir

`polisyos.ir` — канонический контрактный слой Policy Engine.
Пакет фиксирует схемы policy/world/analytics артефактов, валидацию, связывание с registry и правила детерминированной сериализации. Выполнение симуляции находится вне `ir`.

## Роль в системе

```text
Lex / Scholar / Scientist / Packs
            │
            ▼
     polisyos.ir (contracts)
            │
            ├─► core (registry/compliance/report adapters)
            ├─► foundry (execution + uncertainty)
            └─► fabric (world ingest/materialization)
```

## Структура директории

| Подсистема | Роль | Документация |
|---|---|---|
| `trinity/` | Канонический payload `ProblemFrame + PolicySpec + ModelSpec` (`TrinityBundle`) | [`trinity/README.md`](trinity/README.md) |
| `governance/` | Контракты `ProblemFrame`, `PolicySpec`, selectors/schedule/gates | [`governance/README.md`](governance/README.md) |
| `model_spec.py` | Контракт `ModelSpec` ("How": агенты, среда, assumptions, fidelity) | этот файл |
| `kernel/` | Базовые типы и registry-ядро (units/slots/mechanisms/merge/metrics/constraints/selector_fields) | [`kernel/README.md`](kernel/README.md) |
| `registry_fragments.py` | `RegistryBundle` и детерминированная композиция fragment-ов | этот файл |
| `linker/` | Линковка Trinity к registry + `LinkReport` + `LinkedTrinityBundle` | [`linker/README.md`](linker/README.md) |
| `world/` | Контракты world graph (doc/claim/conflict/event/trust/quality + deterministic IDs) | [`world/README.md`](world/README.md) |
| `analytics/` | Контракты аналитики (causal/uncertainty/hte/distribution/backtest/transport и др.) | [`analytics/README.md`](analytics/README.md) |
| `artifacts/` | Унифицированный CAS I/O слой (`ArtifactID`, `ArtifactStore`, `put/get_json_artifact`) | [`artifacts/README.md`](artifacts/README.md) |
| `migrations/` | Runtime-миграции версий canonical policy IR payload | [`migrations/README.md`](migrations/README.md) |
| `norm_pack.py`, `queries.py`, `connectors.py`, `fact_log.py`, `citations.py`, `refs.py` | Доменные и интеграционные контракты (norm/query/source refs/facts/citations) | эти файлы |

## Актуальный поток Trinity

1. `load_policy()` или `load_trinity_bundle()` нормализуют `dict/str/bytes` и валидируют `TrinityBundle`.
2. `compose_registry_fragments(RegistryComposeRequest)` собирает `RegistryBundle` из fragment-ов.
3. `link_trinity(bundle, registries, ...)` строит bindings и `LinkReport`.
4. Связанный bundle передаётся в `foundry`, `core` и `fabric` пайплайны.

## Текущее состояние миграций

- Канонический policy IR: `TrinityBundle`, `schema_version="1.0"`.
- `migrate_policy_ir()` обслуживает только Trinity-формат.
- Зарегистрированная цепочка миграции: `policy_ir 1.0 -> 1.0` (identity через `TrinityBundle.model_validate`).
- Legacy non-Trinity payload (`schema_version` семейства `2.*` или наличие поля `semantic`) отклоняется.

## Ключевые особенности

- Большинство контрактов основаны на `KernelModel` (`extra="forbid"`, `frozen=True`).
- Канонизация и хэширование выполняются через `canon.to_canonical_bytes()` и `canon.content_hash()`.
- Для float-heavy аналитических отчётов persist-функции обычно используют `CanonSpec(forbid_floats=False)`.
- `ir.__init__` — lazy facade для стабильных публичных импортов.
- В коде есть два разных `DataViewRequest`:
  - `ir.analytics.data_views.DataViewRequest` — runtime аналитические data-view запросы;
  - `ir.queries.DataViewRequest` — query-layer контракт доступа к данным.

## Связи с соседними директориями

| Директория | Использование `ir` |
|---|---|
| `fabric/` | `world/*`, `fact_log`, `citations`, `connectors`, часть `analytics` контрактов |
| `foundry/` | `trinity`, `governance`, `kernel`, `linker`, `analytics.*` |
| `core/` | сборка registry, компиляция и сериализация `LinkReport` |
| `lex/` | `norm_pack`, world predicates/ids, corpus structuring |
| `scientist/` | governance gates, trinity preflight, causal/analytics контракты |
| `scholar/` | world events/trust/quality в orchestration |
| `packs/` | поставка registry fragment-ов для compose/link стадий |

## Базовые точки входа

```python
from polisyos.ir.loaders import load_policy
from polisyos.ir.registry_fragments import compose_registry_fragments
from polisyos.ir.linker import link_trinity
```

## Проверки

```bash
pytest /Users/deniskopylov/polisyos/policy-engine/tests/ir
pytest /Users/deniskopylov/polisyos/policy-engine/tests/contract/test_trinity_contracts.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/contract/test_trinity_linker_contract.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/contract/test_ir_migrations.py
```
