# E1.4 (Phase 4) — Core ABI: CAS/Canon/Refs + Contract Ports + Component Skeleton

**Repo snapshot date**: 2026-02-03  
**Scope**: `policy-engine/src/polisyos/core/*` + minimal “touchpoints” в `fabric/`, `foundry/`, `scientist/`, `runtime/` для переподключения импортов.  
**Primary goal**: сделать `polisyos.core` единым инфраструктурным ядром (CAS + канонизация + manifests + run/trace/observability + стабильные контракты‑порты на стыках модулей) **без утечки логики Scientist**.

---

## 0) Invariants (что должно быть истинно после фазы)

### 0.1 Архитектурные границы (import gate — source of truth)

Источник правды: ADR `policy-engine/docs/adr/0004-architecture-boundaries-import-gate.md` + `policy-engine/import_policy.toml` + `policy-engine/tools/lint/lint_imports.py`.

**Критично для E1.4:**

- `polisyos.ir.*` **не импортирует** `polisyos.core.*` (IR остаётся нулевой зависимостью).
- `polisyos.core.*` **может импортировать** `polisyos.ir.*`, но **не импортирует** `polisyos.scientist.*` (никаких циклов снизу‑вверх).
- Любое “стыкование модулей” (Scientist↔Fabric↔Foundry↔Lex↔Scholar) проходит **через**:
  - IR‑контракты (`polisyos.ir.*`) для “что такое данные” и
  - Core‑контракты (`polisyos.core.contracts.*`) для “как передавать артефакты/refs/порты”.

### 0.2 Reproducibility by construction

Любой артефакт, предназначенный для воспроизводимости, обязан:

1) иметь **канонический** байтовый payload (или явно помеченный режим канонизации),  
2) иметь `ArtifactManifest` с `schema` + `inputs` + (по возможности) `producer`/`env`,  
3) быть адресуемым через `ArtifactID` (`sha256:<hex64>`),  
4) передаваться между слоями по **типизированным refs** (см. `polisyos.core.contracts.*`).

### 0.3 Contracts are ports, not implementations

Файлы в `polisyos.core.contracts.*` содержат **только**:

- Pydantic модели (envelopes / refs / “тонкие” DTO),
- `Protocol`/`ABC` интерфейсы (например, `RuleBackend`),
- очень лёгкую валидацию (`@model_validator`) без IO и без вызова бизнес‑логики.

Запрещено:

- импортировать конкретные реализации backend’ов, движков, планировщиков и т.п.,
- импортировать тяжёлые зависимости (LLM clients, DB clients, network),
- делать side‑effects при импорте.

---

## 1) Non-goals (явно вне фазы)

Эта фаза **не** реализует:

- Fabric World Graph / claim/doc pipeline / Lex corpus storage (это E2+).
- Scholar/Lex как подсистемы (их реализация — E2+), но **контракты‑порты** для них появляются уже сейчас.
- Полноценный “расширение = пакет” marketplace (E3). В E1.4 — только минимальный скелет component model.
- Переписывание существующих discovery/registry систем (connectors/methods/plugins) — только подготовка к унификации.

---

## 2) Current repository state (что уже есть)

### 2.1 Core: CAS + канонизация + manifests

Уже реализовано (и является фундаментом E1.4):

- Канонизация: `polisyos.core.canon.canon_json`  
  - `CanonSpec` (по умолчанию `forbid_floats=True`)  
  - `to_canonical_bytes()` поддерживает `datetime/date/Decimal/bytes` и при необходимости **детерминированно** кодирует float как tagged object.
- CAS: `polisyos.core.artifacts.store.FileSystemCAS`  
  - `put_bytes()` и `put_json()` пишут `.blob` + `.manifest.json` под тем же `ArtifactID`  
  - хранит `inputs`, `schema`, `producer`, `env`.
- Manifests: `polisyos.core.artifacts.manifest.ArtifactManifest`  
  - минимальная provenance‑цепочка через `inputs: list[InputRef]`.

### 2.2 Core: run/trace/observability

Уже реализовано:

- `polisyos.core.run.context.RunContext`  
  - пишет `trace.jsonl` (в run dir)  
  - на `finalize()` сохраняет trace как CAS‑артефакт `core.trace.jsonl` и сохраняет `core.run_manifest`.
- `polisyos.core.trace.*`  
  - `TraceRecord` и `JsonlTraceSink` (не каноническое, run‑специфическое).
- `polisyos.core.observability.*`  
  - есть каркас OTel/metrics; в E1.4 важно **согласовать** атрибуты/идентификаторы и не тянуть scientist.

### 2.3 Core: contracts layer уже есть, но требует доведения до “портов”

Сейчас существует `polisyos.core.contracts`:

```
core/contracts/
  compiler.py
  fabric.py
  foundry.py
  legal.py
  scientist.py
  trinity.py
```

**Проблемы/дыры относительно целевого E1.4:**

1) Нет портов `lex.py` и `scholar.py` (нужно добавить сейчас как ABI‑границы).
2) `core/contracts/scientist.py` содержит “свой” `ArtifactRef` (не совместимый с `core.artifacts.manifest.ArtifactRef`) — это размывает типизацию и вводит 2 параллельных модели refs.
3) `core/contracts/legal.py` по смыслу уже является “Lex port”, но имя и наполнение не совпадают с целевым набором (`LegalContext`, `LegalReportRef`, `ChangeProposalRef`).

### 2.4 Import gate уже существует и проходит

Скрипт `policy-engine/tools/lint/lint_imports.py` по `import_policy.toml` (v1):

- **violations: none** (core/ir/foundry не импортируют scientist)  
- cycles присутствуют на уровне пакетов (`polisyos.fabric`↔`polisyos.fabric.udf`, `polisyos.scientist`↔subpackages). Циклы **не** цель E1.4, но должны быть учтены при расширении contracts/components (не добавлять новые).

---

## 3) Target after E1.4 (что именно “появляется”)

### 3.1 Единственный stable port layer: `polisyos.core.contracts.*`

Целевой набор портов E1.4 (минимально‑достаточный для стыков):

- `trinity.py` — refs + `TrinityBundle` envelope
- `fabric.py` — DataView/DataSnapshot requests+responses (refs)
- `foundry.py` — ExecPlan/ExecConfig/SimulationResult (refs + envelopes)
- `compiler.py` — Compile/Link reports (refs)
- `lex.py` — LegalContext/LegalReportRef/ChangeProposalRef + backend protocol (RuleBackend)
- `scholar.py` — ResearchIntent/KnowledgeBundleRef envelopes (refs)
- `scientist.py` — ExperimentStateRef/DecisionPacketRef (refs only; без логики)

**Правило**: contracts‑модули не импортируют реализации и не создают dependency cycles.

### 3.2 Canon/manifest/run/trace стандартизированы так, чтобы все слои могли ими пользоваться

Foundry/Fabric/Scholar/Lex должны уметь:

- писать артефакты в CAS (через `FileSystemCAS`)
- заполнять manifests (`schema`, `inputs`, `producer`, `env`)
- пользоваться `RunContext`/trace **без** импорта scientist
- обмениваться результатами по `core.contracts.*` refs.

### 3.3 Component model skeleton в Core (подготовка E3)

Добавляется `polisyos.core.components.*`:

- `ComponentId` (`namespace.name@semver`)
- `ComponentMetadata` (domains, jurisdictions, tags, capabilities)
- `Capabilities` enum/flag
- `Registry` + conflict policy
- `Discovery` (entry_points + dev scan)

На E1.4 **не требуется** переподключать существующие подсистемы (connectors/methods) к core/components — но ID/metadata формат фиксируется уже сейчас.

---

## 4) Work 4.1 — Fix “как не надо” №2 (Legal port не тянет Scientist)

### 4.1.1 Симптом, который запрещаем навсегда

Запрещённый паттерн:

- `core/contracts/legal.py` (или любой core‑модуль) импортирует `RuleBackend`/ASTPolicy/ValidationProfile из `polisyos.scientist.*`.

Причина:

- Core перестаёт быть нижним слоем и получает знание о control‑plane.

### 4.1.2 Целевое решение (нормативное)

**Решение E1.4:** переносим “Legal port” в `polisyos.core.contracts.lex` и делаем его единственным “официальным” местом для legal интерфейсов.

- `core/contracts/lex.py` содержит:
  - `IssueSeverity`, `ComplianceIssue`
  - `RuleBackend` (`Protocol`)
  - `LegalContext` (envelope входов)
  - `LegalReportRef`, `ChangeProposalRef` (typed refs)
  - (опционально) `LegalReport`/`ChangeProposal` envelopes как DTO (без логики)
- `core/contracts/legal.py` становится:
  - deprecated shim: `from .lex import *` (реэкспорт) на 1 релизный цикл
  - комментарий “use core.contracts.lex”

**Почему так, а не “оставить legal.py”?**

- В целевой архитектуре “Lex” — самостоятельный доменный сервис поверх Fabric, поэтому `lex.py` как port более точен.
- Мы сохраняем backward‑compat через реэкспорт, чтобы не ломать Scientist/Governance сразу.

### 4.1.3 Contract: `RuleBackend`

Нормативная сигнатура (как минимум):

```python
@runtime_checkable
class RuleBackend(Protocol):
    @property
    def backend_id(self) -> str: ...

    def evaluate(self, norm_pack: NormPack, context: dict) -> list[ComplianceIssue]: ...
```

**Invariants:**

- backend **stateless** (повторный вызов при тех же входах не зависит от прошлого вызова).
- backend **не пишет** в внешние системы сам по себе (любая запись — через вызывающий слой).
- `ComplianceIssue.pass_id` устанавливается вызывающим pass’ом (или фиксируется на “legal” — выбрать и закрепить 1 правило; предпочтительнее: pass_id задаёт pass, backend отдаёт issues без знания pipeline).

### 4.1.4 Contract: `LegalContext`

Цель: сделать вход Lex‑проверки типизированным и унифицированным, но не привязанным к реализации.

**Минимальный состав для E1.4:**

- `trinity: TrinityBundle` или refs на Trinity (ProblemFrameRef/PolicySpecRef/ModelSpecRef)
- `fabric_results: list[FabricResultRef] | None`
- `foundry: { exec_plan_ref, simulation_result_ref } | None`
- `jurisdiction: str`
- `as_of_date: str | None` (ISO)
- `norm_pack_ref: ArtifactRef | None` (если norms уже собраны как артефакт) **или** `norm_pack: NormPack | None`

Важно: `LegalContext` **не** должен встраивать огромные payloads (таблицы, тексты). Только refs.

### 4.1.5 Выходы Lex port (минимум)

- `LegalReportRef`:
  - `kind="lex.legal_report"`
  - `media_type="application/json"`
- `ChangeProposalRef` (optional):
  - `kind="lex.change_proposal"`
  - `media_type="application/json"`

Схемы (`SchemaInfo.name/version`) фиксируются в реализации Lex (E2), но refs вводим уже сейчас.

### 4.1.6 DoD для 4.1

- `core/contracts/lex.py` существует и экспортируется в `core/contracts/__init__.py`.
- `core/contracts/legal.py` либо переименован, либо стал реэкспортом (без зависимости на scientist).
- `tools/lint/lint_imports.py` не показывает нарушений.

---

## 5) Work 4.2 — Canonicalization + manifests + refs: reproducibility by construction

### 5.2.1 Canonical JSON ABI (polisyos.canon.json)

**Source of truth**: `polisyos.core.canon.canon_json`.

#### 5.2.1.1 Правила кодирования (normative)

- `dict`:
  - ключи только `str`
  - `sort_keys=True`
- `datetime`:
  - нормализуется в UTC
  - сериализуется как `{"_type":"datetime","iso_utc":"...Z"}`
- `date`:
  - `{"_type":"date","iso":"YYYY-MM-DD"}`
- `Decimal`:
  - `{"_type":"decimal","value":"<decimal-as-string>"}`
- `bytes`:
  - `{"_type":"bytes","encoding":"base64","data":"..."}`
- `float`:
  - **по умолчанию запрещён**
  - если `CanonSpec.forbid_floats=False`, сериализуется как `{"_type":"float","repr":"<.17g>"}` (детерминированно)

#### 5.2.1.2 CanonSpec и “сигнал в manifest”

Проблема текущего состояния:

- `ArtifactManifest.canon` фиксирует только `{name, version}` и **не отражает параметры** (например, `forbid_floats`).

**Решение E1.4 (спецификация):**

Расширить `CanonInfo` так, чтобы manifest **однозначно описывал** режим канонизации.

Минимальный вариант (рекомендуемый):

```python
class CanonInfo(BaseModel):
    name: str
    version: str
    forbid_floats: bool = True
    forbid_nan_inf: bool = True
    sort_keys: bool = True
    separators: tuple[str, str] = (",", ":")
    ensure_ascii: bool = False
```

Альтернатива (если не хотим расширять manifest схему): `canon_params_hash` + `canon_params_json`.

**Требование:** любая запись `put_json(..., canon_spec=...)` должна корректно отражаться в manifest.

### 5.2.2 Manifest inputs/derivation (нормативный минимум)

#### 5.2.2.1 InputRef

`InputRef` остаётся минимальным:

- `artifact_id`
- `role` (строковый идентификатор роли)

Но E1.4 фиксирует **общий словарь roles** для ключевых артефактов, чтобы цепочки derivation были читаемыми:

- `registry_bundle`
- `problem_frame` / `policy_spec` / `model_spec`
- `data_view_request` / `query_plan` / `data_snapshot`
- `program_graph` / `exec_plan` / `exec_config`
- `state_snapshot` / `state_delta`
- `metrics`
- `environment_manifest`
- `trace`
- `evidence_bundle`

#### 5.2.2.2 ProducerInfo и связь с component model

E1.4 фиксирует правило:

- `ProducerInfo.component` должен быть `ComponentId` (см. §6)
- `ProducerInfo.version` соответствует `ComponentId.semver` (или дублирует его)
- `ProducerInfo.git` опционален, но если присутствует — должен быть истинным (commit + dirty)

### 5.2.3 Typed refs: единый базовый класс

Нормативное правило:

- **единственный** базовый класс refs на уровне core — `polisyos.core.artifacts.manifest.ArtifactRef`.
- Любой `*Ref` в `polisyos.core.contracts.*` должен:
  - наследоваться от `ArtifactRef`
  - фиксировать `kind` и `media_type` через `Literal[...]`
  - (опционально) добавлять denormalized поля (только если они вычисляются из payload детерминированно).

Это устраняет текущую “двойную реальность” refs (особенно в `core/contracts/scientist.py`).

### 5.2.4 RunContext / Trace / Metrics (унификация)

E1.4 фиксирует “трёхслойную” модель наблюдаемости:

1) **Trace (run timeline)** — JSONL артефакт `core.trace.jsonl` (не обязан быть каноническим; является аудит‑логом).
2) **Metrics (числовые результаты)** — артефакты `foundry.metrics` / `fabric.uncertainty_bounds` и т.п. (должны быть каноническими).
3) **OTel/Prometheus** — operational observability (вне CAS), но должна быть корреляция через `run_id` и `artifact_id`.

Конвенции для `RunContext.emit()`:

- `phase` = модуль (`core|fabric|foundry|scientist|lex|scholar`) или под‑фаза (`foundry.execute`).
- `event` = UPPER_SNAKE стабильный код (`RUN_STARTED`, `EXEC_STEP`, `LEGAL_CHECK_STARTED`).
- `refs.inputs/outputs` — **только** `ArtifactRef` (или их typed subclass).

---

## 6) Work 4.3 — Core contracts ports на стыках модулей

### 6.3.1 Структура `polisyos.core.contracts` (target)

```
polisyos/core/contracts/
  __init__.py
  compiler.py
  fabric.py
  foundry.py
  trinity.py
  scientist.py
  lex.py        # NEW (E1.4)
  scholar.py    # NEW (E1.4)
  legal.py      # deprecated shim (реэкспорт lex)
```

### 6.3.2 Нормативные правила импорта для contracts

Разрешено:

- stdlib
- `pydantic`, `typing_extensions`
- `polisyos.core.artifacts.*` (ArtifactID/ArtifactRef/SchemaInfo/…)
- `polisyos.ir.*` (если контракту нужны IR‑типы: Trinity models, NormPack)

Запрещено:

- `polisyos.fabric.*`, `polisyos.foundry.*`, `polisyos.scientist.*` (кроме того, что contracts сами описывают как refs; но они не должны импортировать реализации)

### 6.3.3 Trinity port (`contracts/trinity.py`)

Добавить/зафиксировать:

- `ProblemFrameRef`, `PolicySpecRef`, `ModelSpecRef` (уже есть)
- `TrinityBundle` (уже есть)
- **добавить** `TrinityBundleRef` (если bundle тоже хранится как артефакт и передаётся как единый ref)

Рекомендуемые kinds:

- `ir.problem_frame`
- `ir.policy_spec`
- `ir.model_spec`
- `ir.trinity_bundle` (если появится)

### 6.3.4 Fabric port (`contracts/fabric.py`)

Цель: сделать типизированным “вход в мир” и “выход из мира” для Scientist/Foundry/Scholar/Lex.

**Минимальный набор refs E1.4:**

- `DataViewRequestRef` (уже есть)
- `QueryPlanRef` (уже есть)
- `FabricResultRef` (уже есть)
- `EvidenceBundleRef` (core‑ref для портов; IR может держать изоморфный “string ref” для своих схем)
- `UncertaintyBoundsRef` / `WarningsRef` (уже есть)

**Добавить в E1.4:**

- `DataSnapshotRef` (для фиксированных срезов данных, которые Foundry использует как input)
- `DataSnapshot` envelope (опционально; refs достаточно)

**Нормативное разделение:**

- `DataViewRequest` = запрос (декларативный контракт)
- `QueryPlan` = “как получить”
- `FabricResult` = “что получили” (refs на data/evidence/uncertainty/warnings)
- `DataSnapshot` = “фиксируемый input для вычислений” (может быть отдельным видом FabricResult)

### 6.3.5 Foundry port (`contracts/foundry.py`)

**Refs (минимум):**

- `ProgramGraphRef`, `ExecPlanRef`, `ExecConfigRef` (есть)
- `StateSnapshotRef`, `StateDeltaRef`, `MetricsRef`, `TraceSliceRef` (есть)
- **добавить** `SimulationResultRef` (+ envelope `SimulationResult`)

**SimulationResult (E1.4) — контракт Scientist↔Foundry:**

- ссылки на:
  - `exec_plan_ref`
  - `metrics_ref` (обязательно)
  - `state_snapshot_ref` (опционально)
  - `environment_ref` / `environment_fingerprint` (опционально)
  - `trace_slice_ref` (опционально)

Смысл: Scientist не должен знать про внутренние классы Foundry executor’а — только про результат как артефакт.

### 6.3.6 Scientist port (`contracts/scientist.py`)

E1.4 фиксирует:

- contracts.scientist содержит **только refs/envelopes**, не логику workflow.

**Минимум refs:**

- `ExperimentStateRef` (`kind="scientist.experiment_state"`)
- `DecisionPacketRef` (`kind="scientist.decision_packet"`)

Возможные дополнительные refs (если уже есть в коде и нужны):

- `FailureCardRef`, `TimelineRef`, `DecisionCardRef`, `PolicyIRRef`, `CritiqueRef`

**Ключевой рефакторинг E1.4:**

- убрать “внутренний” `ArtifactRef` из `core/contracts/scientist.py` и заменить на наследование от `core.artifacts.manifest.ArtifactRef` как в остальных портах.

### 6.3.7 Scholar port (`contracts/scholar.py`)

E1.4 добавляет только ABI‑стык (без реализации Scholar):

**Вход:** `ResearchIntent` (envelope)

- domain/topic
- jurisdiction(s)
- time window
- required outputs (docs/claims/bundles)
- budgets/limits

**Выход:** `KnowledgeBundleRef`

- `kind="scholar.knowledge_bundle"`
- `media_type="application/json"`

Опционально: `EnrichmentReportRef` (audit artefact).

### 6.3.8 Lex port (`contracts/lex.py`)

См. §4.1.

---

## 7) Work 4.4 — Component model skeleton (E1.4, minimal)

### 7.4.1 Зачем это в E1.4

Чтобы в E3 “расширение = пакет” стало механикой, нам нужен **единый ABI для идентичности компонентов** и **единый способ discovery/registry**, который позже будет использован для:

- Foundry methods
- Fabric connectors
- Scientist nodes
- Scholar/Lex backends

В E1.4 достаточно “скелета” (не переподключая существующие системы).

### 7.4.2 Файловая структура (target)

```
polisyos/core/components/
  __init__.py
  ids.py
  metadata.py
  capabilities.py
  protocols.py
  registry.py
  discovery.py
  compliance.py
```

### 7.4.3 ComponentId (normative)

**Формат:** `namespace.name@semver`

Нормативные правила:

- `namespace` и `name`:
  - lowercase `[a-z][a-z0-9_]*`
  - `.` только как разделитель namespace/name (не внутри сегмента)
- `semver`:
  - минимум `MAJOR.MINOR.PATCH`
  - pre-release/build metadata разрешены как в semver (опционально)

API (минимум):

- `ComponentId.parse(str) -> ComponentId`
- `str(ComponentId) -> "namespace.name@x.y.z"`
- свойства: `.namespace`, `.name`, `.version`

### 7.4.4 ComponentMetadata (normative)

Минимальные поля:

- `component_id: ComponentId`
- `display_name: str | None`
- `description: str | None`
- `domains: list[str]`
- `jurisdictions: list[str]`
- `tags: list[str]`
- `capabilities: set[Capability]` (или `Capabilities` Flag)
- `provides: list[str]` (опционально: “what it provides”, для поиска)
- `depends_on: list[ComponentId]` (опционально, на E1.4 можно оставить строками)

### 7.4.5 Capabilities (normative)

Для E1.4 достаточно малого, но стабильного набора:

- `CAS_READ`, `CAS_WRITE`
- `FABRIC_QUERY`, `FABRIC_WRITE`
- `FOUNDRY_COMPILE`, `FOUNDRY_EXECUTE`
- `LEX_EVALUATE`
- `SCHOLAR_ENRICH`
- `SCIENTIST_NODE`

Рекомендация: использовать `Flag` (как у `ConnectorCapability`) для композиции.

### 7.4.6 Registry (target behavior)

Registry хранит:

- `component_id -> metadata`
- `component_id -> factory/provider` (опционально, в E1.4 можно не делать)

**Conflict policy (минимум):**

- `ERROR` (duplicate id)
- `PREFER_HIGHEST_SEMVER`
- `FIRST_WINS`

Registry умеет query:

- by capability
- by domain
- by jurisdiction
- by tag

### 7.4.7 Discovery (entry_points + dev scan)

E1.4 фиксирует:

- entry point group: `polisyos.components` (универсальный)
- contract: entry point возвращает либо `ComponentMetadata`, либо `ComponentProvider` (Protocol)

Dev scan (опционально для E1.4):

- скан директории на `py` файлы с `__polisyos_components__` списком metadata.

**Важно:** discovery не должен тянуть heavy imports без необходимости. Предпочтение: lazy import.

---

## 8) Deliverables (что должно появиться/измениться)

### 8.1 Code (core)

- `src/polisyos/core/contracts/lex.py` (new)
- `src/polisyos/core/contracts/scholar.py` (new)
- `src/polisyos/core/contracts/legal.py` → deprecated shim (реэкспорт `lex`)
- `src/polisyos/core/contracts/scientist.py` → унификация refs на `core.artifacts.manifest.ArtifactRef`
- `src/polisyos/core/artifacts/manifest.py` → расширение `CanonInfo` (чтобы отражать режим канонизации)
- `src/polisyos/core/components/*` (new package skeleton)

### 8.2 Touchpoints (минимальные правки импортов)

- `scientist/governance/*` → при необходимости переключить `core.contracts.legal` → `core.contracts.lex`
- места, где создаются/валидируются refs Scientist → адаптировать под новый base ref (если меняем `contracts.scientist`)

### 8.3 Docs

- обновить `src/polisyos/core/README.md` (важно: привести зависимость IR↔Core в соответствие с import gate; IR **не** зависит от core)
- обновить `src/polisyos/core/contracts/README.md` (добавить lex/scholar ports, правила)
- добавить/обновить ADR/секцию о component id (если нужно; можно как часть core/components/README.md)

---

## 9) Definition of Done (формально проверяемые критерии)

### 9.1 Dependency check

- `python3 tools/lint/lint_imports.py --policy import_policy.toml --exceptions import_exceptions.toml` → **Violations: none**
- В частности: `polisyos.core.*` не импортирует `polisyos.scientist.*` (ни напрямую, ни транзитивно через contracts).

### 9.2 Contracts ports

- `polisyos.core.contracts` содержит `lex.py` и `scholar.py`.
- `contracts` содержат только модели/Protocol/ABC (без реализаций).
- `contracts.scientist` не содержит собственного “второго” ArtifactRef; базовый ref один.

### 9.3 Canon/manifest correctness

- Любой артефакт, записанный `put_json`, получает manifest с корректным `canon` (включая параметры CanonSpec).
- Для артефактов, допускающих float (например, env/telemetry), режим канонизации явно отражён в manifest.

### 9.4 Component skeleton

- `polisyos.core.components` существует и импортируется без side effects.
- Есть минимальный `ComponentId` parser/validator + `ComponentMetadata` + `Discovery` + `Registry`.

---

## 10) Migration plan (рекомендуемая последовательность имплементации)

1) **Lex/Scholar ports**: добавить `core/contracts/lex.py`, `core/contracts/scholar.py`; сделать `legal.py` shim.
2) **Unify Scientist refs**: привести `core/contracts/scientist.py` к `ArtifactRef` из `core.artifacts.manifest`.
3) **CanonInfo расширение**: обновить `CanonInfo` и запись manifest в `FileSystemCAS.put_json()` так, чтобы параметры `canon_spec` отражались.
4) **Component skeleton**: добавить `core/components/*` без интеграции с существующими discovery.
5) **Docs + import gate**: обновить README/доки, убедиться что lint_imports не показывает новых циклов/нарушений.

---

## Appendix A — Practical notes (anti-footguns)

### A.1 Не добавлять новые cycles

Import cycles, которые уже есть, не должны ухудшаться. Особенно осторожно с:

- `__init__.py` (lazy imports предпочтительнее eager imports)
- contracts modules (не должны тянуть пакеты верхнего уровня)

### A.2 “Строки vs типы” для IDs

- В IR: `ArtifactID` остаётся строкой по `ARTIFACT_ID_PATTERN`.
- В Core: `ArtifactID` — тип (`core.artifacts.ids.ArtifactID`), а refs — `ArtifactRef`.
- Между ними: ports (`core.contracts.*`) являются единственным “мостом” между строковыми IR‑контрактами и типизированными core refs.

### A.3 Версионирование

- Канонизация: `CanonSpec.version` и `CanonInfo.version` должны меняться при изменении алгоритма.
- Contracts: добавления backward compatible, удаления — только через deprecation cycle.

---

## Appendix B — Contract inventory (kinds ↔ refs) (E1.4 baseline)

Ниже — “инвентаризация” артефактных ссылок, которые должны считаться **публичным ABI** port‑слоя.

> Примечание: точные `SchemaInfo.name/version` могут отличаться по текущему коду, но в E1.4 фиксируется правило: **если payload имеет schema_version — записываем её в manifest**. Для “инфраструктурных” envelope‑ов без schema_version допускается `SchemaInfo(name=..., version="0.1.0")` как сейчас.

### B.1 Trinity (`polisyos.core.contracts.trinity`)

| Ref class | kind | media_type | Notes |
|---|---|---|---|
| `ProblemFrameRef` | `ir.problem_frame` | `application/json` | problem definition |
| `PolicySpecRef` | `ir.policy_spec` | `application/json` | policy definition |
| `ModelSpecRef` | `ir.model_spec` | `application/json` | model definition |
| `TrinityBundleRef` (NEW) | `ir.trinity_bundle` | `application/json` | optional “bundle as artifact” |

### B.2 Fabric (`polisyos.core.contracts.fabric`)

| Ref class | kind | media_type | Notes |
|---|---|---|---|
| `DataViewRequestRef` | `ir.data_view_request` | `application/json` | request contract |
| `QueryPlanRef` | `fabric.query_plan` | `application/json` | execution plan |
| `FabricResultRef` | `fabric.result_bundle` | `application/json` | result envelope |
| `EvidenceBundleRef` (core port) | `fabric.evidence_bundle` | `application/json` | evidence/provenance envelope |
| `UncertaintyBoundsRef` | `fabric.uncertainty_bounds` | `application/json` | uncertainty metadata |
| `WarningsRef` | `fabric.warnings` | `application/json` | warnings bundle |
| `DataSnapshotRef` (NEW) | `fabric.data_snapshot` | `application/json` | fixed snapshot for compute inputs |

### B.3 Foundry (`polisyos.core.contracts.foundry`)

| Ref class | kind | media_type | Notes |
|---|---|---|---|
| `PolicySurfaceIRRef` | `ir.policy_surface` | `application/json` | legacy surface IR artifact |
| `ProgramGraphRef` | `foundry.program_graph` | `application/json` | compiled program graph |
| `LoweredIRRef` | `foundry.lowered_ir` | `application/json` | optional lowered IR |
| `ExecPlanRef` | `foundry.exec_plan` | `application/json` | execution plan |
| `ExecConfigRef` | `foundry.exec_config` | `application/json` | exec config |
| `StateSnapshotRef` | `foundry.state_snapshot` | `application/json` | immutable snapshot |
| `StateDeltaRef` | `foundry.state_delta` | `application/json` | patch/delta operations |
| `MetricsRef` | `foundry.metrics` | `application/json` | metrics payload |
| `TraceSliceRef` | `foundry.trace_slice` | `application/jsonl` | slice of trace (optional) |
| `EnvironmentManifestRef` | `foundry.environment_manifest` | `application/json` | reproducibility manifest |
| `SimulationResultRef` (NEW) | `foundry.simulation_result` | `application/json` | top-level result envelope for Scientist |

### B.4 Compiler (`polisyos.core.contracts.compiler`)

| Ref class | kind | media_type | Notes |
|---|---|---|---|
| `LinkReportRef` | `compiler.link_report` | `application/json` | link issues |
| `CompileReportRef` | `compiler.compile_report` | `application/json` | compile issues |

### B.5 Lex (`polisyos.core.contracts.lex`)

| Ref class | kind | media_type | Notes |
|---|---|---|---|
| `LegalReportRef` | `lex.legal_report` | `application/json` | compliance report |
| `ChangeProposalRef` | `lex.change_proposal` | `application/json` | optional proposals |

### B.6 Scholar (`polisyos.core.contracts.scholar`)

| Ref class | kind | media_type | Notes |
|---|---|---|---|
| `KnowledgeBundleRef` | `scholar.knowledge_bundle` | `application/json` | graph/bundle ref |

### B.7 Scientist (`polisyos.core.contracts.scientist`)

| Ref class | kind | media_type | Notes |
|---|---|---|---|
| `ExperimentStateRef` | `scientist.experiment_state` | `application/json` | workflow state snapshot |
| `DecisionPacketRef` | `scientist.decision_packet` | `application/json` | decision envelope |

---

## Appendix C — CanonInfo schema migration (backward compatibility)

Если `CanonInfo` расширяется (см. §5.2.1.2), миграция должна быть “мягкой”:

- новые поля имеют **defaults** → старые manifests валидируются без изменений;
- `ArtifactManifest.canon` может быть `null` (для старых/bytes-only артефактов) → код должен уметь.

Требование E1.4: при записи новых артефактов `FileSystemCAS.put_json()` должен:

1) использовать фактический `canon_spec` (default или переданный),
2) записывать его параметры в `ArtifactManifest.canon`.

---

## Appendix D — DoD commands (ручная проверка)

Из `policy-engine/`:

- import gate: `python3 tools/lint/lint_imports.py --policy import_policy.toml --exceptions import_exceptions.toml`
- (опционально) fail on cycles (не требование E1.4): `python3 tools/lint/lint_imports.py --policy import_policy.toml --exceptions import_exceptions.toml --fail-on-cycles`
