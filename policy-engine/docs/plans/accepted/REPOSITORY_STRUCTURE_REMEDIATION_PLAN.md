---
title: Repository Structure Remediation Plan
status: accepted
owner: team-polisyos
created: 2026-05-03
last_verified: 2026-05-05
stability: stable
---

# Repository Structure Remediation Plan

> Создан: 2026-05-03
> Владелец: Denis Kopylov / team-polisyos
> Область: cross-cutting структурные аномалии в `polisyos/` (workspace) и
> `policy-engine/` (product root), которые остались после Repository SOTA
> Phase 5 closeout
>
> Companion documents:
>
> - `docs/plans/accepted/REPOSITORY_SOTA_PLAN.md` — родительская топологическая
>   политика (accepted, фаза 5 закрыта)
> - `docs/plans/accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md` — закрытое
>   состояние топологии и enforcement-gate-ов
> - `docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md`,
>   `docs/plans/active/FABRIC_BEST_IN_CLASS_PLAN.md`,
>   `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`,
>   `docs/plans/active/FRONTEND_SOTA_PLAN.md`,
>   `docs/plans/active/INFRASTRUCTURE_SOTA_PLAN.md`,
>   `docs/plans/active/TOOLS_AUDIT_REMEDIATION_PLAN.md`,
>   `docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md` — pakage-level планы,
>   с которыми этот план пересекается на стыках
> - `docs/reference/repository-topology.md` — публичная карта расположений

---

## 0. TL;DR

Repository SOTA закрыл топологический контур (`architecture/topology.toml`,
`package_boundaries.toml`, `shims.toml`, gates). Свежий аудит
(2026-05-03) показал, что внутри легитимной топологии живут ещё **семь
структурных дефектов**, которые SOTA Phase 5 closeout не убирает, потому что
они находятся либо ниже слоя топологии (внутри пакетов), либо выше
(workspace‑boundary), либо в семантической плоскости (наименование).

Эти дефекты:

1. **9 пустых namespace‑placeholder’ов в `foundry/methods/`**
   (`bayesian/`, `causal/`, `dependence/`, `econometrics/`, `microsim/`, `ml/`,
   `network/`, `optimization/`, `spatial/`) рядом с реальными
   `foundry/methods/catalog/{bayesian,causal,...}` — прямой коллизионный
   namespace, легитимизированный, но не закрытый `MIGRATION_V2.md`.
2. **Двойной workspace** `polisyos/` ↔ `policy-engine/`: дублированные
   кэши (`.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.hypothesis`,
   `.benchmarks`), две `.venv`, два `.polisyos/`, root‑разбросанные
   tmp/runs/output/data.
3. **Два «слона»** в `src/polisyos/`: `scientist/` (517 файлов) и
   `foundry/` (505) = 48% всего src; у обоих 17–22 loose `.py` в корне
   пакета смешаны с public API.
4. **Кросс‑пакетная коллизия имён**: `governance/`, `contracts/`,
   `discovery/`, `methods/`, `causal/`, `kernel/`, `data_plane/`,
   `provenance/`, `validation/`, `analytics/`, `runtime/` — повторяются
   в 2–5 пакетах без различающего идентификатора.
5. **Слабые / версионированные / placeholder‑пакеты**: `ddm_15_7/` (версия в
   имени), `packs/{econ,roads}/` (пустые), `calibration/` (7 файлов,
   дублируется со `scientist/calibration` и `foundry/calibration`),
   `synthetic_world/` ↔ `foundry/agent_sim/` (пересечение по семантике),
   `berl/` (без явного legacy‑маркера).
6. **`pyproject.toml` 1975 строк**, 22 секции `[tool.*]`. Нечитаем,
   неревьюабелен.
7. **Артефактный хаос** на уровне корня: 7 build‑output директорий
   (`out/`, `output/`, `dist/`, `site/`, `release/`, `release-fragments/`,
   `production_data/`, `benchmark-results/`, `.tmp/`, `logs/`) и
   архитектурные конфиги, утёкшие из `architecture/` (`baseline/`,
   `import_exceptions.toml`, `import_policy.toml`, `freeze_policy.md`).

Этот план превращает каждое наблюдение в machine‑checkable контракт и
поэтапную миграцию с golden/replay/differential‑evidence там, где есть риск
поведения.

План реорганизован под максимальный безопасный параллелизм:

1. **Phase 0** — единственный обязательный first barrier: inventory,
   ADR‑baseline, ownership fences и report‑only gate skeletons.
2. **Wave 1** — шесть независимых фаз, которые стартуют сразу после
   Phase 0 и идут параллельно: quick wins, config/governance split,
   name registry decisions, tools topology, tests topology, frontend
   source duplicate cleanup.
3. **Wave 2** — стабилизация путей: workspace boundary, затем
   `_build/`/`_cache/`. Эти две фазы намеренно последовательные, потому
   что обе меняют root paths и tool cache paths.
4. **Wave 3** — параллельно идут decomposition preflight и small‑package
   planning. В этой wave нет risky source moves.
5. **Wave 4** — параллельно идут small‑package implementation и frontend
   workspace/build-output finalization.
6. **Phase 5 → Phase 6** — `scientist/` и `foundry/` decomposition
   строго последовательно после safety net.
7. **Phase 7** — enforcement + closeout.

Самая чувствительная работа — декомпозиция гигантских пакетов
`scientist/` и `foundry/` — остаётся за **Phase 3A preflight**: фаза,
в которой ни одного `.py` в `src/scientist/` или `src/foundry/` не
двигается, но строится полный safety net (pickle compat, dynamic imports
registry, public surface snapshot, schema diff baseline, cyclic import
audit, JAX/Pydantic registration audit, codemod tooling, import‑time
benchmark). Без зелёного safety net Phase 5 и Phase 6 не стартуют.

---

## 1. Scope

### В scope

- Структурные дефекты внутри `policy-engine/src/polisyos/`, не покрытые
  per‑package best‑in‑class планами.
- Граница workspace ↔ product‑root и связанные дублированные артефакты
  (кэши, venv, runtime state, скретч).
- Конфигурационная декомпозиция `pyproject.toml` и консолидация
  archi‑контрактов в `architecture/`.
- Зонтичная политика для эфемерных артефактов (`_artifacts/`, `_cache/`).
- Дедупликация имён директорий между пакетами (semantic name registry).
- Frontend monorepo manager и устранение дубликатов внутри `runtime-dashboard/src`.

### Вне scope

- Поведенческие изменения внутри `scientist/`, `foundry/`, `fabric/`,
  `data_forge/`, `lex/`, `ir/`, `core/`, `runtime/` — это территория
  соответствующих per‑package планов; этот план только перепакетирует
  существующие модули и закрывает структурные коллизии без рефакторинга
  логики.
- Любые изменения, требующие поведенческой миграции (отдельный contract
  switch, прохождение golden/replay), делегируются в companion‑планы.
- Изменения публичного API runtime‑потребителей: переход на новые
  пути проводится через `shims.toml` без удаления старых FQN до
  истечения sunset.

---

## 2. Source of Truth

| Concern                            | Source                                                              |
| ---------------------------------- | ------------------------------------------------------------------- |
| Repository topology                | `architecture/topology.toml` + ADR‑0111                             |
| Package boundaries                 | `architecture/package_boundaries.toml`                              |
| Import contracts                   | `architecture/import_contracts.toml` (+ to‑be‑merged registries)    |
| Migration shims                    | `architecture/shims.toml`                                 |
| Public surface                     | `architecture/public_surface.toml` + `architecture/public_surface/` |
| Generated artifacts                | `architecture/generated_artifacts.toml`                             |
| Loose‑file allowlist               | `architecture/topology.toml` (`[[loose_file]]` или sentinels)       |
| Структурные decisions этого плана  | новые ADR‑0129..ADR‑0135 (см. Phase 0)                              |
| Tests topology                     | `tests/README.md` + `tests/architecture/`                           |
| Frontend workspace                 | `frontend/` + новый workspace‑manager (Phase 1F / 4B)               |
| Closeout evidence                  | `docs/plans/accepted/REPOSITORY_STRUCTURE_REMEDIATION_CLOSEOUT.md`  |

---

## 3. Что НЕ закрывает Repository SOTA Phase 5

Repository SOTA Phase 5 closeout зафиксировал:

- топологию первого уровня (`architecture/topology.toml`),
- package boundaries (`architecture/package_boundaries.toml`),
- gates: import-linter, deptry, topology, shim-audit, public-surface,
  generated-header, gitleaks, OSV/SBOM, complexity, docs-freshness,
  loose-file, pii-redaction.

Что осталось вне его контура:

| Дефект                                                | Почему не закрывается SOTA                                    |
| ----------------------------------------------------- | ------------------------------------------------------------- |
| Пустые `foundry/methods/{name}/` namespaces           | Topology не различает пустые от populated пакетов             |
| Loose `.py` в корне `scientist/`/`foundry/`           | `package_boundaries` не нормирует layout внутри пакета        |
| Кросс‑пакетные дубликаты имён (`governance/` × N)     | Boundaries описывают edges, не имена                          |
| Дублированные кэши и venv на двух уровнях             | Topology классифицирует пути, не запрещает дубль              |
| Версионированное `ddm_15_7`                           | Topology допускает любое имя пакета                           |
| `pyproject.toml` size                                 | SOTA не контролирует размер конфиг‑файлов                     |
| Дробление build‑outputs                               | Topology маркирует категорию, но не требует umbrella          |
| `architecture/` ↔ `baseline/` параллель               | Оба легальны по topology                                      |
| Frontend `lib/` ↔ `shared/lib/`                       | Frontend SOTA Plan ведёт это, но без machine‑контракта        |
| `synthetic_world/` ↔ `foundry/agent_sim/`             | Boundaries не диагностируют семантическое пересечение         |

Этот план занимает именно эту нишу.

---

## 4. Сквозные принципы

1. **Один пакет — один dominant namespace.** Никаких пустых директорий с
   именем, занятым в другом месте дерева тем же словом.
2. **Один артефакт — одно имя — одно место.** Нет `out/`, `output/`,
   `release/`, `release-fragments/` параллельно.
3. **Public façade per package.** В корне пакета — только `__init__.py`
   и `_api.py` (или `api.py`); остальной топ‑level код переезжает в
   осмысленные подпакеты или становится `_internal/`.
4. **Версии в имени пакета запрещены.** Версионирование — через
   `__version__`, `package.version`, ABI‑контракты.
5. **Дублированные имена между пакетами требуют явного решения**: либо
   они оправданы как bounded contexts (тогда — явная регистрация в
   `package_boundaries.toml` с указанием семантической оси), либо
   переименование.
6. **Каждое структурное решение — ADR.** Phase 0 материализует ADR‑0129..0135.
7. **Gates вводятся report‑only при создании, переводятся в fail‑closed
   в финальной Phase 7** — кроме gates из Phase 3A, которые становятся
   fail‑closed по завершении Phase 3A (без них Phase 5/6 не сдаются).
8. **Никаких поведенческих изменений без golden/replay/differential**;
   этот план — структурный, поведение защищается safety net из Phase 3A.
9. **Plan‑first.** Каждая фаза с code moves имеет artifact‑планер
   (blueprint, move map, или decision matrix), принятый владельцами
   до начала work. Phase 5/6 не стартуют без принятого
   `DECOMPOSITION_BLUEPRINT.md`.
10. **Granular rollback.** Откат — на уровне отдельного файла через
    `git checkout HEAD~1 -- <path>` + revert codemod (его dry‑run
    показывает, какие импорты вернуть). Не нужны отдельные PR на
    каждый файл — нужен чёткий scope внутри фазы и зелёные тесты.

---

## 5. Целевая структура (sketch)

### 5.1 Workspace boundary (Phase 2A — implementation)

Два варианта (Phase 2A фиксирует один ADR‑ом 0130):

**Вариант A — collapse:** `polisyos/` upper layer убирается, `policy-engine/`
становится репозиторием первого уровня.

**Вариант B — true monorepo:** root становится workspace‑aware:
```
polisyos/
├── pyproject.toml          (uv workspace root)
├── pnpm-workspace.yaml     (TS workspace root)
├── apps/                   (runtime-dashboard, runtime-reference-shell)
├── packages/               (runtime-api-client, cli, ui-kit)
├── services/policy-engine/ (Python product, бывший policy-engine/)
├── docs/                   (cross‑service)
└── tools/                  (workspace‑level only)
```

В обоих случаях после фазы остаётся **одна** `.venv`, **один** набор
кэшей, **один** `.polisyos/`.

### 5.2 Эфемерный umbrella (Phase 2B)

```
policy-engine/
├── _build/                 ← всё, что генерится: dist, out, output, site,
│                              release/{sbom,artifacts}, frontend/dist
├── _cache/                 ← все каши: ruff, mypy, pytest, basedpyright,
│                              hypothesis, benchmarks, uv
├── .polisyos/              ← runtime state (как есть)
└── (release/templates/, release-fragments/template.toml — committed only)
```

Все три полностью в `.gitignore` (для `_build`, `_cache`); `.polisyos`
уже игнорируется.

### 5.3 `architecture/` — единственный источник для governance

```
policy-engine/architecture/
├── topology.toml
├── boundaries.toml
├── imports/
│   ├── contracts.toml      (← переименование import_contracts.toml)
│   ├── policy.toml         (← вмержить import_policy.toml)
│   ├── exceptions.toml     (← вмержить import_exceptions.toml)
│   ├── exceptions.md       (registry)
│   └── gate_baseline.txt   (← бывший baseline/import_gate.txt)
├── public_surface.toml
├── public_surface/         (inventory JSONs)
├── shims.toml              (registry совместимости и relocation)
├── generated_artifacts.toml
├── exceptions/
│   ├── complexity.toml
│   ├── guardrail.toml
│   ├── guardrail_registry.md
│   └── docs_freshness.toml
├── overlays/
│   ├── conservative.toml
│   └── data_policy.toml
├── repository_sota_gates.toml
├── domain_migration_batches.toml
├── ops_baselines.toml
└── README.md
```

Удаляются: `policy-engine/baseline/`,
`policy-engine/freeze_policy.md`, `policy-engine/import_exceptions*`,
`policy-engine/import_policy.toml`.

### 5.4 `pyproject.toml` декомпозиция (Phase 1B)

```
policy-engine/
├── pyproject.toml          ← ≤ 300 строк: project metadata + deps + build-system
├── ruff.toml               ← все [tool.ruff.*]
├── mypy.ini                ← [tool.mypy] + overrides
├── basedpyright.toml
├── pytest.ini              ← [tool.pytest.ini_options]
├── mutmut.cfg
└── (все [project.optional-dependencies] могут переехать в
   [dependency-groups] PEP 735, если uv поддерживает в текущей версии)
```

### 5.5 `src/polisyos/` целевой layout (Phase 1C, 3A, 4A, 5, 6)

```
src/polisyos/
├── common/             (~15)
├── ir/                 (~150 после выноса аналитики)
├── core/               (~150 после выноса observability/security/governance)
├── data_forge/         (~240, не трогаем)
├── fabric/             (~270, не трогаем)
├── lex/                (~35)
├── runtime/            (~60)
├── scholar/            (~25)
├── scientist/          (~250 после выделения engine/methods/agents в
│                        scientist_engine, scientist_methods/, scientist_agents/
│                        ИЛИ через явный façade-only top-level)
├── foundry/            (~250 после выделения foundry_methods/ как
│                        отдельного top-level пакета или жёсткой
│                        дисциплины внутри)
├── ddm/                (← переименование ddm_15_7)
└── (synthetic_world, calibration, packs, berl — planning Phase 3B, implementation Phase 4A)
```

Выбор «split top‑level» или «façade‑only» закрепляется в ADR‑0133/0134.

### 5.6 Тесты (Phase 1E)

```
tests/
├── conftest.py                ← глобальные хуки
├── fixtures/<package>/        ← все фикстуры локализованы
├── unit/<package>/            (один conftest на пакет)
├── integration/<package>/
├── property/<package>/
├── contract/  e2e/  performance/  golden/  lint/  architecture/  tools/
```

Удаляется: `tests/integration/scientist/` (дубль), `tests/unit/data_forge/`
поднимается в `tests/unit/data_forge/`, `tests/unit/scientist/orchestrator_v2/`
переименовывается осмысленно.

### 5.7 Frontend (Phase 1F + 4B)

- `frontend/` ↔ `packages/cli` — единый pnpm workspace (или turbo).
- `runtime-dashboard/src/lib/` сливается в `runtime-dashboard/src/shared/lib/`.
- `runtime-dashboard/src/i18n/` → `runtime-dashboard/src/shared/i18n/`.
- Build‑output дир (`coverage/`, `dist/`, `playwright-report/`,
  `output/`, `storybook-static/`, `test-results/`) переезжают под
  `_build/<workspace>/...` — с обновлённым `.gitignore`.

---

## 6. Execution model

Этот план теперь читается как **barrier → parallel wave → barrier**.
Номер фазы — это порядок безопасного merge, а не исторический номер из
старого линейного плана.

| Execution slot | Фазы                    | Параллельность                        | Barrier / правило merge                                      |
| -------------- | ----------------------- | ------------------------------------- | ------------------------------------------------------------ |
| First barrier  | Phase 0                 | Не параллелится                       | До Phase 0 нельзя начинать implementation                    |
| Wave 1         | 1A, 1B, 1C, 1D, 1E, 1F  | Все шесть фаз можно вести параллельно | Все Wave 1 фазы merged до workspace/path changes             |
| Path barrier   | 2A → 2B                 | Последовательно                       | Сначала workspace, потом `_build/`/`_cache/`                 |
| Wave 2         | 3A, 3B                  | Можно вести параллельно               | 3A строит safety net; 3B только планирует small-package moves |
| Wave 3         | 4A, 4B                  | Можно вести параллельно               | 4A backend/package moves; 4B frontend workspace/build output |
| Decomp barrier | 5 → 6                   | Последовательно                       | `scientist/` перед `foundry/`; оба после 3A и 4A             |
| Final barrier  | Phase 7                 | Не параллелится                       | Все gates fail‑closed, closeout, move plan to `accepted/`    |

### 6.1 New phase map

| New phase | Old phase / concern                                  | Deliverable                                                 |
| --------- | ---------------------------------------------------- | ----------------------------------------------------------- |
| 0         | old 0                                                | Inventory, ADR baseline, contracts, ownership fences        |
| 1A        | old 1                                                | Quick wins and artifact eviction                            |
| 1B        | old 4                                                | `pyproject.toml` split + `architecture/` governance merge   |
| 1C        | old 5 decision part                                  | Cross-package name registry decisions, no risky source moves |
| 1D        | old 10                                               | Tools consolidation                                         |
| 1E        | old 11                                               | Tests topology stabilization before safety baselines        |
| 1F        | old 12 source part                                   | Frontend source duplicate cleanup                           |
| 2A        | old 2                                                | Workspace boundary implementation                           |
| 2B        | old 3                                                | `_build/` + `_cache/` umbrella                              |
| 3A        | old 7                                                | Decomposition preflight safety net                          |
| 3B        | old 6 decision part                                  | Small-package consolidation blueprint                       |
| 4A        | old 6 implementation part                            | Small-package consolidation implementation                  |
| 4B        | old 12 workspace/output part                         | Frontend workspace manager + build-output finalization      |
| 5         | old 8                                                | Scientist decomposition                                     |
| 6         | old 9                                                | Foundry decomposition                                       |
| 7         | old 13                                               | Enforcement + closeout                                      |

### 6.2 Ownership fences

Параллельные фазы безопасны только если соблюдаются file-ownership
fences. Shared registries (`architecture/shims.toml`,
`architecture/public_surface.toml`, `architecture/package_boundaries.toml`)
обновляются короткими serialized patches, а не независимыми долгоживущими
ветками.

| Фаза | Owns                                                                 | Не трогает параллельно                                              |
| ---- | -------------------------------------------------------------------- | ------------------------------------------------------------------- |
| 1A   | `foundry/methods/`, loose data/runtime artifacts, `generated_artifacts` | `pyproject.toml`, `tools/quality/validation/`, frontend source      |
| 1B   | `pyproject.toml`, split config files, `architecture/imports/`, `architecture/policies/` | `tests/`, frontend, package source moves                            |
| 1C   | `architecture/name_registry.toml`, `architecture/package_layout.toml`, name ADRs | Physical moves in `scientist/` / `foundry/`                         |
| 1D   | `tools/{devx,ops,quality,research,ci}`, tool shims, CI refs           | `tools/devx/refactor/move_module.py`, new Phase 3A validation gates |
| 1E   | `tests/`, `architecture/test_topology.toml`                           | Source package moves                                                |
| 1F   | `apps/runtime-dashboard/src/**` source duplicate cleanup          | Lockfiles, workspace manager, `_build/` paths                       |
| 2A   | Workspace root layout, `.venv`, lockfile placement, topology paths    | Safety net baselines                                                |
| 2B   | `_build/`, `_cache/`, `.gitignore`, tool cache dirs                   | Source package moves                                                |
| 3A   | `DECOMPOSITION_BLUEPRINT.md`, safety gates, codemod, baselines        | Any `.py` moves in `scientist/` / `foundry/`                        |
| 3B   | `SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md`, ADR‑0138/0139 decisions   | Actual package moves                                                |
| 4A   | `ddm`, `packs`, `synthetic_world`, `agent_sim`, `calibration`, `berl` | Frontend workspace                                                  |
| 4B   | Frontend workspace manager, frontend build outputs                    | Backend package source                                              |
| 5    | `src/polisyos/scientist/**`, scientist tests/contracts                | `src/polisyos/foundry/**` except explicitly accepted shared shims   |
| 6    | `src/polisyos/foundry/**`, foundry tests/contracts                    | Scientist moves                                                     |

---

## 7. Phase 0 — Inventory, ADR baseline & concurrency contract

**Цель:** материализовать решения этого плана в ADR, обновить
machine‑readable inventory и зафиксировать ownership fences для
параллельной работы.

**Работа:**

1. Переснять inventory:
   - список empty `__init__.py`‑only пакетов;
   - список loose `.py` в корне каждого top‑level пакета (с size в LoC);
   - список пар (name, package) для каждого повторяющегося имени
     директории (`governance/`, `contracts/`, ...);
   - список дублированных кэшей/venv между root и `policy-engine/`;
   - список build‑output дир и их `.gitignore`‑статус;
   - размер `pyproject.toml` и расход по `[tool.*]` секциям;
   - тестовую топологию (`unit/`, `integration/`, `property/`, fixtures);
   - frontend source duplicates и lockfile/build‑output placement.
2. Написать ADR:
   - **ADR‑0129** — Empty placeholder package policy (no namespace
     placeholder may share a name with a populated descendant).
   - **ADR‑0130** — Workspace boundary (collapse vs monorepo).
   - **ADR‑0131** — Build‑output and cache umbrella (`_build/` + `_cache/`).
   - **ADR‑0132** — `architecture/` as single governance source (merge
     `baseline/` and root‑level `import_*`/`freeze_policy`).
   - **ADR‑0133** — Top‑level package size budget (≤ 250 файлов;
     ≤ 5 loose `.py` в корне; обязательный `_api.py`).
   - **ADR‑0134** — Cross‑package name registry (allowed shared names
     declared in `architecture/name_registry.toml`).
   - **ADR‑0135** — Versioning out of package names (`ddm_15_7 → ddm`).
   - **ADR‑0136** — `foundry/methods` flat vs catalog.
   - **ADR‑0137** — Production data / fixtures classification.
   - **ADR‑0138** — `synthetic_world` ↔ `agent_sim` merge direction.
   - **ADR‑0139** — Canonical home for `calibration/`.
3. Создать новый contract `architecture/name_registry.toml` (Phase 1C
   будет его наполнять).
4. Создать `architecture/package_layout.toml` с правилами «façade в
   корне», «не более N loose .py», «empty namespace ban».
5. Создать `architecture/test_topology.toml` skeleton.
6. Расширить `tools/quality/validation/` хуки report‑only‑gate'ами:
   - `empty_namespace_gate` — проваливает наличие
     `foundry/methods/<X>/` без файлов кроме `__init__.py`, если в
     дереве есть `foundry/methods/<Y>/<X>/` с тем же именем.
   - `loose_files_gate` — считает `.py` в корне пакета,
     сравнивает с `package_layout.toml`.
   - `name_collision_gate` — пара (name, package) против
     `name_registry.toml`.
   - `pyproject_size_gate` — checks LOC, секции, [tool.*] count.
   - `cache_dir_gate` и `build_output_gate` — пока report‑only.
7. Создать `architecture/baselines/structure_remediation/` со снапшотами
   inventory (для drift‑сравнения в Phase 7).
8. Создать `docs/plans/active/REPOSITORY_STRUCTURE_REMEDIATION_CONCURRENCY.md`
   с ownership map из секции 6.2.

**Deliverables:**

- ADR‑0129..0139 skeletons.
- Inventory snapshot in `docs/archive/reports/REPOSITORY_STRUCTURE_REMEDIATION_PHASE_0_INVENTORY.md`.
- `architecture/name_registry.toml` (skeleton).
- `architecture/package_layout.toml` (skeleton).
- `architecture/test_topology.toml` (skeleton).
- `docs/plans/active/REPOSITORY_STRUCTURE_REMEDIATION_CONCURRENCY.md`.
- Report‑only gate wiring.

**Acceptance:**

- Каждый дефект из секции 0 имеет владельца и target‑контракт.
- Все Wave 1 фазы имеют disjoint primary ownership.
- Gates запускаются report‑only и фиксируют baseline.
- Никаких структурных move‑ов в этой фазе.

---

### 7.1 Wave 1 navigation

После Phase 0 можно одновременно стартовать:

- Phase 1A — quick wins (секция 8).
- Phase 1B — config/governance split (секция 11).
- Phase 1C — name registry decisions (секция 12).
- Phase 1D — tools consolidation (секция 17).
- Phase 1E — tests topology stabilization (секция 18).
- Phase 1F — frontend source duplicate cleanup (секция 19).

Секции ниже остаются тематическими, но execution order определяется
таблицами 6 и 6.1. Phase 2A не стартует, пока все Phase 1A..1F не
merged и не зелёные.

---

## 8. Phase 1A — Quick wins & artifact eviction

**Цель:** убрать самые громкие structural smells без поведенческих рисков.

### 8.1 `foundry/methods/` namespace cutover

Сейчас:
```
foundry/methods/{bayesian,causal,dependence,econometrics,
                 microsim,ml,network,optimization,spatial}/  ← только __init__.py
foundry/methods/catalog/{bayesian,causal,...}/               ← реальная логика
```

`MIGRATION_V2.md` фиксирует «flat API + canonical в catalog» — выбрать
один из двух финалов, ADR‑0136 (companion к ADR‑0129):

**Вариант A (рекомендуется):** убрать пустые placeholders. Все импорты
идут через `foundry.methods.catalog.<domain>.<module>`; flat re‑exports
живут в `foundry/methods/__init__.py` как явные `from .catalog.causal
import SyntheticControlMethod` (без отдельных `causal/__init__.py`).

**Вариант Б:** заполнить placeholders re‑export‑шимами:
```python
# foundry/methods/causal/__init__.py
from polisyos.foundry.methods.catalog.causal import *  # noqa
```
плюс sunset‑date в `shims.toml`.

В обоих случаях:

1. Inventory всех external импортёров `foundry.methods.<X>` (где X —
   placeholder) — `tools/quality/validation/empty_namespace_gate.py`.
2. Заменить deep imports на явные façade‑импорты.
3. Удалить либо placeholder директории (вариант A), либо `__init__.py`
   с реэкспортом и sunset (вариант B).
4. `empty_namespace_gate` переводится в fail‑closed.

### 8.2 Empty `foundry/engine/` директория

Удаляется; её имя освобождается. Если что‑то ссылается — replace на
`scientist.engine` или удалить ссылку.

### 8.3 Eviction loose data из репо

Удаляются (через .gitignore + git rm --cached, без потери истории):

- `polisyos/runs/test_004/` (один-единственный test_004 — это явно
  локальный run, переносится в `.polisyos/runs/`).
- `polisyos/output/playwright/` (build artifact).
- `polisyos/data/_loose/`.
- `polisyos/relevant_topics_domain_files/` — переезжает в
  `data_forge/domains/.../fixtures/` или DVC, регистрируется в
  `architecture/generated_artifacts.toml`.
- `polisyos/tmp/*` (датированные `.sh`/`.log`/`.py` от 20260428–20260501).
- `policy-engine/production_data/` — fixture? тогда в
  `tests/fixtures/<domain>/`. Production snapshot? тогда в DVC/external.
  Любой из вариантов фиксируется ADR‑0137.
- `policy-engine/runs/` (27+ хеш‑директорий) — переезжают в
  `.polisyos/runs/` (gitignored).

### 8.4 Loose root `.sh` и удалённые `.py` в git status

`policy-engine/install.sh`, `policy-engine/migrate.py`,
`policy-engine/jax_bootstrap.py` — уже зарегистрированы как shims в
`shims.toml` с sunset 2026‑08‑01. Подтвердить, что удалённые
`filter_topics.py`, `organize_relevant_topics.py` (в git status) имеют
замену в `tools/research/experiments/`, либо нужен явный delete‑commit.

**Acceptance:**

- `empty_namespace_gate` fail‑closed по `foundry/methods/`.
- `policy-engine/runs/` пуст или удалён; `.polisyos/runs/` его заменяет.
- `production_data/` либо в `tests/fixtures/` (с DVC ref), либо вне репо.
- 0 файлов в `polisyos/tmp/`, кроме `.gitkeep` (или директория удалена).
- Нет регрессов в `tests/` после foundry/methods cutover (golden coverage
  для `from polisyos.foundry.methods.causal import …` сохраняется).

---

## 9. Phase 2A — Workspace boundary implementation

**Цель:** убрать двойной workspace.

ADR‑0130 фиксирует один из двух путей.

**Sequencing:** Phase 2A стартует только после полностью закрытой Wave 1
(Phase 1A..1F). Она не параллелится с Phase 2B и не должна идти
параллельно с baseline‑снятием Phase 3A.

### 9.1 Вариант A — collapse

1. Перенести из `polisyos/` (root) в `policy-engine/`:
   - `README.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`
     (одна копия каждого).
   - `lefthook.yml` (если применяется к product) → объединить с
     `policy-engine/.pre-commit-config.yaml` или оставить только один.
   - `renovate.json` (если репо одно — нужен на root уровне).
   - `data/`, `design/` (если они product‑level).
2. Удалить root‑level кэши, дубли venv, `.tmp/`, `tmp/`.
3. Поднять `.github/` на root (он там уже).
4. Topology: `topology.toml` на root‑уровне исчезает; product‑root‑секции
   становятся root‑секциями.

### 9.2 Вариант B — monorepo

1. Установить `uv` workspaces (через root `pyproject.toml` с
   `[tool.uv.workspace]`).
2. Установить `pnpm-workspace.yaml` или `turbo.json` для TS.
3. Переместить:
   - `policy-engine/apps/runtime-dashboard/` → `apps/runtime-dashboard/`
   - `policy-engine/apps/runtime-reference-shell/` → `apps/runtime-reference-shell/`
   - `policy-engine/packages/runtime-api-client/` → `packages/runtime-api-client/`
   - `policy-engine/packages/cli/` → `packages/cli/`
   - `policy-engine/` → `services/policy-engine/`
4. Обновить `architecture/topology.toml` под новую root‑топологию.
5. Один `node_modules`/`pnpm-lock.yaml`, один `uv.lock`.

В обоих случаях после фазы:

- Одна `.venv` (root или service‑local).
- Один набор кэшей.
- Одна копия `.polisyos/`.

**Acceptance:**

- `find /polisyos -name ".venv" -type d` возвращает ровно 1 путь.
- `find /polisyos -name ".mypy_cache" -type d` возвращает ровно 1 путь.
- `topology.toml` не содержит дублирующихся `scope=repo_root` и
  `scope=product_root` для одного и того же категориального бакета.

**Risk:**

- Это крупная миграция. Делается через одну PR с полным green‑CI;
  rollback — через revert.
- Если выбран monorepo, package_boundaries.toml требует обновления
  (`polisyos.*` paths).

---

## 10. Phase 2B — Build / cache umbrella

**Цель:** свернуть 7 build‑output и 6 кэш‑дир в две зонтичных папки.

**Sequencing:** Phase 2B идёт сразу после Phase 2A. Её нельзя делать
параллельно с workspace boundary implementation, потому что обе фазы
переписывают root paths, `.gitignore`, topology и tool commands.

### 10.1 `_build/`

Под единый `_build/` сливаются:

- `policy-engine/dist/` → `_build/dist/`
- `policy-engine/out/` → `_build/out/` (или удалить, если эфемерное)
- `policy-engine/output/` → `_build/output/`
- `policy-engine/site/` → `_build/site/` (mkdocs build)
- `policy-engine/logs/` → `_build/logs/`
- `policy-engine/.tmp/` → `_build/.tmp/` (или `_build/scratch/`)
- `policy-engine/benchmark-results/` → `_build/benchmark-results/`
- `policy-engine/release/sbom/` → `_build/release/sbom/`
- `policy-engine/release-fragments/releases/` → `_build/release-fragments/`
- `apps/runtime-dashboard/{coverage,dist,playwright-report,output,
  storybook-static,test-results}/` → `_build/apps/runtime-dashboard/...`

Всё в `.gitignore`. Шаблоны (`release/templates/`, `release/*.toml`,
`release-fragments/template.toml`, `release-fragments/unreleased/`)
**остаются commited** в `release/` (как сейчас) — они не build output.

### 10.2 `_cache/`

Под единый `_cache/` сливаются:

- `.cache/`, `.uv-cache/`, `.mypy_cache/`, `.pytest_cache/`,
  `.ruff_cache/`, `.hypothesis/`, `.basedpyright/`, `.benchmarks/`.

Каждый инструмент конфигурируется на писать туда:

```toml
# pyproject.toml / ruff.toml
[tool.ruff]
cache-dir = "_cache/ruff"
[tool.mypy]
cache_dir = "_cache/mypy"
[tool.pytest.ini_options]
cache_dir = "_cache/pytest"
```

Альтернатива — XDG `$XDG_CACHE_HOME/polisyos/...` (если CI это допускает).

### 10.3 `.gitignore` хирургия

После фазы — `.gitignore` сильно сокращается:

```
# Эфемерные артефакты
_build/
_cache/
.polisyos/
.venv/

# Что специфично оставлено
**/__pycache__/
*.pyc
*.egg-info/
```

**Acceptance:**

- `find policy-engine -maxdepth 1 -name "*.cache" -o -name ".tmp" ... `
  возвращает 0 результатов.
- `topology.toml` `scope=product_root` содержит ровно `_build/`,
  `_cache/`, `.polisyos/`, `.venv/` для эфемерного.
- Все linter/type/test commands продолжают работать (cache misses
  допустимы).

---

## 11. Phase 1B — `pyproject.toml` split + `architecture/` merge

**Цель:** свернуть 1975 строк в 5 ревьюабельных файлов; собрать
governance в одно место.

**Parallelism:** можно вести параллельно с Phase 1A/1C/1D/1E/1F.
Primary ownership — config/governance paths. Эта фаза не двигает package
source и не перестраивает tests/frontend.

### 11.1 Декомпозиция `pyproject.toml`

| Извлечь                         | В файл              | Ожидаемый размер |
| ------------------------------- | ------------------- | ---------------- |
| `[tool.ruff.*]`                 | `ruff.toml`         | ~150 строк       |
| `[tool.mypy]` + overrides       | `mypy.ini`          | ~200 строк       |
| `[tool.basedpyright]`           | `basedpyright.toml` | ~50 строк        |
| `[tool.pytest.ini_options]`     | `pytest.ini`        | ~100 строк       |
| `[tool.mutmut]`                 | `mutmut.cfg`        | ~30 строк        |
| `[tool.hatch.build.targets.*]`  | оставить            |                  |

Цель: финальный `pyproject.toml` ≤ 300 строк.

`[project.optional-dependencies]` — оценить, не пора ли часть из ~30
extras унести в `[dependency-groups]` PEP‑735 (uv поддерживает).
Особенно `causal-*` (8 групп), `ml`, `analytics`, `bayesian`,
`sensitivity`, `notebooks` — все не‑runtime.

Оценка Phase 1B (2026-05-03): перенос extras в `[dependency-groups]`
не выполняется в этой фазе. В репозитории 50 extras, и текущие CI/templates,
docs и локальные команды всё ещё вызывают `uv sync` / `uv run` через
`--extra ml`, `--extra runtime`, `--extra research`, `--extra causal-*`.
Миграция этих групп меняет install/API контракт и должна идти отдельным
поведенчески видимым cutover.

### 11.2 Slot‑in `architecture/`

Перенесения (без поведения, только paths):

- `policy-engine/baseline/import_gate.txt` →
  `architecture/imports/gate_baseline.txt`.
- `policy-engine/baseline/summary.json` →
  `architecture/imports/gate_summary.json`.
- `policy-engine/import_exceptions.toml` →
  `architecture/imports/exceptions.toml`.
- `policy-engine/import_exceptions_registry.md` →
  `architecture/imports/exceptions.md`.
- `policy-engine/import_policy.toml` →
  `architecture/imports/policy.toml`.
- `policy-engine/freeze_policy.md` →
  `architecture/policies/freeze.md`.

Все ссылающиеся скрипты (`tools/quality/lint/...`,
`tools/architecture/...`) обновляются. После — `policy-engine/baseline/`
удаляется; топология `topology.toml` снимает её ярлык
`baseline_artifacts`.

### 11.3 Migration shims

В `architecture/shims.toml` (после переименования):

```toml
[[shim]]
id = "imports-config-relocation"
source_path = "import_policy.toml"
target_path = "architecture/imports/policy.toml"
type = "file_relocation"
sunset_date = "2026-09-01"
owner = "team-architecture"
```

(аналогично для `import_exceptions.toml`, `freeze_policy.md`,
`baseline/import_gate.txt`).

**Acceptance:**

- `wc -l pyproject.toml` ≤ 300.
- `policy-engine/baseline/` отсутствует; топология не содержит
  `baseline_artifacts` категории на product‑root.
- Все 5 governance файлов в `architecture/imports/` или
  `architecture/policies/`.
- `pyproject_size_gate` fail‑closed.
- `ruff`/`mypy`/`pytest` корректно видят свои конфиги (CI green).

---

## 12. Phase 1C — Cross‑package name registry decisions

**Цель:** сделать каждое повторяющееся имя директории либо явно
одобренным bounded context'ом, либо поставить его в конкретный
implementation backlog. Эта фаза intentionally **не делает risky source
moves** в `scientist/` или `foundry/`.

### 12.1 Inventory

В Phase 0 собирается таблица, а Phase 1C принимает решения:

| Имя              | Локации                                                                                                       | Решение           |
| ---------------- | ------------------------------------------------------------------------------------------------------------- | ----------------- |
| `governance/`    | `core/`, `foundry/`, `ir/`, `scientist/`                                                                      | bounded — declare |
| `contracts/`     | `core/`, `foundry/`, `berl/`, `ddm/`, `scientist/`, `lex/` (?)                                                | bounded — declare |
| `discovery/`     | `core/`, `foundry/`, `scientist/`                                                                             | смерж?            |
| `validation/`    | `scientist/`, `foundry/`                                                                                      | bounded — declare |
| `methods/`       | `foundry/`, `scientist/`                                                                                      | bounded — declare |
| `causal/`        | `scientist/`, `foundry/methods/` (empty), `foundry/methods/catalog/`                                          | Phase 1A убирает 1 |
| `kernel/`        | `data_forge/`, `ir/`, `scientist/`                                                                            | bounded — declare |
| `data_plane/`    | `fabric/`, `foundry/`                                                                                         | bounded — declare |
| `analytics/`     | `ir/`, `foundry/methods/catalog/...`                                                                          | bounded — declare |
| `runtime/`       | top‑level `runtime/`, `scientist/runtime/`, `foundry/runtime/`                                                | rename inner ones |
| `provenance/`    | `fabric/`, `lex/`, `scientist/`                                                                               | bounded — declare |

### 12.2 `architecture/name_registry.toml`

```toml
[name_registry]
version = 1
description = "Allowed shared directory names across top-level packages."

[[shared_name]]
name = "governance"
allowed_in = ["core", "foundry", "ir", "scientist"]
semantic_axis = "policy enforcement / decision audit"
disambiguation = "qualified imports required"

[[shared_name]]
name = "contracts"
allowed_in = ["core", "foundry", "berl", "ddm", "scientist", "lex"]
semantic_axis = "Pydantic models per bounded context"
disambiguation = "qualified imports required"
```

### 12.3 Rename backlog, not implementation

Где имя нельзя оправдать:

- `foundry/runtime/` (3 файла) → `foundry/_runtime_glue/` или вмерж в
  `foundry/__init__.py`. Имя `runtime/` оставляем за top‑level пакетом.
- `scientist/runtime/` — то же.
- `foundry/methods/causal/` — удаляется в Phase 1A.

Physical moves в `scientist/` и `foundry/` не выполняются в Phase 1C.
Они попадают в `DECOMPOSITION_BLUEPRINT.md` и выполняются только в
Phase 5/6 после Phase 3A safety net. Moves вне этих пакетов попадают в
Phase 4A, если они покрыты `SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md`.

### 12.4 Gate

`name_collision_gate.py` переводится в fail‑closed для новых
collisions. Существующие collisions разрешены только если у них есть
registry entry или backlog item с owner, target phase и sunset.

**Acceptance:**

- Каждое повторяющееся имя имеет либо запись в `name_registry.toml`,
  либо target phase для переименования/удаления.
- `name_collision_gate` fail‑closed for new unregistered collisions.
- 0 physical moves in `src/polisyos/scientist/` and `src/polisyos/foundry/`.

---

## 13. Phase 3B / 4A — Small‑package consolidation

**Цель:** убрать «зомби» и слабые пакеты, но без смешивания planning и
implementation. Эта работа разделена на две безопасные части:

- **Phase 3B** — blueprint/ADR/move map, 0 source moves; можно вести
  параллельно с Phase 3A.
- **Phase 4A** — implementation под уже зелёным Phase 3A safety net;
  можно вести параллельно с Phase 4B frontend work.

`SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md` — обязательный вход для
Phase 4A. Если move касается `scientist/`, `foundry/`, `agent_sim` или
shared `calibration`, Phase 4A должна завершиться до Phase 5/6.

### 13.0 Phase 3B planning deliverable

Phase 3B создаёт `docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md`.
Для каждого weak package фиксируются: source path/FQN, target path/FQN,
public surface impact, dynamic import impact, tests, shim, sunset,
rollback и target owner. Никакие файлы в `src/polisyos/` в Phase 3B не
двигаются.

### 13.1 `ddm_15_7` → `ddm`

ADR‑0135. Phase 3B выбирает exact move map; Phase 4A implements it.

1. Создать `src/polisyos/ddm/` идентичный `ddm_15_7/`.
2. Зарегистрировать shim:
   ```toml
   [[shim]]
   id = "ddm-15-7-rename"
   source_path = "src/polisyos/ddm_15_7"
   target_path = "src/polisyos/ddm"
   type = "wrapper_only"  # ddm_15_7/__init__.py = re-export from ddm
   sunset_date = "2026-10-01"
   ```
3. Обновить `package_boundaries.toml`, `import_contracts.toml`,
   `public_surface.toml`.
4. Внешние импортёры мигрируют до sunset.
5. После sunset — удалить `ddm_15_7/`.

### 13.2 `packs/` sunset

`packs/{econ, roads}` пустые. Если задумывались как user‑contributed
extension namespace — оформить в ADR с явной target‑семантикой.
Если нет — удалить.

Phase 3B принимает решение; Phase 4A удаляет или формализует namespace.

### 13.3 `synthetic_world/` ↔ `foundry/agent_sim/`

ADR‑0138.

Семантическое пересечение:
- `synthetic_world/{configs, core, evaluators, operators, targets,
  templates}` (~31 файл).
- `foundry/agent_sim/` (~42 файла, distributions, mechanisms,
  evolution, executors).

Phase 3B решение (на выбор, через ADR):

- **A:** `synthetic_world` мигрирует в `foundry/agent_sim/world/`, имя
  `synthetic_world` освобождается.
- **B:** `foundry/agent_sim` мигрирует в `synthetic_world/agent_sim/`,
  и top‑level пакет — `synthetic_world` (переименовать `foundry/agent_sim`).

Phase 4A реализует выбранное направление. В любом случае в
`shims.toml` появляется shim, и нет двух пакетов с одной
ответственностью.

### 13.4 `calibration/` (top‑level) merge

`src/polisyos/calibration/` (7 файлов) дублирует
`src/polisyos/scientist/calibration/` (другой скоп) и
`src/polisyos/foundry/calibration/`. Свести к одному месту:

- Если общий — `src/polisyos/calibration/` остаётся, но владелец и
  публичный API чётко описаны; `scientist/calibration` и
  `foundry/calibration` импортируют из него.
- Если scientist/foundry‑specific — top‑level `calibration/` исчезает,
  его содержимое распределяется.

Решение фиксируется ADR‑0139 в Phase 3B, implementation выполняется в
Phase 4A.

### 13.5 `berl/` legacy маркировка

`berl/` (31 файл) — текущий `package_boundaries.toml` упоминает его в
forbidden‑списках всех других пакетов, что косвенно говорит «не
импортировать». Но нет `legacy = true` или `frozen = true` в его
секции. Phase 3B решение:

- Если legacy → пометить `legacy = true`, `frozen = true`,
  `migration_target = "<куда>"` в `package_boundaries.toml`.
- Если активный → дописать его роль в README и убрать из forbidden
  списков активных потребителей.

Phase 4A вносит выбранные изменения.

**Acceptance:**

- 0 пустых placeholder пакетов в `src/polisyos/`.
- Нет версии в имени Python‑пакета (`ddm_15_7` отсутствует).
- `synthetic_world` ↔ `agent_sim` resolved one way (ADR + shim).
- `calibration/` имеет один canonical home.
- `berl/` имеет либо `legacy=true`, либо чёткую активную роль.
- Phase 3B completed before any source move; Phase 4A green under
  Phase 3A safety gates.

---

## 14. Phase 3A — Decomposition preflight (safety net)

**Цель:** до любых перемещений в `scientist/` и `foundry/` собрать
полный safety net, который железно закрывает риски декомпозиции:
pickle/checkpoint FQN, dynamic imports, Pydantic schema FQN, JAX/Pydantic
top‑level регистрации, циклические импорты, public surface, import‑time
регрессии. Эта фаза не двигает ни одного `.py` в `src/polisyos/scientist/`
или `src/polisyos/foundry/` — только инфраструктура и контракты.

> ⚠️ **Phase 3A — обязательный prerequisite для Phase 5 и Phase 6.**
> Без зелёного safety net Phase 5/6 не запускаются. После Phase 3A ни один
> риск декомпозиции не остаётся неконтролируемым.

### 14.1 Plan‑first artefact

Перед любой работой Phase 3A фиксирует blueprint:
`docs/plans/active/DECOMPOSITION_BLUEPRINT.md` (формат — ADR‑0143).
Содержание:

- exhaustive `move_map` для scientist/foundry с актуальными count из
  принятого blueprint: source FQN → target FQN, тип (public/internal),
  reasoning;
- inventory всех external импортёров каждого source FQN
  (grep по `src/`, `tests/`, `tools/`, `frontend/`);
- список планируемых re‑export shims с черновыми sunset‑датами;
- список Pydantic моделей в каждом перемещаемом файле + список их
  использований в `schemas/runtime_api_v1.openapi.json`;
- список JAX/Pydantic top‑level регистраций (если есть).

Без принятого blueprint Phase 5/6 не стартуют.

### 14.2 Pickle / checkpoint compatibility

ADR‑0140.

Работа:

1. **Inventory call sites:** grep `pickle.dump`, `pickle.load`,
   `cloudpickle`, `joblib.dump`, `joblib.load`, `torch.save`,
   `torch.load`, `dill` по `src/` и `tools/`.
2. **Inventory live artifacts:** перечислить все `*.pkl`, `*.pickle`,
   `*.joblib`, `*.ckpt` в `.polisyos/` (live runs) и
   `tests/fixtures/` (test fixtures).
3. **Snapshot canonical checkpoints:** для каждого top‑level пакета,
   у которого есть pickle‑артефакты (минимум — scientist/foundry):
   - запустить один canonical workflow до точки checkpoint,
   - сохранить файл как fixture в
     `tests/fixtures/checkpoint_compat/<package>/<scenario>.pkl`,
   - committed (или зарегистрирован в DVC, если bulk).
4. **Contract test:** `tests/contract/test_pickle_compat.py` — для
   каждого fixture делает `pickle.load()` и валидирует поля. Этот тест
   становится частью обычного `pytest` прогона; в Phase 5/6 он зелёный
   по определению (после move'ов он проходит благодаря re‑export shim).
5. **Sunset arithmetic:** в blueprint фиксируется max workflow lifetime
   (по `architecture/shims.toml` существующих shims +
   эмпирически по `.polisyos/runs/*/manifest.json` timestamps). Sunset
   re‑export shim из Phase 5/6 = max(60 дней, 2× max workflow lifetime).

### 14.3 Dynamic imports registry

ADR‑0141.

Работа:

1. **Grep audit:** `importlib.import_module`, `__import__`,
   `pkgutil.iter_modules`, `pkgutil.walk_packages`, `entry_points`,
   `importlib.resources.files`, `importlib.metadata.entry_points`.
2. **Plugin registries:** отдельный inventory для `foundry/plugins/`,
   `foundry/methods/components_bridge.py`,
   `foundry/methods/compat_matrix.py`,
   `foundry/methods/discovery.py`,
   `foundry/methods/selection.py`, `scientist/registry.py`.
3. **`architecture/dynamic_imports.toml`** — каждое dynamic FQN
   pattern с полями: `pattern`, `source_file`, `owner`,
   `allowed_targets` (явный whitelist допустимых FQN), `notes`.
4. **`dynamic_imports_gate`:** report‑only тест, который для каждого
   зарегистрированного pattern пробует resolve все `allowed_targets`;
   падает, если хоть один не resolved. После Phase 3A — fail‑closed.

### 14.4 Cyclic import audit

ADR‑0145.

Работа:

1. Прогнать `pydeps` (или `import-linter --report` режим) на текущем
   `src/polisyos/scientist/` и `src/polisyos/foundry/`; если эти
   внешние утилиты недоступны в dev env, Phase 3A использует
   deterministic AST import graph collector и фиксирует `collector_mode`
   в baseline.
2. Снапшот import graph в
   `architecture/baselines/structure_remediation/import_graph_pre_decomp.json`.
3. Идентифицировать lazy‑resolution циклы (работают только потому что
   `if TYPE_CHECKING:` или function‑local imports).
4. Решение для каждого цикла:
   - **Резолвить upfront** (вынести общие типы в `_types.py`), или
   - **Зафиксировать как допустимый lazy edge** в
     `architecture/imports/lazy.toml` с reason.
5. **`import_cycles_gate`** — fail‑closed после Phase 3A: запрещает
   новые non‑lazy циклы; разрешает только записанные в `lazy.toml`.

### 14.5 JAX / Pydantic registration audit

ADR‑0144.

Работа:

1. Grep:
   - `jax.tree_util.register_pytree_node`,
     `jax.tree_util.register_pytree_node_class`,
     `register_dataclass` (jax / equinox / chex);
   - `BaseModel.model_rebuild`, manual `update_forward_refs`,
     `discriminator`‑based registration.
2. Для каждой top‑level регистрации в перемещаемом файле:
   - либо инлайн lazy‑register pattern (регистрация при первом
     использовании, не при импорте),
   - либо файл переносится в `_internal/` так, чтобы re‑export shim
     импортировал ИМЕННО точечно (`from .new import OnlyTheClass`,
     не `from .new import *`).
3. **ADR‑0144 contract:** запрещает `from .new import *` в re‑export
   shim. `reexport_shim_shape_gate` — статический AST‑анализатор
   shim‑файлов; после Phase 3A — fail‑closed.

### 14.6 Public surface snapshot

Работа:

1. Refresh Phase 3A snapshot
   `architecture/baselines/structure_remediation/public_surface_pre_decomp.json`
   — пройти AST по всем top‑level пакетам, собрать `__all__` +
   публичные классы / функции / Pydantic модели с сигнатурами и FQN.
   Legacy `architecture/public_surface_inventory.json` остаётся
   отдельным façade inventory и не является источником Phase 3A gate.
2. **`tests/architecture/test_public_surface_snapshot.py`** — diff
   против committed snapshot. Любое изменение требует явного
   обновления snapshot (зелёный diff = ровно запланированные удаления
   /переименования из blueprint).
3. После Phase 5/6 — snapshot обновляется ровно в тех точках, что
   зафиксированы в blueprint; если diff больше — фаза не сдана.

### 14.7 Schema diff baseline

Работа:

1. Snapshot `schemas/runtime_api_v1.openapi.json` и любых других
   regenerated schemas (Pydantic JSON schemas) до Phase 5.
2. После Phase 5/6 — `tests/architecture/test_schema_diff.py`
   сравнивает; diff в `$defs` ключах допустим только для FQN,
   зафиксированных в blueprint.

### 14.8 Codemod tooling

ADR‑0142.

Работа:

1. Adopt `libcst` (Instagram, активно поддерживается, AST‑level,
   сохраняет форматирование) → добавить в `[dependency-groups.dev]`.
2. Написать reusable codemod: `tools/devx/refactor/move_module.py`.
   Входы: `--from polisyos.scientist.feedback`,
   `--to polisyos.scientist.feedback.utils`. Выходы:
   - физический move файла (`git mv`),
   - update всех `from X import Y` и `import X` в `src/`, `tests/`,
     `tools/`, `packages/runtime-api-client/scripts/`,
   - генерация re‑export shim в старом FQN (`from .new_path import *  # noqa: F401`,
     **либо точечный** список — выбор зависит от ADR‑0144 проверки,
     обычно точечный),
   - dry‑run mode (выводит планируемый diff без записи),
   - запись entry в `architecture/shims.toml`.
3. **Самопроверка codemod:** провести один experimental move
   (например, `synthetic_world/world.py` → внутри того же пакета),
   убедиться что unit + integration зелёные, откатить через
   `git checkout -- <files>`. Это валидирует codemod до Phase 5.

### 14.9 Import‑time benchmark baseline

Работа:

1. Замерить `python -X importtime -c "import polisyos.scientist"` и
   `import polisyos.foundry` 10 раз; сохранить median + p95 в
   `architecture/baselines/structure_remediation/import_time_pre_decomp.json`.
2. **`import_time_regression_gate`** — после Phase 5/6: регрессия
   median > 15% — fail. fail‑closed после Phase 3A.

### 14.10 Existing tests baseline

1. Локальный полный прогон `pytest tests/unit tests/integration
   tests/property tests/contract tests/golden -q` **не является
   обязательным acceptance для Phase 3A**: он слишком тяжёлый для
   developer laptop и намеренно не завершается локально.
2. Phase 3A фиксирует это как explicit deferred baseline в
   `architecture/baselines/structure_remediation/tests_baseline.txt`
   вместе с причиной и partial evidence.
3. Полный прогон выполняется в облаке или на более мощной машине.
4. Cloud full-suite baseline зафиксирован как зелёный для Phase 3A:
   `2026-05-04`, GCP VM `phase3a-fulltests-20260503`
   (`europe-west1-b`, 12 xdist workers). Основной прогон:
   `pytest tests/unit tests/integration tests/property tests/contract
   tests/golden -q -n 12 --dist loadscope -m "not benchmark"
   --benchmark-disable`; результат — 10,955 tests, 0 failures, 0 errors,
   35 skipped, 2,318 s. Benchmark slice:
   `pytest tests/unit/foundry/benchmarks tests/unit/ir/test_phase3_benchmarks.py
   -q`; результат — 20 tests, 0 failures, 0 errors, 24 s.
5. Evidence stored in GCS:
   `gs://lex-1-494208-data/experiments/phase3a_fulltests/phase3a-fulltests-12core-20260504-rerun-20260504T111449Z/`.
   Accepted skips are explicit optional dependency / environment gates
   (`dowhy`, `pygraphviz`, `ray`, `kuzu`, `econml`, `plotly`, BoTorch,
   OTel metrics backend, `POLISYOS_RUN_INTEGRATION=1`) plus compatibility
   skips for environments where accelerated/optional capabilities are present.
6. Phase 5/6 всё ещё обязаны держать зелёными focused safety net gates
   Phase 3A и package‑scoped проверки из acceptance своих фаз. Полный
   Phase 3A репозиторный baseline уже green; Phase 7 должен только
   подтвердить итоговый full-suite verdict после структурных moves.

**Deliverables:**

- `docs/plans/active/DECOMPOSITION_BLUEPRINT.md` (принят).
- `architecture/dynamic_imports.toml` (полное покрытие grep).
- `architecture/imports/lazy.toml` (классифицированные циклы).
- `tests/contract/test_pickle_compat.py` + canonical fixtures.
- `tests/architecture/test_public_surface_snapshot.py` + snapshot.
- `tests/architecture/test_schema_diff.py` + baseline.
- `tools/devx/refactor/move_module.py` (codemod, протестирован).
- ADR‑0140..0145.
- 6 новых report‑only gates: `dynamic_imports_gate`,
  `pickle_compat_gate`, `public_surface_snapshot_gate`,
  `import_cycles_gate`, `import_time_regression_gate`,
  `reexport_shim_shape_gate`.
- Baseline снапшоты в `architecture/baselines/structure_remediation/`.

**Acceptance:**

- DECOMPOSITION_BLUEPRINT принят владельцами scientist и foundry
  (через PR review).
- `pickle_compat_gate` зелёный на baseline.
- `dynamic_imports_gate` зелёный на baseline (все registered FQN
  resolve).
- `public_surface_snapshot_gate` зелёный на baseline.
- `import_cycles_gate` зелёный (все циклы либо разрешены, либо
  записаны в `lazy.toml`).
- Codemod протестирован на experimental move; rollback подтверждён.
- 0 файлов в `src/polisyos/scientist/` или `src/polisyos/foundry/`
  перемещены в этой фазе.
- Cloud full‑suite baseline green для Phase 3A; локальный laptop-прогон
  остаётся необязательным, потому что тяжёлый для MacBook Air.

---

## 15. Phase 5 — Scientist decomposition

**Цель:** довести количество loose `.py` в корне `scientist/` до ≤ 5;
держать верхний уровень `scientist/` ≤ 250 entries; зафиксировать
façade pattern. Никаких поведенческих изменений.

> Phase 3A inventory count `517` был recursive `python_file_count`, а не
> число файлов в верхнем уровне. Принятый `DECOMPOSITION_BLUEPRINT.md`
> разрешает только Scientist-internal moves из root modules; recursive
> package split за пределы `scientist/` остаётся вне Phase 5.

> Этот phase пересекается с
> [`SCIENTIST_BEST_IN_CLASS_PLAN.md`](SCIENTIST_BEST_IN_CLASS_PLAN.md):
> здесь — только структурный move, без рефакторинга логики, изменения
> сигнатур или семантики. Поведенческие изменения остаются в
> companion‑плане.

### 15.1 Prerequisite check

Перед стартом — Phase 3A gate tests зелёные
(`pytest tests/architecture/test_decomposition_preflight_gates.py -q`;
`tools/quality/validation/` содержит implementation modules для этих
gates). DECOMPOSITION_BLUEPRINT (раздел scientist) принят. Phase 4A
закрыта, если она трогала `scientist/` или shared `calibration`.

### 15.2 Move map (фиксируется в blueprint)

Loose `.py` в корне `scientist/` по принятому blueprint: 12
non-façade root modules. Это supersedes старый draft count `17`.

```
api.py                        → остаётся (façade, public)
decision_validity.py          → scientist/validation/decision_validity.py
error_semantics.py            → scientist/engine/error_semantics.py
evidence_sources.py           → scientist/evidence/sources.py
                                  (dedup и слияние с уже существующим
                                   scientist/evidence/, blueprint
                                   уточняет имена)
feedback.py                   → scientist/feedback/core.py
feedback_utils.py             → scientist/feedback/utils.py
frontier_runtime.py           → scientist/engine/frontier_runtime.py
latent_separation.py          → scientist/causal/latent_separation.py
llm_cycle.py                  → scientist/llm/cycle.py
publisher.py                  → scientist/orchestrator/publisher.py
reliability_scorecard.py      → scientist/validation/reliability_scorecard.py
remediation_status.py         → scientist/governance/remediation_status.py
replay_backend.py             → scientist/replay/backend.py (rename)
```

Файлы, которые остаются в корне: `__init__.py`, `api.py`, `README.md`.
Это max 3 root files; root `.py` — только façade files. Старые FQN
получают package re-export shims (`scientist/<old_name>/__init__.py`),
чтобы не увеличивать число loose root `.py`.

Внутренний layout (по ADR‑0133, рекомендованный Вариант A — façade в
одном пакете):

- `scientist/_engine/` — закрытые внутренности существующего
  `scientist/engine/` (если в blueprint решено сделать внутренним).
- `scientist/_methods/` — то же для существующих методов.
- `scientist/_agents/` — то же для агентов.

Решение «префиксовать `_` или оставить публичным» принимается
поэлементно в blueprint, на основе grep по external консумерам.

### 15.3 Execution (single coherent scope)

1. Принять blueprint (раздел scientist).
2. Прогнать codemod (`tools/devx/refactor/move_module.py`) для каждой
   строки move map. Codemod:
   - делает `git mv`,
   - обновляет все импортёры в `src/`, `tests/`, `tools/`, `frontend/`,
   - создаёт re‑export shim на старом FQN с точечным списком
     (соответствует ADR‑0144),
   - регистрирует shim в `architecture/shims.toml` с
     `sunset_date = move_date + max(60d, 2× max workflow lifetime)`.
3. Обновить `scientist/__init__.py`: `__all__` строго ограничен
   façade символами; всё остальное — приватное.
4. Обновить `architecture/public_surface.toml` секцию scientist.
5. Обновить `architecture/package_boundaries.toml` если надо
   (allowed_dependencies остаются прежними; меняется только
   internal layout).
6. Прогнать **полный safety net** (acceptance ниже).
7. Если хоть один gate красный — `git checkout -- <file>` точечный
   откат конкретного файла, доработать blueprint, повторить.

### 15.4 Acceptance

Все следующие проверки зелёные:

- `find src/polisyos/scientist -maxdepth 1 -name "*.py" | wc -l` ≤ 5.
- `pytest tests/unit/scientist tests/integration/scientist
  tests/property/scientist tests/contract -q` — нет регрессий vs
  Phase 3A baseline.
- `pytest tests/contract/test_pickle_compat.py -q` — green.
- `pytest tests/architecture/test_public_surface_snapshot.py -q` —
  diff = ровно запланированное в blueprint, ничего лишнего.
- `pytest tests/architecture/test_schema_diff.py -q` — green
  (нет shifts в `$defs` за пределами blueprint).
- `dynamic_imports_gate` зелёный (re‑export shims дают valid resolve).
- `import_cycles_gate` зелёный.
- `import_time_regression_gate` — median import time
  `import polisyos.scientist` регрессия ≤ 15%.
- `reexport_shim_shape_gate` зелёный (нет `import *` в shim'ах).
- `uv run python tools/quality/validation/repository_structure_phase0.py
  gate --gate loose_files --package scientist --scope root --mode
  fail-closed` — green.
- Все re‑export shims зарегистрированы в `shims.toml`.

### 15.5 Rollback

Если acceptance красный после фазы — точечный откат: для каждого
проблемного файла `git checkout HEAD~1 -- <path>` + соответствующий
revert codemod (его dry‑run mode сразу покажет, какие импорты
вернуть). Phase 5 переоткрывается, blueprint уточняется.

---

## 16. Phase 6 — Foundry decomposition

**Цель:** уменьшить `foundry/` с 505 до ≤ 250 файлов в верхнем уровне;
довести loose `.py` в корне до ≤ 5; зафиксировать façade pattern.
Никаких поведенческих изменений.

> Этот phase пересекается с
> [`FOUNDRY_REMEDIATION_PLAN.md`](FOUNDRY_REMEDIATION_PLAN.md). Здесь —
> только структурный move; behavioral остаётся там.

### 16.1 Prerequisite check

- Phase 3A safety net зелёный.
- Phase 5 закрыта; codemod валидирован на scientist (т.е. отлажен на
  более простом случае). Foundry получает выгоду от lessons learned.
- Phase 4A закрыта, если она трогала `foundry/`, `agent_sim` или shared
  `calibration`.
- DECOMPOSITION_BLUEPRINT (раздел foundry) принят.

### 16.2 Move map (фиксируется в blueprint)

Нормативная карта для Phase 6 — принятый
[`DECOMPOSITION_BLUEPRINT.md`](DECOMPOSITION_BLUEPRINT.md). Он
зафиксировал audited count в 28 root modules и supersedes старые draft
цифры 17/22, а также старую цель `foundry/_internal/executor/*`.

Текущая принятая карта Foundry:

```
_execution_posture.py         → foundry/execute/_posture.py
_executor_graph.py            → foundry/execute/_graph.py
_executor_models.py           → foundry/execute/_models.py
_executor_ops.py              → foundry/execute/_ops.py
_executor_patching.py         → foundry/execute/_patching.py
_executor_snapshots.py        → foundry/execute/_snapshots.py
_numeric.py                   → foundry/runtime/numeric.py
agent_metrics.py              → foundry/agent_sim/agent_metrics.py
agents.py                     → foundry/agent_sim/agents.py
conflict_checker.py           → foundry/validation/conflict_checker.py
constraints_engine.py         → foundry/validation/constraints_engine.py
cost_model.py                 → foundry/methods/cost_model.py
executor.py                   → foundry/execute/executor.py
layout.py                     → foundry/methods/layout.py
loss.py                       → foundry/methods/loss.py
mechanism_design.py           → foundry/mechanisms/design.py
merge_engine.py               → foundry/methods/merge_engine.py
patch_vm.py                   → foundry/execute/patch_vm.py
profiles.py                   → foundry/runtime/profiles.py
queue.py                      → foundry/execute/queue.py
quickstart.py                 → foundry/_quickstart.py
registry.py                   → foundry/_registry.py
release_acceptance.py         → foundry/validation/release_acceptance.py
social_weights.py             → foundry/welfare/social_weights.py
specs.py                      → foundry/contracts/specs.py
trace.py                      → foundry/runtime/trace.py
utils.py                      → foundry/_internal/utils.py
welfare_bounds.py             → foundry/welfare/bounds.py
```

Каждый старый source FQN получает targeted re-export shim без `import *`
и регистрируется в `architecture/shims.toml`. Это распространяется и на
старые `_executor_*` FQN: Phase 3A grep показал, что они участвуют в
compatibility surface, поэтому blueprint поднял их до shimmed moves.

В корне остаются только façade/compat entrypoints: `__init__.py`,
`api.py`, `_quickstart.py`, `_registry.py`, `README.md`. Max 5 `.py`
файлов.

### 16.3 Execution

Строго аналогично Phase 5 (15.3): blueprint → codemod → re‑export
shims → public surface refresh → safety net → точечный откат при
красном.

Особенности foundry:

1. **JAX top‑level регистрации:** в blueprint отдельный inventory
   (Phase 3A grep): `jax.tree_util.register_*`, `equinox.Module`. Если
   найдены в перемещаемом файле — re‑export shim строго точечный
   (одно imports per registered class), чтобы не было двойной
   регистрации. ADR‑0144 enforced via gate.
2. **Plugin discovery:** `foundry/plugins/`,
   `foundry/methods/components_bridge.py`, `compat_matrix.py`,
   `discovery.py`, `selection.py` — все они dynamic; их FQN patterns
   уже зарегистрированы в `architecture/dynamic_imports.toml`
   (Phase 3A). Phase 6 не должен ничего ломать в этом контракте; gate
   проверяет.
3. **Foundry/methods empty placeholders уже убраны в Phase 1A**, так
   что коллизий не будет.

### 16.4 Acceptance

Те же проверки, что в Phase 5.4, но для foundry:

- `find src/polisyos/foundry -maxdepth 1 -name "*.py" | wc -l` ≤ 5.
- `pytest tests/unit/foundry tests/property/foundry tests/contract -q` —
  нет регрессий vs Phase 3A baseline.
- pickle compat green.
- public surface snapshot diff = ровно blueprint.
- schema diff = ровно blueprint.
- dynamic imports green (особенно plugin discovery — ключевое для
  foundry).
- import cycles green.
- import‑time регрессия ≤ 15%.
- reexport shim shape green (ноль `import *`, особенно с учётом JAX).
- loose_files_gate fail‑closed green.
- Все internal `_executor_*` собраны в `foundry/execute/_*.py` согласно
  accepted blueprint; старые FQN покрыты targeted shim'ами.
- Все re‑exports зарегистрированы в `shims.toml`.

### 16.5 Public surface freeze

После Phase 6 — `architecture/public_surface.toml` обновляется так,
чтобы единственные публичные FQN в scientist/foundry были те, что в
их `api.py` и узких подпакетах, явно отмеченных `public: true`.

### 16.6 Rollback

Аналогично Phase 5.5. Точечный `git checkout` + revert codemod.

---

## 17. Phase 1D — Tools consolidation

**Цель:** одна ось организации (по стейкхолдеру), 0 дублирующихся имён.

**Parallelism:** можно вести параллельно с Phase 1A/1B/1C/1E/1F.
Важно завершить до Phase 3A, чтобы codemod и новые validation gates
создавались уже в финальной `tools/` структуре.

### 17.1 Текущие дубли

| Дубль                                                        | Решение                  |
| ------------------------------------------------------------ | ------------------------ |
| `tools/architecture/` ↔ `tools/devx/architecture/`            | Один (devx/)             |
| `tools/connectors/` ↔ `tools/devx/connectors/`                | Один (devx/)             |
| `tools/foundry/` ↔ `tools/devx/foundry/`                      | Один (devx/)             |
| `tools/migrations/` ↔ `tools/ops/migrations/`                 | Один (ops/)              |
| deprecated tool archive namespace                            | `tools/archive/`         |
| shared helper namespace                                      | `tools/lib/`             |
| `tools/cli.py`, `tools/registry.py`                           | Оставить (façade)        |

### 17.2 Целевая структура

```
tools/
├── cli.py                     ← unified entry point (polisyos-tools)
├── registry.py
├── lib/                       ← shared utilities (бывший _lib)
├── archive/                   ← бывший _deprecated, явно временный
├── devx/{architecture, connectors, foundry, workspace}/
├── ci/
├── ops/{calibration, cloud, data, deploy, experiments, migrations,
│       release, runtime}/
├── quality/{ci, diagnostics, lint, testing, validation}/
└── research/{benchmarks, demos, experiments}/
```

`tools/ukraine_data/` (под `ops/`) — переименовать или ассоциировать с
`data_forge/domains/ukraine/` (это domain‑specific tooling).

### 17.3 Migration

1. Inventory всех Bash/CI ссылок на `tools/architecture/...`,
   `tools/connectors/...`, `tools/foundry/...`, `tools/migrations/...`.
2. Rename + добавить shim‑скрипты, выводящие deprecation warning,
   sunset 2026‑09‑01.
3. CI/precommit/lefthook обновляются.

**Acceptance:**

- 0 дублирующихся имён в `tools/`.
- Deprecated archive namespace живёт только в `tools/archive/`.
- `polisyos-tools` CLI охватывает все commands; нет "loose" скриптов.

---

## 18. Phase 1E — Tests topology stabilization

**Цель:** один тест‑hub на пакет; локальные фикстуры; нет дублей.

**Parallelism:** можно вести параллельно с остальной Wave 1. Эту фазу
нужно завершить до Phase 3A, потому что Phase 3A фиксирует baseline
tests и любые крупные test moves после baseline делают regressions
шумными.

### 18.1 Move

- `tests/data_forge/` → `tests/unit/data_forge/` (унифицировать с
  остальными пакетами).
- `tests/unit/scientist/integration/` → `tests/integration/scientist/`
  (склеить с существующим, если есть; иначе создать).
- `tests/unit/scientist/wave2/` → переименовать (например,
  `tests/unit/scientist/orchestrator_v2/` если речь об orchestrator
  wave 2; или решить как deprecated test fixture).
- 30+ loose `test_*.py` в `tests/unit/scientist/` — распределить по
  существующим subpackages (`agent/`, `engine/`, `causal/`, ...) или
  оставить только те, что покрывают façade.
- Аналогично `tests/unit/foundry/`.

### 18.2 Conftest locality

Сейчас 6 `conftest.py` на 1481 файл. Цель — `conftest.py` в каждом
`tests/unit/<package>/` с локализованными фикстурами для этого
пакета.

```
tests/conftest.py                        ← глобальные хуки
tests/unit/scientist/conftest.py         ← scientist-specific fixtures
tests/unit/scientist/causal/conftest.py  ← causal fixtures
tests/unit/foundry/conftest.py
...
```

### 18.3 Property tests parity

`tests/property/` сейчас покрывает не все top‑level пакеты. После
фазы — для каждого пакета либо `tests/property/<pkg>/` существует,
либо в `architecture/test_topology.toml` указано «property не
требуется» с обоснованием.

**Acceptance:**

- `find tests/unit -maxdepth 2 -name conftest.py | wc -l` ≥ числа
  top‑level пакетов в src.
- Нет duplicate test файлов между `tests/unit/<pkg>/integration/` и
  `tests/integration/<pkg>/`.
- `architecture/test_topology.toml` фиксирует contract.

---

## 19. Phase 1F / 4B — Frontend source cleanup + workspace finalization

**Цель:** одна workspace‑manager, общие deps, нет дублей.

Эта работа разделена:

- **Phase 1F** — source duplicate cleanup in `runtime-dashboard/src/`;
  можно вести параллельно с остальной Wave 1.
- **Phase 4B** — workspace manager, lockfile alignment and build output
  relocation; стартует только после Phase 2A/2B и Phase 1F.

### 19.1 Workspace manager

Phase 4B:

- pnpm workspaces (`pnpm-workspace.yaml`) или turbo (`turbo.json`).
- Один `pnpm-lock.yaml` на root‑level.
- Команды `pnpm build`, `pnpm test`, `pnpm lint` работают cross‑package.

### 19.2 `lib/` ↔ `shared/lib/` merge

Phase 1F:

В `runtime-dashboard/src/`:

- `lib/{domain, hooks}/` → `shared/lib/{domain, hooks}/`.
- `lib/` удаляется.
- `i18n/{formatters, locales, messages, typography}/` →
  `shared/i18n/`.
- `app/state/` ↔ `app/providers/` — review на пересечение.

### 19.3 Build artifacts → `_build/`

Phase 4B:

Внутри `runtime-dashboard/`:
- `coverage/`, `dist/`, `playwright-report/`, `output/`,
  `storybook-static/`, `test-results/` — переезжают в
  root‑level `_build/apps/runtime-dashboard/...`.

### 19.4 packages/cli alignment

Если выбран monorepo (Phase 2A Вариант B), `packages/cli/` уже
оказывается под root `packages/`. Иначе — пересмотреть, должен ли он
быть под `frontend/` или отдельным пакетом.

**Acceptance:**

- 1 `pnpm-lock.yaml` (или 1 `bun.lockb`) во всём дереве.
- 0 дублирующихся `lib/` в `runtime-dashboard/src/`.
- Все frontend build outputs в `_build/`.

---

## 20. Phase 7 — Enforcement & closeout

**Цель:** перевести все report‑only gates в fail‑closed; закрыть план.

### 20.1 Gates → fail‑closed

| Gate                            | После фазы            | Введён в  |
| ------------------------------- | --------------------- | --------- |
| `empty_namespace_gate`          | fail‑closed           | Phase 0/1A |
| `loose_files_gate`              | fail‑closed           | Phase 0   |
| `name_collision_gate`           | fail‑closed           | Phase 0/1C |
| `pyproject_size_gate`           | fail‑closed (≤ 300)   | Phase 0/1B |
| `cache_dir_gate`                | fail‑closed           | Phase 2B   |
| `build_output_gate`             | fail‑closed           | Phase 2B   |
| `dynamic_imports_gate`          | fail‑closed           | Phase 3A   |
| `pickle_compat_gate`            | fail‑closed           | Phase 3A   |
| `public_surface_snapshot_gate`  | fail‑closed           | Phase 3A   |
| `import_cycles_gate`            | fail‑closed           | Phase 3A   |
| `import_time_regression_gate`   | fail‑closed (≤ 15%)   | Phase 3A   |
| `reexport_shim_shape_gate`      | fail‑closed (no `*`)  | Phase 3A   |

Все exception'ы — в `architecture/exceptions/` с owner+sunset.

### 20.2 Закрытие shims

Все `shims.toml` записи, созданные этим планом, должны быть
либо удалены (приоритетний путь если sunset прошёл), либо явно продлены (не желательно) через ADR. В
особенности — re‑export shims из Phase 5/6; их sunset = move_date +
2× max workflow lifetime (но не менее 60 дней). Sunset‑audit
автоматизирован.

### 20.3 Closeout report

`docs/plans/accepted/REPOSITORY_STRUCTURE_REMEDIATION_CLOSEOUT.md`:

- Финальный inventory delta vs Phase 0 baseline.
- Список retired shims (включая re‑export'ы из Phase 5/6).
- Список оставшихся exceptions с owner+sunset.
- Gate status (все fail‑closed или с exception).
- Финальные метрики: scientist/foundry file counts, import time,
  public surface diff summary, pickle compat coverage.
- Cloud full‑suite verdict для команды `pytest tests/unit
  tests/integration tests/property tests/contract tests/golden -q`:
  финальные passed/failed/skipped counts и список failures, если они
  останутся. Этот пункт заменяет локальный full‑suite baseline, который
  Phase 3A намеренно пометила как deferred из‑за thermal load.

### 20.4 Move plan to `accepted/`

Closeout completed:
`docs/plans/accepted/REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md`,
status=accepted, stability=stable. Closeout evidence:
`docs/plans/accepted/REPOSITORY_STRUCTURE_REMEDIATION_CLOSEOUT.md`.

---

## 21. Acceptance Criteria (план в целом)

1. Каждое из 7 наблюдений из секции 0 имеет ADR (0129..0145),
   machine‑readable контракт и тестируемый gate.
2. Repository topology содержит ровно один эфемерный umbrella
   (`_build/` + `_cache/`), а не 13 параллельных дир.
3. `polisyos/` workspace ↔ `policy-engine/` product‑root граница
   зафиксирована ADR‑0130 и реализована (collapse или monorepo).
4. `pyproject.toml` ≤ 300 строк; всё, что было `[tool.*]`, в отдельных
   файлах рядом.
5. `architecture/` — единственный governance‑источник; `baseline/`
   и root‑level `import_*`/`freeze_policy` удалены.
6. 0 пустых namespace placeholders в `foundry/methods/`; flat vs
   catalog решение зафиксировано ADR.
7. **Preflight (Phase 3A) сдан:** pickle compat test green, dynamic
   imports registry полностью покрывает grep‑inventory, public surface
   snapshot test green, codemod протестирован на experimental move,
   import graph baseline и import‑time baseline зафиксированы; cloud
   full‑suite baseline green на GCP VM `phase3a-fulltests-20260503`
   (10,975 total tests, 0 failures, 0 errors, 35 accepted skips), evidence:
   `gs://lex-1-494208-data/experiments/phase3a_fulltests/phase3a-fulltests-12core-20260504-rerun-20260504T111449Z/`.
8. `scientist/` (Phase 5) — ≤ 250 entries в верхнем уровне; ≤ 5 loose
   `.py` в корне; чистый façade; все unit + integration + property +
   golden тесты green; pickle compat test green; public surface diff =
   ровно запланированное; import‑time регрессия ≤ 15%.
9. `foundry/` (Phase 6) — то же самое для foundry: ≤ 250 файлов;
   ≤ 5 loose `.py`; façade; все тесты green; pickle compat green;
   schema diff = запланированное; import‑time регрессия ≤ 15%.
10. Phase 7 closeout содержит cloud full‑suite verdict для `pytest
    tests/unit tests/integration tests/property tests/contract
    tests/golden -q`; без этого closeout не сдан.
11. 0 версий в именах Python‑пакетов (`ddm_15_7` → `ddm`).
12. `synthetic_world` ↔ `foundry/agent_sim` resolved one way.
13. `calibration/` имеет один canonical home.
14. `berl/`, `packs/` явно классифицированы (legacy/sunset).
15. Каждое повторяющееся имя директории либо в
    `architecture/name_registry.toml`, либо переименовано.
16. `tools/` — одна ось (devx/ops/quality/research), 0 дублей.
17. `tests/` — один conftest на `unit/<pkg>/`, нет дублей между
    `unit/<pkg>/integration/` и `integration/<pkg>/`.
18. Frontend — одна `pnpm-lock.yaml`, нет дубля `lib/` ↔ `shared/lib/`,
    build outputs в `_build/`.
19. Все gates fail‑closed; exceptions явные, time‑bounded, с owner.
20. Closeout report записан; план в `accepted/`.

---

## 22. Risks & Mitigations

| Риск                                                                  | Митигация                                                                                                       |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Workspace boundary collapse сломает `.github/` workflows              | Phase 2A включает refresh всех workflow‑путей; CI green обязателен                                              |
| Codemod большого scope в Phase 5/6 даст regression                    | Phase 3A строит safety net (pickle compat, public surface snapshot, golden, dynamic imports gate); прицельный `git checkout -- <file>` для отката одного файла |
| Pickle / checkpoint десериализация ломается из‑за смены FQN           | Phase 3A фиксирует `tests/contract/test_pickle_compat.py`; sunset re‑export shim ≥ 2× max workflow lifetime     |
| Dynamic `importlib.import_module(...)` после move возвращает 404      | Phase 3A регистрирует все dynamic FQN в `architecture/dynamic_imports.toml`; gate fail‑closed до Phase 5        |
| Pydantic `$defs` ключи в OpenAPI меняются после переноса моделей      | Phase 3A включает schema diff baseline; Phase 5/6 acceptance — `schemas/runtime_api_v1.openapi.json` diff = ровно запланированное |
| Двойная регистрация JAX pytree / Pydantic после re‑export             | ADR‑0144 запрещает `from .new import *` в shim; Phase 3A grep‑аудит fail‑closed                                 |
| Скрытые циклические импорты вылезают наружу при façade pattern        | Phase 3A baseline import graph + `import_cycles_gate`; ADR‑0145 фиксирует допустимые lazy edges                 |
| `architecture/` merge сломает import‑linter ссылки                    | Phase 1B включает обновление всех абсолютных путей в `tools/quality/`                                           |
| pnpm workspace миграция сломает CI                                    | Phase 4B — единый scope, repro в CI до merge                                                                    |
| `production_data/` важен и не fixture                                 | Phase 1A требует ADR‑0137 с DVC/external решением до удаления                                                   |
| Long‑running shim‑sunset’ы накопят debt                               | Phase 7 enforcement автоматизирует sunset‑audit                                                                 |
| Import‑time регрессия после декомпозиции                              | Phase 3A фиксирует baseline `python -X importtime`; Phase 5/6 acceptance — регрессия ≤ 15%                      |

---

## 23. Effort & Sequencing

| Phase | Effort | Зависимости                 | Параллелится с                 | Merge rule                         |
| ----- | ------ | --------------------------- | ------------------------------ | ---------------------------------- |
| 0     | M      | —                           | —                              | First barrier                      |
| 1A    | M      | 0                           | 1B, 1C, 1D, 1E, 1F             | Wave 1                             |
| 1B    | M      | 0                           | 1A, 1C, 1D, 1E, 1F             | Wave 1                             |
| 1C    | S      | 0                           | 1A, 1B, 1D, 1E, 1F             | Wave 1; no source moves            |
| 1D    | M      | 0                           | 1A, 1B, 1C, 1E, 1F             | Wave 1; finish before 3A           |
| 1E    | M      | 0                           | 1A, 1B, 1C, 1D, 1F             | Wave 1; finish before 3A baseline  |
| 1F    | M      | 0                           | 1A, 1B, 1C, 1D, 1E             | Wave 1; source only                |
| 2A    | XL     | all Wave 1                  | —                              | Path barrier, singleton            |
| 2B    | M      | 2A                          | —                              | Path barrier, after workspace      |
| 3A    | M      | 1B, 1D, 1E, 2A, 2B          | 3B                             | Safety net; no scientist/foundry moves |
| 3B    | S      | 1C                          | 3A                             | Planning only, no source moves     |
| 4A    | L      | 3A, 3B                      | 4B                             | Backend package moves              |
| 4B    | L      | 1F, 2A, 2B                  | 4A                             | Frontend workspace/output          |
| 5     | L      | 3A, 4A                      | —                              | Scientist singleton                |
| 6     | L      | 3A, 4A, 5                   | —                              | Foundry after scientist            |
| 7     | M      | all                         | —                              | Final barrier                      |

Total: ~12–16 календарных недель при активной параллельной Wave 1 и
Wave 3. Critical path: Phase 0 → Wave 1 closeout → 2A → 2B → 3A →
4A → 5 → 6 → 7. Phase 5 and Phase 6 остаются последовательными, чтобы
переиспользовать safety net и codemod, отлаженные на scientist.

---

## 24. Companion ADRs (создаются в Phase 0 / 3A / 3B)

| ADR     | Тема                                                                  | Создаётся в  |
| ------- | --------------------------------------------------------------------- | ------------ |
| 0129    | Empty placeholder package policy                                       | Phase 0      |
| 0130    | Workspace boundary (collapse vs monorepo)                              | Phase 0      |
| 0131    | Build‑output and cache umbrella                                        | Phase 0      |
| 0132    | `architecture/` as single governance source                            | Phase 0      |
| 0133    | Top‑level package size budget and façade pattern                       | Phase 0      |
| 0134    | Cross‑package shared name registry                                     | Phase 0      |
| 0135    | Versioning out of package names                                        | Phase 0      |
| 0136    | foundry/methods flat vs catalog (companion к 0129)                     | Phase 0      |
| 0137    | Production data / fixtures classification                              | Phase 0      |
| 0138    | synthetic_world ↔ agent_sim merge direction                            | Phase 0 skeleton / 3B final |
| 0139    | Canonical home for `calibration/`                                      | Phase 0 skeleton / 3B final |
| 0140    | Pickle / checkpoint FQN compatibility contract                         | Phase 3A     |
| 0141    | Dynamic imports registry (`architecture/dynamic_imports.toml`)         | Phase 3A     |
| 0142    | Codemod tooling policy (libcst‑based `tools/devx/refactor/`)           | Phase 3A     |
| 0143    | Decomposition blueprint format (per‑package move map)                  | Phase 3A     |
| 0144    | Re‑export shim shape (`from .new import X`, без `import *`)            | Phase 3A     |
| 0145    | Lazy / forbidden‑cycle imports policy (`architecture/imports/lazy.toml`) | Phase 3A   |

---

## 25. Source bibliography

- `docs/plans/accepted/REPOSITORY_SOTA_PLAN.md` — родительская политика
- `docs/plans/accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md` — состояние gates
- `docs/reference/repository-topology.md` — публичная карта paths
- `architecture/topology.toml` — машинный контракт топологии
- `architecture/package_boundaries.toml` — машинный контракт boundaries
- `architecture/shims.toml` — реестр shim‑ов
- `src/polisyos/foundry/methods/catalog/MIGRATION_V2.md` — V2‑миграция methods
- Аудит‑отчёт 2026‑05‑03 (раздел 0 этого плана)
- Companion best‑in‑class планы (см. секцию вверху)
