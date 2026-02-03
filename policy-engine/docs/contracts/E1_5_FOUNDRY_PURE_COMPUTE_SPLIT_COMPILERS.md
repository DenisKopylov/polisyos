# E1.5 (Phase 5) — Foundry: purge зависимостей + split компиляторов (surface_compiler vs trinity_compiler)

**Repo snapshot date**: 2026-02-03  
**Scope**: `policy-engine/src/polisyos/foundry/*` + touchpoints в `core/contracts/*`, `core/compiler/*`, `ir/linker/*`, `scientist/*`, `tests/*`  
**Primary goal**: сделать Foundry **pure compute** ядром (CAS-in/CAS-out), удалить утечки верхних слоёв, и физически разделить компиляцию на:

- **Legacy**: `PolicySurfaceIR → ExecPlan` (surface compiler, frozen compatibility)
- **Canonical**: `TrinityBundle → ExecPlan` (trinity compiler, основной путь вперёд)

При этом снаружи Foundry остаётся **один фасад** `compile()/execute()` с выбором компилятора по типу входа (или флагу), не смешивая модели.

---

## 0) Цель фазы (что должно измениться “в ощущениях”)

После E1.5:

1) **Foundry = pure compute**:
   - входы: только **IR/Core контракты** и/или **CAS refs** (`ArtifactRef`, typed refs из `core.contracts.*`)
   - выходы: только **CAS артефакты** (через `FileSystemCAS.put_*`) + typed refs
   - Foundry **не знает** про Scientist (ни типами, ни импортами, ни governance-профилями).

2) **Компиляция политики разделена**:
   - `surface_compiler` обслуживает legacy `PolicySurfaceIR` (заморожен: только совместимость/bugfix)
   - `trinity_compiler` обслуживает Trinity (`ProblemFrame/PolicySpec/ModelSpec`), строится поверх `ir.linker.link_trinity()`.

3) **Один публичный входной API**:
   - `polisyos.foundry.compile.api.compile(request) -> CompileResult`
   - `polisyos.foundry.execute.api.execute(request) -> ExecuteResult`
   - выбор компилятора **по kind входного ref** (`ir.policy_surface` vs `ir.trinity_bundle`) или явному `input_kind`.

4) **“До зелёного” по зависимостям**:
   - import gate (`tools/lint_imports.py` + `import_policy.toml`) зелёный
   - внутри Foundry нет импортов `polisyos.scientist.*` и реализаций `polisyos.fabric.*` (контракты `core.contracts.fabric` разрешены).

---

## 1) Входные условия (что уже есть после E1.1–E1.4)

### 1.1 Import gate / Dependency-guard

Источник правды: `policy-engine/docs/adr/0004-architecture-boundaries-import-gate.md`, `policy-engine/import_policy.toml`, `policy-engine/tools/lint_imports.py`, тест `policy-engine/tests/test_arch_import_gate.py`.

Текущее правило: `foundry` может импортировать только `foundry|core|ir|common` (см. `import_policy.toml`).

### 1.2 Trinity и Linker уже существуют

- `polisyos.ir.trinity.TrinityBundle` (payload контракт)
- `polisyos.ir.linker.link_trinity()` + `LinkedTrinityBundle` + `LinkReport` (детерминированный, без I/O)
- legacy surface linker живёт в `polisyos.ir.linker.legacy_surface.link_policy()`

### 1.3 Core ports уже есть

Ключевые артефактные “порты” и refs, которые используются в E1.5:

- `polisyos.core.contracts.foundry`:
  - `ProgramGraphRef`, `ExecPlanRef`, `StateSnapshotRef`, `MetricsRef`, `ConstraintReportRef`
  - `SimulationResultRef` + envelope `SimulationResult` (введён в E1.4, но ещё не везде используется)
- `polisyos.core.contracts.trinity`:
  - `TrinityBundleRef` (kind=`ir.trinity_bundle`)
- `polisyos.core.contracts.compiler`:
  - `LinkReportRef` (kind=`compiler.link_report`)
  - `CompileReportRef` (kind=`compiler.compile_report`)
- Core registry plumbing:
  - `polisyos.core.registry.build_default_registry_bundle()` создаёт `core.registry_bundle`
  - `polisyos.core.registry.load_registry_bundle_content()` загружает typed registries из bundle

---

## 2) Текущее состояние репозитория (важное для E1.5)

### 2.1 Legacy компиляция (surface)

Файл: `policy-engine/src/polisyos/foundry/compiler.py`

- `put_policy_surface(store, policy) -> PolicySurfaceIRRef` кладёт `ir.policy_surface` в CAS.
- `compile_surface_policy(store, policy, mechanism_registry, slot_registry, merge_registry, ...) -> CompileArtifacts`
  - строит `ProgramGraph` (`foundry.program_graph`)
  - строит `ExecPlan` (`foundry.exec_plan`)
  - кладёт вспомогательные артефакты: `foundry.slot_layout`, `foundry.treasury_plan`

Текущий важный факт для split:

- `ProgramGraph.ir_ref` в core.contracts **типизирован как `PolicySurfaceIRRef`**, то есть Trinity-путь сейчас физически невозможен без изменения порта.

### 2.2 Выполнение (execute)

Файл: `policy-engine/src/polisyos/foundry/executor.py`

- `execute_program_graph(...) -> ExecuteArtifacts`:
  - читает `ProgramGraph`/`ExecPlan` из CAS
  - выполняет шаги, возвращает:
    - `foundry.state_delta` + `foundry.metrics`
    - (опционально) `foundry.constraint_report`
    - (опционально) `foundry.environment_manifest` (сейчас **capture_env=True по умолчанию**)

Текущий важный факт для Trinity:

- executor извлекает constraint values, загружая `PolicySurfaceIR` через `program_graph.ir_ref`.
  - для Trinity нужно расширить это место: распознавать `ir.trinity_bundle` и извлекать constraints из `ProblemFrame`.

### 2.3 Scientist сейчас вызывает legacy compiler напрямую

Файл: `policy-engine/src/polisyos/scientist/orchestrator/flow_nodes.py`

- делает `link_policy(...)` (legacy linker) + кладёт `compiler.link_report`
- затем вызывает `compile_surface_policy(...)` напрямую

Это точка миграции: в E1.5 Scientist должен вызывать **Foundry facade** (см. §8).

---

## 3) Non-goals (вне E1.5)

E1.5 **не делает**:

- Fabric World Graph / Doc/Claim pipelines / Lex/Scholar (это E2+).
- Унификацию “компонентной” расширяемости всех плагинов (это E3; skeleton уже есть в E1.4).
- Переписывание plugin-системы `polisyos.foundry.plugins` (она не является целевым компилятором ExecPlan).

E1.5 делает только то, что необходимо для:

- чистого compute-ядра Foundry,
- двух компиляторов,
- одного стабильного фасада compile/execute,
- миграции Scientist вызовов и тестового контура.

---

## 4) 5.2 Аудит: найти и классифицировать утечки зависимости / I/O

### 4.1 Итог скана зависимостей (imports)

На snapshot 2026-02-03 в `polisyos.foundry.*` **нет**:

- `import polisyos.scientist.*`
- `import polisyos.fabric.*`

Это соответствует import gate и является **инвариантом** E1.5: любые новые модули `foundry.compile/*` и `foundry.execute/*` обязаны сохранять это.

### 4.2 Прямой I/O внутри Foundry (нарушает “pure compute”, если считать границу по пакету)

Ниже перечислены места, где код внутри `polisyos.foundry.*` работает с файлами/подпроцессами/внешним миром вне CAS.

> Важно: часть этих мест — tooling/dev-only. E1.5 фиксирует правило: **compute-kernel Foundry** (compile/execute) не делает таких операций; tooling выносится или изолируется (см. §9).

#### 4.2.1 Таблица утечек и классификация замены

| Локация | Симптом | Тип утечки | Классификация замены | Нормативное решение E1.5 |
|---|---|---|---|---|
| `polisyos.foundry.calibration.preflight.fetch_targets()` | дергает `udf_engine.query()` / `fetcher(...)` | I/O (world/data plane) | **Оркестрация** (должна жить в Scientist/Fabric) | Вынести fetch в Scientist. Foundry получает `raw_targets` как input артефакт/параметр. |
| `polisyos.foundry.executor.execute_program_graph(..., capture_env=True)` | по умолчанию вызывает `capture_environment()` (FS, git, deps) | I/O (host env) | **Оркестрация/observability** (control plane) | По умолчанию `capture_env=False` в kernel API; env capture делает Scientist/RunContext и передаёт refs. |
| `polisyos.foundry.methods.artifacts` | читает исходники (`Path.open`) и вызывает `git` через `subprocess.run` | I/O + subprocess | **Нужно как контракт/metadata** | Сместить вычисление source fingerprints в Core (env manifest) или в build-time. Метод-артефакт должен ссылаться на уже зафиксированный artifact/ref, а не читать FS. |
| `polisyos.foundry.plugins.cli` | читает/пишет файлы результатов, создаёт директории | FS I/O | **Tooling** | Вынести CLI в `policy-engine/tools/` или `polisyos.runtime` (не в compute kernel). |
| `polisyos.foundry.agent_sim.*` | пишет конфиги/метрики/артефакты в run dir | FS I/O | **Tooling / demo** | Вынести в `polisyos.runtime`/`tools` или пометить как отдельный пакет (не часть compute kernel). |
| `polisyos.foundry.methods.testing.golden` | хранит “golden records” на FS | FS I/O | **Тестовая инфраструктура** | Перенести в `tests/` или `policy-engine/tools/` (не держать под `polisyos.foundry.*`). |

#### 4.2.2 Минимальный cut E1.5 (чтобы не раздувать фазу)

Для E1.5 достаточно:

1) **Сделать новые фасады compile/execute строго CAS-only** (см. §6–§8).
2) Зафиксировать **policy**: любые I/O tooling модули **не импортируются** из `polisyos.foundry.__init__` и не подтягиваются транзитивно compile/execute.
3) (Рекомендуемо) добавить unit-test “no-IO-in-kernel” на `polisyos/foundry/compile/*` и `polisyos/foundry/execute/*` (см. §11.7).

Полный вынос tooling из пакета Foundry можно выполнить отдельным PR/подфазой, не блокируя split компиляторов.

---

## 5) 5.3 Проектирование API Foundry (минимально стабильный “порт”)

### 5.3.1 Принцип “только refs и контракты”

Foundry фасад **не принимает**:

- “живые” объекты Scientist (state machine, governance profile, UDF engine, DB handle, и т.п.)

Foundry фасад **принимает только**:

- Pydantic модели из IR/Core (`polisyos.ir.*`, `polisyos.core.contracts.*`)
- CAS refs (`ArtifactRef` и typed refs)

### 5.3.2 Изменения в `polisyos.core.contracts.foundry` (обязательные для E1.5)

Файл: `policy-engine/src/polisyos/core/contracts/foundry.py`

#### A) Обобщить `ProgramGraph.ir_ref`

**Проблема:** сейчас `ProgramGraph.ir_ref: PolicySurfaceIRRef` блокирует Trinity путь.

**Решение E1.5:** заменить тип поля на базовый `ArtifactRef`:

- было: `ir_ref: PolicySurfaceIRRef`
- стало: `ir_ref: ArtifactRef`

Инварианты:

- `ir_ref.kind` MUST быть одним из:
  - `"ir.policy_surface"` (legacy)
  - `"ir.trinity_bundle"` (canonical)
- `ir_ref.media_type` SHOULD быть `"application/json"`

> Это изменение backward-compatible для существующих артефактов (payload без новых полей остаётся валидным).

#### B) Добавить compile/execute request/result envelopes

Добавить (или расширить) модели:

1) `CompileRequest`
2) `CompileResult`
3) `ExecuteRequest`
4) `ExecuteResult`

##### `CompileRequest` (нормативный минимум)

```python
class FoundryValidationFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strict_schema: bool = True
    strict_link: bool = True
    allow_extra_params: bool = False
    strict_conflict_check: bool = True
    # reserved for future:
    allow_legacy_units: bool = False


class FoundryCompileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")

    # exec-plan knobs (must be serializable)
    mode: Literal["dev", "perf", "audit"] = "dev"
    jit: bool = True
    max_steps: int | None = None
    nan_guard_enabled: bool = False

    # determinism (no env capture here)
    determinism_tier: str | None = None  # "strict_cpu"|"best_effort_gpu"|"nondeterministic"
    random_seed: int | None = None

    # optional compile-time budgeting (no floats)
    cost_budget_max_total_ms: int | None = None
    cost_budget_max_memory_mb: int | None = None
    cost_budget_max_compile_ms: int | None = None
    cost_budget_max_per_mechanism_ms: int | None = None

    # parameters for cost estimate (if budget enabled)
    estimate_n_agents: int | None = None
    estimate_time_steps: int | None = None


class CompileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")

    input_kind: Literal["auto", "surface", "trinity"] = "auto"
    policy_ref: ArtifactRef  # MUST be ir.policy_surface or ir.trinity_bundle

    registry_bundle_ref: ArtifactRef | None = None  # kind="core.registry_bundle"
    compile_config: FoundryCompileConfig = Field(default_factory=FoundryCompileConfig)
    validation_flags: FoundryValidationFlags = Field(default_factory=FoundryValidationFlags)

    notes: list[str] = Field(default_factory=list)
```

Нормативные правила:

- `CompileRequest` MUST быть сериализуемым в canonical JSON (`polisyos.core.canon.to_canonical_bytes`) без float.
- `input_kind="auto"` ⇒ компилятор выбирается по `policy_ref.kind`.
- `input_kind!="auto"` ⇒ `policy_ref.kind` MUST соответствовать input_kind (иначе ошибка валидации).
- `registry_bundle_ref`:
  - если задан ⇒ используется он
  - если не задан ⇒ компилятор пытается извлечь ref из входного IR:
    - surface: `PolicySurfaceIR.semantic.registry_bundle_ref`
    - trinity: `TrinityBundle.model_spec.registry_bundle_ref`

##### `CompileResult` (нормативный минимум)

```python
class DerivedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    ref: ArtifactRef


class CompileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    ok: bool

    exec_plan_ref: ExecPlanRef | None = None
    compile_report_ref: ArtifactRef  # kind="compiler.compile_report"

    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
```

Инварианты:

- `compile_report_ref` MUST быть всегда (даже если `ok=False`).
- `derived_refs` MUST содержать (когда `ok=True`):
  - `role="program_graph"` → `foundry.program_graph`
  - `role="exec_plan"` → `foundry.exec_plan` (можно дублировать exec_plan_ref, допустимо)
  - (опционально) `slot_layout`, `treasury_plan`, `link_report`, `linked_trinity_bundle`

##### `ExecuteRequest` (нормативный минимум)

```python
class FoundryExecConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    seed: int = 0
    mode: Literal["dev", "perf", "audit"] = "dev"
    max_steps: int | None = None
    deterministic: bool = True
    capture_env: bool = False  # explicit, default off


class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")

    exec_plan_ref: ExecPlanRef

    # input data: prefer Fabric DataSnapshotRef long-term; support StateSnapshotRef short-term
    data_snapshot_ref: ArtifactRef | None = None  # kind="fabric.data_snapshot" (preferred)
    state_snapshot_ref: StateSnapshotRef | None = None  # compat path

    registry_bundle_ref: ArtifactRef | None = None  # kind="core.registry_bundle"
    exec_config: FoundryExecConfig = Field(default_factory=FoundryExecConfig)
    notes: list[str] = Field(default_factory=list)
```

Нормативные правила:

- `execute()` MUST быть CAS-only (никаких DB/network).
- должен быть определён ровно один источник состояния:
  - `state_snapshot_ref` задан ⇒ используется он
  - иначе `data_snapshot_ref` задан ⇒ Foundry читает `core.contracts.fabric.DataSnapshot` и требует, чтобы `data_ref.kind == "foundry.state_snapshot"` (временно, до E2)
  - иначе ошибка.

##### `ExecuteResult` (нормативный минимум)

```python
class ExecuteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")
    ok: bool

    simulation_result_ref: SimulationResultRef | None = None
    derived_refs: list[DerivedArtifact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
```

Инварианты:

- при `ok=True` MUST вернуться `simulation_result_ref` (kind=`foundry.simulation_result`)
- `derived_refs` SHOULD включать:
  - `metrics`, `state_delta`, (опционально) `constraint_report`, `environment_manifest`

### 5.3.3 Изменения в `polisyos.core.contracts.compiler` (опционально, но рекомендуемо)

Файл: `policy-engine/src/polisyos/core/contracts/compiler.py`

Если хочется строгих типов:

- добавить typed `RegistryBundleRef` (kind=`core.registry_bundle`) **или** оставить `ArtifactRef`.

Не является блокером для E1.5, но упрощает ошибки на границе.

---

## 6) 5.4 Split компиляторов: физическая декомпозиция кода

### 6.1 Цель структуры

- Legacy и Canonical компиляторы физически разделены (разные файлы/модули).
- Общая точка входа (`compile.api`) выбирает реализацию.
- Старые entrypoints живут как thin wrappers и помечены deprecated.

### 6.2 Рекомендуемая структура модулей Foundry

Target (E1.5):

```
polisyos/foundry/
  compile/
    __init__.py
    api.py                 # facade compile(request) -> CompileResult
    surface_compiler.py    # legacy path
    trinity_compiler.py    # canonical path
    types.py               # internal types/helpers (not core.contracts)
    _io.py                 # internal CAS load/store helpers (optional)
    _graph.py              # internal graph builder shared by compilers (optional)

  execute/
    __init__.py
    api.py                 # facade execute(request) -> ExecuteResult

  legacy/
    __init__.py
    compiler.py            # deprecated wrappers around new facade
```

Переходное состояние (backward-compat):

- `polisyos.foundry.compiler` остаётся существовать, но превращается в thin wrapper:
  - `compile_surface_policy(...)` → формирует `CompileRequest` и вызывает `foundry.compile.api.compile`
  - `put_policy_surface(...)` остаётся (как helper), но помечается как legacy convenience

### 6.3 “Шлюз” между компиляторами (обязательный инвариант)

Оба компилятора обязаны выпускать один и тот же набор CAS-артефактов:

- `foundry.program_graph`
- `foundry.exec_plan`
- (опционально) `foundry.slot_layout`
- (опционально) `foundry.treasury_plan`
- `compiler.link_report` (если линковка выполняется внутри compile)
- `compiler.compile_report` (всегда)

И один и тот же базовый IR рантайма: `ExecPlan` + `ProgramGraph` из `polisyos.core.contracts.foundry`.

**Критично:** рантайм-исполнение по `ExecPlanRef` не должно требовать Scientist объектов (только CAS + registries bundle ref).

---

## 7) 5.5 surface_compiler: стабилизация legacy без расширения поверхности

### 7.1 Цель

- Сохранить поддержку существующих политик/тестов на `PolicySurfaceIR`.
- Зафиксировать “поверхность” legacy: не добавлять новые фичи в формат.
- Перевести внешний вызов на `CompileRequest`/`CompileResult`.

### 7.2 Поведение surface compiler (нормативно)

`polisyos.foundry.compile.surface_compiler.compile_surface(request, store) -> CompileResult`

Pipeline:

1) **Load policy**:
   - `policy = PolicySurfaceIR.model_validate(from_canonical_bytes(store.get_bytes(policy_ref)))`
2) **Resolve registry bundle** (см. §5.3.2):
   - `registry_bundle_ref = request.registry_bundle_ref or policy.semantic.registry_bundle_ref`
   - если нет ⇒ `ok=False`, compile_report с ошибкой `missing_registry_bundle`
3) **Load registries**:
   - `registry_content = load_registry_bundle_content(store, registry_bundle_ref)`
4) **Link legacy surface**:
   - `link_report = link_policy(policy, registry_content.mechanism_registry, slot_registry=..., units_registry=..., allow_extra_params=request.validation_flags.allow_extra_params, ...)`
   - сохранить `compiler.link_report` (через `core.compiler.report.put_link_report`)
   - если `strict_link=True` и `not link_report.ok` ⇒ `ok=False`, compile_report, выход без компиляции
5) **Compile graph** (без ссылок на Scientist):
   - переиспользовать текущую реализацию из `polisyos.foundry.compiler`:
     - build ProgramGraph nodes/edges
     - conflict check (CompileTimeConflictChecker)
     - cost estimate gating (если budget включён)
6) **Emit compile artifacts**:
   - `foundry.program_graph`
   - `foundry.exec_plan` (поля берутся из `request.compile_config`, environment_* остаётся `None`)
   - `foundry.slot_layout`, `foundry.treasury_plan` (если текущая логика сохраняется)
7) **Emit compile_report** (`compiler.compile_report`, всегда):
   - `ok`, `policy_ref`, `registry_bundle_ref`, `link_report_ref`, `program_graph_ref`, `exec_plan_ref`, `slot_layout_ref`, `treasury_plan_ref`

### 7.3 Запреты и совместимость

- surface_compiler НЕ должен импортировать Trinity модели.
- Любая новая логика доменной компиляции должна идти в `trinity_compiler`, а не в surface.
- Если в legacy-коде есть хардкоды registries/механизмов:
  - либо переводим на `registry_bundle_ref`
  - либо выносим в `polisyos.foundry.legacy/*` и явно помечаем deprecated.

### 7.4 Backward-compat wrappers

Сохранить существующие публичные функции как thin wrappers:

- `polisyos.foundry.compiler.compile_surface_policy(...)`:
  - допустимо оставить старую сигнатуру (для тестов/временной совместимости)
  - внутри:
    - (опционально) собрать `core.registry_bundle` из переданных registries (если bundle_ref не передан)
    - `policy_ref = put_policy_surface(...)` если нужно
    - сформировать `CompileRequest(input_kind="surface", policy_ref=..., registry_bundle_ref=...)`
    - вызвать `foundry.compile.api.compile(request)`
    - вернуть legacy `CompileArtifacts` либо переехать на `CompileResult` (предпочтительнее — постепенно)

Депрекейшн:

- добавить `warnings.warn(..., DeprecationWarning)` при импорте/вызове legacy entrypoints, но не ломать тесты одномоментно.

---

## 8) 5.6 trinity_compiler: канонический путь Trinity → ExecPlan

### 8.1 Цель

- Сделать Trinity компиляцию first-class: `TrinityBundleRef` → `ProgramGraph/ExecPlan`.
- Использовать IR linker `link_trinity()` как единственный источник “сопоставления с registries”.
- Не вводить зависимостей на Scientist и не использовать legacy surface как промежуточный формат на границе.

### 8.2 Входы

`CompileRequest` с:

- `policy_ref.kind == "ir.trinity_bundle"` (payload = `polisyos.ir.trinity.TrinityBundle`)
- `registry_bundle_ref`:
  - из request **или** из `bundle.model_spec.registry_bundle_ref`

Опционально (не блокер E1.5, но полезно):

- сохранять `LinkedTrinityBundle` как derived artifact (kind `compiler.linked_trinity_bundle`)

### 8.3 Pipeline внутри trinity compiler (нормативно)

`polisyos.foundry.compile.trinity_compiler.compile_trinity(request, store) -> CompileResult`

#### Step 0: load inputs

1) `bundle = TrinityBundle.model_validate(from_canonical_bytes(store.get_bytes(policy_ref)))`
2) `registry_bundle_ref = resolve_registry_bundle_ref(bundle, request)`
3) `registry_content = load_registry_bundle_content(store, registry_bundle_ref)`

#### Step 1: validate_structural (schema-level)

Минимально:

- Pydantic validation (уже происходит при `.model_validate`)
- дополнительные проверки, которые не требуют “мира”, только contracts:
  - `bundle.policy_spec.interventions` ids unique (уже валидатор в PolicySpec)
  - `bundle.problem_frame.hard_constraints/soft_constraints` ids unique (уже валидатор)

#### Step 2: resolve_symbols (linking)

1) Собрать IR-level `RegistryBundle` из загруженных registries:

- `mechanisms = registry_content.mechanism_registry`
- `slots = registry_content.slot_registry`
- `merge_rules = registry_content.merge_registry`
- `constraints = registry_content.constraint_registry`
- `selector_fields = registry_content.selector_field_registry`
- `units = registry_content.units_registry`
- `metrics = registry_content.metric_registry` (если есть)

2) Вызвать:

`linked_bundle, link_report = link_trinity(bundle, registries, allow_extra_params=request.validation_flags.allow_extra_params, strict=request.validation_flags.strict_link)`

3) Persist link_report:

- `link_report_ref = put_link_report(store, link_report, inputs=[policy_ref, registry_bundle_ref])`

4) Если `strict_link=True` и `not link_report.ok` ⇒ `ok=False`, emit compile_report и return.

Опционально:

- Persist `linked_bundle` как `compiler.linked_trinity_bundle` (schema `polisyos.ir.LinkedTrinityBundle`, version `linked_bundle.schema_version`) и добавить в `derived_refs`.

#### Step 3: build_program_graph (deterministic)

Цель — тот же `ProgramGraph` контракт, что и в legacy, но:

- `ProgramGraph.ir_ref = policy_ref` (kind=`ir.trinity_bundle`)

Маппинг interventions:

- для каждого `PolicySpec.interventions[i]`:
  - persist `ir.intervention_payload` (как сейчас в surface compiler): schedule/target/params/priority/notes
  - создать `op.make_mask` (selector из intervention.target)
  - создать `op.apply_mechanism`:
    - `mechanism_type = intervention.kind`
    - `params_ref = intervention_payload_ref`
    - `inputs/outputs` брать из `linked_bundle.bindings.interventions[i].reads_slots/writes_slots`

Edges:

- `make_mask → apply_mechanism (depends_on)`
- slot dependency edges: writer → reader, если writer.outputs ∩ reader.inputs ≠ ∅

Op nodes:

- `op.merge_state`
- `op.check_constraints`:
  - `constraint_ids`: собрать из `bundle.problem_frame.hard_constraints + soft_constraints`
  - (в E1.5 можно сохранять только ids; семантика “hard/soft” остаётся в IR, enforcement — позже)

#### Step 4: build_exec_plan

Одинаково для обоих компиляторов:

- `order = topological_sort(program_graph)`
- `exec_plan = ExecPlan(program_ref=..., order=..., mode=request.compile_config.mode, jit=request.compile_config.jit, max_steps=request.compile_config.max_steps, nan_guard_enabled=request.compile_config.nan_guard_enabled, determinism_tier=request.compile_config.determinism_tier, random_seed=request.compile_config.random_seed)`
- **не** заполнять `environment_ref/environment_fingerprint` на compile (env capture переносится в execute/control plane)

#### Step 5: emit artifacts

Persist:

- `foundry.program_graph` (inputs: policy_ref, registry_bundle_ref, intervention_payloads, link_report_ref)
- `foundry.exec_plan` (input: program_graph_ref)
- `foundry.slot_layout`, `foundry.treasury_plan` (если сохраняем parity с legacy)
- `compiler.compile_report` (всегда)

### 8.4 Изменение рантайма для Trinity (обязательная часть E1.5)

Файл: `policy-engine/src/polisyos/foundry/executor.py`

Задача: место, где executor загружает constraints из `PolicySurfaceIR`, должно стать полиморфным:

- если `program_graph.ir_ref.kind == "ir.policy_surface"` ⇒ как сейчас
- если `program_graph.ir_ref.kind == "ir.trinity_bundle"` ⇒
  - загрузить TrinityBundle
  - построить `constraint_values = {constraint.constraint_id: constraint.value}` из `ProblemFrame.hard_constraints/soft_constraints`

Инвариант:

- executor не импортирует Scientist
- executor не импортирует Fabric реализации

---

## 9) 5.7 Pure compute правила (жёстко)

### 9.1 Запреты внутри Foundry compute-kernel (compile/execute)

Запрещено в модулях:

- `polisyos.foundry.compile.*`
- `polisyos.foundry.execute.*`
- и в transitively-imported ими модулях

**Запреты:**

1) `import polisyos.scientist.*`
2) `import polisyos.fabric.*` (кроме `polisyos.core.contracts.fabric` — contracts разрешены)
3) Любые прямые I/O вне CAS:
   - `open()` на произвольных путях
   - чтение/запись файлов с `Path.read_text/write_text/open`
   - `subprocess.run` (git, pip, etc)
   - сетевые вызовы
   - прямой DuckDB/GraphStore доступ
4) Любые записи в FactLog / world state (это Fabric plane).

### 9.2 Разрешено

1) CAS I/O через `polisyos.core.artifacts.store.FileSystemCAS`
2) Канонизация через `polisyos.core.canon.*`
3) Валидация IR через `polisyos.ir.*` (linker, models)
4) Выпуск trace/metrics как **CAS артефактов** (если это делается внутри execute и не требует внешнего I/O).

### 9.3 Практическая стратегия (E1.5)

Чтобы не выносить всю demo/tooling подсистему одномоментно:

- compute-kernel держим в новых пакетах `foundry/compile` и `foundry/execute` и следим, чтобы они не импортировали tooling
- существующие I/O-heavy модули (`foundry.agent_sim`, `foundry.plugins`, `foundry.methods.testing`) не должны импортироваться из compile/execute
- (рекомендуемо) добавить тест-скан, что в `foundry/compile` и `foundry/execute` нет `open(` / `subprocess.run` (см. §11.7)

---

## 10) 5.8 Миграция внешних вызовов Foundry + фасад API

### 10.1 Foundry facade: compile

Файл: `policy-engine/src/polisyos/foundry/compile/api.py`

Нормативная сигнатура:

```python
def compile(store: FileSystemCAS, request: CompileRequest) -> CompileResult:
    ...
```

Поведение:

- валидирует request (schema_version, input_kind/policy_ref.kind)
- выбирает компилятор:
  - `surface` если `policy_ref.kind == "ir.policy_surface"`
  - `trinity` если `policy_ref.kind == "ir.trinity_bundle"`
- гарантирует выпуск `compiler.compile_report` всегда

Критично:

- `compile()` НЕ принимает `PolicySurfaceIR`/`TrinityBundle` напрямую как “живые объекты” в публичном API;
  - для тестов можно иметь internal helper `compile_from_payload(...)`, но он не считается портом.

### 10.2 Foundry facade: execute

Файл: `policy-engine/src/polisyos/foundry/execute/api.py`

Нормативная сигнатура:

```python
def execute(store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult:
    ...
```

Поведение:

- загружает `ExecPlan` и `ProgramGraph` из CAS
- резолвит состояние:
  - `state_snapshot_ref` (прямо)
  - или `data_snapshot_ref` → `DataSnapshot.data_ref` (требуется `foundry.state_snapshot`)
- загружает registries по `registry_bundle_ref` (или из program_graph inputs при желании, но предпочтительно явно)
- вызывает существующий `execute_program_graph(...)`
- формирует `SimulationResult` envelope (`core.contracts.foundry.SimulationResult`) и сохраняет как `foundry.simulation_result`

Инвариант: `capture_env=False` по умолчанию и является **явным** флагом в request.

### 10.3 Миграция Scientist: замена прямых вызовов компилятора

Файл: `policy-engine/src/polisyos/scientist/orchestrator/flow_nodes.py`

Текущее:

- `link_policy(...)`
- `compile_surface_policy(...)`

Целевое (E1.5):

- `compile_result = foundry.compile.api.compile(store, CompileRequest(...))`
- дальнейшие шаги опираются на refs из `compile_result`:
  - `compile_report_ref`
  - `exec_plan_ref` (если ok)
  - `derived_refs` (program_graph, slot_layout, treasury_plan)

Рекомендация:

- сохранить прежние runtime logs (`log_artifact(...)`) но теперь логировать:
  - `compile_report_ref`
  - `link_report_ref` (если он содержится внутри compile_report)
  - `exec_plan_ref`

### 10.4 Миграция Scientist: выполнение через execute facade (минимум)

`scientist/compute/runner.py` сейчас вызывает `execute_program_graph` напрямую.

E1.5 может сделать один из вариантов (выбрать один и закрепить):

**Вариант A (минимум вмешательств):** оставить runner как есть, но добавить “официальный” facade `foundry.execute.api.execute` и постепенно перевести вызовы.

**Вариант B (сразу порт):** runner строит `ExecuteRequest` и вызывает `foundry.execute.api.execute`, получает `SimulationResultRef`, а затем (при необходимости) отдельно загружает итоговое состояние.

Для E1.5 достаточно варианта A + smoke test на execute facade.

---

## 11) 5.9 Тестирование и валидация (обязательная часть фазы)

### 11.1 Dependency gate (уже есть)

- `policy-engine/tests/test_arch_import_gate.py` должен оставаться зелёным.
- В рамках E1.5 добавить регрессию: новые модули `foundry/compile/*` и `foundry/execute/*` не должны нарушать `import_policy.toml`.

### 11.2 Unit tests: surface_compiler

Добавить/обновить тесты в `policy-engine/tests/foundry/`:

- перевести существующие тесты компиляции на новый фасад (или оставить legacy wrapper до миграции):
  - `test_program_graph_ops.py`
  - `test_constraints_executor.py`
  - `test_patch_executor.py`

Минимальный новый тест:

- `compile(request)` с `input_kind="surface"`:
  - поднимает `FileSystemCAS(tmp_path)`
  - строит `core.registry_bundle` (`build_default_registry_bundle`)
  - кладёт `PolicySurfaceIR` в CAS (`put_policy_surface`)
  - вызывает facade compile
  - проверяет:
    - `result.ok is True`
    - `result.exec_plan_ref.kind == "foundry.exec_plan"`
    - среди `derived_refs` есть `program_graph`

### 11.3 Unit tests: trinity_compiler

Новый тест (минимальный Trinity fixture):

- собрать `TrinityBundle`:
  - `ProblemFrame(domain=...)` без сложных целей
  - `PolicySpec` с 1 intervention (`income_tax`/`tax_subsidy`)
  - `ModelSpec(data_snapshot_ref=<sha256 stub>, registry_bundle_ref=<bundle_ref.artifact_id>)`
- persist `ir.trinity_bundle` в CAS (kind=`ir.trinity_bundle`, schema=`polisyos.ir.TrinityBundle`)
- вызвать compile facade (`input_kind="trinity"` или auto)
- проверить:
  - `ok=True`
  - `ProgramGraph.ir_ref.kind == "ir.trinity_bundle"` (т.е. не смешали модели)
  - `ExecPlanRef` существует

### 11.4 Determinism test: одинаковый вход → одинаковый ArtifactID

Нормативный тест:

- дважды вызвать compile с одинаковыми `policy_ref`, `registry_bundle_ref`, `compile_config`, `validation_flags`
- ожидание:
  - `exec_plan_ref.artifact_id` совпадает
  - `program_graph_ref.artifact_id` совпадает

Чтобы тест был корректным:

- compile не должен включать env capture / timestamps в payload.

### 11.5 Contract tests: canonical JSON (без float)

Добавить в `policy-engine/tests/contract/`:

- `to_canonical_bytes(CompileRequest(...))` не выбрасывает `CanonViolation`
- `to_canonical_bytes(CompileResult(...))` не выбрасывает `CanonViolation`
- аналогично для `ExecuteRequest/ExecuteResult`

### 11.6 Smoke execute (минимальный end-to-end)

Цель: доказать, что Foundry может создать `SimulationResultRef` без зависимости на Scientist/Fabric.

Smoke test:

1) скомпилировать минимальную политику (surface или trinity) в `ExecPlanRef`
2) создать `StateSnapshotRef`:
   - собрать минимальный `GlobalState` fixture (как в текущих foundry tests)
   - `put_state_snapshot(store, state=..., step=0)`
3) вызвать `foundry.execute.api.execute` с `ExecuteRequest(state_snapshot_ref=..., exec_plan_ref=..., registry_bundle_ref=...)`
4) проверить:
   - `ok=True`
   - вернулся `SimulationResultRef` (kind=`foundry.simulation_result`)

### 11.7 (Рекомендуемо) “no I/O in kernel” тест

Простой тест-скан (как safety net):

- пройтись по `.py` файлам в `polisyos/foundry/compile/` и `polisyos/foundry/execute/`
- убедиться, что нет подстрок:
  - `"open("`
  - `"subprocess.run"`
  - `"requests."`

Это не заменяет архитектурную дисциплину, но ловит регрессии.

---

## 12) 5.10 Definition of Done (E1.5)

Фаза считается завершённой, когда:

1) В `polisyos.foundry` нет импортов `polisyos.scientist.*`.
2) Реализованы два компилятора:
   - `polisyos.foundry.compile.surface_compiler`
   - `polisyos.foundry.compile.trinity_compiler`
3) Существует один фасад:
   - `polisyos.foundry.compile.api.compile(request) -> CompileResult`
   - `polisyos.foundry.execute.api.execute(request) -> ExecuteResult`
4) `ProgramGraph.ir_ref` поддерживает `ir.policy_surface` и `ir.trinity_bundle` (не смешивая модели).
5) `compiler.compile_report` всегда выпускается, ошибки/предупреждения фиксируются как артефакты.
6) Тесты:
   - import gate зелёный
   - unit tests для surface и trinity компиляции зелёные
   - determinism test зелёный
   - smoke execute зелёный
