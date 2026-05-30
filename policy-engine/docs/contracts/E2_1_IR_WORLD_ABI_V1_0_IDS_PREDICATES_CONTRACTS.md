# E2.1 (Phase 8) — IR World ABI v1.0 (ids/predicates/contracts): NodeKind/EdgeKind + Doc/Claim/WorldEvent

**Repo snapshot date**: 2026-02-03  
**Scope**: IR contract plane only — `policy-engine/src/polisyos/ir/world/*` + contract tests under `policy-engine/tests/contract/*` + this contract doc.

## 0) Goal (why this phase exists)

Introduce a single, stable **World ABI v1.0** in `polisyos.ir` that becomes the **source of truth** for the next phases **Fabric World Store / Materialization (E2.2–E2.4)**.

World ABI v1.0 must:

1. Be **compatible with IR `ID_PATTERN`** (colon-free ids).
2. Define stable **NodeKind** and **EdgeKind** vocabularies (the “minimum worth freezing”).
3. Define the minimal **predicate_id vocabulary** required for a fact log / world graph representation.
4. Provide **Pydantic v2 contracts** (no storage) for the three core world objects:

   - **Doc** (versioned metadata + citation-grade fragments)
   - **Claim** (typed assertions with evidence refs)
   - **WorldEvent** (audit/provenance envelope)

This phase is the **ABI contract layer** only. No persistence, no materialization.

---

## 1) Non-goals (explicitly out of scope)

This phase **does not** implement:

- Any Fabric storage, materialization, DuckDB schema, Kùzu graph, or fact writer logic.
- Any ingestion, crawling, extraction, Scholar/Lex services, or Scientist orchestration.
- Any PROV graph engine or trust/conflict resolver.

This phase **only** defines:

- ids/prefix rules
- kinds/vocabularies
- Pydantic contracts and invariants
- tests proving determinism + invariants

---

## 2) Current repository state (inputs after E1.3–E1.4)

### 2.1 Canonical ID patterns already exist (must be reused)

- `ID_PATTERN = ^[a-z][a-z0-9_.-]*$` (colon-free, fact-log compatible)  
  Source: `policy-engine/src/polisyos/ir/kernel/base.py`

- `ARTIFACT_ID_PATTERN = ^sha256:[0-9a-f]{64}$`  
  Source: `policy-engine/src/polisyos/ir/kernel/base.py`

### 2.2 Canonical JSON is already defined (must be reused)

`polisyos.ir.model_layer.canon.to_canonical_bytes()`:

- Deterministic JSON bytes
- **forbid_floats=True** by default (hard policy)
- Supports `datetime/date/Decimal/bytes`

Source: `policy-engine/src/polisyos/ir/canon.py`

### 2.3 Citations contract already exists (must be reused)

Phase E1.3 introduced `polisyos.ir.loading.citations`:

- `DocumentRef` (doc id + optional version binding)
- `FragmentLocator` (anchor_path / offsets / page range)
- `CitationRef` (fragment_id OR locator; optional text_hash/quote_hash; optional evidence/provenance refs)

Source: `policy-engine/src/polisyos/ir/citations.py`  
Contract tests: `policy-engine/tests/contract/test_citations_contract.py`

### 2.4 Import gate (dependency-guard) is enforced

IR constraints from `policy-engine/architecture/imports/policy.toml`:

- `polisyos.ir.*` may import only `pydantic`, `typing_extensions`, `yaml` + stdlib
- IR must not import `core/fabric/foundry/scientist`

Enforced by `policy-engine/tests/repo_quality/architecture/test_arch_import_gate.py`.

---

## 3) Deliverables (what must exist after E2.1)

### 3.1 New IR package: `polisyos.ir.world`

Create the package (all modules are IR-only, no external deps beyond allowed list):

```text
policy-engine/src/polisyos/ir/world/
  __init__.py
  abi.py          # NodeKind/EdgeKind + reserved world id prefixes
  ids.py          # deterministic WorldID helpers (hashing + artifact mapping)
  predicates.py   # reserved predicate_id constants + helper builders
  doc.py          # DocMeta + DocFragment contracts (reusing ir.citations)
  claim.py        # Claim contract (reusing ir.citations)
  event.py        # WorldEvent (+ agent/activity) contracts
```

### 3.2 Contract tests (ABI-grade)

Add a dedicated contract test module:

```text
policy-engine/tests/contract/test_world_abi_contract.py
```

It must cover:

- ID pattern compliance
- deterministic id derivation
- float rejection
- invariants for Doc/Claim/Event

### 3.3 Contract documentation

This document is the contract doc for Phase 8 (E2.1). It must clearly mark:

- **ABI (frozen)**: what cannot change without versioned migration
- **Extensible**: what can be extended in later phases without breaking v1.0

---

## 4) World ABI v1.0 — identifiers and vocabularies (frozen)

### 4.1 WorldID definition (frozen)

**WorldID** is any string matching IR `ID_PATTERN`:

- No `:` (colon-free)
- Lowercase start (`[a-z]`)
- Only `[a-z0-9_.-]` afterwards

WorldID is the only id allowed in FactLog `Fact.subject_id` and `Fact.target_id`.

### 4.2 Reserved WorldID prefixes (frozen, strict list)

The following **top-level prefixes** are reserved in v1.0:

- `artifact.*`
- `doc.*`
- `docv.*`
- `frag.*`
- `claim.*`
- `event.*`
- `prov.*`

**Rule**:

- Domain extensions **must not** use these prefixes for their own entities.
- Future reserved prefixes may be introduced only in a new ABI version (e.g., `cset.*`, `bundle.*`, `norm.*`, `legal.*`).

### 4.3 ArtifactID → WorldID mapping (frozen)

**ArtifactID** in IR is a string `sha256:<hex64>` (must match `ARTIFACT_ID_PATTERN`).

Mapping to a colon-free WorldID:

- `sha256:<hex64>` → `artifact.sha256_<hex64>`

Properties:

- Deterministic
- Reversible for this prefix (`artifact.sha256_` ↔ `sha256:`)

### 4.4 Hash-based WorldIDs (frozen)

For any object whose identity is derived from a canonical payload:

- `world_id = "<prefix>.sha256_" + sha256_hex(to_canonical_bytes(payload))`

This rule relies on IR canonicalization:

- `to_canonical_bytes()` forbids floats by default.
- Therefore **float in payload is invalid for id derivation**.

### 4.5 NodeKind v1.0 (frozen)

NodeKind is the stable semantic kind recorded via predicate `world.kind`.

Minimal set required for E2.2+:

- `artifact`
- `doc.source`
- `doc.version`
- `doc.fragment`
- `claim`
- `world.event`
- `prov.agent`
- `prov.activity`

**Notes**:

- NodeKind is semantic; it does **not** have to equal the WorldID prefix.
  - Example: a `doc.fragment` node will typically have `frag.*` id prefix.

### 4.6 EdgeKind v1.0 (frozen)

EdgeKind is encoded into the edge predicate id as `world.rel.<edge_kind>`.

Minimal set:

**Document edges:**

- `doc.has_version` (src=`doc.*` → dst=`docv.*`)
- `doc.has_fragment` (src=`docv.*` → dst=`frag.*`)

**Claim edges:**

- `claim.cites` (src=`claim.*` → dst=`frag.*`)
- `claim.derived_from` (src=`claim.*` → dst=`docv.*` OR `artifact.*` depending on source_kind)

**PROV edges (minimal PROV-O subset):**

- `prov.used` (src=`prov.activity.*` or `event.*` → dst=`*`)
- `prov.was_generated_by` (src=`*` → dst=`prov.activity.*` or `event.*`)
- `prov.was_derived_from` (src=`*` → dst=`*`)
- `prov.was_associated_with` (src=`prov.activity.*` or `event.*` → dst=`prov.agent.*`)
- `prov.was_attributed_to` (src=`*` → dst=`prov.agent.*`)

### 4.7 Predicate vocabulary v1.0 (frozen)

#### 4.7.1 Node attribute predicates (frozen)

Minimal node-attribute predicates:

- `world.kind` — `object_value` = NodeKind (string)
- `world.label` — `object_value` = human-readable label (string)
- `world.artifact_id` — `object_value` = ArtifactID (`sha256:...`) (string)
- `world.props_ref` — `object_value` = ArtifactID of a JSON “properties blob” (optional)

#### 4.7.2 Edge predicates (frozen rule)

All world edges are represented as FactLog facts with:

- `predicate_id = "world.rel.<edge_kind>"`
- `target_id = <dst_world_id>`

**Strict rule**: any edge kind used in the world graph must be encoded through `world.rel.*`.

---

## 5) IR package design: `polisyos.ir.world` (implementation spec)

### 5.1 `polisyos.ir.world.abi`

**Responsibilities:**

- Define ABI v1.0 frozen enums/tables:
  - `NodeKind` enum
  - `EdgeKind` enum
  - `RESERVED_WORLD_PREFIXES_V1` (strict list)

**Recommended API:**

- `class NodeKind(str, Enum): ...` (values listed in §4.5)
- `class EdgeKind(str, Enum): ...` (values listed in §4.6)
- `RESERVED_WORLD_PREFIXES_V1: tuple[str, ...] = ("artifact", "doc", "docv", "frag", "claim", "event", "prov")`

**No imports:**

- Must only import stdlib + `Enum` (stdlib).

### 5.2 `polisyos.ir.world.ids`

**Responsibilities:**

- Provide deterministic helpers for:
  - parsing/validating artifact ids
  - mapping ArtifactID → WorldID
  - computing stable hash-based WorldIDs from canonical payloads

**Recommended API (frozen for E2.2+):**

- `def sha256_hex_from_artifact_id(artifact_id: str) -> str:`
  - Validates `ARTIFACT_ID_PATTERN`
  - Returns `<hex64>` (lowercase)

- `def artifact_id_to_world_id(*, prefix: str, artifact_id: str) -> str:`
  - Returns `f"{prefix}.sha256_{hex64}"`
  - `prefix` must be a reserved prefix for v1.0 (`artifact|docv|event` etc) **when used for ABI objects**

- `def stable_world_id_from_canon(*, prefix: str, payload: dict[str, Any]) -> str:`
  - Uses `polisyos.ir.model_layer.canon.to_canonical_bytes(payload)`
  - `sha256_hex = hashlib.sha256(canon).hexdigest()`
  - Returns `f"{prefix}.sha256_{sha256_hex}"`
  - Must raise if canonicalization fails (including floats)

**Deterministic id derivation functions (recommended to add):**

These are strongly recommended for avoiding “hidden id policies” later:

- `def doc_source_id(*, canonical_url: str | None, official_id: str | None, source_kind: str | None = None) -> str:`
  - Enforces “one of canonical_url/official_id”
  - Uses `stable_world_id_from_canon(prefix="doc", payload={...})`

- `def doc_version_id_from_raw_artifact(*, raw_artifact_id: str) -> str:`
  - `docv.sha256_<hex(raw_artifact_id)>`

- `def doc_fragment_id(*, doc_version_id: str, locator: "FragmentLocator", text_artifact_id: str) -> str:`
  - `frag.sha256_<sha256(canon({doc_version_id, locator, text_artifact_id}))>`

- `def claim_id_from_payload(*, claim_payload: dict[str, Any]) -> str:`
  - `claim.sha256_<sha256(canon(payload_without_id_fields))>`

- `def world_event_id_from_payload(*, event_payload: dict[str, Any]) -> str:`
  - `event.sha256_<sha256(canon(payload_without_id_fields))>`

**Why derive ids in IR now:**

- Phase 9+ will rely on deterministic ids for idempotent ingestion and materialization.
- Keeping id policies in IR avoids “Fabric-specific id rules” (which would break portability).

### 5.3 `polisyos.ir.world.predicates`

**Responsibilities:**

- Declare ABI predicate ids as string constants (v1.0 frozen)
- Provide minimal helpers for edge predicate construction

**Recommended constants:**

- `WORLD_KIND = "world.kind"`
- `WORLD_LABEL = "world.label"`
- `WORLD_ARTIFACT_ID = "world.artifact_id"`
- `WORLD_PROPS_REF = "world.props_ref"`
- `WORLD_REL_PREFIX = "world.rel."`

**Recommended helpers:**

- `def rel(edge_kind: "EdgeKind | str") -> str:`
  - Returns `f"world.rel.{edge_kind}"`

### 5.4 `polisyos.ir.world.doc`

#### 5.4.1 DocMeta (contract)

**Purpose:**

Define versioned document metadata:

- `doc_source_id` = stable identity across versions
- `doc_version_id` = stable identity for a particular version (usually derived from raw bytes artifact)

**Fields (minimum v1.0):**

- `schema_version: "1.0"`
- `doc_source_id: WorldID` (recommended prefix: `doc.`)
- `doc_version_id: WorldID` (recommended prefix: `docv.`)
- One of:
  - `canonical_url: str`
  - `official_id: str`
- `retrieved_at: datetime`
- `mime: str`
- `license: str`
- Optional:
  - `jurisdiction: str | None`
  - `language: str | None`
- CAS refs (ArtifactID strings):
  - `raw_ref: ArtifactID` (required)
  - `normalized_ref: ArtifactID | None`
  - `structure_ref: ArtifactID | None`
  - `chunks_ref: ArtifactID | None`
- `props: dict[str, Any]` (must reject floats deep)

**Invariants:**

- Must satisfy IR patterns:
  - ids match `ID_PATTERN`
  - artifact refs match `ARTIFACT_ID_PATTERN`
- Must enforce “one of canonical_url/official_id”.
- Must reject floats in `props` (use `reject_floats_deep`).

**Recommended id rules:**

- `doc_source_id` derived from canonical source identity (url or official id):
  - `doc.sha256_<sha256(canon({canonical_url|official_id}))>`
- `doc_version_id` derived from raw content artifact:
  - `docv.sha256_<hex(raw_ref)>`

#### 5.4.2 DocFragment (contract)

**Purpose:**

Define a citation-grade fragment bound to a document version.

**Re-use from E1.3:**

Use `polisyos.ir.loading.citations.FragmentLocator` as the locator payload.

**Fields (minimum v1.0):**

- `schema_version: "1.0"`
- `fragment_id: WorldID` (recommended prefix: `frag.`)
- `doc_version_id: WorldID` (recommended prefix: `docv.`)
- `locator: FragmentLocator` (required)
- `text_hash: ArtifactID` (preferred; content-addressed text blob)
- Optional:
  - `quote_preview: str | None` (small preview for debugging / UX; must not be required)
- `props: dict[str, Any]` (reject floats deep)

**Invariants:**

- `locator` must be present and valid (already enforced by `FragmentLocator`).
- `text_hash` must be present (v1.0 requirement to keep citations reproducible).

**Recommended id rule:**

- `fragment_id = frag.sha256_<sha256(canon({doc_version_id, locator, text_hash}))>`

### 5.5 `polisyos.ir.world.claim`

#### 5.5.1 Claim (contract)

**Purpose:**

Represent a typed assertion about the world with minimal evidence requirements.

**Re-use from E1.3:**

Use `polisyos.ir.loading.citations.CitationRef` for doc-based evidence.

**Fields (minimum v1.0):**

- `schema_version: "1.0"`
- `claim_id: WorldID` (recommended prefix: `claim.`)
- `predicate_id: WorldID` (domain-extensible; must match `ID_PATTERN`)
- Subject (one required):
  - `subject_id: WorldID | None`
  - `subject_text: str | None`
- Value (minimum index-compatible set):
  - `value_text: str` (required)
  - `value_decimal: Decimal | None` (optional; required if `kind=numeric`)
  - `unit_id: WorldID | None`
- `confidence: Decimal` (strictly Decimal; 0..1)
- `source_kind: Enum` (minimum: `doc`, `dataset`, `simulation`, `expert`, `derived`)
- Evidence (exclusive requirement based on source_kind):
  - if `source_kind == doc`: `citations: list[CitationRef]` must be non-empty
  - else: `source_artifacts: list[ArtifactID]` must be non-empty
- Optional scope:
  - `jurisdiction: str | None`
  - `domain: str | None`
  - `valid_from: datetime | None`
  - `valid_to: datetime | None`
  - `qualifiers: dict[str, str|int|bool]` (reject floats deep)
- `props: dict[str, Any]` (reject floats deep)

**Invariants:**

- `claim_id` and `predicate_id` must match `ID_PATTERN`.
- Must have exactly one of `subject_id` / `subject_text` (at least one; both allowed).
- Must reject floats deep (entire payload).
- Evidence rules:
  - `doc` → citations non-empty
  - non-`doc` → source_artifacts non-empty
- `confidence` is Decimal in `[0, 1]`.
- If `valid_from` and `valid_to` both present → `valid_to >= valid_from`.

**Recommended id rule:**

To keep it stable and audit-friendly in the absence of an “observation” layer:

- `claim_id = claim.sha256_<sha256(canon({predicate_id, subject_id|subject_text, value_text, value_decimal, unit_id, scope, validity, citations|source_artifacts}))>`

This makes claim identity deterministic for the full claim payload (including evidence refs), which is sufficient for E2.2 ingestion idempotency.

### 5.6 `polisyos.ir.world.event`

#### 5.6.1 WorldEvent (contract)

**Purpose:**

`WorldEvent` is the minimal audit envelope describing _who did what_ and _which objects were used/produced_.

It is explicitly the bridge between:

- “history/run trace” (events) and
- “world semantics” (doc/claim nodes and relations)

**Fields (minimum v1.0):**

- `schema_version: "1.0"`
- `event_id: WorldID` (recommended prefix: `event.`)
- `event_kind: Enum` (minimum fixed list for v1.0; can expand in later ABI versions)
  - `fetch_doc`, `normalize_doc`, `structure_doc`, `chunk_doc`
  - `extract_claims`, `resolve_conflicts`, `assemble_norm_pack`, `evaluate_legality`
  - `ingest_dataset`, `query_world`, `simulate`, `validate`
- `agent: ProvAgent` (who)
- `activity: ProvActivity` (what)
- `inputs: list[WorldObjectRef]`
- `outputs: list[WorldObjectRef]`
- References to evidence/provenance artifacts (ArtifactID strings):
  - `evidence_ref: ArtifactID | None`
  - `provenance_ref: ArtifactID | None`
- `props: dict[str, Any]` (reject floats deep)

#### 5.6.2 ProvAgent / ProvActivity (contracts)

Minimal PROV-compatible types:

- `ProvAgentType` enum (minimum):
  - `system`, `user`, `model`, `connector`, `extractor`, `scheduler`, `human_reviewer`
- `ProvActivityType` enum (minimum):
  - `fetch_doc`, `normalize_doc`, `structure_doc`, `chunk_doc`, `extract_claims`, `resolve_conflicts`, `assemble_norm_pack`, `evaluate_legality`, `ingest_dataset`, `query_world`, `simulate`, `validate`

**ProvAgent fields:**

- `agent_id: WorldID` (recommended prefix: `prov.agent.`)
- `agent_type: ProvAgentType`
- `label: str`
- Optional:
  - `component_id: str | None` (component-id string; keep as string in IR)
  - `model_id: str | None`
  - `metadata: dict[str, str]` (reject floats deep)

**ProvActivity fields:**

- `activity_id: WorldID` (recommended prefix: `prov.activity.`)
- `activity_type: ProvActivityType`
- `label: str`
- `started_at: datetime`
- `ended_at: datetime | None`
- Optional:
  - `parameters: dict[str, Any]` (reject floats deep)

**WorldObjectRef fields:**

- `world_id: WorldID | None`
- `artifact_id: ArtifactID | None`
- Invariant: at least one of `world_id` or `artifact_id` must be present.

**Invariants:**

- `activity.ended_at >= activity.started_at` if ended_at present.
- Float rejection applies to all dict payloads / parameters.

**Recommended id rule:**

- `event_id = event.sha256_<sha256(canon({event_kind, agent, activity, inputs, outputs, evidence_ref, provenance_ref}))>`

Rationale: phase 8 is contract-only; deriving from payload is deterministic and does not require CAS in IR.

---

## 6) Testing spec (contract tests to add)

Create `policy-engine/tests/contract/test_world_abi_contract.py` with:

### 6.1 Pattern tests

- `artifact_id_to_world_id(prefix="artifact", artifact_id="sha256:" + "a"*64)`:
  - matches `ID_PATTERN`
  - equals `"artifact.sha256_" + "a"*64`
- `stable_world_id_from_canon(prefix="doc", payload={"a": "b"})`:
  - matches `ID_PATTERN`
  - is stable across runs

### 6.2 Canonicalization tests (determinism + float rejection)

- Two identical payloads → same derived world id.
- Payload containing float → raises (canonicalization forbids floats).

### 6.3 Invariants tests (Doc/Claim/Event)

**DocMeta:**

- missing both `canonical_url` and `official_id` → invalid

**DocFragment:**

- missing locator → invalid
- locator with invalid offsets/page range already covered by E1.3 tests; ensure DocFragment enforces presence of locator + text_hash

**Claim:**

- missing both subject_id and subject_text → invalid
- `source_kind=doc` with empty citations → invalid
- `source_kind!=doc` with empty source_artifacts → invalid
- float anywhere in `props`/`qualifiers`/`parameters` → invalid

**WorldEvent:**

- `WorldObjectRef` missing both `world_id` and `artifact_id` → invalid
- `ended_at < started_at` → invalid

### 6.4 Import gate

No direct test needed: existing `test_arch_import_gate` must stay green after adding the new IR package.

---

## 7) ABI vs extension policy (documented, v1.0)

### 7.1 ABI (frozen in v1.0; breaking requires v2.0 + migration)

- Reserved WorldID prefixes list (§4.2)
- ArtifactID → WorldID mapping rule (§4.3)
- NodeKind v1.0 list (§4.5)
- EdgeKind v1.0 list (§4.6)
- Predicate vocabulary v1.0:
  - `world.kind`, `world.label`, `world.artifact_id`, `world.props_ref`
  - edge predicate rule `world.rel.<edge_kind>`
- Minimal invariants for Doc/Claim/Event contracts (evidence + id format + float rejection)

### 7.2 Extensible without breaking v1.0

- New domain-specific claim predicate ids (e.g., `roads.*`, `tax.*`) — as long as they match `ID_PATTERN`.
- Additional `event_kind` values (should be appended, not renamed).
- Optional extra fields inside `props` dicts (still no floats).
- Additional NodeKinds/EdgeKinds in future ABI versions (v1.1+ or v2.0 depending on the change).

---

## 8) Definition of Done (Phase 8 / E2.1)

1. `polisyos.ir.world` package exists with modules described in §3.1.
2. No forbidden imports from `core/fabric/foundry/scientist` (import gate green).
3. NodeKind/EdgeKind/predicate ids/prefixes are defined as v1.0 ABI.
4. Pydantic v2 contracts exist: `DocMeta`, `DocFragment`, `Claim`, `WorldEvent` (+ minimal prov types).
5. Contract tests exist and pass:

   - id patterns + determinism
   - float rejection
   - invariants (doc/claim/event)

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                                                                                                                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Source plan phase   | D1-L4 Phase 0 canon/CAS containment and Phase 4 PROV/interoperability bridge                                                                                                                                                                                                               |
| Contract tests      | `tests/contract/test_world_abi_contract.py`, `tests/contract/test_citations_contract.py`, `tests/contract/test_golden_record_ids.py`, `tests/unit/ir/test_canon_hash_parity.py`                                                                                                                 |
| Schema snapshots    | `schemas/snapshots/ir/world_event.schema.json`, `schemas/snapshots/ir/doc_meta.schema.json`, `schemas/snapshots/ir/doc_fragment.schema.json`, `schemas/snapshots/ir/claim.schema.json`, `schemas/snapshots/fabric/node_kind.schema.json`, `schemas/snapshots/fabric/edge_kind.schema.json` |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                                                                                                                                                                     |
