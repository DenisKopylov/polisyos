# Documentation SOTA Plan

> Bringing PolicyOS documentation from current state to industry-leading level.
> Created: 2026-03-30

---

## Current State Summary

| Asset | Count | Quality |
|-------|-------|---------|
| Root README.md | **0** | Missing |
| Module READMEs (src/) | 68 | Good structure, need refresh |
| ADRs | 92 | Excellent coverage |
| Contract specs | 14 | Solid |
| Strategic docs (plans/blueprints) | 21 | Stale — many reference outdated state |
| IR exported types | 160 | No docstrings |
| Lex exported types | 58 | No docstrings |
| HTTP API endpoints | 43 | No public reference docs |
| JSON schemas | 87 | Machine-readable, no human docs |
| CLI commands | 4 | No usage docs |
| Governance passes | 18 | No reference docs |
| Fabric connectors | 9 | Connector CONTRIBUTING.md exists |
| CHANGELOG | **0** | Missing |
| CONTRIBUTING.md (general) | **0** | Only connector-specific |
| Style guide | **0** | Standards are implicit |
| Auto-generated docs (MkDocs/Sphinx) | **0** | Not configured |

**Key gaps:** no entry point (README), no auto-generated API reference, no how-to guides,
no tutorials, stale strategic docs, minimal docstrings in public API.

---

## Target State: Diataxis + Auto-generation

```
policy-engine/
  README.md                              # Entry point for all users
  CONTRIBUTING.md                        # How to contribute
  CHANGELOG.md                           # Version history
  mkdocs.yml                             # MkDocs Material config
  docs/
    index.md                             # Docs site landing page
    style-guide.md                       # Documentation standards

    tutorials/                           # Diataxis: learning by doing
      getting-started.md                 # First run, minimal setup
      first-policy-analysis.md           # End-to-end walkthrough
      writing-a-connector.md             # Build a fabric connector
      creating-governance-pass.md        # Build a scientist pass

    how-to/                              # Diataxis: solving specific problems
      install.md                         # Installation options
      run-benchmarks.md                  # Benchmark suite
      add-data-source.md                 # Register new data connector
      write-governance-pass.md           # New pass creation
      configure-lex-pipeline.md          # Lex batch setup
      deploy-runtime.md                  # HTTP runtime deployment
      use-control-plane.md               # Control plane operations
      run-causal-analysis.md             # Causal engine workflow
      debug-failed-run.md               # Troubleshooting runs
      manage-schemas.md                  # ABI schema workflow

    reference/                           # Diataxis: precise, complete
      ir/                                # Auto-generated from docstrings
        index.md                         # IR overview + semantic grouping
        governance.md                    # PolicySpec, GovernancePass, etc.
        analytics.md                     # CausalGraph, HTE, Backtest, etc.
        observation.md                   # Panels, records, contracts
        problem-framing.md              # ProblemFrame, KPIs, constraints
      foundry/
        index.md
        compile-execute.md               # compile() / execute() reference
        calibration.md
        methods-catalog.md               # Causal, econometrics, optimization
      scientist/
        index.md
        workflows.md                     # Workflow specs
        governance-passes.md             # All 18 passes documented
        nodes.md                         # Node protocol reference
      lex/
        index.md
        batch-pipeline.md               # SPO, canonicalization, QC
        knowledge.md                     # Store, search, types
        normpack.md                      # Assembly, mutation, diff
      fabric/
        index.md
        connectors.md                    # All 9 connectors + protocol
        profiles.md                      # Source/binding profiles
        data-plane.md                    # World queries, catalogs
      api/
        index.md                         # REST API overview
        runs.md                          # /api/v1/runs/* (16 endpoints)
        control.md                       # /api/v1/control/* (25 endpoints)
        artifacts.md                     # Artifact inspection
      cli.md                             # polisy, polisyos, polisyos-foundry, polisyos-causal-capabilities
      schemas.md                         # JSON schema catalog (87 types)
      configuration.md                   # pyproject.toml groups, env vars

    explanation/                         # Diataxis: understanding context
      architecture.md                    # System design (from current architecture.md)
      ir-design.md                       # Why IR layer exists separately
      trinity.md                         # ProblemFrame / PolicySpec / ModelSpec
      causal-engine.md                   # Causal engine design rationale
      governance-model.md                # Pass registry, gates, human review
      data-fabric.md                     # Connector architecture, world store
      lex-pipeline.md                    # Legal corpus processing design
      security-model.md                  # JWT, OPA, SPIFFE, TEE, SLSA
      observation-contracts.md           # Observation layer design rationale
      freeze-policy.md                   # Import gates, arch freeze (from current)

    adr/                                 # Already excellent — keep as is
      0001-remove-legacy-foundry-engine.md
      ...
      0092-*.md

    contracts/                           # Already solid — keep as is
      TRINITY.md
      MERGE_SEMANTICS.md
      E1_*.md ... E2_*.md

    archive/                             # Stale plans and blueprints
      plans/                             # Move current *_PLAN.md, *_BLUEPRINT.md here
      reports/                           # Current docs/reports/
```

---

## Execution Phases

All phases below are **maximally parallel**. Within each phase, work streams (WS)
are independent and can be executed simultaneously by different people or agents.

---

### Phase 0 — Foundation (prerequisite for all other phases)

**Duration:** 1 session. **Blockers:** none. **Must complete before Phase 1-5.**

#### WS-0A: Style Guide

Create `docs/style-guide.md`:

```markdown
# Documentation Style Guide

## Language
- Module READMEs, ADRs, contracts: Russian (primary), English technical terms
- Reference docs (auto-generated): English (follows code)
- Tutorials and how-to: Russian

## Docstring Format
- Google-style docstrings
- All public classes, functions, and modules must have docstrings
- Include: one-line summary, Args/Returns/Raises, Example when non-obvious

## README Template (per-module)
1. Title with module path: `# Module Name (`polisyos.module`)`
2. One-paragraph purpose
3. Role in system (what depends on it, what it depends on)
4. Key concepts (3-7 bullet points)
5. Public API surface (link to reference docs)
6. Current state / last updated date

## ADR Template (already followed)
- Michael Nygard format: Status, Context, Decision, Consequences
- Immutable after acceptance — supersede, never edit
- Sequential numbering: 0001, 0002, ...

## Markdown
- Headers: ATX style (`#`, not underline)
- Code blocks: triple backtick with language identifier
- Links: relative paths within docs/
- Max line length: soft 100 chars (no hard wrap in paragraphs)
```

#### WS-0B: MkDocs Scaffold

Create `mkdocs.yml` and `docs/index.md`:

```yaml
# mkdocs.yml
site_name: PolicyOS Documentation
site_description: AI-driven Policy Simulation System
repo_url: https://github.com/<org>/policy-engine

theme:
  name: material
  language: en
  features:
    - navigation.sections
    - navigation.expand
    - navigation.indexes
    - search.highlight
    - content.code.copy
    - content.tabs.link

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            show_if_no_docstring: false
            members_order: source
            show_root_heading: true
            show_source: true
            merge_init_into_class: true

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - toc:
      permalink: true

nav:
  - Home: index.md
  - Tutorials:
    - tutorials/getting-started.md
  - How-to Guides:
    - how-to/install.md
  - Reference:
    - reference/ir/index.md
    - reference/foundry/index.md
    - reference/scientist/index.md
    - reference/lex/index.md
    - reference/fabric/index.md
    - reference/api/index.md
    - reference/cli.md
    - reference/schemas.md
  - Explanation:
    - explanation/architecture.md
    - explanation/trinity.md
    - explanation/causal-engine.md
  - ADRs: adr/
```

#### WS-0C: Directory Structure

Create all empty directories and placeholder `index.md` files:

```
docs/tutorials/
docs/how-to/
docs/reference/ir/
docs/reference/foundry/
docs/reference/scientist/
docs/reference/lex/
docs/reference/fabric/
docs/reference/api/
docs/explanation/
```

Each `index.md` gets a title and one-line description placeholder.

---

### Phase 1 — Entry Points & Essentials (parallel: 6 work streams)

**Dependency:** Phase 0 complete. **All WS below run in parallel.**

#### WS-1A: Root README.md

Write `policy-engine/README.md` following canonical template.

**Обязательные секции (в этом порядке):**

1. **Заголовок + бейджи:**
   - Название: `PolicyOS Policy Engine`
   - Бейджи: CI status (GitHub Actions), Python 3.14, License
   - Одна строка: _"AI-driven Policy Simulation System using JAX and Unified Data Fabric"_

2. **Мотивация (1 абзац, 3-5 предложений):**
   - Проблема: policy evaluation требует causal inference, data integration, governance
   - Решение: единая платформа от данных до решений через IR-слой
   - Источник: `pyproject.toml` description + первые абзацы `architecture.md`

3. **Ключевые возможности (7 буллетов, по одному на подсистему):**
   - **IR** — 160+ типизированных моделей, ABI-совместимость, 87 JSON-схем
   - **Foundry** — JAX-based compile→execute, calibration с measurement-aware loss, agent-based simulation
   - **Scientist** — 18 governance passes, causal workflows, policy search, ensemble causal analysis
   - **Lex** — legal corpus → NormPack pipeline, SPO extraction, hallucination detection, temporal resolution
   - **Fabric** — 14 production connectors (World Bank, Eurostat, WHO, SDMX, CKAN...), 63 source profiles, async fetch
   - **Observation** — 133+ contract types, causal readiness bundles, measurement trust tiers
   - **Runtime** — FastAPI HTTP API (43+ endpoints), control plane, React dashboard

4. **Архитектурная диаграмма (Mermaid):**
   ```mermaid
   graph LR
     IR[IR<br/>160+ types] --> Foundry[Foundry<br/>JAX compute]
     IR --> Scientist[Scientist<br/>orchestration]
     Fabric[Fabric<br/>14 connectors] --> Foundry
     Fabric --> Lex[Lex<br/>legal corpus]
     Foundry --> Scientist
     Scientist --> Runtime[Runtime<br/>HTTP API]
     IR --> Observation[Observation<br/>contracts]
     Observation --> Foundry
   ```

5. **Quickstart (копипастабельный):**
   ```bash
   git clone <repo-url> && cd policy-engine
   pip install -e ".[all]"
   polisyos --version          # проверка
   # Минимальный пример — описать ProblemFrame, compile, execute
   ```
   Включить реальный минимальный Python-пример (5-10 строк), который компилирует
   и выполняет trivial ProblemFrame.

6. **Структура проекта:**
   | Директория | Назначение |
   |---|---|
   | `src/polisyos/ir/` | Intermediate Representation — типы, схемы, контракты |
   | `src/polisyos/foundry/` | JAX compute engine, calibration, agent sim |
   | `src/polisyos/scientist/` | Orchestration: workflows, governance, nodes |
   | `src/polisyos/lex/` | Legal corpus processing, NormPack, interventions |
   | `src/polisyos/fabric/` | Data connectors, profiles, world store |
   | `src/polisyos/runtime/` | HTTP API, dashboard, control plane |
   | `schemas/` | JSON Schema snapshots (ABI) |
   | `benchmarks/` | Performance & correctness benchmarks |
   | `docs/` | Documentation (Diataxis structure) |

7. **Development setup:**
   ```bash
   pip install -e ".[dev,test]"
   pytest tests/ -x --tb=short
   mkdocs serve  # локальная документация
   ```

8. **Ссылки на документацию:**
   Таблица: Tutorials → `docs/tutorials/`, How-to → `docs/how-to/`, Reference → `docs/reference/`, ADRs → `docs/adr/`

9. **License**

**Источники данных для написания:**
- `pyproject.toml` — description, version, extras
- `src/polisyos/ir/__init__.py` — точный подсчёт экспортов (сейчас 160, дубль GovernancePassMappingBundle)
- `src/polisyos/fabric/connectors/sources/__init__.py` — 14 коннекторов
- `src/polisyos/fabric/connectors/profiles/builtin_profiles.py` — 63 профиля
- `schemas/snapshots/ir/_manifest.json` — количество схем
- Существующие module README для feature descriptions

**Нюансы:**
- Python 3.14 (не 3.11 — проект уже на 3.14 через homebrew)
- НЕ упоминать Docker — его пока нет
- Quickstart должен реально работать — проверить `polisyos --version` перед описанием

#### WS-1B: CONTRIBUTING.md

Write general `policy-engine/CONTRIBUTING.md`.

**Обязательные секции:**

1. **Development environment:**
   - Python 3.14+ (homebrew на macOS)
   - `pip install -e ".[dev,test,all]"` — перечислить что входит в каждый extra
   - Нет venv requirement — описать как опциональный шаг
   - Системные зависимости: JAX (CPU/GPU), возможные проблемы на Apple Silicon

2. **Code style:**
   - Ruff — конфигурация в `pyproject.toml` (проверить текущие правила)
   - Type hints: все public API полностью типизированы
   - Pydantic модели: `ConfigDict(extra="forbid")` — обязательно
   - Lazy imports для тяжёлых модулей (scientist, fabric) — объяснить pattern
   - Google-style docstrings — ссылка на `docs/style-guide.md`

3. **Testing:**
   - `pytest tests/` — зеркальная структура к `src/`
   - Именование: `test_<module>.py`, функции `test_<scenario>()`
   - Фикстуры: описать key fixtures (`runtime_api_env` для HTTP, synthetic data)
   - Маркеры: `@pytest.mark.slow`, `@pytest.mark.integration` — перечислить все используемые

4. **Architecture governance:**
   - Freeze policy: ссылка на `docs/explanation/freeze-policy.md`
   - Import gates: что запрещено (circular, cross-layer)
   - CI enforcement: `arch-freeze.yml` workflow
   - Exceptions: `import_exceptions_registry.md`

5. **PR process:**
   - Branch naming: `feature/`, `fix/`, `docs/`
   - Commit messages: русский или английский, содержательные
   - Required checks: arch-freeze, ABI, tests, benchmark regression
   - Review: кто ревьюит, merge policy

6. **Documentation requirements:**
   - Public API: обязателен docstring (Google style)
   - Новый модуль: обновить README.md parent module
   - Новый тип в IR: добавить в `__init__.py`, обновить ABI snapshot
   - Новый коннектор: следовать `docs/connectors/CONTRIBUTING.md`

7. **Ссылки:**
   - `docs/connectors/CONTRIBUTING.md` — connector-specific guide
   - `docs/style-guide.md` — стандарты документации
   - `docs/explanation/freeze-policy.md` — архитектурные правила

**Нюансы:**
- Проверить `pyproject.toml` [project.optional-dependencies] для точного списка extras
- Проверить `.github/workflows/` для точного списка CI checks
- Проверить `conftest.py` для списка основных fixtures и markers

#### WS-1C: CHANGELOG.md

Create `policy-engine/CHANGELOG.md`.

**Формат:** [Keep a Changelog](https://keepachangelog.com/) + [Semantic Versioning](https://semver.org/).

**Алгоритм backfill из git history:**

1. Выполнить `git log --oneline --since="2026-01-01"` — собрать все коммиты за последние 3 месяца
2. Сгруппировать по месяцам и категориям:
   - **Added** — новые модули, файлы, features
   - **Changed** — рефакторинг, расширение существующего
   - **Fixed** — исправления багов
   - **Deprecated** — что помечено для удаления
   - **Removed** — что удалено

3. **Ключевые milestones для backfill (из git log):**

   **Март 2026:**
   - Added: Observation module (133+ contract types)
   - Added: Scientist causal/ directory (BoundsEstimationRunner, ProxyIdentificationRunner, etc.)
   - Added: 10 causal node implementations (ensemble, readiness, transport, etc.)
   - Added: Lex intervention system (LexInterventionCompiler, TemporalInterventionSequencer)
   - Added: Lex quality tier (amendment_detector, hallucination_detector, quality_filters, temporal_resolver)
   - Added: Foundry agent_sim/wiring (FirmLifecycleEventBatch, ProcurementShockBatch, executors)
   - Added: Foundry calibration/measurement.py (MeasurementAwareLossConfig, trust tiers)
   - Added: Governance (backtest_matrix, calibration_*, stress_scenarios, strategic_response_pass)
   - Changed: Fabric profiles expanded (63 profiles, SourceExecutionPolicy, async fetch support)
   - Changed: Foundry contracts/state.py (CellState, HouseholdCellState, ProcurementGraphState)
   - Changed: IR __init__.py now exports 160 types (was ~120)

   **Февраль 2026:**
   - Added: Control Plane (/api/v1/control/, 25 endpoints)
   - Added: Runtime dashboard (React + Vite)
   - Changed: SDMX connector promoted to production
   - (и т.д. — собрать из git log)

   **Январь 2026:**
   - (собрать из git log)

4. **Текущая версия:** определить из `pyproject.toml` [project] version

**Нюансы:**
- Версия в pyproject.toml может быть 0.1.0 — не выдумывать version bumps
- Каждая запись в changelog: одна строка, начинается с глагола (Add, Change, Fix)
- Ссылки на PR/issues если есть (формат `[#123](https://github.com/<org>/<repo>/pull/123)`)
- НЕ включать WIP коммиты — только содержательные изменения

#### WS-1D: Explanation — Architecture

Migrate and restructure current `architecture.md` (140KB) into `docs/explanation/architecture.md`.

**Алгоритм:**

1. **Прочитать** текущий `docs/architecture.md` (140KB) — извлечь ключевые структурные описания
2. **Выбросить:** raw `tree` output, длинные листинги файлов, устаревшие описания
3. **Оставить/переписать:**

**Целевая структура (~5KB):**

```markdown
# Архитектура PolicyOS

## Обзор (1 абзац)
Три уровня: данные (Fabric) → вычисления (Foundry) → оркестрация (Scientist).
IR — общий язык между ними.

## Диаграмма зависимостей (Mermaid)
[6-уровневая диаграмма: IR → Foundry → Scientist, Fabric → both, Lex → IR, Runtime → all]

## Слой IR (2-3 абзаца)
- 160+ Pydantic моделей с ABI-совместимостью
- 87 JSON-схем в schemas/snapshots/
- Observation module: contracts, bundles, measurement
- Ссылка: docs/reference/ir/

## Слой Foundry (2-3 абзаца)
- compile() → execute() pipeline на JAX
- Agent-based simulation (agent_sim + wiring)
- Calibration с measurement-aware loss
- 200+ methods в catalog/
- Ссылка: docs/reference/foundry/

## Слой Scientist (2-3 абзаца)
- Workflow orchestration (causal_full, policy_design)
- 18 governance passes (budget, privacy, equity, safety...)
- 10 causal nodes (discovery, ensemble, readiness, transport...)
- Policy search + hierarchical planning
- Ссылка: docs/reference/scientist/

## Data Fabric (2-3 абзаца)
- 14 production connectors
- 63 source profiles + SourceExecutionPolicy
- Async fetch, SDMX protocol, resilience
- Ссылка: docs/reference/fabric/

## Lex Pipeline (2-3 абзаца)
- Legal corpus → NormPack → evaluation
- SPO extraction, entity resolution, amendment detection
- Hallucination detection, temporal resolution
- Interventions: LexInterventionCompiler, TemporalInterventionSequencer
- Ссылка: docs/reference/lex/

## Runtime (1-2 абзаца)
- FastAPI (43+ endpoints)
- Control plane
- React dashboard
- Ссылка: docs/reference/api/

## Cross-cutting concerns
- Governance: pass registry, checkpoint/replay
- Security: JWT, OPA, SPIFFE (ссылка на docs/explanation/security-model.md)
- Observability: OpenTelemetry tracing
```

**Нюансы:**
- Оригинальный `architecture.md` НЕ удалять — переместить в `docs/archive/` (WS-5A)
- Новый файл ~5KB max — brevity is key
- Каждая секция заканчивается ссылкой на reference docs (которые создаются в Phase 2)
- Mermaid диаграмма должна рендериться в MkDocs Material (проверить синтаксис)
- Упоминать конкретные числа (160 types, 14 connectors, 18 passes) — актуальные на момент написания

#### WS-1E: Explanation — Trinity

Create `docs/explanation/trinity.md`.

**Источники:**
- `docs/contracts/TRINITY.md` — формальная спецификация
- `docs/contracts/MERGE_SEMANTICS.md` — CRDT-inspired merge rules
- `src/polisyos/ir/trinity/` — код (TrinityBundle, etc.)

**Целевая структура:**

```markdown
# Trinity: ProblemFrame / PolicySpec / ModelSpec

## Зачем три сущности (1-2 абзаца)
- Separation of concerns: "что исследовать" / "какую политику" / "как моделировать"
- Позволяет комбинировать: один ProblemFrame + разные PolicySpec
- Позволяет пере-использовать: ModelSpec across different problems

## ProblemFrame
- Определяет: KPIs, entity scope, temporal window, constraints
- Поля: перечислить ключевые (из кода ir/trinity/)
- Пример: "Как образовательные расходы влияют на GDP growth в Украине 2020-2025"

## PolicySpec
- Определяет: intervention parameters, governance requirements, budget
- Поля: ключевые
- Связь с GovernancePassAlias — как governance привязывается к policy

## ModelSpec
- Определяет: causal model, estimation strategy, sensitivity analysis
- Поля: ключевые
- Связь с Foundry compile() — как ModelSpec транслируется в execution plan

## TrinityBundle
- Объединяет три сущности + metadata
- Используется Scientist для запуска workflow

## Merge Semantics
- CRDT-inspired: partial updates, conflict resolution
- Правила приоритетов при merge
- Примеры: что происходит при конфликте KPI definitions

## Жизненный цикл
[Mermaid sequence diagram: User → ProblemFrame → + PolicySpec → + ModelSpec → TrinityBundle → Scientist workflow]
```

**Нюансы:**
- Прочитать `TRINITY.md` и `MERGE_SEMANTICS.md` полностью перед написанием
- Проверить `src/polisyos/ir/trinity/` — какие модели сейчас экспортируются
- TrinityBundle входит в IR exports — использовать актуальные field names
- Контракт E1_*/E2_* может содержать дополнительный контекст — проверить

#### WS-1F: Explanation — Freeze Policy

Migrate `freeze_policy.md` + `import_exceptions_registry.md` into
`docs/explanation/freeze-policy.md`.

**Источники:**
- `docs/freeze_policy.md`
- `docs/import_exceptions_registry.md`
- `.github/workflows/arch-freeze.yml` — CI enforcement
- `.github/workflows/arch.yml` — architecture checks

**Целевая структура:**

```markdown
# Architecture Freeze & Import Gates

## Принцип (1 абзац)
Зачем нужен architecture freeze: предотвращение circular dependencies,
обеспечение layer isolation, предсказуемость build graph.

## Правила импорта
- Таблица: кто может импортировать кого
  | Module | May import | Must NOT import |
  |--------|-----------|----------------|
  | ir | stdlib, pydantic | foundry, scientist, lex, fabric |
  | foundry | ir, core | scientist, lex |
  | scientist | ir, foundry, core | (зависимости через contracts) |
  | ... | ... | ... |

## CI Enforcement
- `arch-freeze.yml` — что проверяет, как работает
- `arch.yml` — дополнительные architectural checks
- Как выглядит ошибка при нарушении

## Exceptions
- Когда исключения допустимы
- Процесс: как добавить exception
- Текущий реестр: ссылка на `import_exceptions_registry.md`
- Формат записи в реестре

## Lazy Import Pattern
- Зачем: тяжёлые модули (JAX, torch) не должны загружаться при import time
- Как: `if TYPE_CHECKING` + runtime lazy import в `__init__.py`
- Пример из codebase
```

**Нюансы:**
- Прочитать оба source файла полностью
- Проверить `arch-freeze.yml` — точно какие правила enforce'ятся
- Проверить `arch.yml` — что он делает отдельно от freeze
- Import exceptions registry может быть устаревшим — сверить с реальным кодом

---

### Phase 2 — Reference Documentation (parallel: 8 work streams)

**Dependency:** Phase 0 complete. **Can run in parallel with Phase 1.**

#### WS-2A: IR Docstrings

Add Google-style docstrings to **all 160 exported types** in `polisyos.ir.__init__.py`.

**Важно:** в `__init__.py` есть дубль — `GovernancePassMappingBundle` встречается дважды (строки 42 и 113). Исправить при обработке.

**Алгоритм работы:**

1. Прочитать `src/polisyos/ir/__init__.py` — получить полный `__all__` список (160 записей)
2. Для каждого типа найти source file (import path в `__init__.py`)
3. Добавить docstring в source file (НЕ в `__init__.py`)
4. Создать reference pages

**Семантические группы (актуальные, на основе кода):**

| Group | Types (примеры) | Source module | Count |
|-------|-----------------|---------------|-------|
| Governance | PolicySpec, GovernancePassAlias, GovernancePassAliasRegistry, GovernancePassAliasStatus, GovernancePassMappingBundle | `ir/governance/` | ~20 |
| Analytics — Causal | CausalGraphModel, CausalEffectReport, HTEResult, StrategicPayoffTable, StrategicSCM, StrategicResponseBundle | `ir/analytics/` + `ir/analytics/strategic.py` (NEW) | ~30 |
| Analytics — Backtest | BacktestReport, BacktestPlanBundle | `ir/analytics/` | ~5 |
| Problem framing | ProblemFrame, EntityScope, KPI | `ir/trinity/`, `ir/kernel/` | ~15 |
| **Observation (NEW)** | ObservationPanel, ObservationRecord, ObservationFamily, SourceConfidenceTier, MultiplexGraphLayerId, StrategicResponseChannel | `ir/observation/` (9 файлов, 133+ классов) | ~50 |
| Observation — Bundles | BacktestPlanBundle, BoundsEstimationBundle, CausalPanelBundleManifest, DTRTreatmentSequenceBundleManifest, LessonRegistrySeedBundle | `ir/observation/bundles.py` | ~15 |
| Observation — Causal | CausalExecutionBundle, CausalReadinessBundle, BoundsEstimationTask, BoundsEstimationEntry | `ir/observation/causal_execution.py`, `causal_readiness.py` | ~12 |
| Observation — Measurement | MeasurementRegistry, MeasurementTrustTier, RegimeCalendar, SchemaChangepoint, ShockCalendar | `ir/observation/measurement.py` | ~12 |
| Observation — Compiler | ObservationContractCompilerSuite, CalibrationSplitLabel, NegativeControlSpec, SparseDenseBridge | `ir/observation/compiler.py`, `contract_compilers.py` | ~15 |
| Sensitivity | SensitivityResult, SpecificationCurveBundle | `ir/analytics/` | ~10 |
| Calibration | CalibrationConfig, CalibrationTargetBundleManifest | `ir/analytics/` | ~10 |
| Temporal | TemporalInterventionSequence, TemporalInterventionStep | `ir/analytics/` | ~5 |
| Kernel | SelectorFieldSpec, SelectorFieldRegistry, SlotSpec, SlotRegistry, SlotKind, SlotScope | `ir/kernel/` | ~10 |
| Refs & loaders | VariableRef, CausalReadinessBundleRef (NEW), CausalExecutionBundleRef (NEW), load_*, persist_* | `ir/refs.py`, `ir/loaders.py` | ~20 |
| Other | TrinityBundle, ContextAdaptiveParameterBundle | `ir/trinity/`, `ir/analytics/` | ~10 |

**Формат каждого docstring:**
```python
class PolicySpec(BaseModel):
    """Specification of a policy intervention for causal evaluation.

    Defines the policy parameters, governance requirements, and budget
    constraints for a single policy analysis run. Used by Scientist
    workflows as input to compile() and governance pass validation.

    Key fields:
        intervention_kind: Type of policy intervention (tax, transfer, etc.)
        governance_pass_aliases: Required governance checks for this policy
        budget_constraint: Maximum budget allocation

    Related types:
        - ProblemFrame: Defines *what* to analyze (this defines *how*)
        - GovernancePassAlias: Individual governance check specifications
        - TrinityBundle: Combines PolicySpec with ProblemFrame and ModelSpec

    Example:
        >>> spec = PolicySpec(intervention_kind="education_spending", ...)
    """
```

**Reference pages:**
- `docs/reference/ir/index.md` — обзор + таблица всех 160 типов по группам
- `docs/reference/ir/governance.md` — `:::polisyos.ir.governance` + manual enrichment
- `docs/reference/ir/analytics.md` — analytics types + strategic (NEW)
- `docs/reference/ir/observation.md` — **НОВАЯ СТРАНИЦА** — все observation types (50+ типов)
- `docs/reference/ir/problem-framing.md` — ProblemFrame, KPIs, constraints

**Нюансы:**
- `ir/observation/` — полностью новая директория (9 файлов), **ни одного docstring**. Здесь самый большой объём работы.
- `ir/analytics/strategic.py` — 708 строк, полностью новый файл, тоже без docstrings
- `ir/refs.py` — добавлены `CausalReadinessBundleRef`, `CausalExecutionBundleRef` (новые)
- Порядок: начать с observation/ (наибольший impact), затем governance/, analytics/, kernel/

#### WS-2B: Lex Docstrings

Add docstrings to **65 exported types** in `polisyos.lex` (НЕ 58 — обновлённый подсчёт).

**Актуальные группы (из `__init__.py`):**

| Group | Types | Count |
|-------|-------|-------|
| Errors | LexError, LexValidationError, LexIngestError, LexStructureError, LexVersioningError, LexNotReadyError, LexIndexError | 7 |
| Ingest pipeline | LexIngestOptions, LexIngestResult, ingest_legal_doc_bytes | 3 |
| Structure pipeline | LexStructureOptions, LexStructureResult, build_legal_structure | 3 |
| Version pipeline | ActiveVersionStrategy, ActiveVersionResult, LexVersionIndexOptions, LexVersionIndexResult, build_version_index, resolve_active_version | 6 |
| NormPack assembly | NormPackBuildRequest, NormPackBuildResult, NormPackBudgets, assemble_norm_pack | 4 |
| NormPack mutation | MutationIntent, NormPackMutator, NormChangeType, NormChange, NormDiff, diff_norm_packs | 6 |
| Impact analysis | NormImpactAnalyzer, NormImpactReport, ComplianceTransition, ComplianceDelta, AffectedKPI | 5 |
| Legal evaluation | LegalEvaluationRequest, evaluate_legality, propose_changes, LegalDocSource, ChangeProposalRef, LegalReportRef | 6 |
| Knowledge | LegalKnowledgeGraph | 1 |
| **Interventions (NEW)** | LexInterventionCompiler, LexProvisionDirective, CompiledLexIntervention, InterventionKnobSpec, InterventionKnobDictionaryEntry, LexInterventionMapEntry, StrategicResponseRegistryEntry, StrategicResponseSpecRegistry, LexPolicyBundleInput | 9 |
| **Temporal interventions (NEW)** | TemporalInterventionSequenceCompiler, TemporalInterventionSequenceCompileResult, TemporalInterventionSequencer, TemporalInterventionStepInput | 4 |
| **Policy search (NEW)** | HierarchicalPolicySearchAdapter, HierarchicalPolicySearchPlan | 2 |
| **Provision mapping (NEW)** | LexProvisionMappingRegistry, ProvisionProgramCrosswalkEntry, WorldEventRefLike | 3 |

**Source файлы для docstrings:**

| File | Types to document | Priority |
|------|-------------------|----------|
| `lex/interventions.py` (NEW) | 12 types — LexInterventionCompiler, TemporalInterventionSequencer, etc. | P1 (нет docstrings) |
| `lex/intervention_artifacts.py` (NEW) | 8 types — InterventionKnobDictionaryEntry, LexInterventionMapEntry, etc. | P1 (нет docstrings) |
| `lex/batch/amendment_detector.py` (NEW) | AmendmentRecord, detect_amendments() | P1 |
| `lex/batch/hallucination_detector.py` (NEW) | detect_hallucination_flags(), has_blocking_hallucination() | P1 |
| `lex/batch/quality_filters.py` (NEW) | 7 filter functions (is_synthetic_subject, is_low_quality_entity_text, etc.) | P1 |
| `lex/batch/temporal_resolver.py` (NEW) | DocTemporalEnvelope, FactTemporalEnvelope, resolve_document_temporal() | P1 |
| `lex/batch/amendment_metrics.py` (NEW) | AmendmentQualityMetrics, collect_amendment_quality_metrics() | P1 |
| Existing files | LexError hierarchy, NormPack types, pipeline functions | P2 |

**Reference pages:**
- `docs/reference/lex/index.md` — обзор + таблица 65 типов
- `docs/reference/lex/batch-pipeline.md` — SPO, canonicalization, QC + **NEW** amendment/hallucination/temporal
- `docs/reference/lex/knowledge.md` — Store, search, types
- `docs/reference/lex/normpack.md` — Assembly, mutation, diff
- `docs/reference/lex/interventions.md` — **НОВАЯ СТРАНИЦА** — все intervention types

**Нюансы:**
- 7 полностью новых файлов без единого docstring — основной объём работы
- `quality_filters.py` содержит украиноязычные regex паттерны — docstrings писать на английском, но отмечать что паттерны Ukrainian-specific
- `temporal_resolver.py` обрабатывает статусы UA законодательства (current, historical, suspended, future) — документировать семантику
- В `__init__.py` есть повторные экспорты (HierarchicalPolicySearchAdapter встречается дважды) — отметить

#### WS-2C: Foundry Docstrings

Add docstrings to key public API in `polisyos.foundry`.

**Файлы для docstrings (по приоритету):**

| File | Public API | Status |
|------|-----------|--------|
| `executor.py` | `compile()`, `execute()` | Существующий, нужен refresh |
| `layout.py` | Layout planning types | Существующий, нужен refresh |
| `contracts/state.py` | `GlobalState`, `AgentState`, `FirmState`, **`CellState` (NEW)**, **`HouseholdCellState` (NEW)**, **`ProcurementGraphState` (NEW)**, **`AgentSimRuntimeState` (NEW)** | 4 новых chex dataclass |
| `calibration/__init__.py` | 25+ exports: Calibrator, CalibratorInputs, CalibrationReport, bijectors, **AuxLossComponent (NEW)**, **InterferenceLossComponent (NEW)**, **MeasurementAwareLossConfig (NEW)**, **MeasurementAwareTarget (NEW)**, **compute_effective_weight (NEW)** | 7 новых типов |
| `calibration/measurement.py` (NEW) | MeasurementAwareTarget, MeasurementAwareLossConfig, CalibrationTargetBundle, DefaultMeasurementAwareLossAdapter, compute_effective_weight() | Полностью новый |
| `calibration/auxiliary.py` (NEW) | AuxLossComponent (protocol), InterferenceLossComponent | Полностью новый |
| `calibration/calibrator.py` | CalibratorInputs, TrainableGroup, Calibrator | Обновлён |
| `agent_sim/wiring/__init__.py` (NEW) | FirmLifecycleEventBatch, FirmLifecycleEventType, InterventionMechanismConfig, ProcurementShockBatch, ContractsDistributionAwareExecutor, ContractsGraphAwareExecutor, ContractsPopulationAwareExecutor | Полностью новый |
| `agent_sim/wiring/contracts.py` (NEW) | multiplex_layer_code(), FirmLifecycleEventBatch, ProcurementShockBatch, InterventionMechanismConfig | Полностью новый |
| `agent_sim/wiring/executors.py` (NEW, 916 строк) | 3 executor classes + ~15 helper functions | Полностью новый |
| `data_plane/bindings.py` | build_input_bindings() + **NEW** _snapshot_binding_notes(), _snapshot_binding_warnings() | Обновлён |
| `methods/catalog/causal/measurement_error.py` | Added metadata propagation, _proxy_boundary_metadata() | Обновлён |
| `methods/catalog/causal/strategic.py` | StrategicSolveResult, coercion helpers | Обновлён |
| `methods/catalog/causal/policy_learning.py` | OptimalPolicyLearner, _extract_policy_tree_rules() | Обновлён |

**Reference pages:**
- `docs/reference/foundry/index.md` — compile/execute overview, system diagram
- `docs/reference/foundry/compile-execute.md` — compile() + execute() полный reference
- `docs/reference/foundry/calibration.md` — Calibrator + **measurement-aware loss** (новое)
- `docs/reference/foundry/methods-catalog.md` — causal, econometrics, optimization methods
- `docs/reference/foundry/agent-sim.md` — **НОВАЯ СТРАНИЦА** — wiring, executors, contracts
- `docs/reference/foundry/state.md` — **НОВАЯ СТРАНИЦА** — GlobalState, CellState, HouseholdCellState

**Нюансы:**
- `contracts/state.py` — chex dataclass'ы (НЕ Pydantic) — docstring формат тот же, но fields описывать как JAX arrays
- `wiring/executors.py` — 916 строк, 3 executor класса + 15 helpers — документировать только public API (3 класса)
- `calibration/measurement.py` — ключевая новая концепция: measurement-aware loss weighting. Docstring должен объяснить что trust_weight, coverage, lag, censoring, shock influence effective weight
- `methods/catalog/causal/` — методы имеют `namespace` и `version` (e.g., `causal.targeting` v1.0.0) — включить в docstring

#### WS-2D: Scientist Docstrings

Add docstrings to all key public API in `polisyos.scientist`.

**Файлы по приоритету:**

**P1 — Новые модули (нет docstrings):**

| File | Public API | Lines |
|------|-----------|-------|
| `causal/__init__.py` (NEW) | BoundsEstimationRunner, CounterfactualQueryRunner, ProxyIdentificationRunner, StrategicResponseRunner, TransportabilityChecker, build_interference_readiness_entries() | 6 exports |
| `causal/execution.py` (NEW) | BoundsEstimationRunner.run() | ~100 |
| `causal/readiness.py` (NEW) | ProxyIdentificationRunner, TransportabilityChecker, StrategicResponseRunner, CounterfactualQueryRunner | 4 runners |
| `governance/backtest_matrix.py` (NEW) | BacktestKind (5 kinds), BacktestMatrixRunner, BacktestMatrixResult | ~150 |
| `governance/calibration.py` (NEW) | CalibrationPassResult, CalibrationGovernanceReport, CalibrationGovernanceInput, CalibrationAdversarialSuiteRegistry, LessonCardPublisher | ~200 |
| `governance/calibration_leaderboard.py` (NEW) | CalibrationLeaderboard, CalibrationLeaderboardEntry, CalibrationLeaderboardMetrics | ~150 |
| `governance/calibration_validation.py` (NEW) | CalibrationValidationRunner, CalibrationValidationBundle | ~150 |
| `governance/stress_scenarios.py` (NEW) | StressScenarioKind (6 kinds), StressScenarioRunner, StressScenarioResult | ~150 |
| `governance/passes/strategic_response_pass.py` (NEW) | StrategicResponsePass | ~50 |
| `nodes/builtins/causal/` (NEW, 11 files) | 10 node classes: BuildLiteraturePriorNode, ReconcileCausalGraphNode, CounterfactualIdentificationGateNode, RunCausalReadinessNode, RunCausalContractExecutionNode, ResolveParametersNode, RunABMConsistencyCheckNode, RunCausalEnsembleNode, RunCausalQueriesNode, RunTransportabilityNode | ~2000 |
| `nodes/builtins/c6c_runtime_support.py` (NEW) | StrategicRuntimeOutput, ParameterOverrideMaterialization, maybe_materialize_policy_override_bundle() | ~200 |
| `nodes/builtins/planning/run_hierarchical_policy_search.py` (NEW) | RunHierarchicalPolicySearchNode | ~300 |
| `compute/advanced_methods.py` (NEW) | C7AdvancedInputs, C7PersistedArtifact, C7AdvancedSuiteResult | ~200 |

**P2 — Существующие модули (обновление):**

| File | Public API |
|------|-----------|
| `__init__.py` | ExperimentState, run_experiment, get_metrics, get_tracer |
| `workflows/causal_full.py` | CausalFullWorkflow spec |
| `workflows/policy_design.py` | PolicyDesignWorkflow spec |
| `governance/__init__.py` | Governance orchestrator |
| `governance/pass_registry.py` | PassRegistry, pass discovery |
| `governance/passes/__init__.py` | All 18+ passes |
| `search/judge_stack.py` | JudgeStack, scoring |
| `search/latent_governance.py` | Latent governance checks |
| `search/readiness.py` | Readiness assessment |

**Reference pages:**
- `docs/reference/scientist/index.md` — обзор orchestration layer
- `docs/reference/scientist/workflows.md` — causal_full, policy_design specs
- `docs/reference/scientist/governance-passes.md` — все 18+ passes. Для каждого:
  - pass_id, estimated_cost_ms
  - Что проверяет (purpose)
  - Inputs (какие artifact keys читает из state)
  - Outputs (ComplianceIssue types)
  - Failure conditions (когда блокирует pipeline)
- `docs/reference/scientist/nodes.md` — Node protocol + все builtin nodes
- `docs/reference/scientist/causal.md` — **НОВАЯ СТРАНИЦА** — 6 runners из causal/
- `docs/reference/scientist/calibration-governance.md` — **НОВАЯ СТРАНИЦА** — CalibrationGovernanceReport, BacktestMatrix, StressScenarios, Leaderboard

**Нюансы:**
- 10 causal node classes — каждый читает/пишет specific state artifact keys. Документировать какие keys каждый node требует и какие пишет
- `governance/passes/` содержит 23 файла — нужно 18+ pass descriptions. Для каждого pass: `pass_id`, `validate(ctx)` signature, list of ComplianceIssue types it can emit
- `compute/advanced_methods.py` — `_METHOD_MODULES` маппинг содержит 6 method categories — документировать каждый
- BacktestKind enum: MACRO, CELL, STRATEGIC_AGENT, HOUSEHOLD, DISTRESS — объяснить семантику каждого
- StressScenarioKind enum: BUDGET_CONTRACTION, PROCUREMENT_SHOCK, WAGE_SUBSIDY, FX, TRADE_DISRUPTION, REIMBURSEMENT_TARIFF — объяснить каждый

#### WS-2E: Fabric Docstrings

Add docstrings to key public API in `polisyos.fabric`.

**14 production connectors** (НЕ 9 — обновлённый подсчёт из `sources/__init__.py`):

| Connector | Source | Auth | Priority |
|-----------|--------|------|----------|
| WorldBankConnector | World Bank WDI API | None | P1 |
| EurostatConnector | Eurostat REST/JSON + **SDMX + async fetch (NEW)** | None | P1 |
| SDMXSourceConnector | ECB, OECD, IMF, BIS, FAO, ILO, UNSD | Per-provider | P1 |
| WHOConnector | WHO GHO | None | P2 |
| UNPDConnector | UN Population Division | None | P2 |
| UNESCOUISConnector | UNESCO UIS | None | P2 |
| WVSConnector | World Values Survey | None | P2 |
| UKONSConnector | UK Office for National Statistics | None | P2 |
| CKANCatalogConnector | CKAN catalog discovery | Per-portal | P3 |
| CKANResourceConnector | CKAN resource fetching | Per-portal | P3 |
| SocrataConnector | NYC, Chicago portals | App token | P3 |
| OpendatasoftConnector | Opendatasoft hub | API key | P3 |
| SPARQLConnector | Wikidata, DBpedia | None | P3 |
| RestJsonConnector | Generic REST JSON | Configurable | P3 |

**Для каждого connector docstring:**
```python
class EurostatConnector(HTTPConnectorBase):
    """Connector for Eurostat statistical data (REST JSON + SDMX).

    Fetches indicators from Eurostat public API with support for
    synchronous single-dataset and asynchronous bulk downloads.

    Data source: https://ec.europa.eu/eurostat
    Protocol: REST JSON (primary), SDMX-JSON (secondary)
    Auth: None required
    Rate limits: profile-configured (default: 10 rps)
    Async support: Yes (via AsyncFetchLease for large datasets)

    Supported operations:
        - fetch(): Synchronous single dataset retrieval
        - fetch_async(): Asynchronous bulk download (NEW)
        - describe_dataset(): Dataset metadata and constraints (NEW)

    Profile: eurostat_public (see builtin_profiles.py)
    """
```

**Profile system docstrings:**

| File | Public API | Status |
|------|-----------|--------|
| `profiles/models.py` | SourceProfile (30+ fields, **many NEW**), **SourceExecutionPolicy (NEW)** | Обновлён значительно |
| `profiles/resolver.py` | resolve_connection_config(), **resolve_execution_policy() (NEW)** | Новая функция |
| `profiles/builtin_profiles.py` | **63 profile instances** | Расширен |
| `profiles/registry.py` | SourceProfileRegistry (singleton) | Существующий |

**SourceProfile новые поля (нужны docstrings):**
- `max_concurrency`, `requests_per_hour` — execution control
- `preferred_core_transport`, `preferred_backfill_transport` — dual transport
- `supports_async_large_responses`, `supports_async_fetch` — async capabilities
- `schema_preflight`, `supports_content_constraints`, `supports_availability_constraints`
- `core_group_limit`, `backfill_group_limit`, `max_sync_cells`, `max_async_cells`
- `capability_cache_ttl_hours`, `negative_cache_ttl_hours`, `soft_negative_cache_ttl_hours`

**Reference pages:**
- `docs/reference/fabric/index.md` — обзор data fabric layer
- `docs/reference/fabric/connectors.md` — все 14 connectors + protocol description
- `docs/reference/fabric/profiles.md` — SourceProfile, SourceExecutionPolicy, resolver, 63 profiles
- `docs/reference/fabric/data-plane.md` — orchestrator, modes, watermarking

**Нюансы:**
- Eurostat connector **значительно расширен** — async fetch, describe_dataset — это ключевое обновление
- SDMX connector **promoted to production** — больше не experimental
- `SourceExecutionPolicy` — полностью новый frozen класс, документировать все поля
- 63 built-in profiles организованы по категориям (production, SDMX, CKAN, Socrata, Opendatasoft, SPARQL, REST Wave 3)
- НЕТ `data_plane/bindings.py` в fabric — bindings в `connectors/bindings/` (deprecated) и `foundry/data_plane/bindings.py`

#### WS-2F: REST API Reference

Generate `docs/reference/api/` from existing OpenAPI schema + manual enrichment.

**Алгоритм:**

1. Прочитать `schemas/runtime_api_v1.openapi.json` — извлечь все endpoints
2. Прочитать route files в `src/polisyos/runtime/http/routes/` — извлечь docstrings и handler signatures
3. Прочитать service files в `src/polisyos/runtime/http/services/` — бизнес-логика

**Целевые файлы:**

- `docs/reference/api/index.md`:
  - Базовый URL, authentication (JWT), error format, pagination
  - Таблица всех endpoints с HTTP method + path + краткое описание
  - Общие headers (Authorization, Content-Type)
  - Error response schema (`{"detail": "...", "status_code": 400}`)

- `docs/reference/api/runs.md` — endpoints под `/api/v1/runs/`:
  - Для каждого: method, path, description, request body (JSON schema), response body, status codes
  - Примеры curl/httpie для каждого endpoint

- `docs/reference/api/control.md` — endpoints под `/api/v1/control/`:
  - 3 POST + 2 GET (минимум, может быть больше)
  - ControlPlaneService bridge logic
  - TaskRunner background execution

- `docs/reference/api/artifacts.md` — artifact inspection endpoints

**Нюансы:**
- OpenAPI schema генерируется через `export_runtime_openapi_schema()` — убедиться что schema актуальна (POST endpoints добавлены)
- `openapi_contract.py` `_iter_operations` теперь фильтрует по `{"get", "post"}` (ранее только `{"get"}`)
- Проверить `runtime_api_env` fixture — может содержать актуальный список endpoints
- Lazy imports в route handlers — docstrings могут быть в imported modules, не в route file

#### WS-2G: CLI Reference

Create `docs/reference/cli.md`.

**Алгоритм:**

1. Выполнить каждую команду с `--help`:
   ```bash
   python -m polisyos --help
   python -m polisyos.foundry --help  # или polisyos-foundry --help
   polisy --help
   polisyos-causal-capabilities --help
   ```
2. Для каждого subcommand — тоже `--help`
3. Задокументировать exit codes (0 = success, 1 = error, 2 = usage error)

**Формат для каждой CLI:**
```markdown
## `polisy` — Foundry CLI

### Synopsis
polisy [COMMAND] [OPTIONS]

### Commands
| Command | Description |
|---------|-------------|
| compile | Compile ProblemFrame + PolicySpec into execution plan |
| execute | Execute compiled plan |
| inspect | Inspect CAS artifacts |

### `polisy compile`
[flags, examples, output format]

### `polisy execute`
[flags, examples, output format]
```

**Нюансы:**
- Проверить `pyproject.toml` [project.scripts] для точного списка CLI entry points
- Некоторые CLI могут быть недоступны без `[all]` extra — отметить prerequisites
- `polisyos-causal-capabilities` — вероятно генерирует report о доступных causal methods

#### WS-2H: Schema Catalog

Create `docs/reference/schemas.md`.

**Алгоритм:**

1. Прочитать `schemas/snapshots/ir/_manifest.json` — полный список схем
2. Для каждой `.schema.json` — извлечь title, description, required properties
3. Сгруппировать семантически

**Актуальный список (87+ схем, включая новые):**

| Group | Schemas (новые выделены) | Count |
|-------|-------------------------|-------|
| Governance | governance_pass_alias, governance_pass_alias_registry, governance_pass_alias_status, **governance_pass_mapping_bundle (NEW)** | ~5 |
| Analytics | causal_graph_model, causal_effect_report, hte_result, backtest_report, **backtest_plan_bundle (NEW)** | ~10 |
| Observation | **entity_scope (NEW)**, **observation_family (NEW)**, **observation_family_policy (NEW)**, **observation_family_policy_registry (NEW)**, **observation_panel (NEW)**, **observation_record (NEW)**, **observation_to_contract_manifest (NEW)**, **source_confidence_tier (NEW)**, **multiplex_graph_layer_id (NEW)** | ~9 NEW |
| Causal execution | **bounds_estimation_bundle (NEW)**, **causal_panel_bundle_manifest (NEW)**, **dtr_treatment_sequence_bundle_manifest (NEW)**, **proxy_identification_bundle (NEW)**, **network_causal_contract_bundle (NEW)**, **network_contract_bundle (NEW)** | ~6 NEW |
| Measurement | **measurement_aware_loss_config (NEW)**, **measurement_aware_target (NEW)**, **calibration_target_bundle_manifest (NEW)** | ~3 NEW |
| Strategic | **strategic_response_channel (NEW)**, **strategic_response_specs_bundle (NEW)**, **specification_curve_bundle (NEW)** | ~3 NEW |
| Temporal | **temporal_intervention_sequence (NEW)**, **temporal_intervention_step (NEW)**, **survival_data_bundle_manifest (NEW)** | ~3 NEW |
| Identification | **identification_mode (NEW)** | 1 NEW |
| IO/Econometric | **leontief_io_bundle (NEW)**, **panel_econometric_bundle_manifest (NEW)**, **microsim_survey_contract_bundle (NEW)** | ~3 NEW |
| Other | **lesson_registry_seed_bundle (NEW)** | 1 NEW |
| Existing | problem_frame, policy_spec, policy_portfolio, trinity_bundle, calibration_config, sensitivity_result, etc. | ~50 |

**Формат таблицы:**
```markdown
| Schema | Domain | Description | Key fields |
|--------|--------|-------------|------------|
| `entity_scope.schema.json` | Observation | Defines entity boundaries for analysis | scope_type, region_codes, sector_ids |
```

**Нюансы:**
- 30+ новых схем добавлены — значительное расширение каталога
- ABI versioning правила: ссылка на ADR-0005 (или актуальный номер — проверить)
- Каждая схема — ссылка на raw JSON file (relative path)
- Fabric schemas в `schemas/snapshots/fabric/` — тоже документировать (отдельная таблица)

---

### Phase 3 — Tutorials & How-to (parallel: 8 work streams)

**Dependency:** Phase 0 complete. **Can run in parallel with Phase 1 and 2.**

#### WS-3A: Tutorial — Getting Started

`docs/tutorials/getting-started.md`

**Целевая аудитория:** разработчик, впервые видящий проект. Цель: запустить первый пример за 15 минут.

**Обязательные секции:**

1. **Prerequisites:**
   - Python 3.14+ (macOS: `brew install python@3.14`, Linux: deadsnakes PPA)
   - Git
   - ~2GB дискового пространства (JAX + dependencies)

2. **Installation:**
   ```bash
   git clone <repo> && cd policy-engine
   pip install -e ".[all]"
   ```
   **Критично:** проверить что `pip install -e ".[all]"` реально работает без ошибок.
   Если есть optional groups — описать минимальный набор: `pip install -e ".[core]"`

3. **Verify installation:**
   ```bash
   polisyos --version
   python -c "from polisyos.ir import ProblemFrame; print('OK')"
   python -c "from polisyos.foundry import compile_program; print('OK')"
   ```
   Каждая команда с ожидаемым output.

4. **Minimal example (полностью рабочий, copy-paste):**
   ```python
   from polisyos.ir import ProblemFrame, PolicySpec, TrinityBundle
   from polisyos.scientist import run_experiment
   # ... minimal setup
   # ... run
   # ... print results
   ```
   **Критично:** пример ДОЛЖЕН работать. Перед написанием — выполнить в реальном окружении.
   Если `run_experiment` требует data — использовать synthetic/mock данные.

5. **Inspect results:**
   - Показать как читать CAS artifacts
   - Показать run timeline / metrics
   - Screenshot или ASCII output

6. **What's next:** ссылки на Tutorial #2, How-to guides, Reference

**Нюансы:**
- НЕ Python 3.11 — проект на 3.14
- Нет Docker — не упоминать
- Нет venv requirement — показать как optional
- JAX на Apple Silicon может требовать `jax[metal]` — отметить
- Если `run_experiment` слишком сложен для getting-started — использовать более простой entry point (compile + execute)

#### WS-3B: Tutorial — First Policy Analysis

`docs/tutorials/first-policy-analysis.md`

**Целевая аудитория:** аналитик/исследователь, хочет понять полный pipeline.

**Сценарий:** "Как образовательные расходы влияют на GDP growth? Анализ для Украины 2015-2023."

**Обязательные секции:**

1. **Постановка задачи (1 абзац):**
   Объяснить: мы хотим оценить causal effect образовательных расходов на GDP.

2. **Шаг 1: Определить ProblemFrame**
   ```python
   from polisyos.ir import ProblemFrame, EntityScope
   frame = ProblemFrame(
       outcome_kpi="gdp_growth",
       treatment="education_expenditure_pct_gdp",
       entity_scope=EntityScope(region_codes=["UKR"]),
       temporal_window=("2015-01-01", "2023-12-31"),
       ...
   )
   ```
   Объяснить каждое поле. Использовать реальные field names из кода.

3. **Шаг 2: Создать PolicySpec**
   ```python
   from polisyos.ir import PolicySpec
   spec = PolicySpec(
       intervention_kind="education_spending_increase",
       ...
   )
   ```

4. **Шаг 3: Привязать данные через Fabric**
   ```python
   from polisyos.fabric.connectors.sources import WorldBankConnector
   # fetch World Bank indicators
   # show actual indicator codes (NY.GDP.MKTP.KD.ZG, SE.XPD.TOTL.GD.ZS)
   ```

5. **Шаг 4: Compile и Execute**
   ```python
   from polisyos.foundry import compile_program, execute
   plan = compile_program(trinity_bundle)
   result = execute(plan)
   ```

6. **Шаг 5: Чтение результатов**
   - Causal graph visualization
   - Effect estimates (ATE, CATE)
   - Backtest metrics
   - Sensitivity analysis

7. **Полный код (один блок, copy-pasteable)**

**Нюансы:**
- Использовать реальные World Bank indicator codes
- Все field names — из текущего кода (проверить ProblemFrame, PolicySpec, EntityScope)
- Если full pipeline слишком complex — упростить, но показать все 5 шагов
- Включить expected output (даже если synthetic)

#### WS-3C: How-to — Installation

`docs/how-to/install.md`

**Секции:**

1. **Minimal install:**
   ```bash
   pip install -e "."   # core only
   ```
   Что включено: IR types, core contracts

2. **Full install:**
   ```bash
   pip install -e ".[all]"
   ```
   Что включено: всё

3. **Specific extras** (проверить `pyproject.toml` [project.optional-dependencies]):
   | Extra | What it adds | Use case |
   |-------|-------------|----------|
   | `[causal]` | ... | Causal analysis |
   | `[ml]` | ... | Machine learning methods |
   | `[deep]` | ... | Deep learning (torch) |
   | `[security]` | ... | JWT, OPA, SPIFFE |
   | `[rag]` | ... | RAG for knowledge store |
   | `[dev]` | ... | Development tools |
   | `[test]` | ... | Testing dependencies |

4. **Development install:**
   ```bash
   pip install -e ".[dev,test,all]"
   pre-commit install  # если есть
   ```

5. **Troubleshooting:**
   - JAX installation issues (CPU vs GPU vs Metal)
   - Apple Silicon specific (jax[metal], grpcio)
   - Missing system deps
   - pip resolver conflicts

**Нюансы:**
- Прочитать `pyproject.toml` для ТОЧНОГО списка extras и их зависимостей
- Python 3.14 — отметить как minimum
- Нет Docker — не включать Docker секцию
- Нет PyPI package — установка только из source

#### WS-3D: How-to — Add Data Source

`docs/how-to/add-data-source.md`

**Полный пошаговый guide:**

1. **Choose connector type:**
   - Если source имеет REST API → extend `HTTPConnectorBase`
   - Если SDMX → extend `SDMXSourceConnector`
   - Если CKAN → extend `CKANResourceConnector`
   - Если SPARQL → extend `SPARQLConnector`

2. **Create connector class:**
   ```python
   # src/polisyos/fabric/connectors/sources/my_source.py
   from polisyos.fabric.connectors.sources._base import HTTPConnectorBase

   class MySourceConnector(HTTPConnectorBase):
       CONNECTOR_ID = "my_source"

       def fetch(self, query: DataQuery) -> DataFrame:
           ...
   ```
   Показать реальный минимальный connector (скопировать pattern из простейшего, e.g., `who.py`)

3. **Register in `__init__.py`:**
   ```python
   # sources/__init__.py — add to imports and __all__
   ```

4. **Create source profile:**
   ```python
   # profiles/builtin_profiles.py — add entry
   SourceProfile(
       profile_id="my_source_public",
       connector_family="my_source",
       base_url="https://api.example.com",
       ...
   )
   ```
   Показать все поля которые нужно заполнить (включая новые execution policy поля)

5. **Add schema contract** (optional):
   ```python
   # sources/_contracts/my_source_contracts.py
   ```

6. **Testing:**
   - Добавить в `test_production_connectors.py` (показать pattern)
   - Integration test с реальным API (mark `@pytest.mark.integration`)

7. **CI validation:**
   - Как arch-freeze проверяет новый connector

**Нюансы:**
- Показать реальный code из существующего простого connector (WHO или UNPD)
- SourceProfile теперь имеет 30+ полей — показать какие обязательные, какие optional
- `SourceExecutionPolicy` — resolve автоматически из profile, не нужно создавать вручную
- Connector-specific CONTRIBUTING.md — ссылка на `docs/connectors/CONTRIBUTING.md`

#### WS-3E: How-to — Write Governance Pass

`docs/how-to/write-governance-pass.md`

**Полный пошаговый guide:**

1. **Pass interface:**
   ```python
   class MyPass(ValidatorPass):
       @property
       def pass_id(self) -> str:
           return "my_check"

       @property
       def estimated_cost_ms(self) -> float:
           return 10.0

       def validate(self, ctx: GovernanceContext) -> list[ComplianceIssue]:
           ...
   ```
   Использовать `StrategicResponsePass` как пример (реальный новый pass).

2. **ComplianceIssue types:**
   - Severity levels
   - Issue categories
   - Blocking vs warning

3. **Registration:**
   - Entry point в `pyproject.toml` (если используется)
   - Или добавление в `pass_registry.py`
   - Или в `governance/passes/__init__.py`

4. **Reading state/artifacts:**
   ```python
   def validate(self, ctx):
       state = ctx.state
       # Read specific artifact keys
       value = state.get("my_artifact_key")
   ```

5. **Testing:**
   ```python
   def test_my_pass():
       pass_ = MyPass()
       ctx = make_governance_context(...)  # show fixture pattern
       issues = pass_.validate(ctx)
       assert len(issues) == 0
   ```
   Показать реальный тест pattern из `tests/scientist/governance/`

6. **Integration с workflow:**
   - Как pass включается в GovernancePassAlias
   - Как alias связывается с PolicySpec

**Нюансы:**
- Прочитать `governance/passes/__init__.py` для точного списка существующих passes
- Прочитать `pass_registry.py` для механизма registration
- `strategic_response_pass.py` — хороший пример нового pass (простой, понятный)
- `GovernanceContext` — показать какие поля доступны (state, artifacts, metadata)

#### WS-3F: How-to — Run Benchmarks

`docs/how-to/run-benchmarks.md`

**Секции:**

1. **Overview:**
   - Benchmark categories: comparators, abstraction, advanced, composition, distributional, governance, interaction, proof_closure, strategic, temporal
   - Suite registry (`benchmarks/suite_registry.py`)

2. **Quick run:**
   ```bash
   cd policy-engine
   bash benchmarks/run_all_benchmarks.sh
   ```
   Показать expected output format.

3. **Selective run:**
   ```bash
   pytest benchmarks/comparators/ -v
   pytest benchmarks/strategic/ -v
   ```

4. **Suite registry configuration:**
   - Как зарегистрировать новый benchmark suite
   - Формат suite descriptor
   - Прочитать `suite_registry.py` для точного API

5. **Interpreting results:**
   - `benchmarks/reporting.py` — как формируется report
   - `benchmarks/build_release_summary.py` — release summary generation
   - Метрики: acceptance rates, execution time, quality scores

6. **Adding new benchmarks:**
   - Создать файл в соответствующей категории
   - Зарегистрировать в suite_registry
   - Формат: показать pattern из существующего benchmark

7. **CI integration:**
   - `perf.yml` workflow — что он делает
   - Regression detection

**Нюансы:**
- Прочитать `run_all_benchmarks.sh` для точной последовательности
- Прочитать `suite_registry.py` для API
- Новые benchmark directories: abstraction/, advanced/, distributional/, governance/, interaction/, proof_closure/, strategic/ — все untracked
- `comparators/` — research acceptance environment (`research_acceptance_environment.yml`)

#### WS-3G: How-to — Deploy Runtime

`docs/how-to/deploy-runtime.md`

**Секции:**

1. **Local development:**
   ```bash
   # Start HTTP server
   python -m polisyos.runtime.http  # или через CLI
   # → http://localhost:8000
   # → Swagger UI: http://localhost:8000/docs
   ```

2. **Configuration:**
   - Environment variables (перечислить все из кода)
   - `pyproject.toml` runtime section (если есть)
   - Auth config (JWT secret, OPA policy path)

3. **Endpoints overview:**
   - `/api/v1/runs/` — 16 endpoints
   - `/api/v1/control/` — POST/GET endpoints
   - `/health`, `/ready` — health checks

4. **Frontend dashboard:**
   ```bash
   cd frontend/runtime-dashboard
   npm install && npm run dev
   # → http://localhost:5173
   ```
   Описать pages: `/launch` (LaunchRun), `/data` (DataManagement)

5. **Production considerations:**
   - Gunicorn/uvicorn workers
   - OPA sidecar for authorization
   - SPIFFE for service identity
   - TLS termination

6. **Monitoring:**
   - OpenTelemetry tracing (get_tracer, get_metrics)
   - Health/readiness probes
   - Structured logging

**Нюансы:**
- Lazy imports для heavy modules — server starts fast
- `runtime_api_env` fixture в tests показывает как создать test app
- Control plane: `ControlPlaneService` + `TaskRunner` (ThreadPoolExecutor)
- NL endpoint uses mock agents when llm_model=None
- Нет Docker — не включать Docker deployment (пока)

#### WS-3H: How-to — Causal Analysis

`docs/how-to/run-causal-analysis.md`

**Полный workflow guide на основе актуального кода:**

1. **Causal Discovery Pipeline:**
   - `discovery_pipeline.py` — constraint-based + DAGMA
   - `constraint_discovery.py` — PC algorithm
   - `dagma_discovery.py` — DAGMA continuous optimization
   - Пример: input data → CausalGraphModel output

2. **Causal Identification:**
   - `id_engine.py` — do-calculus based identification
   - Identification modes (из `IdentificationMode` enum)
   - Back-door, front-door, IV strategies
   - Пример: graph + query → identification strategy

3. **Bounds Estimation (NEW):**
   - `bounds_engine.py` — partial identification bounds
   - `BoundsEstimationRunner` (из `scientist/causal/execution.py`)
   - BoundsEstimationTask → BoundsEstimationEntry
   - Пример: unidentifiable query → bounds

4. **Sensitivity Analysis:**
   - `specification_curve_bundle` — specification curve analysis
   - `sensitivity_result` — sensitivity diagnostics
   - Пример: main estimate → sensitivity checks

5. **Dynamic Treatment Regimes (DTR):**
   - `dtr.py` — temporal treatment sequences
   - `TemporalInterventionSequence`, `TemporalInterventionStep`
   - Пример: multi-period intervention → optimal sequence

6. **Strategic Response (NEW):**
   - `strategic.py` — game-theoretic response modeling
   - `StrategicResponseRunner` (из `scientist/causal/readiness.py`)
   - StrategicSCM → equilibrium analysis
   - Пример: policy + strategic agents → equilibrium

7. **Full Workflow (end-to-end code):**
   ```python
   # Step 1: Discovery
   # Step 2: Identification
   # Step 3: Estimation + Bounds
   # Step 4: Sensitivity
   # Step 5: Strategic Response
   # Step 6: Governance check
   ```

**Нюансы:**
- Новые runner classes в `scientist/causal/` — основной entry point для programmatic use
- 10 causal node classes — для orchestrated pipeline через Scientist workflow
- `measurement_error.py` — proxy boundary metadata propagation (новое)
- `policy_learning.py` — OptimalPolicyLearner для budget-constrained targeting
- Все примеры должны использовать актуальные import paths и class names

---

### Phase 4 — Explanation Deep-dives (parallel: 6 work streams)

**Dependency:** Phase 0 complete. **Can run in parallel with Phase 1-3.**

#### WS-4A: Explanation — Causal Engine

`docs/explanation/causal-engine.md`

**Источники:**
- `docs/CAUSAL_ENGINE_ARCHITECTURE.md` — основной source (архивировать оригинал в WS-5A)
- `src/polisyos/foundry/methods/catalog/causal/` — method implementations
- `src/polisyos/scientist/causal/` — runner classes (NEW)
- `src/polisyos/scientist/nodes/builtins/causal/` — 10 node implementations (NEW)

**Целевая структура:**

```markdown
# Causal Engine: Design Rationale

## Зачем свой causal engine (1-2 абзаца)
- Стандартные инструменты (DoWhy, EconML) не покрывают policy-specific requirements
- Нужна интеграция: discovery → identification → estimation → bounds → sensitivity → strategic → governance
- Поддержка partial identification когда полная идентификация невозможна

## Pipeline архитектура
[Mermaid diagram: Discovery → Graph → Identification → Estimation → Bounds → Sensitivity → Strategic → Governance]

## Stage 1: Causal Discovery
- Двойная стратегия: constraint-based (PC) + continuous optimization (DAGMA)
- ReconcileCausalGraphNode: combines data graph + literature prior + user hints + SCM fragments
- Ensemble: RunCausalEnsembleNode — bootstrap stability + member resolution
- Output: CausalGraphModel

## Stage 2: Identification
- CounterfactualIdentificationGateNode — gate logic: pass/fail
- do-calculus engine (id_engine.py)
- Multiple strategies: back-door, front-door, IV
- IdentificationMode enum — routing logic (из observation/measurement.py)

## Stage 3: Estimation & Bounds
- BoundsEstimationRunner — partial identification
- BoundsEstimationTask → BoundsEstimationEntry pipeline
- Proxy identification: ProxyIdentificationRunner
- Measurement error correction: _proxy_boundary_metadata() propagation

## Stage 4: Sensitivity & Specification Curves
- SpecificationCurveBundle — multiple specifications
- SensitivityResult — robustness diagnostics

## Stage 5: Strategic Response (NEW)
- Зачем: agents adapt to policy → naive estimates biased
- StrategicSCM + StrategicPayoffTable → equilibrium analysis
- StrategicResponseRunner — solves game-theoretic problems
- RunABMConsistencyCheckNode — ABM validation of strategic predictions

## Stage 6: Transportability
- TransportabilityChecker — cross-regime validity
- RunTransportabilityNode — alignment search + certificates
- RegimeCalendar, SchemaRegimeRegistry — temporal regime handling

## Stage 7: Dynamic Treatment Regimes (DTR)
- TemporalInterventionSequence — multi-period treatments
- DTR task execution via causal execution bundles

## Integration с Foundry
- Methods в methods/catalog/causal/: discovery_pipeline, dagma_discovery, constraint_discovery, causal_engine, bounds_engine, id_engine, dtr, measurement_error, strategic, policy_learning
- OptimalPolicyLearner — budget-constrained targeting via CATE

## Integration с Scientist
- CausalFullWorkflow — orchestrates all stages via node graph
- 10 causal nodes: литература, граф, идентификация, readiness, execution, ensemble, ABM, queries, transport, parameters
- Governance: StrategicResponsePass validates strategic analysis presence
```

**Нюансы:**
- Весь causal/ в scientist — НОВЫЙ (3 файла), causal/ в nodes — НОВЫЙ (11 файлов)
- Diagram должна показывать полный pipeline включая новые stages (bounds, strategic, transport)
- Объяснить зачем PARTIAL identification (не всё identifiable — bounds дают honest range)
- Объяснить strategic response: Nash equilibrium в policy context

#### WS-4B: Explanation — Governance Model

`docs/explanation/governance-model.md`

**Источники:**
- `src/polisyos/scientist/governance/` — 21 файл
- `src/polisyos/scientist/governance/passes/` — 23 pass implementations
- `src/polisyos/scientist/governance/pass_registry.py`
- `src/polisyos/scientist/governance/pass_entrypoints.py`
- Новые: `backtest_matrix.py`, `calibration.py`, `calibration_leaderboard.py`, `calibration_validation.py`, `stress_scenarios.py`

**Целевая структура:**

```markdown
# Governance Model

## Зачем governance (1 абзац)
Automated policy analysis может рекомендовать harmful policies.
Governance passes — series of checks before any recommendation is published.

## Pass Registry Architecture
- PassRegistry: discovery + registration
- Pass entry points: pyproject.toml или manual registration
- Pass lifecycle: register → discover → validate → report

## Pass Types
### Automated (fast, always run)
- Budget check, privacy check, equity check, safety check
- estimated_cost_ms: 5-50ms

### Statistical (require computation)
- Calibration validation
- Backtest matrix (5 kinds: MACRO, CELL, STRATEGIC_AGENT, HOUSEHOLD, DISTRESS)
- Stress scenarios (6 kinds: BUDGET_CONTRACTION, PROCUREMENT_SHOCK, WAGE_SUBSIDY, FX, TRADE_DISRUPTION, REIMBURSEMENT_TARIFF)
- Specification curve analysis

### Human review (gate)
- Checkpoint pass — requires human approval
- Условия для trigger

## Calibration Governance Pipeline (NEW)
[Mermaid: CalibrationGovernanceInput → CalibrationValidationRunner → BacktestMatrixRunner + StressScenarioRunner → CalibrationLeaderboard → CalibrationGovernanceReport]
- CalibrationGovernanceReport: master verdict + issues
- CalibrationLeaderboard: ranked entries with 7 metric scores
- LessonCardPublisher: persists lessons from failed governance

## ComplianceIssue Protocol
- Severity: blocking, warning, info
- Categories: budget, privacy, equity, safety, statistical
- How issues flow: pass → issues → report → gate decision

## Integration с Scientist Workflows
- GovernancePassAlias — connects pass to PolicySpec
- GovernancePassAliasRegistry — manages alias lifecycle
- run_governance node — executes pass pipeline within workflow

## Checkpoint & Replay
- CheckpointPass — saves state for replay
- How to resume from checkpoint after human review
```

**Нюансы:**
- 5 НОВЫХ governance файлов — backtest_matrix, calibration*, stress_scenarios
- Полная calibration governance pipeline — это крупное новое addition
- 23 pass файла в passes/ — нужно перечислить все 18+ уникальных passes (не все файлы = уникальные passes)
- Leaderboard: 7 float metric scores — перечислить какие именно (из CalibrationLeaderboardMetrics)

#### WS-4C: Explanation — Data Fabric

`docs/explanation/data-fabric.md`

**Источники:**
- `src/polisyos/fabric/` — весь модуль
- `src/polisyos/fabric/connectors/profiles/` — обновлённая profile system
- `src/polisyos/fabric/connectors/sources/` — 14 connectors

**Целевая структура:**

```markdown
# Data Fabric Architecture

## Обзор (1 абзац)
Fabric = unified interface to 14 heterogeneous data sources.
Abstracts protocol (REST, SDMX, SPARQL, CKAN) behind SourceProfile + connector protocol.

## Connector Pipeline
[Mermaid: SourceProfile → resolve_connection_config → Connector.fetch() → CAS → World Store → Data Plane]

## Connector Protocol
- HTTPConnectorBase — base class for REST connectors
- Required methods: fetch(), optional: fetch_async(), describe_dataset()
- ConnectorMetadataSpec: trust level (AUTHORITATIVE/CURATED/COMMUNITY), quality tier

## Profile System (significantly expanded)
- SourceProfile: 30+ fields defining source capabilities
- **SourceExecutionPolicy (NEW)**: normalized runtime execution control
  - Dual transport: core vs backfill transport preferences
  - Async support: max_sync_cells, max_async_cells
  - Caching: capability/negative/soft-negative cache TTLs
  - Concurrency: max_concurrency, group_limit controls
- resolve_connection_config(): profile → connector config
- resolve_execution_policy(): profile → execution policy

## 63 Built-in Profiles
- Production: worldbank, wvs, eurostat, ukons, who, unpd, unesco_uis
- SDMX: ecb, oecd, imf, bis, ilo, fao, unsd
- Open Data: CKAN portals (UK, US, UA, RO, MD, EU), Socrata, Opendatasoft
- SPARQL: Wikidata, DBpedia
- REST Wave 3: Poland, USGS, OpenAQ, Open-Meteo, EIA, NVD

## Async & Bulk Fetch (NEW)
- AsyncFetchLease — lease for async large responses
- Eurostat: describe_dataset() → DatasetCapabilitySnapshot → decide sync/async
- SDMX: time filter support, multi-provider routing

## Data Quality
- SourceConfidenceTier (from observation module)
- MeasurementTrustTier — per-indicator trust weighting
- Schema validation via contracts/

## CAS Integration
- Artifacts stored in content-addressable store
- Provenance tracking (PROV export)
- Watermarking for version control
```

**Нюансы:**
- Profile system значительно расширена — SourceExecutionPolicy полностью НОВЫЙ
- 14 connectors (не 9) — подсчёт обновлён
- 63 profiles (не считались ранее) — крупное расширение
- Async fetch — ключевое новое capability (Eurostat, SDMX)
- Dual transport strategy (core vs backfill) — новая архитектурная концепция

#### WS-4D: Explanation — Lex Pipeline

`docs/explanation/lex-pipeline.md`

**Источники:**
- `src/polisyos/lex/` — весь модуль (65 exports)
- `src/polisyos/lex/batch/` — 51 файл pipeline
- Новые файлы: interventions.py, intervention_artifacts.py, batch/amendment_*, batch/hallucination_*, batch/quality_filters.py, batch/temporal_resolver.py

**Целевая структура:**

```markdown
# Lex Pipeline: Legal Corpus Processing

## Обзор
Lex = transform raw legal texts → structured NormPacks → policy-ready intervention specs.
51 files in batch pipeline covering extraction, quality, temporal, governance.

## Pipeline Architecture
[Mermaid: Raw docs → Ingest → Structure → SPO Extract → Canonicalize → QC → Temporal → NormPack → Interventions]

## Stage 1: Ingest & Structure
- ingest_legal_doc_bytes() → LexIngestResult
- build_legal_structure() → LexStructureResult
- LegalDocSource, doc_identity.py, legal_unit.py

## Stage 2: SPO Extraction
- spo_extractor.py — LLM-based extraction
- deterministic_spo.py + deterministic_spo_core.py + deterministic_spo_subtypes.py
- Entity resolution (entity_resolver.py)
- Canonicalization (canonicalizers.py)

## Stage 3: Quality Control (significantly expanded)
### Amendment Detection (NEW)
- amendment_detector.py: 9+ regex patterns, 3-pass detection with confidence scoring
- AmendmentRecord: type, target_anchor, old/new text, effective_from
- amendment_metrics.py: 16 QC metrics (resolution rates, coverage %)

### Hallucination Detection (NEW)
- hallucination_detector.py: semantic consistency checks
- Detection types: phantom_article_reference (high), ungrounded_subject (medium), phantom_number (high), norm_type_mismatch (medium)
- has_blocking_hallucination() — gate function

### Quality Filtering (NEW)
- quality_filters.py: Ukrainian-specific deterministic heuristics
- is_synthetic_subject() — detect synthetic subjects
- is_low_quality_entity_text() — comprehensive quality scoring
- has_explicit_modal_signal() — obligation/prohibition markers

### Quality Report
- quality_report.py — aggregated quality metrics
- Gate metrics for pipeline progression

## Stage 4: Temporal Resolution (NEW)
- temporal_resolver.py: deterministic temporal envelope resolution
- DocTemporalEnvelope: published_at, effective_from/to, temporal_state
- FactTemporalEnvelope: inherited/derived temporal bounds
- Status semantics: current, historical, suspended, future
- Confidence scoring + JSON provenance

## Stage 5: NormPack Assembly
- assemble_norm_pack() — assembly from structured provisions
- NormPackBudgets — constraint handling
- Mutation: NormPackMutator, MutationIntent
- Diff: diff_norm_packs() → NormDiff

## Stage 6: Interventions (NEW)
- LexInterventionCompiler — provision directives → executable interventions
- InterventionKnobSpec — tunable parameter specifications with bounds
- TemporalInterventionSequencer — legal timelines → DTR-ready sequences
- HierarchicalPolicySearchAdapter — policy search coordination
- StrategicResponseSpecRegistry — strategic response catalog

## Stage 7: Impact Analysis
- NormImpactAnalyzer → NormImpactReport
- ComplianceTransition, ComplianceDelta, AffectedKPI

## Knowledge Layer
- LegalKnowledgeGraph — graph representation
- Knowledge store with search + filters
- Version management (ActiveVersionStrategy)

## Integration Points
- IR: TemporalInterventionSequence/Step (from IR types)
- Foundry: intervention parameters → agent simulation
- Scientist: LexPolicyBundleInput → policy design workflow
- Observation: ObservationFamily integration for temporal data
```

**Нюансы:**
- 7 полностью новых файлов в Lex — pipeline значительно расширен
- Intervention system (interventions.py + intervention_artifacts.py) — крупное новое addition
- Amendment detection — 3-pass strategy с confidence scoring (описать алгоритм)
- Hallucination detection — post-grounding checks (объяснить зачем после, а не до)
- Quality filters — Ukrainian-specific (объяснить что паттерны для UA законодательства)
- Temporal resolver — ключевая новая capability (effective dates, status semantics)

#### WS-4E: Explanation — Security Model

`docs/explanation/security-model.md`

**Источники:**
- `docs/fedramp/` directory
- `docs/key-rotation.md`
- `src/polisyos/core/security/`
- ADR-0010 (artifact signing)

**Целевая структура:**

```markdown
# Security Model

## Threat Model (1-2 абзаца)
Policy recommendations affect real people → security must be production-grade.
Threats: unauthorized access, data tampering, model poisoning, audit trail gaps.

## Authentication: JWT
- Token format, claims
- Issuance and rotation
- Key rotation procedures (from key-rotation.md)

## Authorization: OPA
- Policy-as-code approach
- Shadow mode: log violations without blocking (development)
- Enforcement mode: block unauthorized operations (production)
- Policy structure and examples

## Identity: SPIFFE
- Service identity for inter-service communication
- SVID (SPIFFE Verifiable Identity Document)
- Trust domain configuration

## Artifact Integrity: CAS + Ed25519
- Content-addressable storage → tamper detection
- Ed25519 signatures on artifacts (ADR-0010)
- Verification pipeline
- Chain of custody: data source → connector → CAS → analysis → results

## Compliance: FedRAMP / NIST 800-53
- Which controls are covered
- Mapping: NIST control → PolicyOS implementation
- Gap analysis (if any)

## Audit Trail
- OpenTelemetry traces → audit events
- Immutable audit log
- What gets logged: data access, policy evaluation, governance decisions
```

**Нюансы:**
- Прочитать `docs/fedramp/` полностью — может содержать готовые mapping tables
- Прочитать `docs/key-rotation.md` — процедуры ротации ключей
- Прочитать `core/security/` — актуальная реализация (imports, classes)
- ADR-0010 — номер может быть другим, проверить в `docs/adr/` по содержанию (artifact signing)
- TEE (Trusted Execution Environment) — упоминался в плане, проверить есть ли реализация

#### WS-4F: Explanation — Observation Contracts

`docs/explanation/observation-contracts.md`

**Источники:**
- `src/polisyos/ir/observation/` — 9 файлов, 133+ классов (полностью NEW)
- JSON schemas: 9 новых observation-related schemas

**Целевая структура:**

```markdown
# Observation Contracts: Data-to-Model Bridge

## Зачем Observation Layer (2 абзаца)
- Проблема: разнородные данные (panel, cross-section, survey, administrative) → одни и те же causal methods
- Решение: Observation contracts — формальный протокол что данные ДОЛЖНЫ содержать для корректного causal inference
- Contract-driven: если данные не соответствуют → bounds, не point estimates

## Иерархия типов
[Mermaid: ObservationFamily → ObservationPanel → ObservationRecord]

### ObservationFamily
- Defines: what kind of data (survey, administrative, experimental)
- ObservationFamilyPolicy: rules per family
- ObservationFamilyPolicyRegistry: manages family policies

### ObservationPanel
- Time-indexed collection of records
- Schema: observation_panel.schema.json

### ObservationRecord
- Single observation unit
- Schema: observation_record.schema.json

### EntityScope
- Geographic + sectoral + temporal boundaries
- Schema: entity_scope.schema.json

## Measurement & Trust (NEW — 12 classes)
### MeasurementTrustTier
- Trust levels for different data sources
- Feeds into calibration effective weight calculation

### RegimeCalendar & SchemaRegimeRegistry
- Temporal regime handling (policy changes = regime breaks)
- SchemaChangepoint: marks structural breaks in data

### ShockCalendar
- External shock events (COVID, financial crisis)
- Discount factors for shock-affected observations

### IdentificationMode & IdentificationModeRouter
- Routes causal queries based on data availability
- Modes: IV, DiD, RDD, panel, cross-section, bounds-only

## Contract Compilers (54 classes in contract_compilers.py)
### ObservationContractCompilerSuite
- Compiles abstract data requirements → concrete data contracts
- Per-method compilation: bounds, IO, specification curve, etc.

### Key compiler artifacts:
- BoundsEstimationInput — what bounds engine needs
- LeontiefIOInput — what IO model needs
- SpecificationCurveInput — what specification curves need
- SparseDenseBridge — handles sparse/dense data transitions

## Causal Execution Integration
### BoundsEstimationTask → BoundsEstimationEntry
- Task defines what to estimate
- Entry contains results + metadata

### CausalExecutionBundle
- Aggregates all causal execution results
- Reference: CausalExecutionBundleRef

### CausalReadinessBundle
- Pre-flight checks before causal analysis
- Reference: CausalReadinessBundleRef

## Bundle Types (42 classes in bundles.py)
- BacktestPlanBundle — backtest configuration
- CausalPanelBundleManifest — panel data contracts
- DTRTreatmentSequenceBundleManifest — DTR data requirements
- SurvivalDataBundleManifest — survival analysis contracts
- PanelEconometricBundleManifest — panel econometric contracts
- NetworkContractBundle / NetworkCausalContractBundle — network data
- MicrosimSurveyContractBundle — microsimulation contracts
- LessonRegistrySeedBundle — governance lesson persistence
- ProxyIdentificationBundle — proxy variable requirements
- CalibrationTargetBundleManifest — calibration data requirements

## Schema Catalog
9 new JSON schemas:
entity_scope, observation_family, observation_panel, observation_record,
source_confidence_tier, multiplex_graph_layer_id, identification_mode,
observation_family_policy, observation_to_contract_manifest

## Integration Map
- → Foundry: calibration/measurement.py reads trust tiers → effective weights
- → Scientist: causal runners consume execution/readiness bundles
- → Fabric: SourceConfidenceTier informs trust weighting
- → IR: all types exported through ir/__init__.py (160 exports)
```

**Нюансы:**
- observation/ — **полностью новый модуль** (9 файлов, 133+ классов). Это самый крупный untracked addition.
- bundles.py — 42 (!) класса — документировать группами, не поштучно
- contract_compilers.py — 54 (!) класса — документировать pattern, не каждый compiler
- measurement.py — 12 классов — ключевая концепция для понимания calibration
- Связь с `foundry/calibration/measurement.py` — те же концепции (trust tiers, regimes, shocks) но на foundry side это compute, на IR side это contracts

---

### Phase 5 — Housekeeping & CI (parallel: 5 work streams)

**Dependency:** Phase 0 complete. **Can run in parallel with Phase 1-4.**

> **КРИТИЧНО для WS-5B:** Документация (README файлы) не обновлялась минимум 5-6 коммитов подряд.
> Каждый WS-5B sub-task выполняется в **ДВА ЭТАПА**:
>
> **Этап A — Глубокое исследование (read-only):**
> 1. Прочитать текущий README файл
> 2. Выполнить `ls` и `tree` на директорию модуля
> 3. Прочитать `__init__.py` — актуальные exports
> 4. Прочитать все НОВЫЕ файлы (untracked in git status)
> 5. Проверить `git diff` на все ИЗМЕНЁННЫЕ файлы
> 6. Составить delta-report: что добавлено, что изменено, что устарело в README
>
> **Этап B — Переписывание README:**
> На основе delta-report из Этапа A переписать README по шаблону из style-guide.
> НЕ начинать Этап B без завершения Этапа A.

#### WS-5A: Archive Stale Documents

Move outdated strategic documents to `docs/archive/plans/`.

**Полный список для архивации (проверить наличие каждого файла перед move):**

```
docs/CAUSAL_ENGINE_BEYOND_SOTA_BLUEPRINT.md    → archive/plans/
docs/CAUSAL_ENGINE_IMPLEMENTATION_PLAN.md      → archive/plans/
docs/CAUSAL_ENGINE_RESEARCH_AGENDA.md          → archive/plans/
docs/CAUSAL_ENGINE_SOTA_PLAN.md                → archive/plans/
docs/FOUNDRY_SOTA_PLAN.md                      → archive/plans/
docs/SCIENTIST_SOTA_AUTORESEARCH_BLUEPRINT.md  → archive/plans/
docs/SCIENTIST_SOTA_ROADMAP.md                 → archive/plans/
docs/ACADEMIC_PIPELINE_10_OF_10_PLAN.md        → archive/plans/
docs/DATASETS_PIPELINE_10_OF_10_PLAN.md        → archive/plans/
docs/LEX_PIPELINE_10_OF_10_PLAN.md             → archive/plans/
docs/LOCAL_SOTA_EVIDENCE_PACK.md               → archive/plans/
docs/UKRAINE_OPEN_DATA_INTEGRATION_BLUEPRINT.md → archive/plans/
```

**Алгоритм для каждого файла:**

1. `ls docs/` — проверить что файл существует
2. `mkdir -p docs/archive/plans/`
3. Добавить header в начало файла:
   ```markdown
   > **Archived:** This document reflects plans as of [YYYY-MM-DD].
   > For current documentation, see [docs/explanation/](../explanation/).
   ```
   Дату взять из `git log -1 --format=%ci -- <file>` (last modification date).
4. `git mv docs/<file> docs/archive/plans/<file>`

**Move reports:**
```bash
git mv docs/reports/ docs/archive/reports/
```

**Дополнительно проверить:** могут быть другие stale docs не в списке:
```bash
ls docs/*.md | grep -v DOCUMENTATION_SOTA_PLAN
```
Если найдутся другие `*_PLAN.md`, `*_BLUEPRINT.md`, `*_ROADMAP.md` — тоже архивировать.

**Нюансы:**
- `docs/DOCUMENTATION_SOTA_PLAN.md` (этот файл) — НЕ архивировать
- `docs/architecture.md` — архивировать ПОСЛЕ создания `docs/explanation/architecture.md` (WS-1D)
- `docs/contracts/` — НЕ архивировать (актуальные контракты)
- `docs/adr/` — НЕ архивировать (immutable ADRs)
- `docs/connectors/` — НЕ архивировать (актуальный connector guide)
- `docs/fedramp/` — НЕ архивировать (актуальная compliance документация)
- Reports (46 dirs) — это auto-generated reports, архивировать целиком

Keep as historical reference, add header:
```markdown
> **Archived:** This document reflects plans as of [date].
> See [current docs](../explanation/) for up-to-date information.
```

Move `docs/reports/` (46 dirs of generated reports) to `docs/archive/reports/`.

#### WS-5B: Refresh Module READMEs — EXPANDED INTO PARALLEL SUB-TASKS

> **76+ README files** across 12 top-level modules.
> All WS-5B-* tasks are **independent and run in parallel**.
>
> ⚠️ **ВАЖНО: README файлы не обновлялись минимум 5-6 коммитов.**
> Последние коммиты (03f979a, be91748, 4e8e0a8, 7d492b1, 2e9e19a, 3535d89) добавили:
> - observation/ модуль (133+ классов)
> - scientist/causal/ (6 runner'ов)
> - scientist/nodes/builtins/causal/ (10 node'ов)
> - lex/interventions.py + intervention_artifacts.py
> - lex/batch/ 5 новых файлов (amendment, hallucination, quality, temporal)
> - foundry/agent_sim/wiring/ (3 файла)
> - foundry/calibration/measurement.py + auxiliary.py
> - scientist/governance/ 5 новых файлов (backtest, calibration, stress)
> - fabric/profiles/ расширение (SourceExecutionPolicy, 63 profiles)
> - contracts/state.py расширение (CellState, HouseholdCellState, ProcurementGraphState)
>
> Каждый README почти гарантированно устарел. Не "verify and update" — а "investigate and rewrite".

**Двухэтапный протокол для КАЖДОГО WS-5B sub-task:**

**Этап A — Глубокое исследование директории (read-only, НЕ редактировать файлы):**

```
Для каждого README в sub-task:
1. cat README.md                                  → текущее содержимое
2. ls -la <directory>/                            → актуальный список файлов
3. cat <directory>/__init__.py                    → актуальные exports
4. git status -- <directory>/                     → какие файлы modified/untracked
5. git diff HEAD -- <directory>/*.py | head -200  → что изменилось в tracked files
6. cat <каждый NEW файл> | head -50               → что добавлено (первые 50 строк = classes)
7. Составить DELTA-REPORT:
   - [ДОБАВЛЕНО] новые файлы/классы/функции не упомянутые в README
   - [ИЗМЕНЕНО] существующие API/types чьё описание в README устарело
   - [УДАЛЕНО] что упоминается в README но больше не существует
   - [НЕТОЧНО] числа, подсчёты, списки которые расходятся с реальностью
```

**Этап B — Переписывание README по style guide template:**

```markdown
# Module Name (`polisyos.module.submodule`)

One paragraph: what this module does and why it exists.

## Role in System
- **Depends on:** list upstream modules
- **Used by:** list downstream modules

## Key Concepts
- Concept 1: one-line explanation
- Concept 2: one-line explanation
- ... (3-7 bullets)

## Public API
| Type/Function | Description |
|--------------|-------------|
| ClassName | One-line |
| function_name() | One-line |

→ Full reference: [docs/reference/module/](link)

## Current State
- Last updated: 2026-03-30
- Files: N
- Exports: M
```

**Style guide template reminder (per `docs/style-guide.md`):**
1. Title with module path: `# Name (`polisyos.module`)`
2. One-paragraph purpose
3. Role in system (depends on / used by)
4. Key concepts (3-7 bullets)
5. Public API surface (link to reference)
6. Current state / last updated date

---

##### WS-5B-IR: IR Module READMEs (9 existing + 1 NEW)

**Этап A — Исследование:**
```bash
# Для каждого README:
cat src/polisyos/ir/README.md
cat src/polisyos/ir/__init__.py | grep -c "^    "  # точный подсчёт exports
ls src/polisyos/ir/observation/                     # НОВАЯ директория — нет README!
cat src/polisyos/ir/observation/__init__.py
cat src/polisyos/ir/analytics/strategic.py | head -30  # НОВЫЙ файл
git diff HEAD -- src/polisyos/ir/refs.py            # новые Ref типы
git diff HEAD -- src/polisyos/ir/kernel/selector_fields.py
git diff HEAD -- src/polisyos/ir/kernel/slots.py
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `ir/README.md` | Exports: README says ~120 → now 160 (with duplicate). Observation module not mentioned. Strategic analytics not mentioned. |
| `ir/analytics/README.md` | `strategic.py` (708 lines, NEW) not mentioned. StrategicPayoffTable, StrategicSCM, StrategicResponseBundle absent. |
| `ir/artifacts/README.md` | May be missing new persist/load for observation bundles |
| `ir/governance/README.md` | Missing: GovernancePassAliasStatus, GovernancePassMappingBundle, ObservationFamilyPolicy, ObservationFamilyPolicyRegistry |
| `ir/kernel/README.md` | selector_fields.py: 16 predefined fields. slots.py: 40+ slots with CellState/HouseholdCellState types. Verify all reflected. |
| `ir/linker/README.md` | Likely needs minor updates |
| `ir/migrations/README.md` | Check if new observation types added migration |
| `ir/trinity/README.md` | Add link to docs/explanation/trinity.md |
| `ir/world/README.md` | Verify — may need observation integration note |
| **`ir/observation/README.md` (CREATE NEW)** | **133+ classes across 9 files. No README exists. Must create from scratch.** |

**Effort:** 2–2.5h (increased due to observation/ CREATE + strategic.py)

---

##### WS-5B-LEX: Lex Module READMEs (7 existing)

**Этап A — Исследование:**
```bash
cat src/polisyos/lex/README.md
cat src/polisyos/lex/__init__.py | wc -l           # exports count → 65
ls src/polisyos/lex/batch/                          # 51 files now
ls src/polisyos/lex/interventions.py                # NEW
ls src/polisyos/lex/intervention_artifacts.py       # NEW
cat src/polisyos/lex/interventions.py | head -50    # 12 exported types
cat src/polisyos/lex/intervention_artifacts.py | head -50  # 8 exported types
cat src/polisyos/lex/batch/amendment_detector.py | head -50
cat src/polisyos/lex/batch/hallucination_detector.py | head -50
cat src/polisyos/lex/batch/quality_filters.py | head -50
cat src/polisyos/lex/batch/temporal_resolver.py | head -50
cat src/polisyos/lex/batch/amendment_metrics.py | head -50
git diff HEAD -- src/polisyos/lex/__init__.py       # new exports
git diff HEAD -- src/polisyos/lex/batch/pipeline.py # pipeline integration changes
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `lex/README.md` | Exports: was ~58 → now **65**. Missing: interventions.py (12 types), intervention_artifacts.py (8 types). Missing: entire intervention system. Missing: batch quality tier (5 new files). |
| `lex/batch/README.md` | Missing 5 NEW files: amendment_detector.py, amendment_metrics.py, hallucination_detector.py, quality_filters.py, temporal_resolver.py. Pipeline has new stages. File count: was ~45 → now **51**. |
| `lex/corpus/README.md` | Check versioning.py changes |
| `lex/knowledge/README.md` | Store filter capabilities may have expanded |
| `lex/legal_evaluation/README.md` | Likely stable — verify |
| `lex/normpack/README.md` | select_sources.py changes — verify |
| `lex/simulator/README.md` | Link to docs/reference/lex/ |

**Effort:** 2–2.5h (increased due to 7 new files to document in batch/ and root)

---

##### WS-5B-SCIENTIST: Scientist Module READMEs (15 existing + 1 NEW)

**Этап A — Исследование (самый объёмный модуль, наибольшие изменения):**
```bash
cat src/polisyos/scientist/README.md                # 173 lines — almost certainly stale
ls src/polisyos/scientist/causal/                   # НОВАЯ директория — нет README!
cat src/polisyos/scientist/causal/__init__.py        # 6 exports
ls src/polisyos/scientist/nodes/builtins/causal/     # 11 NEW files
cat src/polisyos/scientist/nodes/builtins/causal/__init__.py  # 10 node exports
ls src/polisyos/scientist/governance/                # check for 5 new files
cat src/polisyos/scientist/governance/backtest_matrix.py | head -50
cat src/polisyos/scientist/governance/calibration.py | head -50
cat src/polisyos/scientist/governance/stress_scenarios.py | head -50
cat src/polisyos/scientist/governance/passes/strategic_response_pass.py | head -50
cat src/polisyos/scientist/compute/advanced_methods.py | head -50
cat src/polisyos/scientist/nodes/builtins/c6c_runtime_support.py | head -50
cat src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py | head -50
git diff HEAD -- src/polisyos/scientist/search/judge_stack.py
git diff HEAD -- src/polisyos/scientist/search/readiness.py
git diff HEAD -- src/polisyos/scientist/workflows/policy_design.py
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `scientist/README.md` | **Массивные изменения:** causal/ (6 runners), nodes/builtins/causal/ (10 nodes), governance/ (+5 files), compute/advanced_methods.py, c6c_runtime_support.py, hierarchical_policy_search.py. README почти полностью устарел. |
| `scientist/governance/README.md` | Missing 5 NEW files: backtest_matrix.py (BacktestMatrixRunner, 5 BacktestKinds), calibration.py (CalibrationGovernanceReport, LessonCardPublisher), calibration_leaderboard.py (CalibrationLeaderboard), calibration_validation.py (CalibrationValidationRunner), stress_scenarios.py (StressScenarioRunner, 6 StressScenarioKinds). Missing: strategic_response_pass.py. |
| `scientist/nodes/README.md` | Missing entire causal/ subdirectory (10 nodes). Missing c6c_runtime_support.py (2 dataclasses, 1 function). Missing run_hierarchical_policy_search.py. |
| `scientist/compute/README.md` | Missing advanced_methods.py (C7AdvancedInputs, C7AdvancedSuiteResult, 6 method modules). |
| `scientist/search/README.md` | Missing judge_stack.py, latent_governance.py, readiness.py changes |
| `scientist/workflows/README.md` | Missing policy_design.py workflow additions |
| `scientist/backtesting/README.md` | May reference outdated backtest approach; new BacktestMatrixRunner in governance/ |
| `scientist/adapters/README.md` | Verify — likely minor |
| `scientist/agent/README.md` | Verify agent protocol |
| `scientist/doe/README.md` | Likely stable |
| `scientist/engine/README.md` | Check checkpoint/resume changes |
| `scientist/kernel/README.md` | Expand minimal content |
| `scientist/llm/README.md` | Verify model profiles |
| `scientist/orchestrator/README.md` | Expand minimal content |
| `scientist/search/strategies/README.md` | Verify strategy types |
| **`scientist/causal/README.md` (CREATE NEW)** | **6 public exports: BoundsEstimationRunner, CounterfactualQueryRunner, ProxyIdentificationRunner, StrategicResponseRunner, TransportabilityChecker, build_interference_readiness_entries(). Must create from scratch.** |

**Effort:** 3–3.5h (increased — largest delta, 1 new README, 5+ files heavily outdated)

---

##### WS-5B-FOUNDRY: Foundry Module READMEs (9 existing + 1 NEW)

**Этап A — Исследование:**
```bash
cat src/polisyos/foundry/README.md                  # date was 2026-03-03 — at least 5 commits behind
ls src/polisyos/foundry/agent_sim/wiring/           # NEW directory
cat src/polisyos/foundry/agent_sim/wiring/__init__.py  # 8 exports
cat src/polisyos/foundry/calibration/measurement.py | head -50  # NEW
cat src/polisyos/foundry/calibration/auxiliary.py | head -50    # NEW
cat src/polisyos/foundry/calibration/__init__.py    # expanded exports
git diff HEAD -- src/polisyos/foundry/contracts/state.py  # CellState, HouseholdCellState, ProcurementGraphState, AgentSimRuntimeState
git diff HEAD -- src/polisyos/foundry/data_plane/bindings.py  # snapshot metadata
git diff HEAD -- src/polisyos/foundry/methods/catalog/causal/measurement_error.py
git diff HEAD -- src/polisyos/foundry/methods/catalog/causal/strategic.py
git diff HEAD -- src/polisyos/foundry/methods/catalog/causal/policy_learning.py
ls src/polisyos/foundry/contracts/                  # check if README exists
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `foundry/README.md` | Date stale (2026-03-03). Missing: wiring/ (3 files, 8 exports), calibration/measurement.py + auxiliary.py, state.py expansion (4 new types), bindings.py snapshot metadata. |
| `foundry/agent_sim/README.md` | Missing entire wiring/ subdirectory (contracts.py: FirmLifecycleEventBatch, ProcurementShockBatch, InterventionMechanismConfig; executors.py: 3 executor classes, 916 lines). |
| `foundry/calibration/README.md` | Missing measurement.py (MeasurementAwareTarget, MeasurementAwareLossConfig, CalibrationTargetBundle, compute_effective_weight). Missing auxiliary.py (AuxLossComponent protocol, InterferenceLossComponent). |
| `foundry/methods/catalog/causal/README.md` | Missing measurement_error.py proxy boundary metadata. Missing strategic.py StrategicSolveResult. Missing policy_learning.py OptimalPolicyLearner. |
| `foundry/methods/README.md` | Verify method registry matches reality |
| `foundry/methods/catalog/README.md` | Verify catalog tree |
| `foundry/plugins/README.md` | Likely stable |
| `foundry/uncertainty/README.md` | Likely stable |
| **`foundry/contracts/README.md` (CREATE NEW if missing)** | **state.py has GlobalState, AgentState, FirmState + 4 NEW types (CellState, HouseholdCellState, ProcurementGraphState, AgentSimRuntimeState). Create README for contracts/ directory.** |

**Effort:** 2–2.5h (wiring/ is a significant new subsystem)

---

##### WS-5B-FABRIC: Fabric Module READMEs (8 files)

**Этап A — Исследование:**
```bash
cat src/polisyos/fabric/README.md
cat src/polisyos/fabric/connectors/sources/__init__.py  # 14 connectors (not 9!)
cat src/polisyos/fabric/connectors/profiles/models.py | head -80  # SourceExecutionPolicy NEW
cat src/polisyos/fabric/connectors/profiles/builtin_profiles.py | wc -l  # 63 profiles
git diff HEAD -- src/polisyos/fabric/connectors/sources/eurostat.py  # async, describe_dataset
git diff HEAD -- src/polisyos/fabric/connectors/sources/sdmx_source.py  # promoted to production
git diff HEAD -- src/polisyos/fabric/connectors/profiles/resolver.py  # resolve_execution_policy NEW
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `fabric/README.md` | Connector count stale (was ~9 → now **14**). Missing SourceExecutionPolicy. Missing async fetch. Missing 63 built-in profiles mention. |
| `fabric/connectors/README.md` | Missing: SourceExecutionPolicy, resolve_execution_policy(), 14 connectors (not 9), async fetch (Eurostat, SDMX), Wave 3 REST connectors, 63 profiles. |
| `fabric/data_plane/README.md` | Check bindings multiscale changes (if data_plane/bindings.py exists here) |
| `fabric/catalog/README.md` | Verify |
| `fabric/claims/README.md` | Verify |
| `fabric/docs/README.md` | Verify |
| `fabric/retrieval/README.md` | Verify |
| `fabric/world/README.md` | Verify |

**Effort:** 1.5–2h (connector count + profile system are major deltas)

---

##### WS-5B-CORE: Core Module READMEs (11 files)

**Этап A — Исследование:**
```bash
cat src/polisyos/core/README.md
ls src/polisyos/core/
git diff HEAD -- src/polisyos/core/contracts/scientist.py
git diff HEAD -- src/polisyos/core/governance/profiles.py
cat src/polisyos/core/contracts/__init__.py  # check new exports
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `core/README.md` | Verify submodule list matches current state |
| `core/contracts/README.md` | scientist.py changes — new contracts |
| `core/governance/README.md` | profiles.py changes |
| `core/artifacts/README.md` | Verify CAS contracts (observation bundles may use CAS) |
| `core/audit/README.md` | Verify |
| `core/cache/README.md` | Expand minimal content |
| `core/components/README.md` | Verify |
| `core/llm/README.md` | Verify |
| `core/observability/README.md` | Verify |
| `core/registry/README.md` | Verify |
| `core/security/README.md` | Add link to docs/explanation/security-model.md |

**Effort:** 1.5–2h

---

##### WS-5B-ACADEMIC: Academic Module READMEs (4 files)

**Этап A — Исследование:**
```bash
cat src/polisyos/academic/README.md
git diff HEAD -- src/polisyos/academic/batch/resolve_extract.py
git diff HEAD -- src/polisyos/academic/knowledge/runtime_canonical_registry.py
cat src/polisyos/academic/knowledge/__init__.py
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `academic/README.md` | Check knowledge registry expansion |
| `academic/batch/README.md` | resolve_extract.py changes |
| `academic/knowledge/README.md` | runtime_canonical_registry.py changes |
| `academic/openalex/README.md` | Likely stable |

**Effort:** 45 min–1h

---

##### WS-5B-DATASETS: Datasets Module READMEs (3 files)

**Этап A — Исследование:**
```bash
cat src/polisyos/datasets/README.md
git diff HEAD -- src/polisyos/datasets/batch/benchmark.py
git diff HEAD -- src/polisyos/datasets/batch/config.py
git diff HEAD -- src/polisyos/datasets/batch/core_sources_ingest.py
git diff HEAD -- src/polisyos/datasets/batch/publish.py
git diff HEAD -- src/polisyos/datasets/batch/qc.py
git diff HEAD -- src/polisyos/datasets/knowledge/variable_alignment.py
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `datasets/README.md` | Batch changes (5 files modified) |
| `datasets/batch/README.md` | benchmark, config, core_sources_ingest, publish, qc — all modified |
| `datasets/knowledge/README.md` | variable_alignment.py changes |

**Effort:** 30–45 min

---

##### WS-5B-RUNTIME: Runtime Module READMEs (4 files)

**Этап A — Исследование:**
```bash
cat src/polisyos/runtime/README.md                  # date was 2026-03-03
cat src/polisyos/runtime/http/README.md
ls src/polisyos/runtime/http/routes/
ls src/polisyos/runtime/http/services/
# Count actual endpoints
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `runtime/README.md` | Date stale (2026-03-03). Endpoint count may differ. |
| `runtime/http/README.md` | Verify route count |
| `runtime/http/routes/README.md` | Verify route modules |
| `runtime/http/services/README.md` | Verify service modules |

**Effort:** 45 min–1h

---

##### WS-5B-SCHOLAR: Scholar Module READMEs (3 files)

**Этап A — Исследование:**
```bash
cat src/polisyos/scholar/README.md
ls src/polisyos/scholar/
# No files in git status M/? for scholar — likely stable
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `scholar/README.md` | Likely stable — verify pipeline stages |
| `scholar/discover/README.md` | Verify source spec |
| `scholar/orchestrator/README.md` | Verify enrichment flow |

**Effort:** 30–45 min

---

##### WS-5B-COMMON: Common Module READMEs (2 files)

**Этап A — Исследование:**
```bash
cat src/polisyos/common/README.md
ls src/polisyos/common/
```

**Этап B — Файлы для переписывания:**

| File | Delta vs current code |
|------|----------------------|
| `src/polisyos/common/README.md` | Verify utility list |
| `src/polisyos/common/migrations/README.md` | 37 | Verify migration registry |

**Effort:** 20–30 min

---

##### WS-5B Summary (обновлённые оценки с учётом двухэтапного протокола)

| Sub-task | Module | READMEs | New READMEs | Delta severity | Effort (A+B) | Priority |
|----------|--------|---------|-------------|---------------|-------------|----------|
| WS-5B-IR | ir | 9 | **+1** (observation/) | 🔴 HIGH (133+ new classes, strategic.py) | 2–2.5h | P1 |
| WS-5B-LEX | lex | 7 | 0 | 🔴 HIGH (7 new files, 65 exports vs 58) | 2–2.5h | P1 |
| WS-5B-SCIENTIST | scientist | 15 | **+1** (causal/) | 🔴 CRITICAL (6 runners, 10 nodes, 5 gov files) | 3–3.5h | P1 |
| WS-5B-FOUNDRY | foundry | 9 | **+1** (contracts/) | 🔴 HIGH (wiring/, measurement, 4 new state types) | 2–2.5h | P2 |
| WS-5B-FABRIC | fabric | 8 | 0 | 🟡 MEDIUM (14 vs 9 connectors, ExecutionPolicy) | 1.5–2h | P2 |
| WS-5B-CORE | core | 11 | 0 | 🟢 LOW (contracts, governance minor changes) | 1.5–2h | P3 |
| WS-5B-ACADEMIC | academic | 4 | 0 | 🟢 LOW (resolve_extract, canonical_registry) | 0.75–1h | P3 |
| WS-5B-DATASETS | datasets | 3 | 0 | 🟡 MEDIUM (5 files modified in batch) | 0.5–0.75h | P3 |
| WS-5B-RUNTIME | runtime | 4 | 0 | 🟢 LOW (date stale, counts may differ) | 0.75–1h | P3 |
| WS-5B-SCHOLAR | scholar | 3 | 0 | ⚪ NONE (no changes in git status) | 0.5h | P4 |
| WS-5B-COMMON | common | 2 | 0 | ⚪ NONE (no changes in git status) | 0.3–0.5h | P4 |
| **Total** | | **76** | **+3** | | **~15-18h seq / ~3.5h parallel** | |

All 11 sub-tasks are **fully independent** — can run in parallel.

**Критический путь:** WS-5B-SCIENTIST (3–3.5h) — наибольший объём изменений.

**Порядок приоритетов для sequential execution:**
1. SCIENTIST (P1, critical) — causal/, governance/, nodes/causal/ = наибольший delta
2. IR (P1, high) — observation/ = 133+ новых классов, нужен новый README
3. LEX (P1, high) — interventions + 5 batch files = 7 полностью новых файлов
4. FOUNDRY (P2, high) — wiring/ + measurement = значительное расширение
5. FABRIC (P2, medium) — 14 vs 9 connectors, SourceExecutionPolicy
6. Остальные по убыванию delta severity

#### WS-5C: ADR Index

Create `docs/adr/index.md`:

- Table of all 92 ADRs with status (accepted/deprecated/superseded)
- Grouped by domain: architecture, governance, causal, security, data, IR
- Quick summary for each
- Cross-references between related ADRs

#### WS-5D: CI — Docs Build

Add `.github/workflows/docs.yml`:

```yaml
name: Documentation
on: [pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install mkdocs-material mkdocstrings[python]
      - run: mkdocs build --strict
  linkcheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: lycheeverse/lychee-action@v2
        with:
          args: "docs/ README.md CONTRIBUTING.md --exclude-path docs/archive"
```

#### WS-5E: Pre-commit — Docstring Linting

Add to CI or pre-commit:

```yaml
# .pre-commit-config.yaml (addition)
- repo: https://github.com/econchick/interrogate
  rev: 1.7.0
  hooks:
    - id: interrogate
      args: [
        --fail-under=80,
        --ignore-init-module,
        --ignore-init-method,
        --ignore-magic,
        --ignore-private,
        --ignore-semiprivate,
        -v,
      ]
      files: ^src/polisyos/(ir|lex|fabric)/
```

Start enforcement only on IR, Lex, Fabric (highest auto-gen ROI).
Expand to other modules after Phase 2 docstrings are written.

---

## Dependency Graph

```
Phase 0 (Foundation)  ✅ COMPLETE
  ├── WS-0A: Style Guide
  ├── WS-0B: MkDocs Scaffold
  └── WS-0C: Directory Structure
        │
        ▼ (all below start after Phase 0)
   ┌────────────┬────────────┬────────────┬────────────┐
   ▼            ▼            ▼            ▼            ▼
Phase 1      Phase 2      Phase 3      Phase 4      Phase 5
(Entry pts)  (Reference)  (Tutorials)  (Explanation) (Housekeep)
6 WS ∥       8 WS ∥       8 WS ∥       6 WS ∥       15 WS ∥
   │            │            │            │            │
   │            │            │            │       ┌────┴────┐
   │            │            │            │       │  5B-*   │
   │            │            │            │       │ 11 mod  │
   │            │            │            │       │ parallel│
   │            │            │            │       └────┬────┘
   └────────────┴────────────┴────────────┴────────────┘
                             │
                             ▼
                     Phase 6 (Final)
                     Polish & publish
                             │
                             ▼
                     Phase 7 (Semantic)
                     Docstring content upgrade
```

**Maximum parallelism after Phase 0: 49 independent work streams.**
(Phase 5B contributes 11 parallel README sub-tasks; Phase 7 now has 6 initial semantic tracks
plus 5 targeted second-pass burn-down tracks, but the second pass starts only after WS-7F
produces a checker baseline.)

---

## Phase 6 — Final Polish (sequential, after Phase 1-5)

1. **Cross-link audit:** verify all internal links work, reference docs link to explanations, tutorials link to reference
2. **Navigation review:** test `mkdocs serve`, verify nav hierarchy makes sense
3. **Completeness check:** every public type in `__init__.py` has a docstring; every docstring renders in MkDocs
4. **Deploy:** GitHub Pages via `mkdocs gh-deploy` or CI
   - Implemented path: root `.github/workflows/docs-pages.yml` publishes the MkDocs site after a
     successful `CI` run on `main`.
5. **Root README final pass:** ensure all links point to live docs site

---

## Phase 7 — Semantic Docstring Upgrade (parallel: 6 work streams + 5 second-pass burn-down streams, then one merge QA)

**Dependency:** Phase 6 complete. **WS-7A..WS-7F run in parallel with non-overlapping ownership.**

### Цель Phase 7

Phase 6 гарантирует, что docstrings существуют и рендерятся.
Phase 7 поднимает **содержательное качество**: docstrings должны объяснять не только "что это",
но и **когда использовать API, какие инварианты соблюдать, что возвращается, какие ошибки
ожидать, и как объект связан с соседними слоями системы**.

### Общий стандарт качества для всех WS-7*

Для каждого публичного symbol, который экспортируется из `__init__.py` или попадает в
`docs/reference/**`:

1. **Не оставлять generic one-liners** вида `Foo bar helper.` / `Baz data model.` там, где API
   является user-facing или governance-critical.
2. **Классы / Pydantic-модели:**
   - one-line summary, объясняющий назначение в предметной модели;
   - ключевые инварианты и lifecycle;
   - `Attributes:` или `Field(description=...)` для неочевидных полей;
   - явная ссылка на соседний контракт/стадию, если тип является boundary object.
3. **Функции / методы:**
   - one-line summary в imperative mood;
   - `Args`, `Returns`, `Raises`;
   - `Example` для публичных entrypoints, фабрик, loaders, compile/execute APIs,
     connector onboarding и governance passes.
4. **Модули / package facades:**
   - module docstring должен объяснять роль модуля в архитектуре и кому принадлежит API;
   - `__init__.py` facade docstring должен говорить, почему exports lazy и что считается
     стабильной публичной поверхностью.
5. **Язык:** docstrings на English, markdown docs вокруг них остаются в Diataxis-стиле
   согласно `docs/style-guide.md`.
6. **Проверка:** после каждого WS — `python3 -m mkdocs build --strict` и точечный просмотр
   соответствующих `docs/reference/**` страниц.

### WS-7A: IR + Observation + Trinity Semantics

**Write scope:**
- `src/polisyos/ir/**`
- `src/polisyos/core/contracts/**` только если это прямые aliases / shared boundary contracts
- `docs/reference/ir/**` если нужна ручная поясняющая prose вокруг автогенерации

**Главная задача:**
Сделать IR docstrings **семантически полезными как контрактный словарь системы**.
Особый приоритет: `ProblemFrame`, `PolicySpec`, `ModelSpec`, `GovernancePass*`,
`Observation*`, `Measurement*`, `Bounds*`, `Temporal*`, `Transportability*`,
`CausalExecutionBundle*`, ref-объекты и schema/lifecycle types.

**Что конкретно сделать:**
1. Для всех экспортов из `src/polisyos/ir/__init__.py` заменить слабые one-liners на
   контрактные docstrings с назначением, ограничениями и expected lifecycle.
2. Для observation contracts явно объяснить разницу между:
   - raw observations;
   - observation family policy;
   - causal readiness / bundle manifests;
   - measurement trust tiers и routing modes.
3. В docstrings Trinity-типов зафиксировать границы ответственности:
   `ProblemFrame = what`, `PolicySpec = intervention/governance`, `ModelSpec = how`.
4. Для enums и status types описать, **какой downstream gate/runner читает это значение**.
5. Проверить, что IR reference pages читаются как спецификация, а не как список классов.

**DoD:**
- Нет generic docstrings у public exports из `polisyos.ir`.
- Для ключевых Pydantic-моделей есть хотя бы summary + field semantics.
- `docs/reference/ir/*.md` рендерятся и читаются без "пустых" API блоков.

---

### WS-7B: Foundry + Methods Catalog + Calibration + Agent Simulation

**Write scope:**
- `src/polisyos/foundry/**`
- `docs/reference/foundry/**`

**Главная задача:**
Сделать docstrings Foundry полезными для инженера, который реально вызывает
`compile()`, `execute()`, калибрует модели или добавляет новый method backend.

**Что конкретно сделать:**
1. Улучшить docstrings для публичных compile/execute/calibration APIs:
   - входные контракты;
   - purity / determinism expectations;
   - какие artifact refs пишутся;
   - какие ошибки или failure envelopes надо ожидать.
2. Для methods catalog объяснить различия между:
   - method protocol;
   - backend runner;
   - specialization/cache;
   - evidence/artifact persistence.
3. Для causal/econometrics/ml/bayesian/network/simulation families заменить
   generic class docstrings на короткие, но **предметные** описания:
   какой estimand/task решает метод, какие входные предположения и когда метод не подходит.
4. Для agent_sim и calibration docstrings явно зафиксировать:
   - что является synthetic state / observation;
   - где граница между simulation dynamics и measurement loss;
   - какие helper functions являются public, а какие internal.
5. Добавить `Example` в docstrings entrypoints, которые уже используются в tutorials
   или `docs/reference/foundry/*.md`.

**DoD:**
- `src/polisyos/foundry/__init__.py` exports и основные public classes/functions имеют
  неформальные, но точные docstrings без placeholders.
- Foundry reference pages объясняют usage, а не только signatures.
- `mkdocs build --strict` проходит после изменений.

---

### WS-7C: Scientist + Governance + Nodes + Workflows + Search

**Write scope:**
- `src/polisyos/scientist/**`
- `docs/reference/scientist/**`

**Главная задача:**
Сделать Scientist docstrings **операционным руководством по workflow orchestration**:
какой node что читает/пишет, какие governance passes что блокируют, где policy search
создаёт candidate plans, и где появляются decision artifacts.

**Что конкретно сделать:**
1. Для `src/polisyos/scientist/__init__.py` и верхнеуровневых API docstrings явно описать,
   что входит в stable public facade и почему imports lazy.
2. Для workflow specs и node classes:
   - объяснить роль узла в DAG;
   - перечислить state reads/writes и produced artifacts в prose;
   - указать, какие upstream assumptions должны быть выполнены до execute.
3. Для governance passes:
   - docstring должен говорить, **какое правило проверяется**;
   - что считается blocker/warning;
   - какие state/artifact fields pass ожидает;
   - какие профили/thresholds меняют поведение.
4. Для `scientist/causal/**` связать runner/checker docstrings с IR bundle types и Foundry methods.
5. Для search/backtesting/adapters docstrings объяснить различие между candidate generation,
   evaluator feedback, VOI scheduling и replay/composition audit.

**DoD:**
- Каждый user-facing Scientist node/pass/workflow имеет docstring, по которому можно понять
  "зачем этот объект существует" без чтения реализации.
- `docs/reference/scientist/**` рендерится без семантически пустых one-liners.

---

### WS-7D: Lex + Fabric + Connector/Corpus Semantics

**Write scope:**
- `src/polisyos/lex/**`
- `src/polisyos/fabric/**`
- `src/polisyos/datasets/**`
- `src/polisyos/academic/**`
- `docs/reference/lex/**`
- `docs/reference/fabric/**`

**Главная задача:**
Поднять docstrings там, где система соприкасается с внешними источниками данных,
правовыми корпусами, SPO extraction, source profiles и connector resilience.

**Что конкретно сделать:**
1. Для Lex facades и публичных типов объяснить:
   - pipeline stages `ingest -> structure -> version index -> normpack -> legal evaluation`;
   - что такое `NormPack`, `NormDiff`, intervention compiler, amendment handling,
     hallucination/quality checks и temporal resolution.
2. Для Fabric connectors и profiles docstrings должны фиксировать:
   - connector family semantics;
   - какие capabilities действительно поддерживаются;
   - что делает profile resolver / `SourceExecutionPolicy`;
   - какие retry/backoff/cache guarantees есть и где они заканчиваются.
3. Для docs/claims/world-query APIs добавить docstrings, которые объясняют
   contract normalization, provenance, conflict handling и materialization semantics.
4. Для datasets/academic helper APIs убрать placeholder one-liners и объяснить,
   какие функции относятся к batch ETL, canonicalization, QC и benchmark prep.
5. Синхронизировать wording между module README и docstrings, чтобы пользователь
   не видел разные названия одной и той же стадии пайплайна.

**DoD:**
- `polisyos.lex` и `polisyos.fabric` exports документированы предметно.
- `docs/reference/lex/**` и `docs/reference/fabric/**` дают понятный onboarding path
  к source ingestion и legal pipeline.

---

### WS-7E: Core + Runtime + Security + Observability + CLI Contracts

**Write scope:**
- `src/polisyos/core/**`
- `src/polisyos/runtime/**`
- `src/polisyos/common/**`
- `src/polisyos/batch_common/**`
- `src/polisyos/scholar/**`
- `docs/reference/api/**`
- `docs/reference/cli.md`
- `docs/reference/configuration.md`

**Главная задача:**
Сделать базовый platform слой самодокументирующимся: artifacts/CAS, registries,
component discovery, authn/authz, audit, tracing, runtime control-plane и CLI.

**Что конкретно сделать:**
1. Для core contracts/artifacts/registry/components docstrings объяснить:
   - что является стабильным ABI;
   - как строится `ArtifactRef`/manifest/lineage;
   - как работает component metadata/discovery/compliance.
2. Для runtime HTTP/service layers описать request/response boundaries,
   control-plane side effects, pagination/lineage/debug semantics и error model.
3. Для security/observability docstrings убрать формальные заглушки и объяснить:
   - JWT vs SPIFFE scopes;
   - OPA fail-closed behavior;
   - CAS signatures, TEE attestation, audit chain, trace propagation.
4. Для CLI entrypoints и common helpers добавить docstrings, которые объясняют
   user-visible behavior, env vars, и когда модуль можно безопасно импортировать.
5. Проверить, что `docs/reference/api/**`, `cli.md`, `configuration.md` не расходятся
   с обновлёнными docstrings.

**DoD:**
- Core/runtime public APIs имеют docstrings с behavior semantics и error expectations.
- API/CLI reference не противоречат коду и читаются без перехода в source.

---

### WS-7F: Documentation Quality Gates + Semantic Lint + Placeholder Eradication

**Write scope:**
- `tools/validation/**` или отдельные docs-validation scripts
- `.github/workflows/**` только если добавляется неразрушающий docs quality gate
- `docs/style-guide.md`
- `pyproject.toml` только для docstring lint config, если нужно

**Главная задача:**
Не просто вручную улучшить docstrings один раз, а **закрепить качество проверками**,
чтобы generic placeholders не возвращались.

**Что конкретно сделать:**
1. Написать checker, который фейлит на placeholder docstrings вроде:
   - `Public ... module API.`
   - `... helper.`
   - `... data model.`
   - `... implementation.`
   если symbol экспортируется из public facade или отображается в reference docs.
2. Добавить allowlist/pragma для действительно тривиальных internal wrappers,
   чтобы gate не заставлял писать "романы" на каждый tiny helper.
3. Расширить docs style guide секцией **Semantic Docstring Quality**:
   примеры плохого/хорошего docstring для class/function/module.
4. В CI добавить лёгкий docs-quality job:
   - `python3 -m mkdocs build --strict`
   - `python3 tools/validation/check_docs_accuracy.py --repo-root .`
   - custom placeholder-docstring checker with explicit public-surface coverage gate
   - optional `interrogate` threshold, но без ложного confidence если
     нас интересует именно содержательность, а не только наличие.
5. Подготовить итоговый report:
   - сколько placeholder docstrings было заменено;
   - сколько public exports покрыто semantic docstrings;
   - какие пакеты ещё требуют второго прохода.

**DoD:**
- Есть автоматическая проверка, которая не позволяет вернуть массовые placeholder docstrings
  в public API.
- `docs/style-guide.md` описывает не только формат, но и критерии содержательности.

---

### Phase 7 Status After WS-7F Baseline

После внедрения `tools/validation/check_docstring_quality.py` второй проход больше не должен
быть "широким переписыванием всего подряд". Теперь есть измеримый baseline:

- inspected public symbols: **5824**
- semantic docstring coverage: **3466 / 5824 = 59.5%**
- placeholder violations blocking the gate: **703**
- largest package buckets still needing a second pass:
  - `polisyos.foundry`: **874**
  - `polisyos.scientist`: **458**
  - `polisyos.fabric`: **382**
  - `polisyos.core`: **306**
  - `polisyos.ir`: **203**
  - `polisyos.lex`: **71**
  - tail: `academic` 39, `runtime` 9, `scholar` 9, `batch_common` 3, `common` 2, `datasets` 2

**Вывод:** first pass создал quality gate и общий semantic standard, но backlog теперь
достаточно концентрирован, чтобы закрывать его **прицельными, непересекающимися second-pass
ownership windows**, а не повторным broad sweep по всем подсистемам.

### Общий протокол для Second Pass

Перед началом каждого WS-7G..WS-7K:

1. Прогнать `python3 tools/validation/check_docstring_quality.py --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt`
   и выписать свои package-local violations.
2. В первую очередь править **gate-blocking placeholders**, а не просто "улучшать стиль" там,
   где checker уже молчит.
3. Allowlist пополнять только для реально тривиальных compatibility wrappers; public facades,
   boundary models, workflow entrypoints и governance-critical APIs должны лечиться содержательным
   docstring, а не исключением.
4. В каждом WS report фиксировать:
   - before/after placeholder count по своей package bucket;
   - 10-20 самых важных символов, которые были upgraded semantically;
   - остаток, если он не нулевой.

---

### Phase 7 Second Pass — Placeholder Burn-down (parallel: 5 work streams)

**Dependency:** WS-7F merged, a fresh checker snapshot captured, first-pass WS-7A..WS-7E reports collected.
**WS-7G..WS-7K run in parallel with non-overlapping ownership.**

#### WS-7G: Foundry Placeholder Burn-down

**Write scope:**
- `src/polisyos/foundry/**`
- `docs/reference/foundry/**`

**Главная задача:**
Закрыть самый крупный checker bucket: methods catalog, compile/execute surface, state/layout,
agent-sim facades и families, где ещё остались `Public ... module API.`, `... helper.`,
`... data model.`, `... implementation.`.

**Что конкретно сделать:**
1. Пройти package/module facades и reference-rendered modules:
   - `foundry/layout.py`
   - `foundry/contracts/state.py`
   - `foundry/methods/**`
   - `foundry/agent_sim/**`
   - `foundry/calibration/**`
2. Для `methods/selection.py`, `linker.py`, `components_bridge.py` и catalog family `__init__.py`
   заменить helper-style summaries на usage-oriented docstrings: когда вызывать API, какой
   downstream runner/catalog consumer его читает, какие assumptions у входов.
3. Для result/config/ref bundles убрать `... data model.` и описать lifecycle:
   build, persist, cache, replay, evidence emission.
4. Приоритет страниц для spot-check:
   - `docs/reference/foundry/compile-execute.md`
   - `docs/reference/foundry/methods-catalog.md`
   - `docs/reference/foundry/state.md`
   - `docs/reference/foundry/agent-sim.md`

**DoD:**
- checker больше не показывает placeholder violations для `polisyos.foundry*`;
- Foundry reference pages читаются как usage guide, а не как список neutral labels.

---

#### WS-7H: Scientist Placeholder Burn-down

**Write scope:**
- `src/polisyos/scientist/**`
- `docs/reference/scientist/**`

**Главная задача:**
Добить остаточные placeholders в nodes, policy-design, search, engine builtins, causal adapters
и policy-verified models, чтобы `polisyos.scientist` reference не разваливался на `... node implementation.`
и `... data model.`.

**Что конкретно сделать:**
1. Приоритизировать пакеты, уже засвеченные checker-ом:
   - `scientist/nodes/builtins/**`
   - `scientist/policy_design/**`
   - `scientist/policy_verified/**`
   - `scientist/search/**`
   - `scientist/engine/**`
2. Для node classes описывать:
   - роль в DAG;
   - state reads/writes;
   - produced artifacts / contracts;
   - preconditions before execution.
3. Для policy-design/search bundles заменить generic `... data model.` на domain-language:
   candidate frontier, constraint satisfaction, adversarial scenario, transportability report,
   replayable audit bundle.
4. Для builtins `__init__.py` и верхних facades объяснить stable public surface и lazy-loading
   boundaries, а не только факт наличия exports.

**DoD:**
- checker больше не показывает placeholder violations для `polisyos.scientist*`;
- key Scientist pages (`index`, `workflows`, `governance-passes`, `nodes`, `causal`) не содержат
  semantically empty headings.

---

#### WS-7I: Fabric + Lex Ingestion / Corpus Burn-down

**Write scope:**
- `src/polisyos/fabric/**`
- `src/polisyos/lex/**`
- `docs/reference/fabric/**`
- `docs/reference/lex/**`

**Главная задача:**
Закрыть remaining placeholders на boundary between external data/legal sources and internal contracts:
connectors, world/materialization, claims pipeline, normpack/legal-evaluation/batch stages.

**Что конкретно сделать:**
1. Для Fabric устранить placeholders в:
   - connector family modules / package facades;
   - `claims/**`, `world/**`, `materialize/**`, `storage/**`, `manifest/trust/provenance/**`;
   - public persistence/query helpers, которые рендерятся в reference docs.
2. Для Lex устранить placeholders в:
   - `normpack/**`, `legal_evaluation/**`, `batch/**`, `corpus/**`, `simulator/**`;
   - provider/evaluator registries и public pipeline types.
3. Для каждого symbol объяснять pipeline stage и соседние boundaries:
   `ingest -> structure -> version index -> normpack -> legal evaluation -> intervention mapping`.
4. Не тратить second-pass время на truly private batch internals, которые не попадают в gate.

**DoD:**
- checker больше не показывает placeholder violations для `polisyos.fabric*` и `polisyos.lex*`;
- Fabric/Lex reference pages дают понятный onboarding path без формальных заглушек.

---

#### WS-7J: Core + Runtime Platform Contract Burn-down

**Write scope:**
- `src/polisyos/core/**`
- `src/polisyos/runtime/**`
- `src/polisyos/common/**`
- `src/polisyos/batch_common/**`
- `src/polisyos/scholar/**`
- `docs/reference/api/**`
- `docs/reference/cli.md`
- `docs/reference/configuration.md`

**Главная задача:**
Закрыть оставшиеся placeholders в platform/core boundary contracts, runtime service surface,
security/registry layers и common helpers, которые пользователь читает как "операционную документацию".

**Что конкретно сделать:**
1. Для `core` приоритетно пройти:
   - `contracts/**`
   - `components/**`
   - `security/**`
   - `registry/**`
   - `cache/**`
   - `run/**`
2. Для `runtime` заменить `Public ... module API.` и `... helper.` в routes/services/adapters
   на request/response semantics, side effects, pagination/debug/error model.
3. Для `common` / `batch_common` / `scholar` убрать оставшиеся generic facades и helpers,
   особенно вокруг migrations, orchestration bundles и discovery/freshness runtime helpers.
4. Spot-check:
   - `docs/reference/api/index.md`
   - `docs/reference/api/runs.md`
   - `docs/reference/api/control.md`
   - `docs/reference/cli.md`
   - `docs/reference/configuration.md`

**DoD:**
- checker больше не показывает placeholder violations для `polisyos.core*`, `polisyos.runtime*`,
  `polisyos.common*`, `polisyos.batch_common*`, `polisyos.scholar*`;
- API/CLI/config reference остаются согласованными с code-level docstrings.

---

#### WS-7K: IR + Academic / Datasets Boundary Clean-up

**Write scope:**
- `src/polisyos/ir/**`
- `src/polisyos/academic/**`
- `src/polisyos/datasets/**`
- `docs/reference/ir/**`

**Главная задача:**
Добить long-tail placeholders, которые остались после WS-7A: observation contract compilers,
IR boundary refs и academic/datasets batch/canonicalization models.

**Что конкретно сделать:**
1. Для `ir/observation/contract_compilers.py` пройти все `... compiler implementation.` docstrings
   и описать:
   - какой bundle/task строит compiler;
   - какой downstream runner consumes output;
   - какие invariants должен выполнить caller.
2. Для remaining IR refs/status/bundle models заменить `... data model.` на boundary semantics:
   who produces it, who consumes it, when it becomes stable.
3. Для `academic/**` и `datasets/**` закрыть long-tail result/config/model placeholders, если они
   попадают в public facades или reference docs.
4. После правок spot-check `docs/reference/ir/*.md` на читаемость observation/problem-framing pages.

**DoD:**
- checker больше не показывает placeholder violations для `polisyos.ir*`, `polisyos.academic*`,
  `polisyos.datasets*`;
- IR reference остаётся contract-spec first, но без generic placeholders.

---

### Phase 7 Merge Protocol (sequential, after WS-7A..WS-7K)

1. **Freeze ownership windows:** каждый WS мержится отдельным PR/branch или строго
   последовательным batch-commit по своему write scope.
2. **Mid-phase split:** после WS-7F фиксируется checker baseline и только потом открываются
   WS-7G..WS-7K с package-local ownership. Не пересекать write scopes между first pass и second pass.
3. **Conflict policy:** если один WS должен тронуть чужой scope, он сначала добавляет TODO
   в свой report, а не правит чужие файлы напрямую.
4. **Final QA checklist:**
   - `python3 -m mkdocs build --strict`
   - `python3 tools/validation/check_docs_accuracy.py --repo-root .`
   - `python3 tools/validation/check_docstring_quality.py --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt --coverage-scope public-surface --minimum-coverage 85`
   - точечный просмотр 2-3 страниц из каждого `docs/reference/<subsystem>/`
   - smoke-test `mkdocs serve` на главной, tutorials, reference, explanation
5. **Acceptance rule:** Phase 7 считается завершённой только если:
   - `check_docs_accuracy.py` возвращает exit code 0;
   - `check_docstring_quality.py` возвращает exit code 0 на `--coverage-scope public-surface --minimum-coverage 85`;
   - `mkdocs build --strict` возвращает exit code 0;
   - weak/generated docstrings остались исключительно в allowlisted trivial internals;
   - placeholder violations равны `0`;
   - top-level public-surface semantic coverage не ниже **85%**;
   - method-level остаточный backlog, если он ещё существует, перечислен в merge report как
     explicit second-pass follow-up, а не скрыт как regression.

### Current Status After SOTA Closeout

После внедрения content + infra + validation deliverables documentation stack находится в таком
состоянии:

- недостающие Diataxis pages добавлены:
  - `tutorials/writing-a-connector.md`
  - `tutorials/creating-governance-pass.md`
  - `how-to/configure-lex-pipeline.md`
  - `how-to/use-control-plane.md`
  - `how-to/debug-failed-run.md`
  - `how-to/manage-schemas.md`
  - `explanation/ir-design.md`
- `mkdocs.yml` navigation обновлена под полный current target state.
- repo-truth drift закрыт для published docs:
  - убран `<repo-url>` из tutorial docs;
  - README badge переведён на реальный `ci.yml`;
  - stale workflow references удалены из published guides.
- docs-quality gate теперь включает:
  - `mkdocs build --strict`
  - `check_docs_accuracy.py`
  - `check_docstring_quality.py` c `--coverage-scope public-surface --minimum-coverage 85`
- publish path operationalized:
  - root `.github/workflows/docs-pages.yml` публикует сайт в GitHub Pages после успешного `CI` на `main`.

Current measured snapshot:

- docs accuracy violations: **0**
- `mkdocs build --strict`: **pass**
- placeholder violations: **0**
- semantic docstring coverage (all inspected subjects): **4169 / 5824 = 71.6%**
- semantic docstring coverage (public surface): **3267 / 3267 = 100.0%**

Residual advisory backlog after closeout:

- remaining semantic gaps concentrated in public methods rather than top-level public exports;
- largest method-level second-pass buckets:
  - `polisyos.foundry`: **631**
  - `polisyos.fabric`: **324**
  - `polisyos.scientist`: **317**
  - `polisyos.core`: **159**
  - `polisyos.ir`: **124**
  - `polisyos.lex`: **60**

### Ongoing Maintenance Policy

После SOTA closeout следующие проверки считаются обязательной нормой, а не одноразовой cleanup
акцией:

1. Любой новый public API должен приходить с:
   - semantic docstring;
   - корректной visibility через facade/reference page;
   - отсутствием placeholder wording.
2. Любая новая docs claim про workflows, CI, site URLs или publish path должна проходить
   `tools/validation/check_docs_accuracy.py`.
3. Любой PR, меняющий published docs, должен сохранять зелёными:
   - `python3 -m mkdocs build --strict`
   - `python3 tools/validation/check_docs_accuracy.py --repo-root .`
   - `python3 tools/validation/check_docstring_quality.py --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt --coverage-scope public-surface --minimum-coverage 85`
4. GitHub Pages publish workflow остаётся обязательным production path для docs site; ручной
   `mkdocs gh-deploy` не считается canonical release process.

---

## Effort Estimation (обновлённые оценки)

| Phase | Work Streams | Effort per WS | Total (sequential) | Total (parallel) |
|-------|-------------|---------------|-------------------|-----------------|
| 0 | 3 | 30 min | 1.5h | 30 min |
| 1 | 6 | 1.5-3h | 12h | 3h |
| 2 | 8 | 2-8h | 35h | 8h |
| 3 | 8 | 1.5-3h | 18h | 3h |
| 4 | 6 | 2-4h | 18h | 4h |
| 5 (excl 5B) | 4 | 1-3h | 7h | 3h |
| 5B (READMEs, A+B) | 11 | 0.3-3.5h | 15-18h | 3.5h |
| 6 | 1 | 3h | 3h | 3h |
| 7 | 11 + 1 merge QA | 2-8h | 42-56h | 10-12h |
| **Total** | **59** | | **~152-171h** | **~38-40h** |

With maximum parallelism (e.g., Claude agents running WS in parallel),
the critical path is **~38-40 hours** instead of ~152-171 hours sequential.

**Почему оценки выросли vs первоначальные:**
- Phase 2 (Reference): observation/ = 133+ classes без docstrings, strategic.py = 708 lines
- Phase 4 (Explanation): observation contracts explanation значительно объёмнее
- Phase 5B (READMEs): двухэтапный протокол (investigate + rewrite) вместо простого "verify"
- Phase 7: после запуска semantic quality gate появился измеримый second-pass backlog
  (703 placeholder violations across 5824 inspected public symbols), который лучше закрывать
  отдельными burn-down streams, а не размазывать по первому проходу
- Scientist module changes = 36+ new public APIs за последние 5-6 коммитов

### Phase 5B Parallelism Detail

All 11 module README tasks run simultaneously (each: Этап A investigate → Этап B rewrite):

```
WS-5B-SCIENTIST ──── A:1h → B:2.5h ─ (3.5h) ─┐ ← critical path
WS-5B-IR ─────────── A:0.5h → B:2h ─ (2.5h)  ─┤
WS-5B-LEX ────────── A:0.5h → B:2h ─ (2.5h)  ─┤
WS-5B-FOUNDRY ────── A:0.5h → B:2h ─ (2.5h)  ─┤
WS-5B-FABRIC ─────── A:0.5h → B:1.5h (2h)    ─┤
WS-5B-CORE ───────── A:0.5h → B:1.5h (2h)    ─┤
WS-5B-ACADEMIC ───── A:0.25h → B:0.75h (1h)   ─┤
WS-5B-DATASETS ───── A:0.25h → B:0.5h (0.75h) ─┤
WS-5B-RUNTIME ────── A:0.25h → B:0.75h (1h)   ─┤
WS-5B-SCHOLAR ────── A:0.15h → B:0.35h (0.5h) ─┤
WS-5B-COMMON ─────── A:0.1h → B:0.2h (0.3h)  ─┘
                                                → 3.5h wall clock (limited by WS-5B-SCIENTIST)
```

---

## Priority Matrix

If time is limited, execute in this order (highest impact first):

| Priority | Work Stream | Why |
|----------|-------------|-----|
| P0 | WS-0A,0B,0C | Unblocks everything |
| P1 | WS-1A (README) | First thing anyone sees |
| P1 | WS-2A (IR docstrings) | 160 types, highest auto-gen ROI |
| P1 | WS-2F (API reference) | 43 endpoints, external consumers need this |
| P2 | WS-1B (CONTRIBUTING) | Contributor onboarding |
| P2 | WS-2B (Lex docstrings) | 58 types, second highest ROI |
| P2 | WS-3A (Getting started) | New user onboarding |
| P2 | WS-5A (Archive stale) | Reduce noise, improve findability |
| P2 | WS-7F (Docstring quality gates) | Prevent placeholder regressions |
| P3 | WS-2D (Scientist docs) | 18 governance passes need docs |
| P3 | WS-7A..WS-7E (Semantic docstrings) | Convert formal coverage into useful API docs |
| P3 | WS-7G..WS-7K (Phase 7 second pass) | Burn down the measured placeholder backlog package-by-package |
| P3 | WS-1D (Architecture) | Current 140KB is unwieldy |
| P3 | WS-4A (Causal engine) | Core domain, complex |
| P4 | Everything else | Important but not urgent |

---

## Tooling Requirements

```bash
# Documentation build
pip install mkdocs-material mkdocstrings[python] mkdocs-monorepo-plugin

# Docstring linting
pip install interrogate

# Link checking
# (via CI: lychee-action)

# Local preview
mkdocs serve  # http://localhost:8000
```

---

## Success Criteria

- [ ] `mkdocs build --strict` passes with zero warnings
- [ ] Every public type in `ir/__init__.py` (160) has a rendered reference page
- [ ] Every public type in `lex/__init__.py` (58) has a rendered reference page
- [ ] All 43 REST API endpoints documented with request/response examples
- [ ] All 18 governance passes have reference entries
- [ ] All 4 CLI commands documented with `--help` output
- [ ] Root README exists and links to docs site
- [ ] `interrogate` reports >=80% docstring coverage on ir/, lex/, fabric/
- [ ] No placeholder docstrings remain on package-level public exports, except explicit allowlist
- [ ] Public docstrings explain semantics, invariants, and usage for IR / Foundry / Scientist / Lex / Fabric / Core
- [ ] No broken internal links (lychee CI check)
- [ ] Stale plans archived with deprecation headers
- [ ] At least 2 tutorials and 5 how-to guides published
