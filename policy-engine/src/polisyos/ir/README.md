# polisyos.ir — Canonical Intermediate Representation

`polisyos.ir` — это канонический слой контрактов Policy Engine: типизированные схемы, валидация, линковка и детерминированная сериализация артефактов.

Главная идея: IR описывает **что** такое корректная политика/мир/отчёт, но не исполняет симуляции сам.

## Роль в системе

```text
Scholar / Scientist / Lex
          │ формируют и читают контракты
          ▼
    polisyos.ir (schemas + validation + linking)
          │
          ├─► Foundry (compile/execute Trinity)
          ├─► Fabric  (world/facts/citations contracts)
          └─► Core    (registry/contract wiring)
```

IR не зависит от `polisyos.core` (проверяется тестами), поэтому остаётся независимым контрактным слоем между подсистемами.

## Что внутри директории `ir/`

```text
ir/
├── __init__.py              # lazy re-export публичных символов
├── trinity/                 # TrinityBundle + strict loaders
├── governance/              # ProblemFrame / PolicySpec / selectors / schedule / gates
├── model_spec.py            # ModelSpec ("How")
├── analytics/               # uncertainty, causal, hte, distributional, backtest, calibration
├── kernel/                  # базовые типы и реестры (units, slots, mechanisms, metrics, ...)
├── world/                   # семантическая модель world graph (claims/docs/events/conflicts/trust)
├── linker/                  # link_trinity + LinkReport/LinkIssue
├── migrations/              # миграции версий schema_version
├── artifacts/               # IR-контракты CAS I/O (ArtifactID, put/get JSON)
├── registry_fragments.py    # сборка RegistryBundle из фрагментов с конфликт-резолвом
├── connectors.py            # контракты внешних источников и fetch-результатов
├── queries.py               # контракты query layer (DocQuery, ClaimQuery, NormQuery, ...)
├── fact_log.py              # Fact / FactBatch / FactSegmentManifest
├── citations.py             # CitationRef / DocumentRef / FragmentLocator
├── refs.py                  # typed artifact refs для аналитических отчётов
├── canon.py                 # canonical JSON + content hash
└── ...                      # norm_pack, portfolio, predicate, units, migration_report
```

## Архитектура по подсистемам

### 1. Trinity-контракты (центр IR)

- `trinity/` — `TrinityBundle` (ProblemFrame + PolicySpec + ModelSpec), `schema_version`.
- `governance/problem_frame.py` — формализация задачи: objectives, KPI, constraints, stakeholders.
- `governance/policy_spec.py` — интервенции, mechanism bindings, параметры, selectors, расписание.
- `model_spec.py` — модель мира для симуляции: assumptions, agent config, environment, fidelity.

Ключевая особенность: `PolicySpec` валидирует сложность selector AST (`MAX_SELECTOR_DEPTH=10`, `MAX_SELECTOR_NODES=50`).

### 2. Registry/kernel-слой

- `kernel/` — базовые типы и реестры (`MechanismTypeRegistry`, `SlotRegistry`, `UnitsRegistry`, `MetricRegistry`, `ConstraintRegistry`, ...).
- `registry_fragments.py` — композиция `RegistryBundle` из фрагментов с политиками:
  - `error_on_conflict`
  - `prefer_higher_priority`
- `predicate.py` — registry предикатов и privacy-политик.
- `units.py` — compatibility re-export над `kernel.units`.

Подробнее: [`kernel/README.md`](kernel/README.md)

### 3. Семантика мира и данные

- `world/` — graph ABI, `Claim`, `DocFragment`, `WorldEvent`, `ConflictSet`, `QualityReport`, `TrustAssessment`, deterministic world IDs.
- `fact_log.py` — immutable факт-лог и сегменты.
- `citations.py` — citation-grade привязка к фрагментам документов.
- `connectors.py` — fetch-контракты, capabilities, trust/quality tiers.
- `queries.py` — typed query-контракты для docs/claims/norms/data views.

Подробнее: [`world/README.md`](world/README.md)

### 4. Аналитические отчёты и uncertainty

`analytics/` содержит контракты отчётов и CAS I/O-функции (`persist_*`, `load_*`):

- `uncertainty.py` — `UncertaintyEnvelope`
- `causal.py` — `CausalEffectReport`
- `hte.py` — `HTEResult`, `PolicyRecommendation`
- `distributional.py` — winners/losers и breakdowns
- `backtest.py` — retrospective quality reports
- `calibration.py` — `CalibrationConfig` и таргеты калибровки
- `applicability.py` — `NormApplicability`
- `data_views.py` — runtime-запросы аналитических data views

### 5. Линковка, загрузка, миграции

- `linker/` — связывает Trinity с registry bundle:
  - проверка механизмов/параметров/слотов/units/metrics/merge-rules
  - возвращает `LinkedTrinityBundle` + `LinkReport` (типизированные `LinkIssueCode`)
- `loaders.py` — удобная загрузка payload в `TrinityBundle`.
- `trinity/loaders.py` — строгие загрузчики по артефактам (включая проверку `schema_version`).
- `migrations/` — registry миграций версии schema.

## Текущий статус миграций (актуально для текущего кода)

- Канонический формат — Trinity (`schema_version` семейства `1.x`).
- `migrate_policy_ir` работает только для Trinity payloads.
- Текущая зарегистрированная миграция `policy_ir 1.0 -> 1.0` — identity.
- Legacy surface payloads runtime-миграцией не поддерживаются.

## Связь с другими директориями проекта

| Директория | Как использует `polisyos.ir` |
|---|---|
| `fabric/` | `world/*`, `fact_log`, `citations`, `connectors`, `analytics.uncertainty` |
| `foundry/` | `trinity`, `governance`, `kernel`, `linker`, `analytics.*` |
| `scientist/` | `analytics.*`, `queries`, `connectors`, `world` |
| `lex/` | `norm_pack`, `NormApplicability`, governance-контракты |
| `core/` | kernel registries, `registry_fragments`, `LinkReport` |
| `packs/` | `RegistryFragment*`, `NormPack` и domain-расширения |

## Важные особенности модуля

- Иммутабельность и strict-схемы: в большинстве контрактов `extra="forbid"`; kernel-модели frozen.
- Детерминизм: `canon.to_canonical_bytes()` + `content_hash()` для стабильных ID.
- Typed artifact refs: `refs.py` и `artifacts/` стандартизируют I/O с CAS.
- Lazy API-фасад: `ir/__init__.py` сохраняет стабильные импорты через отложенную загрузку.
- Разделение уровней:
  - `analytics.data_views.DataViewRequest` — runtime-аналитический контракт
  - `queries.DataViewRequest` — query-контракт доступа к данным

## Основные входные точки API

```python
from polisyos.ir.loaders import load_policy
from polisyos.ir.linker import link_trinity
from polisyos.ir.registry_fragments import compose_registry_fragments
from polisyos.ir.trinity import TrinityBundle
```

## Рекомендуемые проверки

```bash
pytest policy-engine/tests/ir
pytest policy-engine/tests/contract/test_trinity_contracts.py
pytest policy-engine/tests/contract/test_trinity_linker_contract.py
pytest policy-engine/tests/contract/test_ir_migrations.py
```
