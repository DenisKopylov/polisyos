# E2.10 (Phase 18) — Lex Legal evaluation v1.0: PolicySpec/Results → LegalReport + ChangeProposals (World artifacts)

Repo snapshot date: 2026-02-04

## 0) Цель фазы

Добавить в `polisyos.lex` возможность **детерминированной** проверки “легальности/соответствия нормам”:

- **Вход**:
  - `PolicySpec` (или Trinity refs)
  - `SimulationResult` (Foundry output) + `Metrics` (если доступно)
  - `NormPack` (Phase 17 / E2.9)
  - `JurisdictionContext` (в MVP = `jurisdiction` + `as_of`)
- **Выход**:
  - `LegalReport` (structured findings + ссылки на evidence)
  - `ChangeProposal` (детерминированные предложения изменений, минимальный MVP)

**Запись результата строго в Fabric как “артефакты мира”:**

- CAS artifacts:
  - `lex.legal_report`
  - `lex.change_proposal`
- + `WorldEvent(kind=evaluate_legality)` (IR `EventKind.EVALUATE_LEGALITY`)
- + PROV edges через `fabric.world.store.emit_world_event_facts(...)`

> Никаких внешних вызовов (web/LLM/DB), никаких случайных tie‑break’ов: порядок и вывод воспроизводимы по входным артефактам.

---

## 1) Контекст репозитория (что уже есть и что используем)

### 1.1. World Graph write‑path уже существует (E2.2)

Источник истины:

- `policy-engine/src/polisyos/fabric/world/store/*`
  - `persist_world_event`, `emit_world_event_facts`
  - `stable_world_provenance_v1()` и `event_world_provenance_v1(event_id)`
  - `write_world_fact_segment(...)` + `_segments.jsonl` индекс через `append_world_segment_index`
- IR контракты:
  - `policy-engine/src/polisyos/ir/world/event.py` (`EventKind.EVALUATE_LEGALITY` уже есть)
  - `policy-engine/src/polisyos/ir/world/ids.py` (`world_event_id_from_payload`, `artifact_id_to_world_id`, `stable_world_id_from_canon`)

### 1.2. Lex уже умеет собирать NormPack (E2.9 / Phase 17)

Источник истины:

- `policy-engine/src/polisyos/lex/api.py` → `assemble_norm_pack(...)`
- `policy-engine/src/polisyos/lex/normpack/assemble_pack.py`
  - сохраняет `NormPack` как `lex.norm_pack`
  - пишет WorldEvent(kind=assemble_norm_pack)

Важно для Phase 18:

- `NormRule.backend_metadata` уже содержит `predicate_id`, `value_text`, `value_decimal`, `unit_id` (но **не всегда** operator — см. §4.2)

### 1.3. Foundry SimulationResult/Metrics контракты уже есть

- `policy-engine/src/polisyos/core/contracts/foundry.py`:
  - `SimulationResult(exec_plan_ref, metrics_ref, …)`
  - `Metrics(values: dict[str, int|str])`

### 1.4. Trinity/PolicySpec контракты уже есть

- `PolicySpec` (IR): `policy-engine/src/polisyos/ir/policy_spec.py`
- Trinity typed refs: `policy-engine/src/polisyos/core/contracts/trinity.py`

### 1.5. Lex refs уже присутствуют в ABI (но payload устаревший относительно E2.10)

- `policy-engine/src/polisyos/core/contracts/lex.py` уже содержит:
  - `LegalReportRef(kind="lex.legal_report")`
  - `ChangeProposalRef(kind="lex.change_proposal")`

Phase 18 вводит **новый формат payload** этих артефактов (см. §6–§7).

---

## 2) Deliverables (код/док)

### 2.1. Новый пакет Lex: Legal evaluation v1.0

Рекомендуемое размещение (минимальный surface area; соответствие именам deliverables):

```
policy-engine/src/polisyos/lex/legal_evaluation/
  __init__.py
  context_builder.py
  evaluate.py
  change_proposals.py
  backends/
    __init__.py
    simple_v1.py
```

### 2.2. Обновление публичного Lex API

```
policy-engine/src/polisyos/lex/api.py
  + evaluate_legality(...)
  + propose_changes(...)
```

и, опционально, экспорт из:

```
policy-engine/src/polisyos/lex/__init__.py
```

### 2.3. Scientist bridge (критично)

Добавить builtin node:

```
policy-engine/src/polisyos/scientist/nodes/builtins/governance/legal_check.py
```

и экспортировать его из `policy-engine/src/polisyos/scientist/nodes/builtins/governance/__init__.py`.

### 2.4. Тесты

Новый файл:

```
policy-engine/tests/fabric/test_legal_evaluation_phase18.py
```

### 2.5. Документ контракта

Этот файл:

```
policy-engine/docs/contracts/E2_10_LEX_LEGAL_EVALUATION_V1_0.md
```

---

## 3) Входной контракт (MVP): `LegalEvaluationRequest`

### 3.1. Где хранить

Требование из постановки: “в `lex.py` (если уже есть; иначе в `types.py`)”.

В репозитории уже есть ABI‑файл:

```
policy-engine/src/polisyos/core/contracts/lex.py
```

Поэтому **норма Phase 18**:

- добавить `LegalEvaluationRequest` в `polisyos.core.contracts.lex`
- использовать его в `polisyos.lex.api.evaluate_legality(...)`

### 3.2. Схема (Pydantic, extra=forbid)

```python
from pydantic import BaseModel, ConfigDict, Field
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.trinity import TrinityBundleRef, PolicySpecRef, ModelSpecRef
from polisyos.core.contracts.foundry import SimulationResultRef


class LegalEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\\d+\\.\\d+$")

    # Jurisdiction context
    jurisdiction: str
    as_of: str  # ISO date or datetime; MVP normalizes to YYYY-MM-DD

    # Inputs
    trinity_bundle_ref: TrinityBundleRef | None = None
    policy_spec_ref: PolicySpecRef | None = None
    model_spec_ref: ModelSpecRef | None = None
    simulation_result_ref: SimulationResultRef
    norm_pack_ref: ArtifactRef  # kind=lex.norm_pack (MVP: validate kind)

    # Evaluation policy
    eval_policy_id: str = "lex.eval.simple_v1"
    strict: bool = True
```

### 3.3. Нормализация и валидация (детерминированно)

В `polisyos.lex.legal_evaluation.evaluate._normalize_request(...)`:

1) `jurisdiction_norm = request.jurisdiction.strip().casefold()`
   - должен соответствовать `ID_PATTERN` (`polisyos.ir.kernel.base.ID_PATTERN`)
2) `as_of_norm = normalize_as_of(request.as_of)` (копируем semantics из Lex NormPack / E2.9):
   - принимает `YYYY-MM-DD` или datetime ISO
   - возвращает строго `YYYY-MM-DD`
   - date semantics = “date_inclusive”
3) Exactly‑one policy input source:
   - если `trinity_bundle_ref` задан:
     - разрешить `policy_spec_ref/model_spec_ref` быть `None` и брать их из bundle
   - если `trinity_bundle_ref` не задан:
     - `policy_spec_ref` обязателен
4) `norm_pack_ref.kind` должен быть `"lex.norm_pack"` (иначе `LexValidationError`)
5) `eval_policy_id` должен соответствовать `ID_PATTERN` (и быть из allow‑list в MVP)

> Правило MVP: отсутствующий `model_spec_ref` **не блокирует** оценку (используется только как metadata в отчёте).

---

## 4) Детализация “что именно считается правилом” (MVP semantics)

### 4.1. Норма: как извлекаем `predicate_id`, `operator`, `expected_value`, `unit_id` из NormRule

В Phase 18 **не меняем IR `NormRule`** (это контракт Phase 3), поэтому используем `NormRule.backend_metadata` как carrier:

Минимально обязательные ключи для rule‑by‑rule evaluation:

- `predicate_id: str` (ID_PATTERN)
- `operator: str` ∈ `{ "<", "<=", "=", ">=", ">" }`
- `value_decimal: str | None` (Decimal‑string)
- `value_text: str` (для enum/text сравнения и как fallback)
- `unit_id: str | None` (ID_PATTERN, canonical unit id)

### 4.2. Требуемая поддерживающая правка Phase 17 (обязательна для PASS/FAIL в numeric)

Сейчас `polisyos.lex.normpack.assemble_pack.claims_to_norm_rules(...)` **теряет operator**, хотя extractor `lex_norm_regex_v1` кладёт его в:

- `Claim.qualifiers["op"]`
- `Claim.props["lex"]["operator"]`

Для Phase 18 MVP **нужно**:

- в `claims_to_norm_rules(...)` добавить:
  - `operator = claim.props["lex"]["operator"]` (если есть) иначе `claim.qualifiers["op"]`
  - записать в `NormRule.backend_metadata["operator"] = operator`

Если operator отсутствует:

- finding = `UNKNOWN` (или `FAIL` если `strict=True`)
- quality_issue: `missing_operator`

---

## 5) LegalContextBuilder (детерминированный)

### 5.1. Назначение

`LegalContextBuilder` строит “минимальный слой фактов” для проверки правил:

- загружает все входные артефакты из CAS
- вычисляет **ObservedValue** для каждого `NormRule`:
  - из `SimulationResult.metrics` (preferred)
  - иначе из `PolicySpec` параметров/слотов
- нормализует типы и units (MVP)
- фиксирует quality issues

### 5.2. Размещение и API

Файл: `policy-engine/src/polisyos/lex/legal_evaluation/context_builder.py`

```python
from dataclasses import dataclass
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.lex import LegalEvaluationRequest
from polisyos.ir.norm_pack import NormPack, NormRule
from polisyos.ir.policy_spec import PolicySpec
from polisyos.core.contracts.foundry import SimulationResult, Metrics


@dataclass(frozen=True)
class ObservedValue:
    predicate_id: str
    source_kind: str               # "metrics"|"policy_param"
    value_kind: str                # "numeric"|"boolean"|"text"
    value_text: str                # always present (normalized)
    value_decimal: str | None      # Decimal-string if numeric
    unit_id: str | None

    # Evidence pointers (for LegalReport)
    simulation_result_ref: str | None
    metrics_ref: str | None
    metric_key: str | None
    policy_spec_ref: str | None
    policy_json_pointer: str | None


@dataclass(frozen=True)
class RuleObservation:
    rule_id: str
    predicate_id: str
    applies: bool
    observed: ObservedValue | None
    mapping_notes: list[str]


@dataclass(frozen=True)
class LegalContext:
    request: LegalEvaluationRequest
    jurisdiction_norm: str
    as_of_norm: str
    policy: PolicySpec
    norm_pack: NormPack
    simulation_result: SimulationResult
    metrics: Metrics | None
    observations_by_rule_id: dict[str, RuleObservation]
    quality_issues: list[dict]      # structured, deterministic
    artifacts_used: list[str]       # artifact_id strings
```

### 5.3. Loading rules (CAS)

Норма загрузки (все через CAS, без DB):

- `PolicySpec`:
  - bytes = `cas.get_bytes(ArtifactID(policy_spec_ref.artifact_id))`
  - payload = `json.loads(...)`
  - `PolicySpec.model_validate(payload)`
- `SimulationResult`:
  - `SimulationResult.model_validate(payload)`
- `Metrics`:
  - `metrics_ref = simulation_result.metrics_ref.artifact_id`
  - `Metrics.model_validate(payload)`
- `NormPack`:
  - `NormPack.model_validate(payload)`

Ошибки:

- отсутствует артефакт в CAS → `LexNotReadyError` (stage=`not_ready`)
- payload невалидный → `LexValidationError` (stage=`validation`)

### 5.4. Applicability (MVP)

Используем существующую функцию:

- `polisyos.lex.normpack.applicability.applies_to_context(applicability, jurisdiction_norm, as_of_norm)`

Если `applies=False`:

- finding.status = `NOT_APPLICABLE`
- observed не требуется
- quality issues не добавляем (это не проблема качества)

### 5.5. Mapping predicate_id → observed value (детерминированный)

#### 5.5.1. Из metrics (preferred)

Алгоритм:

1) `predicate_id = rule.backend_metadata["predicate_id"]`
2) если `metrics` есть и `predicate_id in metrics.values`:
   - `raw = metrics.values[predicate_id]`
   - `ObservedValue.source_kind="metrics"`
   - `ObservedValue.metric_key = predicate_id`
   - `ObservedValue.metrics_ref = simulation_result.metrics_ref.artifact_id`
   - `ObservedValue.simulation_result_ref = request.simulation_result_ref.artifact_id`

Парсинг:

- если `raw` is `int` → numeric, `value_decimal=str(raw)`
- если `raw` is `str`:
  - пробуем `Decimal(raw)` (через safe parser, без float)
    - успех → numeric
    - иначе → text

`unit_id` для metrics в MVP:

- `None` (если нет отдельного unit registry/descriptor)

Если значение не распознано:

- observed.value_kind="text"
- observed.value_text=raw.strip()

#### 5.5.2. Из PolicySpec параметров (fallback)

MVP поддержка двух путей (оба детерминированны):

**A) ParameterSpec param_id == predicate_id (preferred)**

1) строим index: `param_id -> ParameterSpec`
2) если найден `ParameterSpec`:
   - находим `InterventionSpec` по `intervention_id`
   - читаем значение из `intervention.params` по `param_path`:
     - `param_path` = dot‑path, поддержать:
       - `"foo"` → `params["foo"]`
       - `"foo.bar"` → `params["foo"]["bar"]` (только dict nesting)

JSON pointer для patch:

- `/interventions/<idx>/params/<foo>/<bar>/...`
- `<idx>` — индекс intervention в массиве (детерминированно по порядку в PolicySpec)

**B) Direct params key == predicate_id (fallback)**

1) ищем все `(intervention_index, intervention_id, value)` где `predicate_id in intervention.params`
2) если найдено ровно одно совпадение → используем его
3) если >1 → mapping ambiguous:
   - observed = None
   - quality_issue: `ambiguous_policy_mapping`

Парсинг `ParamValue` (MVP):

- `bool` → boolean
- `int` → numeric
- `str`:
  - пробуем Decimal‑parse → numeric, иначе text
- `dict`/`BaseModel`:
  - MVP: не поддерживать (UNKNOWN/FAIL по strict)
  - quality_issue: `unsupported_policy_value_type`

unit_id для PolicySpec (MVP):

- если значение из PolicySpec не несёт unit → `None`
- если это `RateValue` / `MoneyValue` / … (если встречается как dict) → MVP не поддерживает

#### 5.5.3. Нет маппинга

Если нет значения ни в metrics, ни в policy:

- observed = None
- quality_issue: `missing_observed_value`
- finding.status:
  - `UNKNOWN` если `strict=False`
  - `FAIL` если `strict=True` (и severity = BLOCKER)

### 5.6. Unit normalization (MVP)

В MVP поддерживаем только:

- `percent` ↔ `ratio`
- `m` ↔ `km`

Порядок:

1) определяем `expected_unit_id` из rule.backend_metadata["unit_id"]
2) определяем `observed_unit_id` из ObservedValue.unit_id
3) если один из unit_id = None:
   - quality_issue: `missing_unit`
   - status: `UNKNOWN` или `FAIL` по strict
4) если `expected_unit_id == observed_unit_id` → ok
5) иначе пробуем конвертировать:
   - percent→ratio: `x/100`
   - ratio→percent: `x*100`
   - km→m: `x*1000`
   - m→km: `x/1000`
6) если конверсия невозможна:
   - quality_issue: `unit_mismatch`
   - status: `UNKNOWN` или `FAIL` по strict

> Конверсия выполняется **только** для numeric observed/expected.

### 5.7. Детерминизм и порядок

`RuleObservation` строится для каждого правила, но порядок строго:

- `rules_sorted = sorted(norm_pack.norms, key=lambda r: r.norm_id)`
- внутри одного правила:
  - citations сортируются по `provision_id`, затем по `citation.doc.doc_id`, затем `fragment_id`

---

## 6) Evaluation backend v1 (simple, rule‑by‑rule)

### 6.1. Статусы и типы (MVP)

Статусы findings:

- `PASS`
- `FAIL`
- `UNKNOWN`
- `NOT_APPLICABLE`

Типы наблюдений:

- numeric (Decimal-string)
- boolean
- enum/text (строгое равенство после нормализации)

Операторы (MVP):

- `<, <=, =, >=, >` (numeric)
- `=` (boolean/text; остальные → UNKNOWN/FAIL по strict)

### 6.2. Размещение и API

Файлы:

- `policy-engine/src/polisyos/lex/legal_evaluation/evaluate.py` — orchestration
- `policy-engine/src/polisyos/lex/legal_evaluation/backends/simple_v1.py` — backend

Backend интерфейс (внутренний, MVP):

```python
from dataclasses import dataclass
from typing import Literal

FindingStatus = Literal["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]
FindingSeverity = Literal["info", "warning", "blocker"]


@dataclass(frozen=True)
class RuleFinding:
    rule_id: str
    status: FindingStatus
    severity: FindingSeverity
    norm_citations: list[dict]         # from NormRule.provision_refs[].citations
    observed_evidence_refs: list[dict] # refs to SimulationResult/Metrics and/or PolicySpec pointers
    observed_value: str | None
    expected: dict | None              # {"op":..., "threshold":..., "unit":...}
    rationale: dict                    # structured deterministic rationale
```

### 6.3. Алгоритм simple_v1 (на 1 правило)

Псевдокод:

1) если `applies=False` → `NOT_APPLICABLE`
2) если `observed is None`:
   - `UNKNOWN` или `FAIL` по strict
3) иначе:
   - извлечь `operator`, `expected_value_decimal/value_text`, `expected_unit_id`
   - привести observed к нужному типу:
     - numeric: Decimal-string обязателен
     - boolean: `value_text` ∈ {"true","false"} (casefold)
     - text: normalize = `collapse_ws(strip()).casefold()` (MVP)
   - применить оператор:
     - numeric: compare Decimal
     - boolean/text: только "="
4) severity mapping (MVP):
   - PASS / NOT_APPLICABLE → `"info"`
   - UNKNOWN → `"warning"` (или `"blocker"` если strict=True)
   - FAIL → `"blocker"` (MVP default)

### 6.4. Детерминированный порядок findings

В `evaluate.evaluate_legality_impl(...)`:

- findings сортируются по `rule_id` (строго, строковый порядок)

---

## 7) LegalReport артефакт (структура v1.0)

### 7.1. CAS kind + schema

- kind: `lex.legal_report`
- schema: `SchemaInfo(name="polisyos.lex.LegalReport", version="1.0")`
- media_type: `application/json`

### 7.2. Payload (v1.0)

```json
{
  "schema_version": "1.0",
  "request": {
    "jurisdiction": "ua",
    "as_of": "2026-02-04",
    "policy_spec_ref": {"artifact_id": "sha256:...", "kind": "ir.policy_spec"},
    "model_spec_ref": {"artifact_id": "sha256:...", "kind": "ir.model_spec"},
    "simulation_result_ref": {"artifact_id": "sha256:...", "kind": "foundry.simulation_result"},
    "norm_pack_ref": {"artifact_id": "sha256:...", "kind": "lex.norm_pack"},
    "eval_policy_id": "lex.eval.simple_v1",
    "strict": true
  },
  "summary": {
    "counts": {"pass": 3, "fail": 1, "unknown": 2, "not_applicable": 5},
    "compliance_grade": "fail"
  },
  "findings": [
    {
      "rule_id": "claim.sha256_...",
      "status": "FAIL",
      "severity": "blocker",
      "norm_citations": [
        {"provision_id": "frag.sha256_...", "citations": [/* CitationRef */]}
      ],
      "observed_evidence_refs": [
        {"kind": "policy_param", "policy_json_pointer": "/interventions/0/params/speed_limit"}
      ],
      "observed_value": "70",
      "expected": {"op": "<=", "threshold": "60", "unit": null},
      "rationale": {
        "predicate_id": "speed_limit",
        "mapping": {"source": "policy_param", "notes": ["..."]},
        "comparison": {"left": "70", "op": "<=", "right": "60", "result": false}
      }
    }
  ],
  "quality_issues": [
    {"code": "missing_observed_value", "rule_id": "claim.sha256_...", "details": {"predicate_id": "kpi.xxx"}}
  ],
  "artifacts_used": [
    "sha256:...policy",
    "sha256:...simulation_result",
    "sha256:...metrics",
    "sha256:...norm_pack"
  ]
}
```

### 7.3. compliance_grade mapping (MVP)

Детерминированное правило:

- если `fail > 0` → `"fail"`
- иначе если `unknown > 0`:
  - `strict=True` → `"fail"`
  - `strict=False` → `"partial"`
- иначе → `"pass"`

---

## 8) ChangeProposal артефакт (структура v1.0, deterministic)

### 8.1. CAS kind + schema

- kind: `lex.change_proposal`
- schema: `SchemaInfo(name="polisyos.lex.ChangeProposal", version="1.0")`
- media_type: `application/json`

### 8.2. Payload (v1.0)

```json
{
  "schema_version": "1.0",
  "based_on_report_ref": {"artifact_id": "sha256:...", "kind": "lex.legal_report"},
  "actions": [
    {
      "action_kind": "policy_patch",
      "target_ref": {"artifact_id": "sha256:...", "kind": "ir.policy_spec"},
      "patch_format": "json_patch_v1",
      "patch_json": [
        {"op": "replace", "path": "/interventions/0/params/speed_limit", "value": "60"}
      ],
      "rationale": "Bring speed_limit to <= 60 to satisfy rule claim.sha256_...",
      "links_to_findings": ["claim.sha256_..."]
    },
    {
      "action_kind": "add_metric",
      "target_ref": null,
      "patch_format": null,
      "patch_json": null,
      "rationale": "Add instrumentation for metric kpi.xxx required by rule claim.sha256_...",
      "links_to_findings": ["claim.sha256_..."],
      "metric_id": "kpi.xxx",
      "metric_type": "numeric",
      "unit_id": null
    }
  ]
}
```

### 8.3. Политика генерации (MVP)

В `polisyos.lex.legal_evaluation.change_proposals.propose_changes_v1(...)`:

1) Для каждого finding со статусом `FAIL`:
   - если `observed.source_kind == "policy_param"` и есть `policy_json_pointer`:
     - если expected numeric threshold задан:
       - сгенерировать JSON Patch replace на `policy_json_pointer`
       - patch value:
         - `<=` или `>=` или `=` → threshold
         - `<` → threshold - epsilon
         - `>` → threshold + epsilon
       - epsilon детерминированный:
         - если threshold имеет десятичную часть → `10^exponent` (по Decimal exponent)
         - иначе `1`
2) Для `missing_observed_value`:
   - action_kind=`add_metric`
   - metric_id = predicate_id
   - metric_type = inferred from expected (numeric/boolean/text)
3) Иначе:
   - в MVP не генерировать `model_patch`/`legal_change_request` (зарезервировано)

Детерминизм:

- actions сортируются:
  - сначала `policy_patch`, затем `add_metric`, затем остальные
  - внутри вида — по `links_to_findings[0]` (rule_id) и затем по `path/metric_id`

---

## 9) Persist в World Graph (строго через world.store)

### 9.1. CAS persist

В `polisyos.lex.legal_evaluation.evaluate.evaluate_legality_impl(...)`:

1) Persist `LegalReport`:
   - `cas.put_json(payload, PutOptions(kind="lex.legal_report", ...))`
2) Persist `ChangeProposal` (если requested / если есть actions):
   - `cas.put_json(payload, PutOptions(kind="lex.change_proposal", ...))`

Inputs (InputRef) для LegalReport (рекомендация):

- role=`policy_spec`, `simulation_result`, `metrics`, `norm_pack`, (опц.) `model_spec`

Inputs для ChangeProposal:

- role=`legal_report` (обязательно)
- role=`policy_spec` (если policy_patch)

### 9.2. Semantic artifact nodes (CAS → world)

Для каждого output‑артефакта:

- world_id = `artifact_id_to_world_id(prefix="artifact", artifact_id=...)`
- facts = `emit_world_node_facts(kind=NodeKind.ARTIFACT, artifact_id=..., provenance=stable_world_provenance_v1())`

### 9.3. WorldEvent(kind=evaluate_legality)

Схема:

- `WorldEvent.event_kind = EventKind.EVALUATE_LEGALITY`
- agent:
  - `agent_id="prov.agent.lex_legal_eval"`
  - `agent_type=ProvAgentType.SYSTEM`
  - `label="Lex Legal Evaluation"`
- activity:
  - `activity_id="prov.activity.lex_legal_eval.evaluate"`
  - `activity_type=ProvActivityType.EVALUATE_LEGALITY`
  - `label="Evaluate legality"`

inputs (минимум):

- policy_spec (world_id или artifact_id)
- simulation_result (world_id или artifact_id)
- norm_pack (world_id или artifact_id)
- (опц.) model_spec
- (опц.) metrics artifact_id

outputs:

- legal_report world_id
- change_proposal world_id (если создан)

event_id:

- вычислять через `world_event_id_from_payload(...)` с payload без runtime полей

Далее:

- `persist_world_event(cas, event)`
- `emit_world_event_facts(event, event_artifact_id, provenance=event_world_provenance_v1(event_id))`
- `write_world_fact_segment(facts, segment_name="lex_legal_evaluate")`
- `append_world_segment_index(...)`

> MVP: не вводим отдельные NodeKind `legal.report`/`legal.change_proposal`; достаточно artifact nodes + PROV.

---

## 10) Lex public API (Phase 18)

Файл: `policy-engine/src/polisyos/lex/api.py`

Добавить:

```python
from pathlib import Path
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.lex import LegalEvaluationRequest, LegalReportRef, ChangeProposalRef
from polisyos.lex.legal_evaluation.evaluate import evaluate_legality_impl
from polisyos.lex.legal_evaluation.change_proposals import propose_changes_impl


def evaluate_legality(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    request: LegalEvaluationRequest,
    segment_name: str | None = None,
) -> tuple[LegalReportRef, list[ChangeProposalRef]]:
    ...


def propose_changes(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    based_on_report_ref: LegalReportRef,
    segment_name: str | None = None,
) -> list[ChangeProposalRef]:
    ...
```

Норма Phase 18:

- `evaluate_legality(...)` делает **и report, и proposals** (MVP), чтобы было “одним вызовом”.
- `propose_changes(...)` — опциональный отдельный шаг (например, позже для разных policy).

Возврат: (report_ref, proposals[]), где proposals[] может быть пустым.

---

## 11) Scientist bridge: builtin node `legal_check.py`

### 11.1. Размещение

```
policy-engine/src/polisyos/scientist/nodes/builtins/governance/legal_check.py
```

### 11.2. State contract (MVP)

Node читает:

- `state.inputs["trinity_bundle_ref"]` (опционально) или `state.inputs["policy_spec_ref"]`
- `state.artifacts_index["simulation_result_ref"]` (обязательно)
- `state.inputs["norm_pack_ref"]` (опционально)
- `state.params["jurisdiction"]` (обязательно для Phase 18)
- `state.params["as_of"]` (обязательно; ISO)
- `state.params["strict_legal"]` (опционально, default True)

Node пишет:

- `state.reports_index["legal_report_ref"] = <LegalReportRef>`
- `state.reports_index["change_proposal_ref"] = <ChangeProposalRef>` (первый или агрегированный; MVP = первый)

### 11.3. Behaviour

1) Если `norm_pack_ref` отсутствует:
   - собрать его через `polisyos.lex.api.assemble_norm_pack(...)` (Phase 17)
   - положить в `state.inputs["norm_pack_ref"]`
2) Сформировать `LegalEvaluationRequest`:
   - jurisdiction/as_of из params
   - refs из state
3) Вызвать `polisyos.lex.api.evaluate_legality(...)`
4) Положить refs в state
5) Gate outcome:
   - если `strict=True` и report.summary.compliance_grade != "pass" → NodeOutcome.status="error" или "ok" + event с warning (решение зависит от workflow policy)
   - MVP рекомендация: NodeOutcome.status="ok", а gating делает следующий governance node.

> Важно: для записи world facts node должен иметь `fact_log_root`. MVP‑правило: использовать `Path(ctx.store.root).parent` (как в Lex Corpus), либо прокидывать явно через node params.

---

## 12) Тесты (обязательные)

Файл: `policy-engine/tests/fabric/test_legal_evaluation_phase18.py`

### 12.1. Unit tests

1) `simple_v1` evaluator:
   - numeric PASS/FAIL на `<,<=,=,>=,>`
   - UNKNOWN при missing operator/value
2) Mapping:
   - `predicate_id` → metrics.value
   - fallback → policy param
   - детерминированный tie-break / ambiguous mapping → quality issue

### 12.2. Integration test (end‑to‑end)

Fixture‑минимум:

- `PolicySpec` (CAS):
  - 1 intervention с `params={"speed_limit": "70"}`
  - `ParameterSpec(param_id="speed_limit", intervention_id=..., param_path="speed_limit")`
- `Metrics` (CAS):
  - `values={"accident_rate": "0.03"}`
- `SimulationResult` (CAS):
  - `metrics_ref` на metrics artifact
- `NormPack` (CAS):
  - 2 `NormRule`:
    - PASS rule: predicate_id="accident_rate" op "<=" threshold "0.05"
    - FAIL rule: predicate_id="speed_limit" op "<=" threshold "60" (maps to policy)
  - provision_refs/citations должны ссылаться на `doc.fragment` ids (можно синтетические)

Пайплайн:

1) `evaluate_legality(...)` → получить `LegalReportRef` + `ChangeProposalRef`
2) `materialize_world_duckdb_from_fact_log(tmp_path, db, cas)`
3) asserts:
   - CAS артефакт `lex.legal_report` существует
   - CAS артефакт `lex.change_proposal` существует
   - `world.world_events` содержит запись с `activity_id='prov.activity.lex_legal_eval.evaluate'`
   - report.findings содержит ссылки на provision fragments (citations)
   - change proposal содержит JSON Patch, который “чинит” FAIL rule

---

## 13) DoD (Phase 18)

Готово, когда:

1) Lex по `policy+results+norms` выдаёт воспроизводимый `LegalReport` и `ChangeProposal(s)` (без внешних вызовов).
2) `LegalReport` и `ChangeProposal` сохраняются в CAS с правильными kind’ами.
3) В world fact log появляется `WorldEvent(kind=evaluate_legality)` + PROV edges, и это материализуется в DuckDB (`world.world_events`).
4) Есть тест `test_legal_evaluation_phase18.py`, который проходит end‑to‑end и проверяет artifacts + world event + ключевые поля отчёта/предложений.
