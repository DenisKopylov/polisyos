# polisyos.ir — Intermediate Representation

Каноническое промежуточное представление политик Policy Engine. IR определяет все типы данных, контракты и спецификации, которые используются остальными модулями системы — от формулировки задачи до результатов каузального анализа.

62 Python-файла, 4 подсистемы с собственными пакетами.

## Роль в системе

IR — центральный пакет типов. Он не содержит логики исполнения, только **декларативные модели** (Pydantic, `frozen=True`, `extra="forbid"`) и функции загрузки/валидации. Все runtime-модули (Foundry, Scientist, Lex, Fabric) импортируют контракты отсюда.

```
Scientist / Scholar                       Lex
       ↓  формулируют                      ↓  нормативный анализ
   ┌────────────────────────────────────────────┐
   │                polisyos.ir                 │
   │  Trinity Contracts · Kernel · World · ...  │
   └────────────────────────────────────────────┘
       ↓  линкуются          ↓  загружаются
    Foundry (компиляция)    Fabric (данные)
       ↓
    Runtime (симуляция)
```

~200 файлов в проекте импортируют `polisyos.ir`.

## Структура модуля

```
ir/
├── __init__.py                 # Lazy-импорт ~75 публичных символов
│
│  ── Trinity-контракты (Why / What / How) ──
├── problem_frame.py            # ProblemFrame: задача, KPI, ограничения, стейкхолдеры
├── policy_spec.py              # PolicySpec: интервенции, параметры, механизмы
├── model_spec.py               # ModelSpec: мир, агенты, допущения, fidelity
├── trinity/                    # TrinityBundle — контейнер трёх артефактов + загрузчики
│
│  ── Нормативные правила и таргетирование ──
├── norm_pack.py                # NormPack / NormRule — деонтическая логика
├── applicability.py            # NormApplicability — условия применимости норм
├── schedule.py                 # ScheduleSpec — временные рамки интервенций
├── selector_expr.py            # SelectorExpr (AST) — выбор целевых сущностей
├── gate.py                     # GateRequest / GateDecision — governance gates
│
│  ── Анализ и оценка эффектов ──
├── uncertainty.py              # UncertaintyEnvelope — доверительные интервалы
├── causal.py                   # CausalEffectReport — каузальная оценка
├── hte.py                      # HTEResult — гетерогенные эффекты
├── distributional.py           # DistributionalReport — анализ winners/losers
├── backtest.py                 # BacktestReport — ретроспективная проверка
├── calibration.py              # CalibrationConfig — конфигурация калибровки
│
│  ── Данные и документы ──
├── connectors.py               # ConnectorMetadataSpec, FetchRequest/Result
├── data_views.py               # DataViewRequest — запросы к данным
├── fact_log.py                 # Fact, FactBatch — журнал фактов с provenance
├── citations.py                # CitationRef, DocumentRef — цитирование
├── refs.py                     # EvidenceBundleRef
├── queries.py                  # DocQuery, ClaimQuery, NormQuery
│
│  ── Типы и утилиты ──
├── types.py                    # EntityType, OptimizationDirection, TranslatableString
├── canon.py                    # to_canonical_bytes() — детерминированная сериализация
├── units.py                    # Реэкспорт kernel.units
├── predicate.py                # PredicateRegistry, PrivacyPolicyRegistry
├── registry_fragments.py       # RegistryBundle, compose_registry_fragments()
├── validation.py               # ValidationReport, build_validation_report()
├── migration_report.py         # MigrationReport
│
│  ── Подсистемы (см. собственные README) ──
├── kernel/                     # Фундаментальные реестры и типы (13 файлов)
├── world/                      # Семантическая модель фактов и событий (9 файлов)
│
│  ── Вспомогательные пакеты ──
├── linker/                     # Валидация Trinity → LinkedTrinityBundle
└── migrations/                 # Миграция схем артефактов
```

## Trinity-контракты

Центральная абстракция IR — **Trinity**: три независимых артефакта, собранных в `TrinityBundle`.

| Артефакт | Файл | Вопрос | Содержание |
|---|---|---|---|
| `ProblemFrame` | `problem_frame.py` | **Why** | Домен, KPI, objectives, success criteria, hard/soft constraints, stakeholders |
| `PolicySpec` | `policy_spec.py` | **What** | Интервенции, mechanism bindings, tunable parameters, selector expressions |
| `ModelSpec` | `model_spec.py` | **How** | Data snapshot ref, agent config, assumptions, environment, fidelity level |

`TrinityBundle` (`trinity/__init__.py`) — Pydantic-модель, объединяющая все три:

```python
from polisyos.ir.trinity import TrinityBundle

bundle = TrinityBundle(
    problem_frame=ProblemFrame(problem_id="fiscal", domain=ProblemDomain.FISCAL),
    policy_spec=PolicySpec(policy_id="tax_reform", interventions=[...]),
    model_spec=ModelSpec(model_id="baseline", data_snapshot_ref="sha256:..."),
)
```

**Загрузка из JSON/YAML**:

```python
from polisyos.ir.loaders import load_policy, load_trinity_bundle

bundle = load_policy(payload)                          # -> TrinityBundle
bundle, migration_report = load_trinity_bundle(payload) # -> (TrinityBundle, MigrationReport | None)
```

### Ключевые модели Trinity

**ProblemFrame** определяет 11 доменов (`ProblemDomain`: fiscal, monetary, social, environmental, labor, healthcare, education, infrastructure, regulatory, trade, custom), KPI со связью с metric registry, success criteria с пороговыми операторами, hard/soft constraints с типизированными значениями (`MoneyValue`, `RateValue` и др.), stakeholders с приоритетами.

**PolicySpec** описывает интервенции через `InterventionSpec` (kind → mechanism, target → `SelectorExpr` AST, schedule → `ScheduleSpec`, params → типизированные `ParamValue`), явные bindings к механизмам из kernel registry, tunable `ParameterSpec` для калибровки и sensitivity analysis. Валидатор проверяет глубину/размер selector expressions (max depth=10, max nodes=50).

**ModelSpec** задаёт fidelity level (`surrogate_fluid` → `full_discrete`), конфигурацию агентов (типы, популяция, поведенческие параметры, adaptive agents с RL), explicit assumptions с типизацией и confidence, environment parameters.

## Нормативные правила и таргетирование

| Модуль | Ключевые типы | Назначение |
|---|---|---|
| `norm_pack.py` | `NormPack`, `NormRule`, `RuleType` | Деонтические правила (obligation / prohibition / permission) с backend expressions |
| `applicability.py` | `NormApplicability`, `TimeWindow`, `ConditionExpr` | Условия применимости норм: entity selectors, temporal windows |
| `selector_expr.py` | `SelectorExpr`, `SelectorPredicate`, `SelectorAll/Any/Not` | Типизированный AST для выбора целевых сущностей |
| `schedule.py` | `ScheduleSpec` | Временные рамки: start_step, duration_steps |
| `gate.py` | `GateRequest`, `GateDecision`, `GateVerdict` | Governance gates: approve / reject / escalate с приоритетами |

## Анализ и оценка эффектов

Группа контрактов для результатов аналитических pipeline'ов:

**`UncertaintyEnvelope`** — единый контракт неопределённости: point estimate + confidence interval, distribution family (normal, bootstrap, bayesian, uniform, triangular), propagation method (delta, Monte Carlo, analytical), interval semantics (confidence vs credible vs deterministic bounds). Heuristic intervals автоматически исключаются из governance gates.

**`CausalEffectReport`** — результат каузальной оценки: метод (DID, RDD, IV, matching, SCM), статус (identified, weak, failed), diagnostic tests, placebo results. Поддерживает persist/load через CAS.

**`HTEResult`** — гетерогенные эффекты: subgroup effects, feature importance, targeting rules, policy recommendations.

**`DistributionalReport`** — распределительный анализ: breakdowns по когортам, winners/losers таблицы, equity metrics.

**`BacktestReport`** — ретроспективная проверка: сценарии, сравнение outcomes, обнаружение систематического смещения.

**`CalibrationConfig`** — конфигурация калибровки: trainable parameters, target alignment, gradient norm, prior loss.

## Данные, документы и цитирование

**`connectors.py`** — контракты для data connectors: `ConnectorCapability`, `TrustLevel` (verified/high/medium/low), `QualityTier`, `FetchRequest`/`FetchResult` с resilience info и version strategy.

**`fact_log.py`** — журнал фактов: `Fact` с provenance (`FactProvenance`), trust (`FactTrust`), legal metadata (`FactLegal`). Batching через `FactBatch`, детерминированные ID через `build_fact_id()`.

**`citations.py`** — citation-grade ссылки: `CitationRef` → `DocumentRef` + `FragmentLocator` с anchor kinds (page, section, paragraph, line).

**`queries.py`** — спецификации запросов: `DocQuery`, `ClaimQuery`, `NormQuery` с temporal ranges, quality thresholds, pagination.

## Linker — валидация Trinity

Пакет `ir/linker/` (3 файла) обеспечивает валидацию `TrinityBundle` относительно kernel-реестров перед компиляцией в Foundry.

```
TrinityBundle + RegistryBundle → link_trinity() → (LinkedTrinityBundle | None, LinkReport)
```

**Основной API:**

```python
from polisyos.ir.linker import link_trinity, LinkReport, LinkIssueCode

linked, report = link_trinity(bundle, registries, strict=True)
if not report.ok:
    for issue in report.issues:
        print(f"{issue.severity}: [{issue.code}] {issue.message}")
```

**Процесс линковки**: валидация ProblemFrame (constraints, KPIs vs registries) → линковка PolicySpec (mechanisms, params, selectors) → проверка ModelSpec → создание `LinkedTrinityBundle` с `TrinityBindings` (resolved interventions, constraints, metrics, selectors).

**`LinkReport`** содержит типизированные `LinkIssue` со стабильными кодами (`LinkIssueCode`): `UNKNOWN_MECHANISM`, `MISSING_PARAM`, `PARAM_RANGE`, `UNKNOWN_SLOT`, `UNKNOWN_UNIT`, `UNIT_MISMATCH`, `UNKNOWN_SELECTOR_FIELD`, `UNKNOWN_MERGE_RULE`, `UNKNOWN_CONSTRAINT`, `MISSING_REGISTRY` и др. Severity: error / warning / info.

## Migrations — миграция схем

Пакет `ir/migrations/` (4 файла) обеспечивает миграцию артефактов между версиями схем.

```python
from polisyos.ir.migrations import migrate_policy_ir, IR_CURRENT_VERSION

migrated = migrate_policy_ir(payload, target_version="1.1")
```

**Гарантии**: только канонические Trinity payloads (legacy surface payloads отклоняются), детерминированность, явный контроль major version bumps (`allow_major=True`). Версионирование — `MAJOR.MINOR`.

**Утилиты**: `register_migration()` для добавления новых миграций, `parse_version()`, `is_major_bump()`.

## Registry Fragments — композиция реестров

`registry_fragments.py` решает задачу сборки `RegistryBundle` из отдельных фрагментов с разрешением конфликтов:

```python
from polisyos.ir.registry_fragments import compose_registry_fragments, RegistryBundle

result = compose_registry_fragments(request)  # -> RegistryComposeResult
bundle: RegistryBundle = result.bundle
```

Содержит 13+ типов фрагментов для каждого kernel registry.

## Типы, утилиты, canon

**`types.py`** — общие перечисления: `EntityType` (person, firm, government, ...), `OptimizationDirection`, `TimeFrequency`, `SelectorOperator`, `TranslatableString`.

**`canon.py`** — `to_canonical_bytes()`: детерминированная JSON-сериализация (sorted keys, separators=(",",":"), float запрещён). Используется для генерации content-addressable ID.

**`predicate.py`** — реестры предикатов (`PredicateRegistry`) и политик приватности (`PrivacyPolicyRegistry`).

**`validation.py`** — утилиты валидации: `build_validation_report()`, `issues_from_validation_error()`, `diff_payloads()`.

## Подсистемы с собственной документацией

| Подсистема | Файлов | README | Назначение |
|---|---|---|---|
| `kernel/` | 13 | [kernel/README.md](kernel/README.md) | Фундаментальные реестры: mechanisms, slots, units, constraints, metrics, merge rules, trust, selector fields. Типы: `KernelModel`, `DecimalValue`, `MoneyValue`, `RateValue`. Float rejection. |
| `world/` | 9 | [world/README.md](world/README.md) | Семантическая модель: `Claim`, `WorldEvent`, `ConflictSet`, `DocFragment`, `QualityReport`, `TrustAssessment`. Provenance tracking, deterministic IDs. |

## Архитектурные принципы

**Immutable models** — все Pydantic-модели `frozen=True`, `extra="forbid"`. Нет мутабельного состояния.

**Float rejection** — kernel-модели запрещают `float` через `reject_float()` валидатор, требуя `Decimal`/`int`/`str`. `UncertaintyEnvelope` — исключение (допускает float для совместимости с NumPy).

**Lazy imports** — `__init__.py` использует `__getattr__` + `_LAZY_IMPORTS` dict для отложенной загрузки ~75 символов.

**Deterministic IDs** — content-addressable идентификаторы через `canon.to_canonical_bytes()` → SHA256. Используется в world, fact_log, migrations.

**Typed AST для selectors** — `SelectorExpr` представляет expression tree из `SelectorPredicate`, `SelectorAll`, `SelectorAny`, `SelectorNot` с ограничениями на глубину и размер.

## Зависимости

### IR зависит от

- `polisyos.core.canon` — каноническая сериализация (в `uncertainty.py`)
- `polisyos.core.artifacts` — CAS store для persist/load (TYPE_CHECKING)
- `polisyos.core.contracts` — ref-типы (TYPE_CHECKING)
- `pydantic` — базовый фреймворк моделей

### От IR зависят

| Модуль | Что использует |
|---|---|
| **foundry** | `TrinityBundle`, `LinkedTrinityBundle`, kernel registries, `CalibrationConfig`, `UncertaintyEnvelope` |
| **scientist** | Trinity-контракты, `CausalEffectReport`, `HTEResult`, `BacktestReport`, `DistributionalReport` |
| **lex** | `NormPack`, `NormApplicability`, `GateRequest`/`GateDecision`, `SelectorExpr` |
| **fabric** | `ConnectorMetadataSpec`, world types, `Claim`, `DocFragment`, `FetchRequest` |
| **core** | IR types для contracts, registry, components |
| **scholar** | Trinity-контракты для bundling |
| **packs** | `RegistryFragment` для domain-specific реестров |

## Тестирование

```bash
# Unit-тесты IR
pytest tests/unit/test_ir_*.py

# Contract-тесты линкера
pytest tests/contract/test_ir_linker.py

# Kernel-реестры
pytest tests/unit/test_ir_kernel_*.py

# Генерация и проверка JSON-схем
python tools/diagnostics/gen_schema.py --check --output-dir schemas/snapshots
```
