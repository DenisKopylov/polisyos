# E2.2 (Phase 9) — Fabric World Store: CAS persist + FactLog emission + WorldEvent (write‑path for World Graph)

**Repo snapshot date**: 2026-02-03
**Scope**: `policy-engine/src/polisyos/fabric/world/*` (new) + `policy-engine/tests/unit/fabric/*` (new tests) + this contract doc.
**Primary goal**: add a single, reusable **write‑path** for the World Graph in Fabric:

- persist typed World objects into **Core CAS** (`DocMeta`, `DocFragment`, `Claim`, `WorldEvent`)
  Source of truth: `polisyos.ir.world.*` (Phase 8 / E2.1)

- emit **ABI‑compatible** World facts into **FactLog** segments:
  - node baseline facts: `world.kind`, `world.label`, `world.artifact_id`, `world.props_ref`
  - edge facts: `world.rel.<edge_kind>` (Doc/Claim + minimal PROV edges)
- write each action as a **WorldEvent** (audit/timeline) _without breaking idempotency of semantic facts_

> This phase is a **write-only** surface. No DuckDB/Kùzu materialization, no query API (except minimal helpers for tests if needed).

---

## 0) Context (what already exists in the repo)

### 0.1 IR World ABI v1.0 exists (Phase 8 / E2.1)

Source of truth:

- IR types and vocabularies: `policy-engine/src/polisyos/ir/world/*`
  - `NodeKind`, `EdgeKind`, predicate helpers: `polisyos.ir.world.abi`, `polisyos.ir.world.predicates`
  - deterministic ID plumbing: `polisyos.ir.world.ids`
  - typed contracts: `polisyos.ir.world.doc.DocMeta`, `polisyos.ir.world.doc.DocFragment`, `polisyos.ir.world.claim.Claim`, `polisyos.ir.world.event.WorldEvent`
- Contract tests: `policy-engine/tests/contract/test_world_abi_contract.py`
- ABI doc: `policy-engine/docs/contracts/E2_1_IR_WORLD_ABI_V1_0_IDS_PREDICATES_CONTRACTS.md`

**Important constraints from IR / ABI:**

- `WorldID` must match `ID_PATTERN = ^[a-z][a-z0-9_.-]*$` (colon‑free)
- `ArtifactID` is `sha256:<hex64>`
- all edges are encoded as fact predicates: `predicate_id="world.rel.<edge_kind>"`
- canonical JSON forbids floats (`polisyos.ir.model_layer.canon.to_canonical_bytes()`)

### 0.2 CAS exists in Core (E1.4)

Source of truth: `policy-engine/src/polisyos/core/artifacts/store.py`

- `FileSystemCAS.put_json()` stores canonical JSON bytes and returns `ArtifactRef`
- `PutOptions.kind` is required (artifact kind string)
- `SchemaInfo(name, version)` is optional but recommended

### 0.3 FactLog contracts + segment writer exist

Source of truth:

- Fact contracts: `policy-engine/src/polisyos/ir/fact_log.py`
  - `Fact`, `FactProvenance`, `FactSegmentManifest`, `build_fact_id()`
- Fact builder + parquet segment writer: `policy-engine/src/polisyos/fabric/fact_writer.py`
  - `build_fact()` produces deterministic `fact_id` (tx_time is not part of the hash)
  - `write_fact_segment()` writes `<segment_id>.parquet` + `<segment_id>_manifest.json`
- Segment index pattern (`_segments.jsonl`) exists in ingestion:
  - `_append_segment_index()` in `policy-engine/src/polisyos/fabric/ingestion.py`
  - `load_fact_manifests()` in `policy-engine/src/polisyos/fabric/materializer.py`

---

## 1) Non‑goals (explicitly out of scope for E2.2)

This phase **does not** implement:

- DuckDB materialization for world facts (Phase 10+).
- Kùzu materialization for world graph (Phase 10+).
- Query API for world graph (Phase 10+), except minimal helpers for tests.
- ConflictSet / conflict resolution contracts and storage (not present in IR yet as of 2026‑02‑03).

---

## 2) The core architectural decision: “Semantics vs History”

### 2.1 Why this is hard

In this repo, `Fact.fact_id` is computed from canonical payload bytes of:

`{subject_id, predicate_id, object_value, target_id, valid_time, provenance, trust, legal}`

Source of truth: `polisyos.fabric.evidence.fact_writer._fact_from_payload()` + `polisyos.ir.loading.fact_log.build_fact_id()`.

Therefore, **provenance changes change fact_id**.

### 2.2 Required behaviour after Phase 9

We need both:

1. **Idempotent semantic facts**: re‑emitting the same World node/edge facts must not create new `fact_id` values.
2. **Append‑only audit timeline**: each write action must create a new `WorldEvent` artifact and corresponding PROV edges that accumulate as a history.

### 2.3 Normative rule (Phase 9)

We implement two provenance profiles:

#### A) Stable provenance (semantic facts)

Used for facts representing **world semantics** (nodes/edges that represent “what exists”).

- `FactProvenance.source_id` is a constant (must match `ID_PATTERN`), e.g.:
  - `source_id="fabric.world"`
- `raw_hash` is a constant tag of the ABI, e.g.:
  - `raw_hash="world_abi_v1"`
- `license` is a constant (or configurable), e.g.:
  - `license="internal"`
- **MUST be None**:
  - `ingestion_run_id=None`
  - `script_hash=None`

Result: repeated emission yields identical `fact_id` (tx_time may differ).

#### B) Event provenance (audit facts)

Used for facts that encode **history/audit** (WorldEvent node facts + PROV edges).

- `FactProvenance.source_id` is a constant, e.g.:
  - `source_id="fabric.world.event"`
- `raw_hash` is a constant tag, e.g.:
  - `raw_hash="world_event_v1"`
- `license` same as above
- **MUST include event binding**:
  - `ingestion_run_id = <WorldEvent.event_id>` (string)

Result: even if an audit fact payload (other than provenance) is identical across runs, it remains unique per event.

> Note: Audit facts are already unique in practice because `subject_id` / `target_id` include unique event ids, but we bind provenance to event anyway to make “this edge came from that event/run” explicit at the Fact level.

---

## 3) Deliverables (what must exist after E2.2)

### 3.1 New Fabric package: `polisyos.fabric.world.store`

Create the new package:

```text
policy-engine/src/polisyos/fabric/world/
  __init__.py                 # thin facade; re-export stable API only
  store/
    __init__.py               # stable write surface
    errors.py                 # error families (catchable categories)
    provenance.py             # stable + event provenance helpers
    ids.py                    # adapter/wrappers around polisyos.ir.world.ids
    persist.py                # persist_* (typed -> CAS ArtifactRef)
    emit.py                   # emit_*_facts (typed -> list[Fact])
    validate.py               # runtime validations (ids + fact ABI)
    segments.py               # write_world_fact_segment + _segments.jsonl index helpers
```

### 3.2 Minimal tests (no DuckDB/Kùzu)

Add tests under:

```text
policy-engine/tests/unit/fabric/test_world_store_phase9.py
```

Test focus is E2.2 write‑path invariants only (see §8).

### 3.3 No dependency violations

Import gate must remain green:

- `polisyos.fabric.world.*` may import: `polisyos.fabric.*`, `polisyos.core.*`, `polisyos.ir.*`, `polisyos.common.*`
- Must not import `polisyos.scientist.*`

Enforced by: `policy-engine/tests/repo_quality/architecture/test_arch_import_gate.py`.

---

## 4) World FactLog channel layout (filesystem contract)

### 4.1 Separate world channel directory

Do not mix world facts with existing “data facts” (macro/agents/interactions).

Normative layout (Phase 9):

- **world fact log root**: `<fact_log_root>/world/`
- index file: `<fact_log_root>/world/_segments.jsonl`
- segment files: `<fact_log_root>/world/<segment_id>.parquet`
- segment manifests: `<fact_log_root>/world/<segment_id>_manifest.json`

The `<fact_log_root>` should be passed explicitly by the caller. Recommended defaults (caller-level):

- `FabricConfig.curated_dir / "fact_log"` (existing data-plane layout), so world log becomes:
  - `data/curated/fact_log/world/`
    or
- `FileSystemCAS.root / "fact_log"` (CAS-root co-location), so world log becomes:
  - `.polisyos/fact_log/world/`

Phase 9 does not mandate which root wins; it mandates **the “/world/” channel separation**.

### 4.2 Segment schema (parquet columns)

World facts use the existing `polisyos.fabric.evidence.fact_writer.write_fact_segment()` writer.

Therefore the parquet columns are normative (Phase 9):

- `fact_id` (sha256:<hex64>)
- `schema_version` ("1.0")
- `subject_id` (WorldID)
- `predicate_id` (World predicate id; WorldID syntax)
- `object_value` (stringified scalar; nullable)
- `target_id` (WorldID; nullable)
- `valid_time` (str|int; nullable)
- `tx_time` (ISO string)
- `provenance` (JSON string)
- `trust` (JSON string; nullable)
- `legal` (JSON string; nullable)

---

## 5) Public API surface (Phase 9)

### 5.1 Export policy

**Rule**: external callers must not deep-import internal implementation modules.

Allowed:

```python
from polisyos.fabric.world.store import persist_doc_meta, emit_doc_meta_facts, write_world_fact_segment
```

Not guaranteed stable (internal):

```python
from polisyos.fabric.world.store.emit import _some_private_helper
```

### 5.2 `polisyos.fabric.world.__init__`

Role: **thin facade** (for Phase 9 it may simply re-export `polisyos.fabric.world.store` public symbols).

### 5.3 `polisyos.fabric.world.store.__init__`

Exports (Phase 9 stable surface):

- error families from `errors.py`
- provenance helpers from `provenance.py`
- persist functions from `persist.py`
- fact emitters from `emit.py`
- segment functions from `segments.py`
- validation helpers from `validate.py` (at least the entrypoints)

> This is the surface all producers must use for World writes.

---

## 6) Module specs (implementation-level, non-ambiguous)

### 6.1 `errors.py`

Define catchable error categories:

```python
class WorldStoreError(Exception): ...
class WorldValidationError(WorldStoreError): ...
class WorldIDError(WorldValidationError): ...
class WorldFactError(WorldValidationError): ...
class WorldSegmentError(WorldStoreError): ...
```

Guidelines:

- raise `WorldIDError` when deterministic id rules mismatch (see `validate.py`)
- raise `WorldFactError` when a Fact violates ABI requirements (predicate/type/edge shape)
- raise `WorldSegmentError` for IO/manifest/index problems

### 6.2 `provenance.py`

Provide provenance builders used by all emitters.

Normative API:

```python
from polisyos.ir.loading.fact_log import FactProvenance

def stable_world_provenance_v1(*, license: str = "internal") -> FactProvenance: ...

def event_world_provenance_v1(
    event_id: str, *, license: str = "internal"
) -> FactProvenance: ...
```

Normative payload values:

- stable:
  - `source_id="fabric.world"`
  - `raw_hash="world_abi_v1"`
  - `ingestion_run_id=None`
  - `script_hash=None`
- event:
  - `source_id="fabric.world.event"`
  - `raw_hash="world_event_v1"`
  - `ingestion_run_id=event_id`

### 6.3 `ids.py` (Fabric adapter)

Role: provide “safe” wrappers around IR id helpers for Fabric usage.

At minimum re-export from `polisyos.ir.world.ids` and add strict validators:

```python
from polisyos.ir.world.ids import (
  artifact_id_to_world_id,
  doc_source_id,
  doc_version_id_from_raw_artifact,
  doc_fragment_id,
  claim_id_from_payload,
  world_event_id_from_payload,
)

def ensure_world_id(value: str, *, field: str = "id") -> str: ...
def ensure_artifact_id(value: str, *, field: str = "artifact_id") -> str: ...
```

### 6.4 `persist.py` (typed → CAS)

All persist functions:

- must use `FileSystemCAS.put_json()` (core canonical JSON, float-forbidden)
- must use fixed `PutOptions.kind` strings (Phase 9 normative list)
- must set `SchemaInfo` to the Pydantic model identity

Normative kinds:

- `fabric.world.doc_meta`
- `fabric.world.doc_fragment`
- `fabric.world.claim`
- `fabric.world.event`

Normative schema names:

- `polisyos.ir.world.DocMeta`
- `polisyos.ir.world.DocFragment`
- `polisyos.ir.world.Claim`
- `polisyos.ir.world.WorldEvent`

Normative API:

```python
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.world.doc import DocMeta, DocFragment
from polisyos.ir.world.claim import Claim
from polisyos.ir.world.event import WorldEvent

def persist_doc_meta(store: FileSystemCAS, meta: DocMeta) -> ArtifactRef: ...
def persist_doc_fragment(store: FileSystemCAS, fragment: DocFragment) -> ArtifactRef: ...
def persist_claim(store: FileSystemCAS, claim: Claim) -> ArtifactRef: ...
def persist_world_event(store: FileSystemCAS, event: WorldEvent) -> ArtifactRef: ...
```

**Optional but strongly recommended (manifest inputs):**

Persist functions may add `PutOptions.inputs` so that CAS manifests capture direct dependencies:

- DocMeta: `raw_ref` (required) + optional `normalized_ref`/`structure_ref`/`chunks_ref`
- DocFragment: `text_hash`
- Claim:
  - if `source_kind!=doc`: all `source_artifacts`
  - if `source_kind==doc`: include citation `text_hash` / `quote_hash` if present
- WorldEvent: include `evidence_ref`/`provenance_ref` if present, plus any `WorldObjectRef.artifact_id` present in inputs/outputs

### 6.5 `emit.py` (typed → Facts)

#### 6.5.1 Core primitives

Emitters must build facts via `polisyos.fabric.evidence.fact_writer.build_fact()` to ensure deterministic `fact_id` hashing rules are consistent across the codebase.

Normative primitives:

```python
from polisyos.ir.loading.fact_log import Fact, FactProvenance, FactLegal
from polisyos.ir.world.abi import NodeKind, EdgeKind

def emit_attr_fact(
    *, subject_id: str, predicate_id: str, object_value: str | int | bool | None,
    provenance: FactProvenance, trust_policy_id: str | None = None, legal: FactLegal | None = None,
    valid_time: str | int | None = None,
) -> Fact: ...

def emit_edge_fact(
    *, src_id: str, edge_kind: EdgeKind | str, dst_id: str,
    provenance: FactProvenance, trust_policy_id: str | None = None, legal: FactLegal | None = None,
    valid_time: str | int | None = None,
) -> Fact: ...

def emit_world_node_facts(
    *, node_id: str, kind: NodeKind | str, label: str | None, artifact_id: str | None, props_ref: str | None,
    provenance: FactProvenance, trust_policy_id: str | None = None, legal: FactLegal | None = None,
) -> list[Fact]: ...
```

Rules:

- `emit_world_node_facts` must always emit `world.kind`
- optional facts (`world.label`, `world.artifact_id`, `world.props_ref`) are emitted only if the value is not None
- `emit_edge_fact` must set `predicate_id = polisyos.ir.world.predicates.rel(edge_kind)`

#### 6.5.2 Domain emitters (Doc/Fragment/Claim/Event)

All domain emitters:

- must not perform any IO (no CAS reads, no DB/graph access)
- must not import `scientist` (guarded by import gate)
- must rely on IR ABI enums/constants where available (`NodeKind`, `EdgeKind`, `WORLD_KIND`, `rel(...)`, id helpers)

##### A) `emit_doc_meta_facts(meta, meta_artifact_id, provenance, ...)`

Inputs:

- `meta: DocMeta` (IR contract)
- `meta_artifact_id: str | None` — usually `str(persist_doc_meta(...).artifact_id)`
- `provenance: FactProvenance` — **stable provenance** for semantic facts

Must emit:

1. doc.source node baseline:

   - subject=`meta.doc_source_id`
   - `world.kind = "doc.source"`
   - `world.label`:
     - preferred: `meta.canonical_url` if present else `meta.official_id`
2. doc.version node baseline:

   - subject=`meta.doc_version_id`
   - `world.kind = "doc.version"`
   - `world.artifact_id = meta_artifact_id` (if provided)
   - `world.props_ref = meta_artifact_id` (optional; if you want to reserve `world.artifact_id` for other use, but do it consistently)
3. edge `doc.has_version`:

   - src=`meta.doc_source_id`
   - dst=`meta.doc_version_id`
   - predicate=`world.rel.doc.has_version`

Notes:

- Phase 9 does **not** emit doc.\* attribute facts (url/mime/license/retrieved_at). Those remain in the DocMeta CAS artifact for Phase 10 materialization.

##### B) `emit_doc_fragment_facts(fragment, fragment_artifact_id, provenance, ...)`

Must emit:

1. doc.fragment node baseline:

   - subject=`fragment.fragment_id`
   - `world.kind="doc.fragment"`
   - `world.artifact_id = fragment_artifact_id` (if provided)
2. edge `doc.has_fragment`:

   - src=`fragment.doc_version_id`
   - dst=`fragment.fragment_id`
   - predicate=`world.rel.doc.has_fragment`

##### C) `emit_claim_facts(claim, claim_artifact_id, provenance, ...)`

Must emit:

1. claim node baseline:

   - subject=`claim.claim_id`
   - `world.kind="claim"`
   - `world.artifact_id = claim_artifact_id` (if provided)
   - `world.label` recommended as a short debug string (bounded length):
     - e.g. `"{predicate_id}={value_text}"` truncated

2. edges `claim.cites` (doc claims):

For each `CitationRef` in `claim.citations`:

- Determine `fragment_id` for the edge target:
  - if `citation.fragment_id` present → use it
  - else (locator-based citation):
    - require:
      - `citation.locator` present (already required by contract)
      - `citation.text_hash` present (**Phase 9 requirement for edge emission**)
      - a resolvable `doc_version_id`:
        - prefer `citation.doc.doc_version_id`
        - else if `citation.doc.doc_version_ref` present: derive `docv_id = doc_version_id_from_raw_artifact(raw_artifact_id=citation.doc.doc_version_ref)`
        - else: cannot derive → raise `WorldValidationError`
    - compute `fragment_id = doc_fragment_id(doc_version_id=docv_id, locator=citation.locator, text_artifact_id=citation.text_hash)`

Emit edge:

- src=`claim.claim_id`
- dst=`fragment_id`
- predicate=`world.rel.claim.cites`

1. optional edge `claim.derived_from`:

Emit only if a resolvable source exists:

- doc-based:
  - if any citation has `doc.doc_version_id` → claim → that doc_version_id
  - else if any citation has `doc.doc_version_ref` → claim → derived `docv_id`
- non-doc:
  - for each `artifact_id` in `claim.source_artifacts`:
    - map to artifact node id: `artifact_id_to_world_id(prefix="artifact", artifact_id=artifact_id)`
    - emit edge claim → artifact via `world.rel.claim.derived_from`

##### D) `emit_world_event_facts(event, event_artifact_id, ...)`

WorldEvent facts are **audit facts**, therefore their default provenance is the **event provenance** (see §2.3).

Must emit:

1. world.event node baseline:

   - subject=`event.event_id`
   - `world.kind="world.event"`
   - `world.artifact_id = event_artifact_id` (if provided)
   - `world.label` recommended: `event.event_kind.value`

2. prov.agent node baseline:

   - subject=`event.agent.agent_id`
   - `world.kind="prov.agent"`
   - `world.label = event.agent.label`

3. (optional) prov.activity node baseline:

   - subject=`event.activity.activity_id`
   - `world.kind="prov.activity"`
   - `world.label = event.activity.label`

Phase 9 does not mandate whether PROV edges bind to `event.event_id` or `event.activity.activity_id`. To avoid introducing a new edge kind “event ↔ activity”, we choose a normative rule:

**Normative PROV binding rule for Phase 9:** treat the WorldEvent node id as the PROV activity id for emitted PROV edges.

Emit minimal PROV edges (as `world.rel.prov.*`):

- `prov.was_associated_with`:
  - src=`event.event_id`
  - dst=`event.agent.agent_id`
- `prov.used` for each input ref:
  - src=`event.event_id`
  - dst=resolved entity id (see below)
- `prov.was_generated_by` for each output ref:
  - src=resolved entity id
  - dst=`event.event_id`
- `prov.was_attributed_to` for each output ref:
  - src=resolved entity id
  - dst=`event.agent.agent_id`

Entity id resolution for `WorldObjectRef`:

- if `ref.world_id` is present → use it
- else:
  - require `ref.artifact_id`
  - compute `artifact_world_id = artifact_id_to_world_id(prefix="artifact", artifact_id=ref.artifact_id)`
  - (recommended) emit artifact node baseline facts for that node:
    - `world.kind="artifact"`
    - `world.artifact_id=<ref.artifact_id>`

> This rule ensures event links remain usable even when producers only have CAS refs for some inputs/outputs.

### 6.6 `validate.py` (safety rails)

Phase 9 must add **runtime validation** (in addition to IR Pydantic validation) to prevent garbage from entering the world log.

#### 6.6.1 Deterministic id checks

Implement validators that confirm the typed object ids match IR deterministic id derivation rules.

Normative API:

```python
from polisyos.ir.world.doc import DocMeta, DocFragment
from polisyos.ir.world.claim import Claim
from polisyos.ir.world.event import WorldEvent

def validate_doc_meta_ids(meta: DocMeta) -> None: ...
def validate_doc_fragment_ids(fragment: DocFragment) -> None: ...
def validate_claim_id(claim: Claim) -> None: ...
def validate_world_event_id(event: WorldEvent) -> None: ...
```

Rules:

- DocMeta:
  - `meta.doc_source_id == doc_source_id(canonical_url=meta.canonical_url, official_id=meta.official_id)`
  - `meta.doc_version_id == doc_version_id_from_raw_artifact(raw_artifact_id=meta.raw_ref)`
- DocFragment:
  - `fragment.fragment_id == doc_fragment_id(doc_version_id=fragment.doc_version_id, locator=fragment.locator, text_artifact_id=fragment.text_hash)`
- Claim:
  - `claim.claim_id == claim_id_from_payload(claim_payload=claim.model_dump())`
  - note: claim_id is sensitive to list ordering (citations/source_artifacts). Producers must ensure deterministic ordering upstream.
- WorldEvent:
  - `event.event_id == world_event_id_from_payload(event_payload=event.model_dump())`

On mismatch → raise `WorldIDError`.

#### 6.6.2 Fact ABI checks (world facts)

Implement:

```python
from polisyos.ir.loading.fact_log import Fact

def validate_fact_is_world_abi(fact: Fact, *, strict_edge_kinds: bool = False) -> None: ...
def validate_world_facts(facts: list[Fact]) -> None: ...
```

Rules:

- `fact.subject_id` matches ID_PATTERN (already validated by Fact model, but validate anyway for error clarity)
- `fact.predicate_id` matches ID_PATTERN
- If `fact.predicate_id` starts with `"world.rel."`:
  - `fact.target_id` must be present
  - `fact.object_value` must be None
  - `edge_kind = predicate_id[len("world.rel."):]` must match `ID_PATTERN`
  - (optional strict mode) if you want to forbid non‑ABI edge kinds in this phase:
    - require `edge_kind in {EdgeKind.*.value}`
- Else (node attribute fact):
  - `fact.target_id` must be None
  - `fact.object_value` must be present (Fact contract already enforces this, but validate for clarity)
  - Reserved `world.*` keys must be exact:
    - allow only: `WORLD_KIND`, `WORLD_LABEL`, `WORLD_ARTIFACT_ID`, `WORLD_PROPS_REF`
    - reject any other predicate starting with `"world."` to avoid typos/ABI drift
  - Additional checks for reserved keys:
    - if predicate is `world.kind`: object_value must be one of `NodeKind` values
    - if predicate is `world.artifact_id` or `world.props_ref`: object_value must match `ARTIFACT_ID_PATTERN`

On violation → raise `WorldFactError`.

### 6.7 `segments.py` (segment writer + index)

This module must provide the world-channel segment writing API and reuse existing writer logic.

Normative API:

```python
from pathlib import Path
from polisyos.ir.loading.fact_log import Fact, FactSegmentManifest

SEGMENTS_INDEX_NAME = "_segments.jsonl"

def write_world_fact_segment(
    facts: list[Fact],
    *,
    fact_log_root: Path,
    segment_name: str,
) -> FactSegmentManifest: ...

def append_world_segment_index(
    manifest: FactSegmentManifest,
    *,
    fact_log_root: Path,
) -> None: ...

def load_world_fact_manifests(fact_log_root: Path) -> list[FactSegmentManifest]: ...
```

Normative behaviours:

- world channel directory is `fact_log_root / "world"`
- `segment_name` must be normalized to match `ID_PATTERN` constraints for `segment_id` generation:
  - must start with `[a-z]`
  - may contain only `[a-z0-9_.-]`
  - recommended: lower-case and replace invalid chars with `_`
- the writer should deduplicate facts **within a segment** by `fact_id` to avoid intra-segment duplicates
  - dedup is stable: keep first in input order
- append index is append-only JSONL:
  - one line per `FactSegmentManifest.model_dump_json()`
  - file: `<world_dir>/_segments.jsonl`
- `load_world_fact_manifests`:
  - reads `_segments.jsonl`
  - validates each line via `FactSegmentManifest.model_validate_json`
  - skips invalid lines with a warning (same policy as `polisyos.fabric.materializer.load_fact_manifests`)

Optional helper (recommended):

- `persist_fact_segment_manifest(store, manifest) -> ArtifactRef` reusing the existing kind/schema `ir.fact_segment_manifest` (same as in `fabric.ingestion`).

---

## 7) Recommended end-to-end write flow (how producers use Phase 9)

### 7.1 “Write doc meta + event” pattern

1. Producer constructs a valid `DocMeta` (IR contract) and validates deterministic ids:

   - `validate_doc_meta_ids(meta)`
2. Persist typed object:

   - `meta_ref = persist_doc_meta(cas, meta)`
3. Emit semantic facts (stable provenance):

   - `semantic = stable_world_provenance_v1()`
   - `facts = emit_doc_meta_facts(meta, meta_artifact_id=str(meta_ref.artifact_id), provenance=semantic)`
4. Construct a `WorldEvent` describing the operation:

   - inputs: at least `WorldObjectRef(artifact_id=meta.raw_ref)`
   - outputs: at least `WorldObjectRef(world_id=meta.doc_version_id)` and optionally `WorldObjectRef(artifact_id=str(meta_ref.artifact_id))`
   - validate deterministic id: `validate_world_event_id(event)`
5. Persist event:

   - `event_ref = persist_world_event(cas, event)`
6. Emit audit facts (event provenance):

   - `audit_prov = event_world_provenance_v1(event.event_id)`
   - `facts += emit_world_event_facts(event, event_artifact_id=str(event_ref.artifact_id), provenance=audit_prov)`
7. Validate ABI facts:

   - `validate_world_facts(facts)`
8. Flush segment:

   - `manifest = write_world_fact_segment(facts, fact_log_root=fact_log_root, segment_name="doc_meta")`
   - `append_world_segment_index(manifest, fact_log_root=fact_log_root)`

### 7.2 Idempotency expectations

- Re-emitting semantic facts for the same doc/fragment/claim must yield the same `fact_id` values:
  - because semantic provenance is stable and fact payloads are stable
- Events should accumulate:
  - each new WorldEvent has a distinct `event_id` (derived from payload per IR rule), therefore its node facts and PROV edges are distinct

---

## 8) Tests (must be implemented in Phase 9)

Create `policy-engine/tests/unit/fabric/test_world_store_phase9.py`.

Minimum tests:

### 8.1 `test_emit_doc_meta_facts_idempotent_fact_ids()`

- Build a valid `DocMeta` with deterministic ids:
  - `doc_source_id = doc_source_id(canonical_url=..., official_id=None)`
  - `doc_version_id = doc_version_id_from_raw_artifact(raw_ref)`
- Use `stable_world_provenance_v1()` and emit facts twice.
- Assert:
  - the multiset of `fact_id` values is identical
  - the multiset of `(subject_id, predicate_id, object_value, target_id, valid_time)` tuples is identical
  - do **not** assert `tx_time` equality (it is expected to differ)

### 8.2 `test_emit_edge_fact_requires_target()`

- Call `emit_edge_fact(..., dst_id="")` or `dst_id=None` (depending on API choice)
- Expect `WorldFactError` or `ValidationError` (normative: `WorldFactError`)

### 8.3 `test_claim_doc_requires_citations_contract_guardrail()`

- This is already covered by IR contract tests, but keep one Fabric-side sanity check:
  - constructing `Claim(source_kind=DOC, citations=[])` must raise `ValidationError`

### 8.4 `test_write_world_fact_segment_roundtrip()`

- Create a small list of valid world facts (e.g., 3 node facts + 1 edge fact).
- Write a segment to a `tmp_path` fact_log_root.
- Append to index.
- Load manifests via `load_world_fact_manifests()`.
- Read parquet file and assert:
  - required columns exist (see §4.2)
  - `row_count` in manifest matches parquet row count
  - `sha256` in manifest matches file bytes sha256 (writer already does this; re-check in test)

---

## 9) Definition of Done (Phase 9 / E2.2)

1. `polisyos.fabric.world.store` package exists with modules described in §3.1.
2. Write-path primitives exist and are usable:

   - persist typed world objects to CAS (DocMeta/DocFragment/Claim/WorldEvent)
   - emit ABI world facts (node baseline + edges + minimal PROV)
   - write world fact segments and `_segments.jsonl` index under a dedicated `world/` channel
3. Runtime validations exist:

   - deterministic id checks for typed objects
   - fact ABI validation (world._+ world.rel._ strict)
4. Minimal tests in §8 pass.
5. Dependency guard stays green (no `fabric -> scientist` leaks).

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 0 world ID/CAS determinism and Phase 2 lineage graph inputs                                                                              |
| Contract tests      | `tests/contract/test_world_abi_contract.py`, `tests/unit/fabric/test_world_store.py`, `tests/unit/fabric/connectors/test_ingestion_fetch_activity_contract.py` |
| Schema snapshots    | `schemas/snapshots/ir/world_event.schema.json`, `schemas/snapshots/ir/fact.schema.json`, `schemas/snapshots/ir/fact_segment_manifest.schema.json`    |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                               |
