# E1.3 (Phase 3) — IR ABI Stabilization: Citations + Norm Applicability + Trinity→Registry Linker

**Repo snapshot date**: 2026-02-03  
**Scope**: `policy-engine/src/polisyos/ir/*` (IR contract plane only)

## 0) Goal (why this phase exists)

Bring the IR contract layer to an ABI-grade state so that other subsystems can reliably build on it without re-inventing formats:

1. **Norms are citation‑grade**: any `NormRule` can reference an exact source fragment (document → version → fragment / anchor/offset) without embedding the source text.
2. **Norm applicability is declarative data**: jurisdiction/time window + subject/object + exceptions/conditions are represented as serializable structures (no evaluation engine inside IR).
3. **Trinity can be linked to registries contractually**: IR provides a pure, deterministic `link_trinity()` contract that produces a linked result + a structured `LinkReport` with stable issue codes and precise paths.
4. **Legacy policy is frozen**: legacy namespaces remain only as input formats and shims; new functionality must not land in legacy.

## 1) Non-goals (explicitly out of scope)

This phase **does not** implement:

- Any legal reasoning engine (Lex backend), expression evaluation, crawling, document storage, Scholar pipelines, Fabric world graph, or I/O.
- Any Foundry compiler/executor changes.
- Any network calls or CAS reads/writes during linking.

IR remains a **pure contract/kernel** with deterministic, side-effect-free operations.

## 2) Current repository state (what exists now)

### 2.1 Norms today

- `polisyos.ir.norm_pack` defines:
  - `NormPack`, `NormRule`, `NormRef`, `RuleType`  
  - `Applicability` is currently **underspecified** and embedded in `norm_pack.py`.  
  - `NormRef` is **not citation-grade**: it stores `source_document: str` + optional `version: str`.
  - IR includes `parse_expr_syntax()` which only does `ast.parse(..., mode="eval")` (good: IR does not import Scientist backends).

Files:
- `policy-engine/src/polisyos/ir/norm_pack.py`
- Documentation: `policy-engine/src/polisyos/ir/README.md` section “NormPack”

### 2.2 Trinity today

- Canonical Trinity artifacts exist:
  - `ProblemFrame` (`problem_frame.py`)
  - `PolicySpec` (`policy_spec.py`)
  - `ModelSpec` (`model_spec.py`)
  - `TrinityBundle` container (`trinity/__init__.py`)

### 2.3 Linker today

- `polisyos.ir.linker` is currently **legacy-surface oriented**:
  - `link_policy(policy: PolicySurfaceIR, mechanism_registry, ...) -> LinkReport`
  - Report types: `LinkReport`, `LinkIssue` (free-form `code: str`)
  - It validates params, units, slots, selector fields, constraints, merge rules for `PolicySurfaceIR`.

File:
- `policy-engine/src/polisyos/ir/linker.py`

### 2.4 Registry bundle contracts exist (useful for E1.3)

- `polisyos.ir.registry_fragments` defines `RegistryBundle`, plus `ActorRegistry`, `ConceptRegistry`, `GeoRegistry`, `TimeAxisRegistry`, and fragment composition utilities.

File:
- `policy-engine/src/polisyos/ir/registry_fragments.py`

This is the **correct** IR-level “registries bundle” type for `link_trinity()` (pure input).

### 2.5 Legacy namespace policy already partially in place

- Legacy format lives under `polisyos.ir.legacy.*`.
- `polisyos.ir.surface` is a shim re-exporting legacy `PolicySurfaceIR`.
- Loaders already support legacy→Trinity migration: `polisyos.ir.loaders`, `polisyos.ir.legacy.migrations.*`.

## 3) Deliverables (what must exist after E1.3)

### 3.1 New IR modules (contracts)

1. `polisyos/ir/citations.py`
   - Unified citation/source reference primitive (document → version → fragment/anchor/offset).
2. `polisyos/ir/applicability.py`
   - Declarative applicability structures for norms (jurisdiction/time + subject/object + exceptions/conditions).
3. `polisyos/ir/linker/` package (replace `linker.py` module)
   - `reports.py`: stable `LinkIssue`/`LinkReport` contracts (issue code enums, stable fields)
   - `link_trinity.py`: pure contract `link_trinity()`
   - `legacy_surface.py`: legacy `link_policy()` (moved, deprecated)
   - (optional) `types.py`: shared helpers for paths/ids/bindings

### 3.2 Updated contracts

4. Update `polisyos/ir/norm_pack.py`:
   - Adopt `CitationRef` and `NormApplicability` (from new modules).
   - Keep backward compatibility for legacy `NormRef.source_document/version` but mark deprecated.

### 3.3 Documentation + deprecation markers

5. Update docs (minimum):
   - `policy-engine/src/polisyos/ir/README.md`:
     - Mark legacy sections as deprecated (surface IR, legacy linker).
     - Document new citations/applicability/link_trinity.
   - Add/Update schema snapshots as needed (optional but recommended for ABI stability).

## 4) Work 3.1 — Citation primitives (Lex/Scholar/Fabric speak one format)

### 4.1 Contract requirements

The IR citation primitive MUST:

- Represent a reference to a **specific source fragment** without embedding the fragment text.
- Be reconstructible by later systems:
  - identify the **document**
  - identify the **document version**
  - identify the **fragment** (explicit id) or **locator** (anchor/path/offset/page range)
- Allow attaching **evidence/provenance by reference** (artifact ids), but not embed evidence payloads or source text.
- Be stable and safe:
  - `extra="forbid"`, `frozen=True` (via `KernelModel`)
  - no floats (deep) in arbitrary dicts; use explicit string/int/bool; allow `Decimal` where already used in IR.

### 4.2 Proposed file: `polisyos/ir/citations.py`

#### 4.2.1 Types

- `AnchorKind`: enum of supported anchor kinds (minimum set):
  - `article`, `section`, `clause`, `paragraph`, `page`, `table`, `figure`, `heading`, `chunk`, `other`
- `FragmentLocator`: declarative pointer *within a specific document version*:
  - `anchor_kind: AnchorKind`
  - `anchor_path: str | None` (human + machine-readable label; e.g. `"Art.126(2)(b)"`, `"§3 p.2"`)
  - `offset_start: int | None`, `offset_end: int | None` (character offsets in canonical normalized text)
  - `page_start: int | None`, `page_end: int | None` (for paginated docs/PDF)
  - Validation:
    - At least one locator method must exist:
      - `anchor_path` OR (`offset_start` and `offset_end`) OR (`page_start` and `page_end`)
    - If offsets present: `offset_end >= offset_start`
    - If page range present: `page_end >= page_start`
- `DocumentRef` (document identity + version binding):
  - `doc_id: str` (pattern: `polisyos.ir.kernel.base.ID_PATTERN`)
  - `doc_version_id: str | None` (pattern: `ID_PATTERN`) — **preferred** for ABI compatibility with Fabric/WorldGraph ids
  - `doc_version_ref: str | None` (pattern: `ARTIFACT_ID_PATTERN`) — optional CAS artifact ref for the version payload
  - Validation:
    - For citation-grade fragment locations, at least one of `doc_version_id`/`doc_version_ref` MUST be present.
    - `doc_id` is always required (even if only version is known).
- `CitationRef` (the actual reusable citation primitive):
  - `doc: DocumentRef`
  - `fragment_id: str | None` (pattern: `ID_PATTERN`) — if a fragment is already registered/minted
  - `locator: FragmentLocator | None` — if fragment isn’t minted yet or when additional verification is desired
  - `text_hash: str | None` (pattern: `ARTIFACT_ID_PATTERN`) — sha256 hash of the fragment text (NOT the text itself)
  - `quote_hash: str | None` (pattern: `ARTIFACT_ID_PATTERN`) — optional hash of a specific quote selection
  - `evidence_ref: str | None` (pattern: `ARTIFACT_ID_PATTERN`) — optional EvidenceBundle artifact id
  - `provenance_ref: str | None` (pattern: `ARTIFACT_ID_PATTERN`) — optional ProvenanceGraph artifact id
  - `notes: list[str]`
  - `props: dict[str, Any]` (free-form, no floats deep)
  - Validation:
    - Must have either `fragment_id` or `locator` (or both)
    - If `locator` is present, then `doc.doc_version_id` or `doc.doc_version_ref` MUST be present
    - If both `fragment_id` and `locator` are present, they must refer to the same fragment *logically* (IR does not verify; consumer may).

#### 4.2.2 JSON example

```json
{
  "schema_version": "1.0",
  "doc": {
    "schema_version": "1.0",
    "doc_id": "lex.treaty_tei",
    "doc_version_id": "docv.sha256_0123abcd",
    "doc_version_ref": "sha256:0123abcd0123abcd0123abcd0123abcd0123abcd0123abcd0123abcd0123abcd"
  },
  "locator": {
    "schema_version": "1.0",
    "anchor_kind": "article",
    "anchor_path": "Art. 126",
    "offset_start": 10420,
    "offset_end": 10710
  },
  "text_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "evidence_ref": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

### 4.3 Integration points (where citations must be used)

#### 4.3.1 Norms (E1.3 scope)

Norm packs MUST be able to include citation-grade references to provisions.

- `NormRule` should carry citations via `NormRef`/`NormCitation` (see §6).

#### 4.3.2 Optional adoptions (out of strict E1.3 scope, but enabled by this design)

- `ModelSpec.AssumptionSpec.source: str | None` should be deprecated in favor of `citations: list[CitationRef]`.
- Foundry `MethodMetadata.citations: tuple[str, ...]` may remain a human-facing bibliography list, but can be optionally augmented with `CitationRef` later.

## 5) Work 3.2 — Norm applicability as data (not an engine)

### 5.1 Contract requirements

Applicability contract MUST:

- Be **fully declarative** and serializable.
- Express (minimum):
  - jurisdiction (1..N)
  - time window (valid_from/valid_to)
  - subject/object selectors (actors/concepts)
  - conditions and exceptions
- Be **computable later** by a Lex backend:
  - IR does not interpret or execute conditions.
  - IR only provides a stable structure for those conditions.

### 5.2 Proposed file: `polisyos/ir/applicability.py`

#### 5.2.1 Building blocks

- `TimeWindow`
  - `valid_from: str | None` (ISO-8601 date/time recommended)
  - `valid_to: str | None`
  - Validation: if both set, `valid_to >= valid_from` (lexicographic ISO ordering is acceptable if strict ISO).

- `IdSelector`
  - Purpose: express AND/OR/NOT constraints without inventing a general expression language.
  - Fields:
    - `any_of: list[str]` (set OR; empty means unconstrained)
    - `all_of: list[str]` (set AND)
    - `none_of: list[str]` (set NOT)
  - Validation:
    - ids must match `ID_PATTERN`
    - no duplicates per list

- `ApplicabilityEntitySelector`
  - `actors: IdSelector` (actor_type ids; validated against `RegistryBundle.actors` when available)
  - `concepts: IdSelector` (concept ids; validated against `RegistryBundle.concepts` when available)

- `ConditionExpr`
  - Declarative, engine-agnostic expression envelope:
    - `language: str` (e.g. `"expr_ast"`, `"datalog"`, `"lex_rules_v1"`)
    - `expr: str` (non-empty)
    - `notes: list[str]`
    - `refs: dict[str, str]` (optional linkouts to external specs)
  - IR does not parse/evaluate it; Lex backend may.

#### 5.2.2 `NormApplicability` contract

```text
NormApplicability = (
  jurisdiction: IdSelector,
  time: TimeWindow,
  subject: ApplicabilityEntitySelector,
  object: ApplicabilityEntitySelector,
  conditions: list[ConditionExpr],
  exceptions: list[NormApplicability],
  notes: list[str],
)
```

Semantics (normative, required for consumers):

- A rule is applicable if:
  1. jurisdiction matches (`any_of/all_of/none_of`)
  2. time matches (intersection with context time; IR defines structure only)
  3. subject selector matches (context-defined)
  4. object selector matches (context-defined)
  5. all `conditions` evaluate to True (backend-defined by `language`)
  6. **none** of `exceptions` match (exceptions are treated as applicability blocks that negate applicability)

Notes:
- Context shape is owned by Lex backend; IR only defines data contract.
- For MVP, many fields can be empty → “unconstrained”.

#### 5.2.3 Example

```json
{
  "schema_version": "1.0",
  "jurisdiction": { "any_of": ["ua"], "all_of": [], "none_of": [] },
  "time": { "valid_from": "2024-01-01", "valid_to": null },
  "subject": { "actors": { "any_of": ["employer"], "all_of": [], "none_of": [] }, "concepts": { "any_of": [], "all_of": [], "none_of": [] } },
  "object": { "actors": { "any_of": ["employee"], "all_of": [], "none_of": [] }, "concepts": { "any_of": ["wage"], "all_of": [], "none_of": [] } },
  "conditions": [
    { "language": "expr_ast", "expr": "employment_status == 'employed'", "notes": [] }
  ],
  "exceptions": [
    {
      "schema_version": "1.0",
      "jurisdiction": { "any_of": ["ua"], "all_of": [], "none_of": [] },
      "time": { "valid_from": "2020-01-01", "valid_to": "2020-12-31" },
      "subject": { "actors": { "any_of": ["intern"], "all_of": [], "none_of": [] }, "concepts": { "any_of": [], "all_of": [], "none_of": [] } },
      "object": { "actors": { "any_of": [], "all_of": [], "none_of": [] }, "concepts": { "any_of": ["wage"], "all_of": [], "none_of": [] } },
      "conditions": [],
      "exceptions": [],
      "notes": ["Temporary internship exception"]
    }
  ],
  "notes": ["Wage floor applies to employers in UA since 2024"]
}
```

### 5.3 Applicability reference validation (small helper, still no “engine”)

Although applicability evaluation is out of scope for IR, **reference validation** (do ids exist?) is useful and should share the same `LinkReport` format.

Add a small pure helper (location choice: `polisyos.ir.linker` package, recommended):

```python
def validate_norm_applicability_refs(
    applicability: NormApplicability,
    registries: RegistryBundle,
    *,
    path_prefix: list[str | int],
) -> list[LinkIssue]:
    """
    - Checks concept ids against registries.concepts (if present)
    - Checks actor ids against registries.actors (if present)
    - Checks jurisdiction ids against registries.geo (if present)
    Emits LinkIssueCode.unknown_concept / unknown_actor / unknown_jurisdiction (additive).
    """
```

This is purely structural validation and keeps IR free of applicability semantics.

## 6) Norm contracts update (`polisyos.ir.norm_pack`)

### 6.1 Required changes

Update `NormRef` and `NormRule` to be compatible with citation primitives and applicability contract.

#### 6.1.1 `NormRef` (citation-grade)

Current:
- `provision_id`, `source_document`, `version`

Target:
- Keep `provision_id` (stable symbolic id for the provision; useful for legal corpus normalization)
- Add `citations: list[CitationRef]`
- Deprecate legacy fields:
  - `source_document: str | None` (DEPRECATED)
  - `version: str | None` (DEPRECATED)

Validation rules:
- For ABI v1 (migration-friendly):
  - At least one of these MUST be present:
    - `citations` is non-empty
    - OR `source_document` is provided (legacy)
- For citation-grade compliance (recommended, not enforced by IR unless a strict flag exists):
  - `citations` MUST be non-empty

#### 6.1.2 `NormRule.applicability`

Replace embedded `Applicability` in `norm_pack.py` with:
- `from polisyos.ir.applicability import NormApplicability`
- `NormRule.applicability: NormApplicability = Field(default_factory=NormApplicability)`

### 6.2 Backward compatibility strategy

No hard break is required if:

- `NormRef.source_document` stays accepted as optional deprecated input.
- Existing JSON/YAML payloads remain parseable because new fields are additive and legacy fields are still allowed.

### 6.3 Deprecation markers

At minimum:

- Update `policy-engine/src/polisyos/ir/README.md`:
  - mark legacy `NormRef.source_document/version` as deprecated
  - show new `CitationRef` usage

Optionally:
- Add `warnings.warn(..., DeprecationWarning)` when legacy fields are used **in helper/conversion code** (avoid warnings on pure model validation unless explicitly requested).

## 7) Work 3.3 — Linker contracts and reports (Trinity linking)

### 7.1 Contract requirements

Linker contracts MUST:

- Be **pure**: no I/O, no network, no CAS reads/writes, no global mutable state.
- Be **deterministic**: given the same Trinity + registries bundle, produce the same report and linked bindings.
- Produce **structured LinkReport/LinkIssue** with:
  - stable issue codes
  - severity
  - precise path to a Trinity field
  - stable identifiers for list items (intervention_id, objective_id, etc.)

### 7.2 Package restructure: `polisyos.ir.linker` becomes a package

Current:
- `polisyos/ir/linker.py` (single module)

Target:
- `polisyos/ir/linker/__init__.py`
- `polisyos/ir/linker/reports.py`
- `polisyos/ir/linker/link_trinity.py`
- `polisyos/ir/linker/legacy_surface.py`

Compatibility goal:
- Keep `from polisyos.ir.linker import LinkReport, LinkIssue, link_policy, link_trinity` working.

### 7.3 `LinkIssue` / `LinkReport` ABI

#### 7.3.1 Link severity

Define:
- `LinkSeverity = "error" | "warning" | "info"` (enum)

#### 7.3.2 Stable issue codes

Define `LinkIssueCode` enum (minimum ABI set required by E1.3):

- `unknown_unit`
- `unknown_concept`
- `missing_slot`
- `incompatible_constraint`

Recommended additional codes (align with existing linker behavior):

- `unknown_mechanism`
- `missing_param`
- `unknown_param`
- `param_type`
- `param_enum`
- `param_range`
- `unit_mismatch`
- `unknown_metric`
- `unknown_selector_field`
- `selector_scope_mismatch`
- `unknown_merge_rule`
- `merge_rule_conflict`
- `unknown_constraint`
- `unknown_actor` (for applicability refs)
- `unknown_jurisdiction` (for applicability refs)

Rule:
- Codes are stable ABI. Adding new codes is backward compatible. Renaming/removing codes is a breaking change.

#### 7.3.3 Path + identifiers

`LinkIssue` MUST carry:

- `path: list[str | int]`
  - Always starts with one of: `"problem_frame" | "policy_spec" | "model_spec"`
  - Uses indices for list positions.
- `ids: dict[str, str]`
  - Optional but strongly recommended for list items:
    - interventions: `{ "intervention_id": "..." }`
    - objectives: `{ "objective_id": "..." }`
    - constraints: `{ "constraint_id": "..." }`
  - This allows consumers to locate the problematic object even if list order changes.

#### 7.3.4 Issue payload shape

```text
LinkIssue = (
  severity: LinkSeverity,
  code: LinkIssueCode,
  message: str,
  path: list[str|int],
  ids: dict[str,str],
  data: dict[str,Any],
)
```

Guidelines for `data` (normative keys, per code):

- `unknown_unit`: `{ "unit_id": "...", "where": "param|slot|metric|constraint", "ref_id": "..." }`
- `unknown_concept`: `{ "concept_id": "...", "where": "norm_applicability|..." }`
- `missing_slot`: `{ "slot_id": "...", "where": "mechanism_reads|mechanism_writes|constraint|action_space" }`
- `incompatible_constraint`:
  - `{ "constraint_id": "...", "expected": "...", "actual": "...", "details": "..." }`

#### 7.3.5 LinkReport

`LinkReport` remains:

- `schema_version: "1.x"`
- `ok: bool` (`True` if no `severity="error"` issues)
- `issues: list[LinkIssue]`
- `notes: list[str]`

Optional:
- `stats` (counts by severity) can be added later; keep additive-only.

### 7.4 Pure function contract: `link_trinity()`

#### 7.4.1 Signature (normative)

```python
def link_trinity(
    bundle: TrinityBundle,
    registries: RegistryBundle,
    *,
    allow_extra_params: bool = False,
    strict: bool = True,
) -> tuple[LinkedTrinityBundle, LinkReport]:
    ...
```

Where:
- `TrinityBundle` is `polisyos.ir.trinity.TrinityBundle`
- `RegistryBundle` is `polisyos.ir.registry_fragments.RegistryBundle`
- `strict=True` means:
  - missing required registries produce `severity="error"` issues
  - “citation-grade required” checks (if added later) can be enforced only under strict mode

#### 7.4.2 Required registries for Trinity linking

For Trinity policies, the linker requires (by default):

- `registries.mechanisms` (required)
- `registries.slots` (required)
- `registries.merge_rules` (required if merge/schedule conflict checks enabled)
- `registries.units` (required for unit validation)
- `registries.metrics` (required if ProblemFrame objectives/KPIs used)
- `registries.selector_fields` (required if PolicySpec targets use selectors)
- `registries.constraints` (required if ProblemFrame constraints use constraint ids)

If any required registry is missing:
- emit `LinkIssue(code="incompatible_constraint" or dedicated "missing_registry")`  
  **Recommendation**: introduce `LinkIssueCode.missing_registry` as an additive improvement (allowed), but E1.3 minimum does not mandate it.

#### 7.4.3 Linked output type

Define `LinkedTrinityBundle` (IR contract, new):

- `schema_version: "1.0"`
- `bundle: TrinityBundle` (original input, unchanged)
- `registry_digest: str | None` (optional, `sha256:<hex>` of canonical registries bundle)
- `bundle_digest: str | None` (optional, `sha256:<hex>` of canonical bundle)
- `bindings: TrinityBindings` (derived “what is used / resolved”)

Define `TrinityBindings` (new):

- `schema_version: "1.0"`
- `interventions: list[LinkedIntervention]`
- `used_mechanisms: list[str]`
- `used_slots_read: list[str]`
- `used_slots_write: list[str]`
- `used_units: list[str]`
- `used_metrics: list[str]`
- `used_constraints: list[str]`
- `used_selector_fields: list[str]`

Define `LinkedIntervention`:

- `intervention_id: str`
- `mechanism_id: str`
- `reads_slots: list[str]`
- `writes_slots: list[str]`
- `schedule_start: int`
- `schedule_end: int`

Notes:
- These bindings are intentionally “thin”: they allow downstream compilation and provenance without embedding full registry specs.
- This is ABI-safe because it only depends on stable ids already in IR registries.

### 7.5 Trinity linking algorithm (detailed)

This section defines behavior precisely so different implementations match.

#### 7.5.1 Inputs

- `bundle.problem_frame`, `bundle.policy_spec`, `bundle.model_spec`
- `registries` (bundle of registries)

#### 7.5.2 Step A — PolicySpec interventions vs mechanism registry

For each `intervention` in `bundle.policy_spec.interventions`:

1. **Mechanism exists**
   - lookup `registries.mechanisms.mechanisms[intervention.kind]`
   - if missing:
     - emit `LinkIssue(code="unknown_mechanism", severity="error")`
     - `path=["policy_spec","interventions",i,"kind"]`
     - `ids={"intervention_id": intervention.intervention_id}`
     - continue (skip further checks for this intervention)

2. **Param validation**
   - for each `ParamSpec` in the mechanism:
     - if required and missing → `missing_param`
     - if present:
       - type checks (bool/string/object/array)
       - numeric coercions for validation (`Decimal`, `RateValue`, `MoneyValue`, `CountValue`, `DurationValue`, numeric strings)
       - range checks if `min_value/max_value` exist
       - enum checks if `enum_values` exist
     - unit checks:
       - if `param_spec.unit_id` exists:
         - if unit missing in `registries.units` → `unknown_unit`
         - if value is MoneyValue ensure currency matches MoneyUnit, else `incompatible_constraint` or a dedicated `money_currency_mismatch` code
   - if `allow_extra_params=False`:
     - any extra param keys produce `unknown_param` warnings/errors (severity policy is up to implementation; recommended `warning`)

3. **Slot usage**
   - compute `(reads_slots, writes_slots) = resolve_mechanism_slots(mech, intervention.params)`
   - for each slot_id in reads+writes:
     - if `registries.slots.slots` does not contain it:
       - emit `LinkIssue(code="missing_slot", severity="error", data={"slot_id": slot_id})`

4. **Selector field validation**
   - collect selector fields from `intervention.target` recursively
   - for each field:
     - if missing in `registries.selector_fields.fields`:
       - emit `LinkIssue(code="unknown_selector_field", severity="error")`
   - if selector fields span multiple scopes (per registry specs):
     - emit `selector_scope_mismatch`

5. **Schedule normalization for bindings**
   - use `schedule_range(intervention.schedule)` to compute `(start,end)`
   - store in `LinkedIntervention`

#### 7.5.3 Step B — ProblemFrame vs metric/units registries

1. Objectives:
   - for each `ObjectiveSpec.metric_id`:
     - if missing in `registries.metrics.metrics` → `unknown_metric` (severity error)
     - if metric has `unit_id` and unit missing → `unknown_unit`
2. KPIs:
   - same as objectives plus `KPISpec.unit_id` validation (if present)

#### 7.5.4 Step C — ProblemFrame constraints vs constraint/slot/unit registries

For each `ConstraintSpec`:

- If `ConstraintSpec.slot_id` is present:
  - validate slot exists (`missing_slot`)
  - if slot has a unit ref:
    - validate unit exists (`unknown_unit`)
- If `registries.constraints` exists and constraint_id is treated as a registry reference:
  - validate `constraint_id` exists, else `unknown_constraint` (severity error)
  - if registry spec defines `slot_id`:
    - ensure referenced slot exists (`missing_slot`)
  - if registry spec defines `unit_id`:
    - ensure unit exists (`unknown_unit`)
    - ensure constraint value is compatible (money currency, numeric types, etc.)
      - mismatch → `incompatible_constraint`

#### 7.5.5 Step D — Merge/schedule conflict checks

This is optional but recommended for parity with current legacy linker behavior.

If enabled (default):

- Build a map `slot_id -> list[interventions writing slot]`
  - Use `writes_slots` computed in Step A.
- For each `slot_id` with 2+ writers:
  - Determine if schedules overlap (`schedule_range`)
  - If no overlap → ok
  - If overlap:
    - read slot spec from `registries.slots.slots[slot_id]`
      - missing → `missing_slot`
    - read merge rule id from slot spec and resolve in `registries.merge_rules.rules`
      - missing → `unknown_merge_rule`
    - verify merge rule kind compatibility with slot value type if such constraint exists
      - conflict → `merge_rule_conflict` (severity error)

Notes:
- The exact merge compatibility rules should mirror `polisyos.ir.linker` legacy behavior:
  - SUM only for numeric/decimal slots
  - OVERRIDE allowed for most
  - etc. (re-use current logic and encode as stable issues)

#### 7.5.6 Step E — Build bindings + final report

- Collect:
  - `used_*` sets from validated interventions/objectives/constraints
  - `interventions` bindings list with resolved reads/writes + schedule ranges
- Compute optional digests:
  - `registry_digest = sha256(to_canonical_bytes(registries))`
  - `bundle_digest = sha256(to_canonical_bytes(bundle))`
- `ok = not any(issue.severity == "error" for issue in issues)`
- Return `(LinkedTrinityBundle(...), LinkReport(ok=ok, issues=issues, notes=...))`

### 7.6 Legacy linker policy (surface IR)

`link_policy()` for `PolicySurfaceIR` remains supported **only as legacy**:

- Move implementation to `polisyos.ir.linker.legacy_surface`.
- Re-export it from `polisyos.ir.linker` package for compatibility.
- Mark as deprecated in docs:
  - “Use `link_trinity()` for canonical Trinity.”
- No new functionality should be added to legacy linker beyond bug fixes and compatibility shims.

## 8) Work 3.4 — Legacy namespace policy (finalization)

### 8.1 What is “legacy” in this repo

Legacy namespace is everything that exists primarily for backwards compatibility:

- `polisyos.ir.legacy.*` (all)
- `polisyos.ir.surface` (shim re-export of legacy surface IR)
- `polisyos.ir.linker.link_policy` (surface IR linker)
- legacy Trinity v0 payloads (`polisyos.ir.legacy.trinity_v0`)

### 8.2 What stays (allowed)

Allowed in legacy:

- Input parsing / loading
- One-way or two-way migrations (legacy ↔ Trinity)
- Shims that map legacy fields to canonical equivalents
- Bug fixes that unblock loading/migration, security fixes

### 8.3 What is forbidden (policy)

Forbidden in legacy:

- New schema fields / new “features”
- New issue code semantics
- New business logic
- New canonical “source of truth”

All feature work must target canonical IR (Trinity, new citations/applicability, new linker).

### 8.4 Deprecation marking (minimum viable)

E1.3 requires at least **documentation-level** deprecation markers:

- In `policy-engine/src/polisyos/ir/README.md`:
  - mark `PolicySurfaceIR` and `link_policy()` as deprecated
  - point to `load_trinity()` + `link_trinity()`
- In `policy-engine/src/polisyos/ir/norm_pack.py` docs:
  - mark `NormRef.source_document/version` as deprecated; prefer `citations`

Optional (recommended):

- Add `DeprecationWarning` to shim functions (NOT during pure model validation).

## 9) Tests (contract-level)

### 9.1 New contract tests to add

Add under `policy-engine/tests/contract/` (preferred) or `policy-engine/tests/ir/`.

#### 9.1.1 Citations

`test_citations_contract.py`:

- Accepts:
  - fragment_id only (with doc_id; doc_version optional)
  - locator only (requires doc_version_id or doc_version_ref)
  - locator with offsets and/or anchor_path
- Rejects:
  - locator missing all location methods
  - offset_end < offset_start
  - page_end < page_start
  - `props` containing floats (deep) if float rejection is implemented (recommended)

#### 9.1.2 Applicability

`test_applicability_contract.py`:

- Validates:
  - ISO ordering constraint for `TimeWindow` if implemented
  - id selectors enforce `ID_PATTERN`
  - recursion depth sane (optional safeguard)

#### 9.1.3 Trinity linker

`test_trinity_linker_contract.py`:

- Unknown mechanism → `unknown_mechanism` error with stable path + ids
- Missing required param → `missing_param` error
- Unknown slot in mechanism reads/writes → `missing_slot` error
- Unknown selector field → `unknown_selector_field` error
- Unknown unit referenced by param spec → `unknown_unit` error
- Constraint mismatch (money currency mismatch, wrong type) → `incompatible_constraint` error

Note: tests should not require Foundry/Scientist imports; only IR + kernel registries.

### 9.2 Existing tests to keep passing

- Legacy linker tests in `policy-engine/tests/contract/test_surface_ir.py` should keep passing after moving `link_policy` into package form (import path compatibility).
- Scientist legal backend tests should keep passing if NormPack changes are additive (do not make citations mandatory in schema validation).

## 10) Implementation plan (step-by-step)

This section is the engineering breakdown for implementing E1.3.

### 10.1 Citations module

1. Add `polisyos/ir/citations.py`:
   - implement enums + models + validators
2. Add minimal tests for citation validation

### 10.2 Applicability module

1. Add `polisyos/ir/applicability.py`:
   - implement `TimeWindow`, `IdSelector`, `ApplicabilityEntitySelector`, `ConditionExpr`, `NormApplicability`
2. Add tests

### 10.3 NormPack migration

1. Update `polisyos/ir/norm_pack.py`:
   - import and use `NormApplicability`
   - update `NormRef` to support `citations: list[CitationRef]`
   - keep legacy `source_document/version` fields (optional) with docs marked deprecated
2. Update `policy-engine/src/polisyos/ir/README.md` NormPack examples

### 10.4 Linker package migration + Trinity linker

1. Replace `polisyos/ir/linker.py` with package `polisyos/ir/linker/`:
   - move existing code to `legacy_surface.py`
   - create `reports.py` with new stable contracts
   - create `link_trinity.py` implementing algorithm in §7.5
   - create `__init__.py` re-exporting both legacy and new entrypoints
2. Add contract tests for `link_trinity`
3. Update imports in repo to point to package form (should stay stable via re-exports)

### 10.5 Docs + schema snapshots (optional but recommended)

- Consider generating new schema snapshots for:
  - `polisyos.ir.norm_pack:NormPack`
  - `polisyos.ir.citations:CitationRef`
  - `polisyos.ir.applicability:NormApplicability`
  - `polisyos.ir.linker.reports:LinkReport`

If adding snapshots, document how to regenerate using:

```bash
python policy-engine/tools/gen_schema.py --model polisyos.ir.norm_pack:NormPack --output norm_pack_schema.json
```

## 11) Definition of Done (E1.3)

E1.3 is complete when all are true:

1. IR defines unified citation primitive (`polisyos.ir.citations`) that can express doc→version→fragment/anchor/offset and references evidence/provenance by artifact id.
2. IR defines applicability as declarative data (`polisyos.ir.applicability`) with jurisdiction/time + subject/object + exceptions/conditions.
3. IR provides `link_trinity()` as a pure contract:
   - signature is stable
   - inputs are TrinityBundle + RegistryBundle
   - output includes linked bindings + LinkReport
4. Link reports are structured with stable codes and stable field paths/ids.
5. Legacy is explicitly frozen:
   - docs mark surface IR + legacy linker as deprecated
   - no new features land in `polisyos.ir.legacy.*`
6. Tests cover:
   - citation validation
   - applicability validation
   - trinity linker issue reporting (at least: `unknown_unit`, `missing_slot`, `incompatible_constraint`)
   - concept id validation for `NormApplicability`/norm packs (at least: `unknown_concept`)
7. IR has **no dependency** on `polisyos.scientist` / `polisyos.foundry` / `polisyos.fabric`.
