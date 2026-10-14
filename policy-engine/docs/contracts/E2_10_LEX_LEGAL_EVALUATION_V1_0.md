# E2.10 (Phase 18) — Lex Legal evaluation v1.0: PolicySpec/Results → LegalReport + ChangeProposals (World artifacts)

Repo snapshot date: 2026-02-04

> Historical snapshot note: Repository-state statements describe the dated snapshot above; phase labels and completion criteria belong to that historical plan. They do not establish current E02 status or end-to-end functionality.

## 0) Phase goal

Add deterministic checks for “legality/compliance with norms” to `polisyos.lex`:

- **Input**:
  - `PolicySpec` (or Trinity refs)
  - `SimulationResult` (Foundry output) + `Metrics` (if available)
  - `NormPack` (Phase 17 / E2.9)
  - `JurisdictionContext` (MVP = `jurisdiction` + `as_of`)
- **Output**:
  - `LegalReport` (structured findings + evidence references)
  - `ChangeProposal` (deterministic change proposals, minimal MVP)

**Write the result to Fabric strictly as “world artifacts”:**

- CAS artifacts:
  - `lex.legal_report`
  - `lex.change_proposal`
- - `WorldEvent(kind=evaluate_legality)` (IR `EventKind.EVALUATE_LEGALITY`)
- - PROV edges through `fabric.world.store.emit_world_event_facts(...)`

> No external calls (web/LLM/DB) and no random tie-breaks: the order and output are reproducible from the input artifacts.

---

## 1) Repository context (what already exists and is used)

### 1.1 The World Graph write path already exists (E2.2)

Source of truth:

- `policy-engine/src/polisyos/fabric/world/store/*`
  - `persist_world_event`, `emit_world_event_facts`
  - `stable_world_provenance_v1()` and `event_world_provenance_v1(event_id)`
  - `write_world_fact_segment(...)` + the `_segments.jsonl` index through `append_world_segment_index`
- IR contracts:
  - `policy-engine/src/polisyos/ir/world/event.py` (`EventKind.EVALUATE_LEGALITY` already exists)
  - `policy-engine/src/polisyos/ir/world/ids.py` (`world_event_id_from_payload`, `artifact_id_to_world_id`, `stable_world_id_from_canon`)

### 1.2 Lex can already assemble a NormPack (E2.9 / Phase 17)

Source of truth:

- `policy-engine/src/polisyos/lex/api.py` → `assemble_norm_pack(...)`
- `policy-engine/src/polisyos/lex/normpack/assemble_pack.py`
  - saves `NormPack` as `lex.norm_pack`
  - writes `WorldEvent(kind=assemble_norm_pack)`

Important for Phase 18:

- `NormRule.backend_metadata` already contains `predicate_id`, `value_text`, `value_decimal`, and `unit_id` (but not always `operator`—see §4.2)

### 1.3 Foundry `SimulationResult`/`Metrics` contracts already exist

- `policy-engine/src/polisyos/core/contracts/foundry.py`:
  - `SimulationResult(exec_plan_ref, metrics_ref, …)`
  - `Metrics(values: dict[str, int|str])`

### 1.4 Trinity/PolicySpec contracts already exist

- `PolicySpec` (IR): `policy-engine/src/polisyos/ir/policy_spec.py`
- Trinity typed refs: `policy-engine/src/polisyos/core/contracts/trinity.py`

### 1.5 Lex refs are already present in the ABI (but their payload is outdated relative to E2.10)

- `policy-engine/src/polisyos/core/contracts/lex.py` already contains:
  - `LegalReportRef(kind="lex.legal_report")`
  - `ChangeProposalRef(kind="lex.change_proposal")`

Phase 18 introduces a **new payload format** for these artifacts (see §6–§7).

---

## 2) Deliverables (code/docs)

### 2.1 New Lex package: Legal Evaluation v1.0

Recommended location (minimal surface area; matches the deliverable names):

```text
policy-engine/src/polisyos/lex/legal_evaluation/
  __init__.py
  context_builder.py
  evaluate.py
  change_proposals.py
  backends/
    __init__.py
    simple_v1.py
```

### 2.2 Update the public Lex API

```text
policy-engine/src/polisyos/lex/api.py
  + evaluate_legality(...)
  + propose_changes(...)
```

and optionally export from:

```text
policy-engine/src/polisyos/lex/__init__.py
```

### 2.3 Scientist bridge (critical)

Add a built-in node:

```text
policy-engine/src/polisyos/scientist/nodes/builtins/governance/legal_check.py
```

and export it from `policy-engine/src/polisyos/scientist/nodes/builtins/governance/__init__.py`.

### 2.4 Tests

New file:

```text
policy-engine/tests/unit/fabric/test_legal_evaluation_phase18.py
```

### 2.5 Contract document

This file:

```text
policy-engine/docs/contracts/E2_10_LEX_LEGAL_EVALUATION_V1_0.md
```

---

## 3) Input contract (MVP): `LegalEvaluationRequest`

### 3.1 Where to define it

Requirement from the source specification (quoted verbatim): “в `lex.py` (если уже есть; иначе в `types.py`)” (“in `lex.py` (if it already exists; otherwise in `types.py`)”).

The repository already has an ABI file:

```text
policy-engine/src/polisyos/core/contracts/lex.py
```

Therefore, the Phase 18 rule is:

- add `LegalEvaluationRequest` to `polisyos.core.contracts.lex`
- use it in `polisyos.lex.api.evaluate_legality(...)`

### 3.2 Schema (Pydantic, `extra=forbid`)

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

### 3.3 Normalization and validation (deterministic)

In `polisyos.lex.legal_evaluation.evaluate._normalize_request(...)`:

1. `jurisdiction_norm = request.jurisdiction.strip().casefold()`
   - must match `ID_PATTERN` (`polisyos.ir.kernel.base.ID_PATTERN`)

2. `as_of_norm = normalize_as_of(request.as_of)` (copy the semantics from Lex NormPack / E2.9):
   - accepts `YYYY-MM-DD` or ISO datetime
   - returns exactly `YYYY-MM-DD`
   - date semantics = “date_inclusive”

3. Exactly‑one policy input source:
   - if `trinity_bundle_ref` is set:
     - allow `policy_spec_ref/model_spec_ref` to be `None` and read them from the bundle
   - if `trinity_bundle_ref` is not set:
     - `policy_spec_ref` is required

4. `norm_pack_ref.kind` must be `"lex.norm_pack"` (otherwise `LexValidationError`)
5. `eval_policy_id` must match `ID_PATTERN` (and be on the MVP allowlist)

> MVP rule: a missing `model_spec_ref` does **not** block evaluation (it is used only as report metadata).

---

## 4) Details of “what counts as a rule” (MVP semantics)

### 4.1 Norm: how to extract `predicate_id`, `operator`, `expected_value`, and `unit_id` from `NormRule`

In Phase 18, do **not** change IR `NormRule` (that is the Phase 3 contract); use `NormRule.backend_metadata` as the carrier:

Minimum required keys for rule-by-rule evaluation:

- `predicate_id: str` (ID_PATTERN)
- `operator: str` ∈ `{ "<", "<=", "=", ">=", ">" }`
- `value_decimal: str | None` (Decimal‑string)
- `value_text: str` (for enum/text comparisons and as a fallback)
- `unit_id: str | None` (ID_PATTERN, canonical unit id)

### 4.2 Required supporting change to Phase 17 (mandatory for numeric PASS/FAIL)

Currently, `polisyos.lex.normpack.assemble_pack.claims_to_norm_rules(...)` loses `operator`, although the `lex_norm_regex_v1` extractor puts it in:

- `Claim.qualifiers["op"]`
- `Claim.props["lex"]["operator"]`

For the Phase 18 MVP, do the following:

- in `claims_to_norm_rules(...)`, add:
  - `operator = claim.props["lex"]["operator"]` if present, otherwise `claim.qualifiers["op"]`
  - write `NormRule.backend_metadata["operator"] = operator`

If `operator` is missing:

- finding = `UNKNOWN` (or `FAIL` when `strict=True`)
- quality_issue: `missing_operator`

---

## 5) `LegalContextBuilder` (deterministic)

### 5.1 Purpose

`LegalContextBuilder` builds a “minimal fact layer” for rule evaluation:

- loads all input artifacts from CAS
- computes an **ObservedValue** for each `NormRule`:
  - from `SimulationResult.metrics` (preferred)
  - otherwise from `PolicySpec` parameters/slots
- normalizes types and units (MVP)
- records quality issues

### 5.2 Location and API

File: `policy-engine/src/polisyos/lex/legal_evaluation/context_builder.py`

```python
from dataclasses import dataclass
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.lex import LegalEvaluationRequest
from polisyos.ir.loading.norm_pack import NormPack, NormRule
from polisyos.ir.governance.policy_spec import PolicySpec
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

Loading rule (all inputs through CAS, no DB):

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

Errors:

- artifact missing from CAS → `LexNotReadyError` (stage=`not_ready`)
- invalid payload → `LexValidationError` (stage=`validation`)

### 5.4. Applicability (MVP)

Use the existing function:

- `polisyos.lex.normpack.applicability.applies_to_context(applicability, jurisdiction_norm, as_of_norm)`

If `applies=False`:

- finding.status = `NOT_APPLICABLE`
- `observed` is not required
- do not add quality issues (this is not a quality problem)

### 5.5 Map `predicate_id` to an observed value (deterministic)

#### 5.5.1 From metrics (preferred)

Algorithm:

1. `predicate_id = rule.backend_metadata["predicate_id"]`
2. if `metrics` exists and `predicate_id in metrics.values`:
   - `raw = metrics.values[predicate_id]`
   - `ObservedValue.source_kind="metrics"`
   - `ObservedValue.metric_key = predicate_id`
   - `ObservedValue.metrics_ref = simulation_result.metrics_ref.artifact_id`
   - `ObservedValue.simulation_result_ref = request.simulation_result_ref.artifact_id`

Parsing:

- if `raw` is `int` → numeric, `value_decimal=str(raw)`
- if `raw` is `str`:
  - try `Decimal(raw)` (through a safe parser, without floats)
    - success → numeric
    - otherwise → text

`unit_id` for metrics in the MVP:

- `None` (if there is no separate unit registry/descriptor)

If the value is not recognized:

- observed.value_kind="text"
- observed.value_text=raw.strip()

#### 5.5.2. From `PolicySpec` parameters (fallback)

The MVP supports two paths (both deterministic):

**A) ParameterSpec param_id == predicate_id (preferred):**

1. build an index: `param_id -> ParameterSpec`
2. if a `ParameterSpec` is found:
   - find `InterventionSpec` by `intervention_id`
   - read the value from `intervention.params` using `param_path`:
     - `param_path` is a dot path; support:
       - `"foo"` → `params["foo"]`
       - `"foo.bar"` → `params["foo"]["bar"]` (dict nesting only)

JSON pointer for the patch:

- `/interventions/<idx>/params/<foo>/<bar>/...`
- `<idx>` — intervention index in the array (deterministic order from `PolicySpec`)

**B) Direct params key == predicate_id (fallback):**

1. find every `(intervention_index, intervention_id, value)` where `predicate_id in intervention.params`
2. if exactly one match is found, use it
3. if more than one is found, the mapping is ambiguous:
   - observed = None
   - quality_issue: `ambiguous_policy_mapping`

Parse `ParamValue` (MVP):

- `bool` → boolean
- `int` → numeric
- `str`:
  - try Decimal parsing → numeric, otherwise text
- `dict`/`BaseModel`:
  - not supported in the MVP (`UNKNOWN`/`FAIL` depending on `strict`)
  - quality_issue: `unsupported_policy_value_type`

`unit_id` for `PolicySpec` (MVP):

- if the value from `PolicySpec` has no unit → `None`
- if it is a `RateValue`/`MoneyValue`/… (when represented as a dict) → not supported in the MVP

#### 5.5.3. No mapping

If no value is available from either metrics or policy:

- observed = None
- quality_issue: `missing_observed_value`
- finding.status:
  - `UNKNOWN` when `strict=False`
  - `FAIL` when `strict=True` (with severity = BLOCKER)

### 5.6. Unit normalization (MVP)

The MVP supports only:

- `percent` ↔ `ratio`
- `m` ↔ `km`

Order:

1. determine `expected_unit_id` from `rule.backend_metadata["unit_id"]`
2. determine `observed_unit_id` from `ObservedValue.unit_id`
3. if either `unit_id` is `None`:
   - quality_issue: `missing_unit`
   - status: `UNKNOWN` or `FAIL` depending on `strict`

4. if `expected_unit_id == observed_unit_id` → OK
5. otherwise, try to convert:
   - percent→ratio: `x/100`
   - ratio→percent: `x*100`
   - km→m: `x*1000`
   - m→km: `x/1000`

6. if conversion is not possible:
   - quality_issue: `unit_mismatch`
   - status: `UNKNOWN` or `FAIL` depending on `strict`

> Conversion is performed **only** for numeric observed/expected values.

### 5.7. Determinism and ordering

Build a `RuleObservation` for each rule, with this strict ordering:

- `rules_sorted = sorted(norm_pack.norms, key=lambda r: r.norm_id)`
- within one rule:
  - sort citations by `provision_id`, then `citation.doc.doc_id`, then `fragment_id`

---

## 6) Evaluation backend v1 (simple, rule‑by‑rule)

### 6.1. Statuses and types (MVP)

Finding statuses:

- `PASS`
- `FAIL`
- `UNKNOWN`
- `NOT_APPLICABLE`

Observation types:

- numeric (Decimal-string)
- boolean
- enum/text (strict equality after normalization)

Operators (MVP):

- `<, <=, =, >=, >` (numeric)
- `=` (boolean/text; others → `UNKNOWN`/`FAIL` depending on `strict`)

### 6.2. Location and API

Files:

- `policy-engine/src/polisyos/lex/legal_evaluation/evaluate.py` — orchestration
- `policy-engine/src/polisyos/lex/legal_evaluation/backends/simple_v1.py` — backend

Backend interface (internal, MVP):

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

### 6.3. `simple_v1` algorithm (per rule)

Pseudocode:

1. if `applies=False` → `NOT_APPLICABLE`
2. if `observed is None`:
   - `UNKNOWN` or `FAIL` depending on `strict`

3. otherwise:
   - extract `operator`, `expected_value_decimal/value_text`, `expected_unit_id`
   - coerce the observed value to the required type:
     - numeric: a Decimal string is required
     - boolean: `value_text` ∈ {"true","false"} (casefold)
     - text: normalize = `collapse_ws(strip()).casefold()` (MVP)
   - apply the operator:
     - numeric: compare Decimal
     - boolean/text: `=` only

4. severity mapping (MVP):
   - PASS / NOT_APPLICABLE → `"info"`
   - `UNKNOWN` → `"warning"` (or `"blocker"` when `strict=True`)
   - FAIL → `"blocker"` (MVP default)

### 6.4. Deterministic finding order

In `evaluate.evaluate_legality_impl(...)`:

- sort findings by `rule_id` (strict lexicographic string order)

---

## 7) `LegalReport` artifact (v1.0 structure)

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
    "policy_spec_ref": {
      "artifact_id": "sha256:...",
      "kind": "ir.policy_spec"
    },
    "model_spec_ref": { "artifact_id": "sha256:...", "kind": "ir.model_spec" },
    "simulation_result_ref": {
      "artifact_id": "sha256:...",
      "kind": "foundry.simulation_result"
    },
    "norm_pack_ref": { "artifact_id": "sha256:...", "kind": "lex.norm_pack" },
    "eval_policy_id": "lex.eval.simple_v1",
    "strict": true
  },
  "summary": {
    "counts": { "pass": 3, "fail": 1, "unknown": 2, "not_applicable": 5 },
    "compliance_grade": "fail"
  },
  "findings": [
    {
      "rule_id": "claim.sha256_...",
      "status": "FAIL",
      "severity": "blocker",
      "norm_citations": [
        {
          "provision_id": "frag.sha256_...",
          "citations": [
            /* CitationRef */
          ]
        }
      ],
      "observed_evidence_refs": [
        {
          "kind": "policy_param",
          "policy_json_pointer": "/interventions/0/params/speed_limit"
        }
      ],
      "observed_value": "70",
      "expected": { "op": "<=", "threshold": "60", "unit": null },
      "rationale": {
        "predicate_id": "speed_limit",
        "mapping": { "source": "policy_param", "notes": ["..."] },
        "comparison": {
          "left": "70",
          "op": "<=",
          "right": "60",
          "result": false
        }
      }
    }
  ],
  "quality_issues": [
    {
      "code": "missing_observed_value",
      "rule_id": "claim.sha256_...",
      "details": { "predicate_id": "kpi.xxx" }
    }
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

Deterministic rule:

- if `fail > 0` → `"fail"`
- otherwise, if `unknown > 0`:
  - `strict=True` → `"fail"`
  - `strict=False` → `"partial"`
- otherwise → `"pass"`

---

## 8) `ChangeProposal` artifact (v1.0 structure, deterministic)

### 8.1. CAS kind + schema

- kind: `lex.change_proposal`
- schema: `SchemaInfo(name="polisyos.lex.ChangeProposal", version="1.0")`
- media_type: `application/json`

### 8.2. Payload (v1.0)

```json
{
  "schema_version": "1.0",
  "based_on_report_ref": {
    "artifact_id": "sha256:...",
    "kind": "lex.legal_report"
  },
  "actions": [
    {
      "action_kind": "policy_patch",
      "target_ref": { "artifact_id": "sha256:...", "kind": "ir.policy_spec" },
      "patch_format": "json_patch_v1",
      "patch_json": [
        {
          "op": "replace",
          "path": "/interventions/0/params/speed_limit",
          "value": "60"
        }
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

### 8.3. Generation policy (MVP)

In `polisyos.lex.legal_evaluation.change_proposals.propose_changes_v1(...)`:

1. For each finding with status `FAIL`:
   - if `observed.source_kind == "policy_param"` and `policy_json_pointer` is present:
     - if an expected numeric threshold is defined:
       - generate a JSON Patch `replace` for `policy_json_pointer`
       - patch value:
         - `<=`, `>=`, or `=` → threshold
         - `<` → threshold - epsilon
         - `>` → threshold + epsilon
       - epsilon is deterministic:
         - if the threshold has a decimal part → `10^exponent` (using the Decimal exponent)
         - otherwise, `1`

2. For `missing_observed_value`:
   - action_kind=`add_metric`
   - metric_id = predicate_id
   - metric_type = inferred from expected (numeric/boolean/text)

3. Otherwise:
   - do not generate `model_patch`/`legal_change_request` in the MVP (reserved)

Determinism:

- sort actions:
  - `policy_patch` first, then `add_metric`, then the rest
  - within each kind, by `links_to_findings[0]` (`rule_id`), then by `path/metric_id`

---

## 9) Persist to the World Graph (through `world.store` only)

### 9.1. CAS persist

In `polisyos.lex.legal_evaluation.evaluate.evaluate_legality_impl(...)`:

1. Persist `LegalReport`:
   - `cas.put_json(payload, PutOptions(kind="lex.legal_report", ...))`

2. Persist `ChangeProposal` (if requested / if there are actions):
   - `cas.put_json(payload, PutOptions(kind="lex.change_proposal", ...))`

Inputs (`InputRef`) for `LegalReport` (recommended):

- roles = `policy_spec`, `simulation_result`, `metrics`, `norm_pack`, and optionally `model_spec`

Inputs for `ChangeProposal`:

- role=`legal_report` (required)
- role=`policy_spec` (when `policy_patch` is present)

### 9.2. Semantic artifact nodes (CAS → world)

For each output artifact:

- world_id = `artifact_id_to_world_id(prefix="artifact", artifact_id=...)`
- facts = `emit_world_node_facts(kind=NodeKind.ARTIFACT, artifact_id=..., provenance=stable_world_provenance_v1())`

### 9.3. WorldEvent(kind=evaluate_legality)

Schema:

- `WorldEvent.event_kind = EventKind.EVALUATE_LEGALITY`
- agent:
  - `agent_id="prov.agent.lex_legal_eval"`
  - `agent_type=ProvAgentType.SYSTEM`
  - `label="Lex Legal Evaluation"`
- activity:
  - `activity_id="prov.activity.lex_legal_eval.evaluate"`
  - `activity_type=ProvActivityType.EVALUATE_LEGALITY`
  - `label="Evaluate legality"`

inputs (minimum):

- `policy_spec` (world_id or artifact_id)
- `simulation_result` (world_id or artifact_id)
- `norm_pack` (world_id or artifact_id)
- optionally, `model_spec`
- optionally, `metrics` artifact_id

outputs:

- legal_report world_id
- `change_proposal` world_id (if created)

event_id:

- compute it through `world_event_id_from_payload(...)` with a payload that excludes runtime fields

Then:

- `persist_world_event(cas, event)`
- `emit_world_event_facts(event, event_artifact_id, provenance=event_world_provenance_v1(event_id))`
- `write_world_fact_segment(facts, segment_name="lex_legal_evaluate")`
- `append_world_segment_index(...)`

> MVP: do not introduce separate `NodeKind`s `legal.report`/`legal.change_proposal`; artifact nodes + PROV are sufficient.

---

## 10) Lex public API (Phase 18)

File: `policy-engine/src/polisyos/lex/api.py`

Add:

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

Phase 18 rule:

- `evaluate_legality(...)` creates **both the report and proposals** (MVP), so they are available through “one call.”
- `propose_changes(...)` is an optional separate step (for example, later for different policies).

Return: `(report_ref, proposals[])`, where `proposals[]` may be empty.

---

## 11) Scientist bridge: builtin node `legal_check.py`

### 11.1 Location

```text
policy-engine/src/polisyos/scientist/nodes/builtins/governance/legal_check.py
```

### 11.2. State contract (MVP)

The Node reads:

- `state.inputs["trinity_bundle_ref"]` (optional) or `state.inputs["policy_spec_ref"]`
- `state.artifacts_index["simulation_result_ref"]` (required)
- `state.inputs["norm_pack_ref"]` (optional)
- `state.params["jurisdiction"]` (required for Phase 18)
- `state.params["as_of"]` (required; ISO)
- `state.params["strict_legal"]` (optional, default `True`)

The Node writes:

- `state.reports_index["legal_report_ref"] = <LegalReportRef>`
- `state.reports_index["change_proposal_ref"] = <ChangeProposalRef>` (first or aggregated; MVP = first)

### 11.3. Behaviour

1. If `norm_pack_ref` is missing:
   - assemble it through `polisyos.lex.api.assemble_norm_pack(...)` (Phase 17)
   - put it in `state.inputs["norm_pack_ref"]`

2. Build `LegalEvaluationRequest`:
   - jurisdiction/as_of from params
   - refs from state

3. Call `polisyos.lex.api.evaluate_legality(...)`
4. Put the refs in state
5. Gate outcome:
   - if `strict=True` and `report.summary.compliance_grade != "pass"` → `NodeOutcome.status="error"`, or `"ok"` + a warning event (the choice depends on workflow policy)
   - MVP recommendation: `NodeOutcome.status="ok"`; the next governance node handles gating.

> Important: writing world facts requires the Node to have `fact_log_root`. MVP rule: use `Path(ctx.store.root).parent` (as in Lex Corpus) or pass it explicitly through node params.

---

## 12) Tests (required)

File: `policy-engine/tests/unit/fabric/test_legal_evaluation_phase18.py`

### 12.1. Unit tests

1. `simple_v1` evaluator:
   - numeric PASS/FAIL for `<,<=,=,>=,>`
   - UNKNOWN when `operator`/`value` is missing

2. Mapping:
   - `predicate_id` → metrics.value
   - fallback → policy param
   - deterministic tie-break / ambiguous mapping → quality issue

### 12.2. Integration test (end‑to‑end)

Minimum fixture:

- `PolicySpec` (CAS):
  - one intervention with `params={"speed_limit": "70"}`
  - `ParameterSpec(param_id="speed_limit", intervention_id=..., param_path="speed_limit")`
- `Metrics` (CAS):
  - `values={"accident_rate": "0.03"}`
- `SimulationResult` (CAS):
  - `metrics_ref` to a metrics artifact
- `NormPack` (CAS):
  - 2 `NormRule`:
    - PASS rule: predicate_id="accident_rate" op "<=" threshold "0.05"
    - FAIL rule: predicate_id="speed_limit" op "<=" threshold "60" (maps to policy)
  - `provision_refs`/citations must point to `doc.fragment` IDs (synthetic ones are allowed)

Pipeline:

1. `evaluate_legality(...)` → obtain `LegalReportRef` + `ChangeProposalRef`
2. `materialize_world_duckdb_from_fact_log(tmp_path, db, cas)`
3. asserts:
   - CAS artifact `lex.legal_report` exists
   - CAS artifact `lex.change_proposal` exists
   - `world.world_events` contains an entry with `activity_id='prov.activity.lex_legal_eval.evaluate'`
   - `report.findings` contains references to provision fragments (citations)
   - the change proposal contains a JSON Patch that “fixes” the failing rule

---

## 13) DoD (Phase 18)

Complete when:

1. Lex produces a reproducible `LegalReport` and `ChangeProposal(s)` from `policy+results+norms` (without external calls).
2. `LegalReport` and `ChangeProposal` are stored in CAS with the correct kinds.
3. A `WorldEvent(kind=evaluate_legality)` + PROV edges appears in the world fact log and is materialized in DuckDB (`world.world_events`).
4. `test_legal_evaluation_phase18.py` passes end-to-end and checks artifacts + the world event + key report/proposal fields.

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                                            |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 5 governance/frontier contract and Phase 4 world-event interoperability                                                                       |
| Contract tests      | `tests/unit/fabric/test_legal_evaluation.py`, `tests/unit/scientist/nodes/test_legal_check_node.py`, `tests/unit/scientist/governance/test_legal_pass.py` |
| Schema snapshots    | `schemas/snapshots/ir/policy_spec.schema.json`, `schemas/snapshots/ir/norm_pack.schema.json`, `schemas/snapshots/ir/world_event.schema.json`              |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                                    |
