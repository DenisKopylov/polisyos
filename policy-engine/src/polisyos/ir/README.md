# polisyos.ir

`polisyos.ir` — канонический контрактный слой Policy Engine.
Он описывает структуру policy/world/analytics артефактов, правила валидации и линковки, но не исполняет симуляцию.

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

## Что находится в `ir/`

| Подсистема | Назначение | Документация |
|---|---|---|
| `trinity/` | Канонический bundle `ProblemFrame + PolicySpec + ModelSpec` | [`trinity/README.md`](trinity/README.md) |
| `governance/` | Контракты "Why/What" + selectors/schedule/gates | [`governance/README.md`](governance/README.md) |
| `model_spec.py` | Контракт "How" (agents, assumptions, environment, fidelity) | этот файл |
| `kernel/` | Базовые типы, реестры units/slots/mechanisms/merge/metrics | [`kernel/README.md`](kernel/README.md) |
| `registry_fragments.py` | Сборка `RegistryBundle` из фрагментов с конфликт-резолвом | этот файл |
| `linker/` | Валидация Trinity против `RegistryBundle` + `LinkReport` | [`linker/README.md`](linker/README.md) |
| `world/` | Контракты world graph (docs/claims/conflicts/trust/quality/events) | [`world/README.md`](world/README.md) |
| `analytics/` | Контракты аналитических отчётов и CAS-persistence | [`analytics/README.md`](analytics/README.md) |
| `artifacts/` | Унифицированные CAS I/O контракты (`ArtifactID`, `put/get_json`) | [`artifacts/README.md`](artifacts/README.md) |
| `migrations/` | Runtime миграции schema_version для canonical payload | [`migrations/README.md`](migrations/README.md) |
| `norm_pack.py`, `queries.py`, `connectors.py`, `fact_log.py`, `citations.py`, `refs.py` | Юридические/поисковые/данные/ссылочные контракты | эти файлы |

## Актуальный поток (Trinity)

1. Загрузка canonical payload: `load_policy()` / `load_trinity_bundle()`.
2. Сборка registry: `compose_registry_fragments()`.
3. Линковка: `link_trinity(bundle, registries)`.
4. Передача связанного контракта в `foundry`/`core`/`fabric` пайплайны.

## Статус миграций на текущем коде

- Канонический формат policy IR: `TrinityBundle` со `schema_version="1.0"`.
- `migrate_policy_ir()` поддерживает только Trinity payload.
- Зарегистрированная migration-цепочка: `policy_ir 1.0 -> 1.0` (identity).
- Legacy non-Trinity payload (`schema_version` семейства `2.*` или поле `semantic`) runtime-миграцией отклоняется.

## Связи с другими директориями

| Директория | Как использует `ir` |
|---|---|
| `fabric/` | `world/*`, `fact_log`, `citations`, `connectors`, `analytics.uncertainty` |
| `foundry/` | `trinity`, `governance`, `kernel`, `linker`, `analytics.*` |
| `core/` | registry builders, compliance contracts, `LinkReport` сериализация |
| `lex/` | `norm_pack`, world predicates/IDs, corpus structuring |
| `scientist/` | governance gates, trinity preflight, query/analysis контракты |
| `scholar/` | world events/trust contracts в knowledge orchestration |
| `packs/` | поставка registry fragments для compose/link фаз |

## Важные особенности

- Большинство IR-моделей базируются на `KernelModel` (`extra="forbid"`, `frozen=True`).
- Детерминизм обеспечивается через `canon.to_canonical_bytes()` и `content_hash()`.
- `ir.__init__` — lazy facade публичных символов для стабильных импортов.
- Есть два разных `DataViewRequest`:
  - `ir.analytics.data_views.DataViewRequest` — runtime аналитические data-view запросы.
  - `ir.queries.DataViewRequest` — query-контракт доступа к данным.

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
