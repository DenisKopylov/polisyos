# E2.3 (Phase 10) — DuckDB World Materialization v1.0: `world_nodes/world_edges` + projections (`docs/claims/events`) + conflicts schema (placeholder)

**Repo snapshot date**: 2026-02-03  
**Scope**:
- new DuckDB DDL contract: `policy-engine/src/polisyos/fabric/world/ddl/duckdb_world.sql`
- new world materializer package (Phase 10): `policy-engine/src/polisyos/fabric/world/materialize/*`
- new tests (Phase 10): `policy-engine/tests/fabric/test_world_materialization_phase10.py`

This phase turns **World FactLog segments** (Phase 9 / E2.2) into a **DuckDB analytical schema** that is:

- fast for joins and filters (canonical `world_nodes/world_edges`)
- able to answer “document/claim/event” questions via projections
- **incremental** over fact segments (`_meta_world_segments`)
- deterministic & idempotent (re-apply does not grow PK counts)

> Important repo-specific constraint: Phase 9 intentionally emits **only node baseline facts** (`world.kind/label/artifact_id/props_ref`) and **edges** (`world.rel.*`). Detailed Doc/Claim/Event fields live in **CAS artifacts** (see E2.2 §6.5.2 notes).  
> Therefore, Phase 10 projections are **CAS-driven**, keyed by `world_nodes.artifact_id` (latest meta) + edge tables for relationships.

---

## 0) Goal (what exists after Phase 10)

Given:

- a world FactLog directory: `<fact_log_root>/world/` containing parquet segments + `_segments.jsonl` (Phase 9),
- a DuckDB database (existing `SimulationDB`, Phase E1.x),
- a CAS root (Core `FileSystemCAS`) containing persisted `DocMeta/DocFragment/Claim/WorldEvent` artifacts (Phase 9),

we can run one call:

```python
materialize_world_duckdb_from_fact_log(fact_log_root, db, cas)
```

and obtain a DuckDB schema `world` with:

**Canonical graph tables**
- `world.world_facts` (optional but recommended as “raw index”)
- `world.world_nodes` (canonical nodes)
- `world.world_edges` (canonical edges)

**Projections (read-friendly tables)**
- `world.doc_sources`, `world.doc_versions`, `world.doc_fragments`
- `world.claims`, `world.claim_citations`
- `world.world_events`
- `world.conflict_sets`, `world.conflict_members` (**schema only**, since conflict objects are not in IR World ABI v1.0 as of 2026-02-03)

**Incrementality**
- meta-table `world._meta_world_segments` stores applied segments and diagnostic counters.

---

## 1) Inputs & constraints (repo reality)

### 1.1 FactLog segment contracts (Phase 9)

Sources of truth:

- Fact contracts: `policy-engine/src/polisyos/ir/fact_log.py`
- Fact parquet writer: `policy-engine/src/polisyos/fabric/fact_writer.py`
- World channel IO: `policy-engine/src/polisyos/fabric/world/store/segments.py`

World segments are written under:

- `<fact_log_root>/world/<segment_id>.parquet`
- `<fact_log_root>/world/_segments.jsonl`

Parquet columns (normative, Phase 9):

- `fact_id` (PK-like; `sha256:<hex64>`)
- `schema_version`
- `subject_id` (WorldID)
- `predicate_id` (World predicate id)
- `object_value` (stringified scalar; nullable)
- `target_id` (WorldID; nullable)
- `valid_time` (str|int; nullable)
- `tx_time` (ISO string; not part of fact hash)
- `provenance` (JSON string)
- `trust` (JSON string; nullable)
- `legal` (JSON string; nullable)

### 1.2 World ABI v1.0 (Phase 8) + World Store (Phase 9)

Sources of truth:

- World ABI v1.0: `policy-engine/src/polisyos/ir/world/*` (E2.1)
- World Store emit/persist: `policy-engine/src/polisyos/fabric/world/store/*` (E2.2)

Frozen vocabularies (v1.0):

- Node kinds: `artifact`, `doc.source`, `doc.version`, `doc.fragment`, `claim`, `world.event`, `prov.agent`, `prov.activity`
- Edge kinds (minimal): `doc.has_version`, `doc.has_fragment`, `claim.cites`, `claim.derived_from`, `prov.*`
- Base predicates: `world.kind`, `world.label`, `world.artifact_id`, `world.props_ref`, and `world.rel.<edge_kind>`

Repo-specific note (Phase 9 decision):

- Doc fields (`url/mime/license/retrieved_at/...`) are **not** emitted as facts; they remain in the persisted `DocMeta` CAS artifact.
- Claim fields are also stored in the persisted `Claim` CAS artifact.
- Event fields are stored in the persisted `WorldEvent` CAS artifact.

### 1.3 Conflicts are not in ABI v1.0 (important)

As of 2026-02-03, `polisyos.ir.world` has **no** `conflict_set` NodeKind and no ConflictSet contract.

Phase 10 must:

- create DuckDB tables `world.conflict_sets` and `world.conflict_members` anyway (so downstream code can rely on schema),
- but **must not require** that they are populated.

If later phases introduce conflict facts/contracts, Phase 10 materializer can be extended to fill those tables without breaking the base schema.

---

## 2) Deliverables (what must be implemented in code)

### 2.1 DDL contract file (frozen for v1.0)

**File**: `policy-engine/src/polisyos/fabric/world/ddl/duckdb_world.sql`

This file is the **contract** for world materialization. The materializer must execute it (or an embedded copy kept identical) to ensure schema exists.

Policy:

- changing this DDL requires updating this contract doc and adding a migration plan (Phase 10 is the first “frozen DDL” moment for world materialization).

### 2.2 New materializer package

Add:

```
policy-engine/src/polisyos/fabric/world/materialize/
  __init__.py
  errors.py         # WorldMaterializationError (+ helpers)
  rules.py          # merge strategies + predicate merge table (world.*)
  staging.py        # parquet → staging frames + touched node ids
  sql.py            # SQL templates (anti-join inserts + canonical selection)
  duckdb.py         # orchestrator: apply segment, update meta, update projections
  projections.py    # CAS-driven projection builders (docs/claims/events)
```

> This is intentionally separate from the existing `policy-engine/src/polisyos/fabric/materializer.py` which materializes *non-world* facts (`macro.*`, `agent.*`, etc.).

### 2.3 Public API (Phase 10)

At minimum, implement:

```python
def ensure_world_schema(db: SimulationDB, *, ddl_path: Path | None = None) -> None: ...

def ensure_world_materialized(
    db: SimulationDB,
    cas: FileSystemCAS,
    fact_manifests: Iterable[FactSegmentManifest],
) -> WorldMaterializeStats: ...

def materialize_world_duckdb_from_fact_log(
    fact_log_root: Path,
    db: SimulationDB,
    cas: FileSystemCAS,
) -> WorldMaterializeStats: ...
```

and a per-segment entrypoint:

```python
def apply_world_segment(
    db: SimulationDB,
    cas: FileSystemCAS,
    manifest: FactSegmentManifest,
) -> WorldMaterializeSegmentStats: ...
```

### 2.4 Tests (mandatory)

Add Phase 10 tests:

```
policy-engine/tests/fabric/test_world_materialization_phase10.py
```

Required tests are specified in §9.

---

## 3) DuckDB schema contract (what `duckdb_world.sql` must contain)

The DDL contract must define:

### 3.1 Schema namespace

```sql
CREATE SCHEMA IF NOT EXISTS world;
```

### 3.2 Meta-table (incremental apply)

`world._meta_world_segments` must exist with columns:

- `segment_id` (PK) — manifest.segment_id
- `segment_sha256` — manifest.sha256
- `row_count` — manifest.row_count
- `applied_at` — timestamp
- `facts_inserted` — how many new `fact_id` rows were inserted into `world.world_facts` (if raw storage enabled)
- `nodes_touched` — how many node ids were touched by the segment
- `edges_inserted` — how many new edges were inserted into `world.world_edges`
- `projections_updated` — how many projection operations were executed for the segment (not necessarily row counts)
- `notes` — optional JSON/text for diagnostics

### 3.3 Raw fact index (optional but recommended)

`world.world_facts` should store (mostly 1:1 with the parquet schema):

- `fact_id` (PK)
- `schema_version`
- `subject_id`
- `predicate_id`
- `object_value`
- `target_id`
- `valid_time`
- `tx_time` (ISO string)
- `provenance_json` (JSON string from parquet `provenance`)
- `trust_json` (JSON string from parquet `trust`)
- `legal_json` (JSON string from parquet `legal`)
- `segment_id` (which segment inserted the fact)
- `inserted_at` timestamp

Indexes (v1.0):

- `(subject_id)`, `(predicate_id)`, `(target_id)`

### 3.4 Canonical graph tables

#### 3.4.1 `world.world_nodes`

Columns:

- `node_id` (PK)
- `kind` (NOT NULL) — canonical NodeKind string or `"unknown"` placeholder
- `label` (nullable)
- `artifact_id` (nullable) — CAS ArtifactID string (e.g., `sha256:...`) pointing to the latest typed world artifact for the node (DocMeta/DocFragment/Claim/WorldEvent)
- `props_ref` (nullable) — CAS ArtifactID string (optional properties blob)
- `updated_at`

Index:

- `(kind)`

#### 3.4.2 `world.world_edges`

Columns:

- `edge_id` (PK) — equals `fact_id` for the edge fact
- `src_id`
- `predicate_id` — full predicate, e.g. `world.rel.claim.cites`
- `kind` — edge kind stripped from predicate (`claim.cites`)
- `dst_id`
- `valid_time` (nullable)
- `tx_time` (ISO string)
- `provenance_json`, `trust_json`, `legal_json` (strings)
- `segment_id` (segment that inserted the edge; for diagnostics)
- `inserted_at`

Indexes (v1.0):

- `(kind)`
- `(src_id, kind)`
- `(dst_id, kind)`

### 3.5 Projections (v1.0)

#### 3.5.1 Documents

`world.doc_sources`:

- `doc_source_id` (PK)
- `canonical_url` (nullable)
- `official_id` (nullable)
- `jurisdiction` (nullable; latest known)
- `language` (nullable; latest known)
- `updated_at`

`world.doc_versions`:

- `doc_version_id` (PK)
- `doc_source_id` (NOT NULL)
- `retrieved_at` (TIMESTAMP; from DocMeta)
- `mime`, `license`, `jurisdiction`, `language`
- `raw_ref` (NOT NULL; ArtifactID)
- `normalized_ref`, `structure_ref`, `chunks_ref` (ArtifactID; nullable)
- `props_json` (canonical JSON string)
- `meta_artifact_id` (ArtifactID of the persisted `DocMeta` JSON; this is typically the `world_nodes.artifact_id` for doc.version nodes)
- `updated_at`

`world.doc_fragments`:

- `fragment_id` (PK)
- `doc_version_id` (NOT NULL)
- `anchor_kind` (NOT NULL)
- `anchor_path` (nullable)
- `offset_start`, `offset_end`, `page_start`, `page_end` (nullable numeric)
- `text_hash` (NOT NULL; ArtifactID)
- `quote_preview` (nullable)
- `props_json`
- `meta_artifact_id` (ArtifactID of the persisted `DocFragment` JSON)
- `updated_at`

#### 3.5.2 Claims

`world.claims`:

- `claim_id` (PK)
- `predicate_id` (NOT NULL)
- `subject_id`, `subject_text`
- `value_text` (NOT NULL)
- `value_decimal` (nullable; decimal string)
- `unit_id` (nullable)
- `confidence` (nullable; decimal string)
- `source_kind` (nullable string; from ClaimSourceKind enum)
- `jurisdiction`, `domain`
- `valid_from`, `valid_to` (TIMESTAMP; nullable)
- `qualifiers_json` (canonical JSON string)
- `props_json` (canonical JSON string)
- `meta_artifact_id` (ArtifactID of persisted Claim JSON)
- `updated_at`

`world.claim_citations`:

- composite PK `(claim_id, fragment_id)`
- `edge_id` (optional, if populated from `world_edges.edge_id`)

#### 3.5.3 Events

`world.world_events` (projection of `WorldEvent` CAS artifact):

- `event_id` (PK)
- `event_kind` (NOT NULL)
- `agent_id` (NOT NULL)
- `agent_type`, `agent_label`
- `activity_id`, `activity_type`, `activity_label`
- `started_at`, `ended_at` (TIMESTAMP; nullable)
- `evidence_ref`, `provenance_ref` (ArtifactID strings; nullable)
- `props_json`
- `meta_artifact_id` (ArtifactID of persisted WorldEvent JSON)
- `updated_at`

#### 3.5.4 Conflicts (placeholder only)

Create (even if empty):

- `world.conflict_sets(conflict_set_id PK, kind, props_json, updated_at)`
- `world.conflict_members(conflict_set_id, claim_id, edge_id, PK(conflict_set_id, claim_id))`

> No code in Phase 10 is required to populate these tables, but nothing should prevent future phases from doing so.

---

## 4) Materializer responsibilities and architecture

### 4.1 Materializer is an incremental segment applier

The materializer consumes `FactSegmentManifest` entries and applies only the new ones:

- segment uniqueness by `segment_id`
- integrity by `sha256`
- idempotency by:
  - anti-join inserts by `fact_id` and `edge_id`
  - merge rules for canonical node attributes

### 4.2 “Source of truth” hierarchy

This repo’s storage design is explicitly layered:

1. **CAS artifacts** — source of truth for rich objects (DocMeta, DocFragment, Claim, WorldEvent).
2. **World FactLog** — append-only minimal index: nodes exist + relationships exist.
3. **DuckDB world schema** — materialized, query-friendly projections.

Therefore:

- `world.world_nodes/world_edges` are derived strictly from FactLog rows.
- `world.doc_*`, `world.claims`, `world.world_events` are derived from the **latest** CAS artifacts pointed by `world.world_nodes.artifact_id` (after merge rules are applied).

### 4.3 Module specs

#### 4.3.1 `errors.py`

Define error families to allow callers to catch by category:

- `WorldMaterializationError(Exception)` base
- `WorldSchemaError(WorldMaterializationError)` DDL/schema problems
- `WorldSegmentHashMismatch(WorldMaterializationError)` manifest hash mismatch
- `WorldMergeConflict(WorldMaterializationError)` merge rule violation (e.g., `world.kind` conflict)
- `WorldArtifactReadError(WorldMaterializationError)` missing/unparseable CAS artifact

#### 4.3.2 `rules.py` (merge rules)

Define a small merge strategy enum:

- `ERROR_ON_CONFLICT`
- `PREFER_NON_NULL_LAST_TX`
- `LAST_TX`
- `FIRST_TX`

Phase 10 must hardcode (v1.0) merge rules for `world.*` attributes:

- `world.kind`: `ERROR_ON_CONFLICT`
- `world.label`: `PREFER_NON_NULL_LAST_TX`
- `world.artifact_id`: `PREFER_NON_NULL_LAST_TX`
- `world.props_ref`: `PREFER_NON_NULL_LAST_TX`

> Note: merge rules apply to “canonical view” construction (`world.world_nodes`). Facts remain append-only.

#### 4.3.3 `staging.py`

Responsibilities:

- read parquet into DataFrame (using `pd.read_parquet(manifest.path)`)
- validate minimal required columns exist (Phase 9 schema)
- split into:
  - `attr_df`: non-edge facts (target_id is NULL)
  - `edge_df`: edge facts (`predicate_id LIKE 'world.rel.%'` and `target_id IS NOT NULL`)
- compute `touched_node_ids`:
  - all `subject_id` in the segment
  - plus all `target_id` from edge facts

#### 4.3.4 `sql.py`

Provide **parametric SQL strings** (or simple helpers) for:

- creating meta-table if needed (but DDL file should already do it)
- loading applied segments
- anti-join insert of new raw facts
- anti-join insert of new edges
- inserting missing nodes (from touched ids)
- selecting canonical attribute values per node (merge rules)

#### 4.3.5 `projections.py` (CAS-driven)

Responsibilities:

- for a list of node ids + their `artifact_id`:
  - read CAS artifact bytes (`FileSystemCAS.get_bytes`)
  - `json.loads` → dict → validate typed model:
    - DocMeta: `polisyos.ir.world.doc.DocMeta`
    - DocFragment: `polisyos.ir.world.doc.DocFragment`
    - Claim: `polisyos.ir.world.claim.Claim`
    - WorldEvent: `polisyos.ir.world.event.WorldEvent`
- convert models to “row dicts” for DuckDB projections
- perform update strategy (Phase 10 contract):
  - **delete+insert** for the touched ids (safe, deterministic)

#### 4.3.6 `duckdb.py`

Responsibilities:

- ensure schema exists (`ensure_world_schema`)
- ensure meta table exists (`world._meta_world_segments`)
- load applied segments
- for each new segment:
  - verify sha256
  - apply within a transaction
  - insert raw facts (optional)
  - update canonical nodes & edges
  - update projections (docs/claims/events + edge-derived tables)
  - record segment in meta table with counters

---

## 5) Incremental apply algorithm (non-ambiguous)

### 5.1 Segment loop

Materialize entrypoint:

1. `ensure_world_schema(db)` executes `duckdb_world.sql`
2. Load manifests from world channel:
   - `load_world_fact_manifests(fact_log_root)` (Phase 9 helper)
3. Load applied segments:
   - `SELECT segment_id, segment_sha256 FROM world._meta_world_segments`
4. For each manifest (in file order):
   - if `segment_id` present:
     - if sha mismatch → raise `WorldSegmentHashMismatch`
     - else skip
   - else apply segment

### 5.2 Segment apply (transactional)

Within one DuckDB transaction:

1. Verify segment file exists.
2. Verify hash:
   - `sha256(path.read_bytes()) == manifest.sha256`
3. Read parquet into `df`.
4. If `df` empty:
   - record meta row with `facts_inserted=0, edges_inserted=0, projections_updated=0` (still mark applied to avoid rework)
5. Compute staging frames + `touched_node_ids`.
6. **Raw facts insert** (if enabled):
   - anti-join by `fact_id` into `world.world_facts`
7. **Nodes materialization**:
   - insert missing `world.world_nodes(node_id, kind='unknown')` for all touched ids
   - compute canonical attributes for touched ids and update:
     - `kind`, `label`, `artifact_id`, `props_ref`
     - `world.kind` merge rule enforced
8. **Edges materialization**:
   - from edge facts: map to edge rows and insert anti-join by `edge_id=fact_id` into `world.world_edges`
9. **Projections update**:
   - update docs/claims/events from CAS for touched ids of relevant kinds
   - update `claim_citations` from edges `kind='claim.cites'`
10. Insert meta row into `world._meta_world_segments`.

Commit transaction.

If any step fails:

- rollback transaction
- do **not** write meta row (segment stays unapplied)

### 5.3 Dedupe rules (must be stable)

- Edge primary key = `edge_id = fact_id` (Phase 10 invariant)
- Raw facts primary key = `fact_id`
- Nodes primary key = `node_id`

No other “fuzzy” dedup in v1.0.

---

## 6) Canonical node construction (merge rules)

### 6.1 Where node attributes come from

In Phase 9, only these attributes are emitted as facts:

- `world.kind`
- `world.label`
- `world.artifact_id`
- `world.props_ref`

The canonical `world.world_nodes` must be computed from the union of all known attribute facts (append-only), using merge rules.

### 6.2 Required behaviour per attribute

#### 6.2.1 `world.kind` — `ERROR_ON_CONFLICT`

For any node:

- if there are **0** kind facts: keep `kind='unknown'`
- if there is **1** distinct kind value: set it
- if there are **>=2** distinct kind values: raise `WorldMergeConflict`

Rationale:

- NodeKind collision is ABI-breaking and indicates emitter bug or id collision.

#### 6.2.2 `world.label` — `PREFER_NON_NULL_LAST_TX`

Select the label fact with:

1. `object_value IS NOT NULL` preferred
2. maximum `tx_time` (lexicographic ISO works)

#### 6.2.3 `world.artifact_id` — `PREFER_NON_NULL_LAST_TX`

Same strategy as label. This supports “same semantic node, updated meta artifact”.

#### 6.2.4 `world.props_ref` — `PREFER_NON_NULL_LAST_TX`

Same strategy as label.

### 6.3 Implementation hint (DuckDB SQL)

Canonical selection can be implemented via window functions over `world.world_facts`:

- filter to touched node ids and predicate in `{world.kind, world.label, world.artifact_id, world.props_ref}`
- use `ROW_NUMBER() OVER (PARTITION BY subject_id, predicate_id ORDER BY ...)`
- pick `rn=1`

`world.kind` conflict can be detected by:

```sql
SELECT subject_id
FROM world.world_facts
WHERE predicate_id='world.kind'
  AND subject_id IN (...)
GROUP BY subject_id
HAVING COUNT(DISTINCT object_value) > 1;
```

---

## 7) Canonical edge construction

### 7.1 Which facts become edges

Edge facts are:

- `predicate_id LIKE 'world.rel.%'`
- `target_id IS NOT NULL`

Materialization mapping:

- `edge_id = fact_id`
- `src_id = subject_id`
- `predicate_id = predicate_id`
- `kind = predicate_id[len('world.rel.'):]`
- `dst_id = target_id`
- metadata copied through as strings:
  - `valid_time`, `tx_time`, `provenance_json`, `trust_json`, `legal_json`

### 7.2 Dedupe rule (stable)

Insert only edges with `edge_id` not present in `world.world_edges`.

---

## 8) Projections: docs / claims / events (CAS-driven)

### 8.1 Normative approach for v1.0

Phase 10 uses a hybrid approach:

- Graph index comes from FactLog → `world_nodes/world_edges`
- Rich projections are loaded from CAS artifacts referenced by `world_nodes.artifact_id`

This is required because Phase 9 does not emit doc.* / claim.* / event.* attributes as facts.

### 8.2 Projection update strategy (v1.0)

For each projection table, updates are executed only for touched node ids of relevant kinds:

1. Identify node ids to update:
   - `SELECT node_id, kind, artifact_id FROM world.world_nodes WHERE node_id IN touched_ids`
2. For each kind group:
   - if `artifact_id` is NULL: skip (cannot load projection row)
   - else load artifact JSON from CAS and validate typed model
3. For each updated table:
   - `DELETE ... WHERE <pk> IN (...)`
   - `INSERT ... SELECT ... FROM <staging_df>`

This ensures:

- updates reflect latest artifact_id chosen by merge rules
- “same PK but different artifact payload” is handled cleanly

### 8.3 Documents projections

#### 8.3.1 `doc_versions` (from `DocMeta`)

Input:

- nodes where `kind='doc.version'` and `artifact_id` points to a persisted `DocMeta` JSON artifact (Phase 9: `persist_doc_meta`).

Validation:

- parse artifact → `DocMeta`
- optionally run deterministic id validators:
  - `polisyos.fabric.world.store.validate_doc_meta_ids(meta)`

Row mapping:

- `doc_version_id = meta.doc_version_id`
- `doc_source_id = meta.doc_source_id`
- `retrieved_at = meta.retrieved_at`
- `mime = meta.mime`
- `license = meta.license`
- `jurisdiction = meta.jurisdiction`
- `language = meta.language`
- `raw_ref = meta.raw_ref`
- `normalized_ref = meta.normalized_ref`
- `structure_ref = meta.structure_ref`
- `chunks_ref = meta.chunks_ref`
- `props_json = json.dumps(meta.props, sort_keys=True, separators=(',', ':'))` (or reuse IR canonical bytes → str)
- `meta_artifact_id = node.artifact_id`

#### 8.3.2 `doc_sources` (derived from DocMeta)

Rule:

- `doc_sources` is derived from the **set of doc versions** present in `doc_versions`:
  - for each `DocMeta`, insert/update `doc_source_id` row.

Row mapping:

- `doc_source_id = meta.doc_source_id`
- `canonical_url = meta.canonical_url` (nullable)
- `official_id = meta.official_id` (nullable)
- `jurisdiction = meta.jurisdiction` (best-effort; latest known)
- `language = meta.language` (best-effort; latest known)

Merge rule inside projections (v1.0):

- `canonical_url/official_id` must be stable for a doc_source_id:
  - if multiple non-null conflicting values exist → raise `WorldMergeConflict`
- for nullable fields like jurisdiction/language:
  - prefer non-null from the latest `retrieved_at` among versions for that source

#### 8.3.3 `doc_fragments` (from `DocFragment`)

Input:

- nodes where `kind='doc.fragment'` and `artifact_id` points to persisted `DocFragment` JSON.

Row mapping:

- `fragment_id = fragment.fragment_id`
- `doc_version_id = fragment.doc_version_id`
- locator fields:
  - `anchor_kind = fragment.locator.anchor_kind.value`
  - `anchor_path = fragment.locator.anchor_path`
  - `offset_start/end`, `page_start/end`
- `text_hash = fragment.text_hash`
- `quote_preview = fragment.quote_preview`
- `props_json` from `fragment.props`
- `meta_artifact_id = node.artifact_id`

### 8.4 Claims projections

#### 8.4.1 `claims` (from `Claim`)

Input:

- nodes where `kind='claim'` and `artifact_id` points to persisted `Claim` JSON (Phase 9: `persist_claim`).

Row mapping:

- `claim_id = claim.claim_id`
- `predicate_id = claim.predicate_id`
- `subject_id = claim.subject_id`
- `subject_text = claim.subject_text`
- `value_text = claim.value_text`
- `value_decimal = str(claim.value_decimal) if not None`
- `unit_id = claim.unit_id`
- `confidence = str(claim.confidence)` (Decimal → string)
- `source_kind = claim.source_kind.value`
- `jurisdiction = claim.jurisdiction`
- `domain = claim.domain`
- `valid_from = claim.valid_from`
- `valid_to = claim.valid_to`
- `qualifiers_json` from `claim.qualifiers`
- `props_json` from `claim.props`
- `meta_artifact_id = node.artifact_id`

#### 8.4.2 `claim_citations` (from edges)

Source:

- `world.world_edges` filtered by `kind='claim.cites'`

Mapping:

- `claim_id = src_id`
- `fragment_id = dst_id`
- `edge_id = edge_id`

Update strategy (v1.0):

- delete+insert for all citations where `claim_id` in touched claim ids OR where `fragment_id` in touched ids.

### 8.5 Events projection (`world_events`)

Input:

- nodes where `kind='world.event'` and `artifact_id` points to persisted `WorldEvent` JSON (Phase 9: `persist_world_event`).

Row mapping (best-effort; keep nullable):

- `event_id = event.event_id`
- `event_kind = event.event_kind.value`
- agent:
  - `agent_id = event.agent.agent_id`
  - `agent_type = event.agent.agent_type.value`
  - `agent_label = event.agent.label`
- activity:
  - `activity_id = event.activity.activity_id`
  - `activity_type = event.activity.activity_type.value`
  - `activity_label = event.activity.label`
  - `started_at = event.activity.started_at`
  - `ended_at = event.activity.ended_at`
- `evidence_ref = event.evidence_ref`
- `provenance_ref = event.provenance_ref`
- `props_json` from `event.props`
- `meta_artifact_id = node.artifact_id`

---

## 9) Tests (mandatory)

All tests are end-to-end at the “Phase 10 surface”:

- create CAS + world facts segment(s)
- run materializer
- assert DuckDB schema/tables + key invariants

### 9.1 Test 1: single segment → nodes/edges/projections

`test_materialize_single_segment_creates_nodes_edges_projections()`

Setup:

- `tmp_path` as fact_log_root
- `FileSystemCAS(tmp_path / "cas")`
- `SimulationDB(db_path=str(tmp_path/"sim.duckdb"))`
- create and persist:
  - one DocMeta artifact (`persist_doc_meta`)
  - one WorldEvent artifact (`persist_world_event`)
  - optionally one Claim artifact (`persist_claim`) with at least one citation edge to a fragment id
- emit facts:
  - `emit_doc_meta_facts(meta, meta_artifact_id, stable_provenance)`
  - `emit_world_event_facts(event, event_artifact_id, event_provenance)`
  - `emit_edge_fact(..., edge_kind=EdgeKind.CLAIM_CITES, ...)` + baseline claim node facts
- write world segment + index using Phase 9 helpers.

Assertions:

- DuckDB has schema `world` and tables exist
- `world.world_nodes` contains at least:
  - `doc.source`, `doc.version`, `world.event`, `prov.agent` rows
- `world.world_edges` contains at least:
  - `doc.has_version` and some `prov.*` edges
- projections:
  - `world.doc_versions` contains the version row with correct `raw_ref/mime/license`
  - `world.world_events` contains event row with event_kind, agent_id, activity_id

### 9.2 Test 2: idempotent re-apply

`test_materialize_idempotent_on_reapply()`

Setup:

- same as above, but call materializer twice.

Assertions:

- count of `world.world_edges.edge_id` unchanged between runs
- count of `world.world_facts.fact_id` unchanged (if raw facts enabled)
- meta table has exactly 1 row for that segment_id (or 1 row if applied once; second run skips)

### 9.3 Test 3: `world.kind` conflict fails

`test_merge_rules_world_kind_conflict_fails()`

Setup:

- create two facts for the same `subject_id`, predicate `world.kind`:
  - object_value `"doc.version"`
  - object_value `"claim"`
  - both with stable provenance (so both are semantic assertions)
- write them into one segment and materialize.

Assertion:

- materializer raises `WorldMergeConflict` (or `WorldMaterializationError`)

### 9.4 Test 4: claim citations projection

`test_projection_claim_citations()`

Setup:

- create a claim node + edge `world.rel.claim.cites` to some fragment id
- materialize

Assertion:

- `world.claim_citations` contains `(claim_id, fragment_id)` row

---

## 10) Definition of Done (Phase 10)

Phase 10 is complete when:

1. A single entrypoint can materialize world schema from `<fact_log_root>/world/` incrementally.
2. DuckDB tables exist per `duckdb_world.sql` contract.
3. `world.world_nodes` and `world.world_edges` are populated end-to-end from world fact segments.
4. At minimum, `doc_versions` and `world_events` projections are populated end-to-end from CAS artifacts referenced by world nodes.
5. Idempotency is proven by tests (re-apply does not increase PK counts).
6. Merge conflict for `world.kind` is detected and surfaced as a dedicated error.

## D1-L4 Validation Links

| Link type | Current anchor |
|-----------|----------------|
| Source plan phase | D1-L4 Phase 0 world ABI determinism and Phase 4 ecosystem/materialization bridge |
| Contract tests | `tests/contract/test_world_abi_contract.py`, `tests/fabric/test_world_store.py`, `tests/fabric/test_world_materialization.py` |
| Schema snapshots | `schemas/snapshots/ir/world_event.schema.json`, `schemas/snapshots/ir/claim.schema.json`, `schemas/snapshots/ir/doc_fragment.schema.json`, `schemas/snapshots/ir/doc_meta.schema.json` |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md) |
