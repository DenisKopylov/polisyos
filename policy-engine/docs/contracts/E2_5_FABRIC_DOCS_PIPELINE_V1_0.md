# E2.5 (Phase 12) — Fabric Docs v1.0: deterministic pipeline `ingest → normalize → structure → chunk` (Documents as first‑class World Graph entities)

**Repo snapshot date**: 2026-02-03  
**Scope**:

- new package: `policy-engine/src/polisyos/fabric/docs/*`
- new tests: `policy-engine/tests/unit/fabric/test_docs_pipeline_phase12.py`
- (no IR contract changes required for MVP): re-use `policy-engine/src/polisyos/ir/world/*` + `policy-engine/src/polisyos/ir/citations.py`

This phase implements the **data-plane** “Documents pipeline” on top of the already-existing:

- **IR World ABI v1.0** (E2.1): `DocMeta`, `DocFragment`, `WorldEvent`, ID rules  
  `policy-engine/src/polisyos/ir/world/*`

- **World Store write-path** (E2.2): persist typed objects into CAS + emit World facts into FactLog (`/world/`)  
  `policy-engine/src/polisyos/fabric/world/store/*`

- **DuckDB World materialization** (E2.3): FactLog → `world.*` tables + CAS-driven projections  
  `policy-engine/src/polisyos/fabric/world/materialize/*` and `policy-engine/src/polisyos/fabric/world/ddl/duckdb_world.sql`

---

## 0) Goal (what exists after Phase 12)

### 0.1 Documents become first-class entities of Fabric World Graph

After Phase 12, documents are represented in the World Graph as:

- nodes:
  - `doc.source` (World node kind) — stable identity of the document “as a thing”
  - `doc.version` — content-addressed version (derived from raw bytes artifact)
  - `doc.fragment` — citation-grade fragments/chunks
- edges:
  - `doc.has_version`: `doc.source → doc.version`
  - `doc.has_fragment`: `doc.version → doc.fragment`

### 0.2 Deterministic, reproducible pipeline

We introduce a deterministic pipeline (no network; no ML):

1. **Ingest** raw bytes → CAS (`fabric.doc.raw`) + `DocMeta` + world facts + `WorldEvent`
2. **Normalize** raw → canonical text artifact (`fabric.doc.normalized`) + update `DocMeta.normalized_ref` + `WorldEvent`
3. **Structure** normalized text → anchors/sections artifact (`fabric.doc.structure`) + `DocFragment` (anchors) + facts + `WorldEvent`
4. **Chunk** normalized text → deterministic chunk-set artifact (`fabric.doc.chunks`) + `DocFragment` (chunks) + facts + `WorldEvent`

### 0.3 End-to-end verification via DuckDB materialization

Running the pipeline and then materializing World facts must yield:

- `world.doc_sources` has 1 row
- `world.doc_versions` has 1 row with `raw_ref`, `normalized_ref`, `structure_ref`, `chunks_ref`
- `world.doc_fragments` has `>0` rows (structure fragments + chunk fragments)
- `world.world_edges` includes `doc.has_version` and `doc.has_fragment`
- `world.world_events` includes events for each pipeline stage

---

## 1) Non-goals (explicitly out of scope for Phase 12)

- Scholar/Lex (claims extraction, normative structuring of laws, conflict resolution).
- Embedding indexes / vector DB / full-text search.
- “Perfect” HTML semantic structuring (tables, lists, footnotes) — MVP only.
- PDF parsing **in core MVP** (no dependencies in `pyproject.toml`); PDF support is optional (see §12).
- Any new IR ABI fields for `DocMeta`/`DocFragment` (MVP must work with the existing IR contracts).

---

## 2) Repository reality constraints (must be respected)

### 2.1 ID rules are already enforced by validators

Source of truth:

- `DocMeta` must satisfy:
  - `doc_source_id == doc_source_id(canonical_url|official_id)`
  - `doc_version_id == doc_version_id_from_raw_artifact(raw_ref)`  
    Implemented in: `policy-engine/src/polisyos/fabric/world/store/validate.py`
- `DocFragment.fragment_id` must satisfy:
  - `fragment_id == doc_fragment_id(doc_version_id, locator, text_hash)`

**Critical implication for Phase 12**:

- `doc_source_id` MUST be derived only from `canonical_url` OR `official_id`.
  - **Do not** include `source_type`, jurisdiction, language in doc_source_id derivation in Phase 12.
  - Put all extra identity hints into `DocMeta.props`.
- `doc_version_id` MUST be derived from the **raw bytes artifact id** (`DocMeta.raw_ref`).

### 2.2 FactLog write-path must go through World Store

World facts must be produced via:

- `polisyos.fabric.world.store.persist_*`
- `polisyos.fabric.world.store.emit_*_facts`
- `polisyos.fabric.world.store.write_world_fact_segment` + `append_world_segment_index`

No producers should call `polisyos.fabric.fact_writer.write_fact_segment()` directly for world facts.

### 2.3 World materialization projections are CAS-driven

DuckDB projections for documents are built from:

- `world.world_nodes.artifact_id` (latest meta artifact for `doc.version`, latest fragment artifact for `doc.fragment`)
- `DocMeta` fields stored in CAS (`raw_ref`, `normalized_ref`, `structure_ref`, `chunks_ref`)

Therefore:

**Every time we update `DocMeta.*_ref`, we MUST re-persist `DocMeta` and re-emit `emit_doc_meta_facts(meta, meta_artifact_id=<new>)`**, so that the canonical `world_nodes.artifact_id` for `doc.version` points to the updated meta artifact.

### 2.4 Dependencies available in this repo (MVP constraint)

From `policy-engine/pyproject.toml`:

- No `beautifulsoup4`, `lxml`, `pdfminer`, `pypdf`.
- Therefore:
  - `text/plain` is always supported.
  - `text/html` is supported via stdlib `html.parser` only (simplified extraction).
  - PDF is out-of-scope unless implemented as optional backend with optional deps.

---

## 3) Package layout (`polisyos.fabric.docs`) — mandatory deliverable

Create the new package (separate from `polisyos.fabric.world` by design):

```text
policy-engine/src/polisyos/fabric/docs/
  __init__.py
  errors.py
  types.py
  ingestion.py
  normalize.py
  structure.py
  chunking.py
  backends/
    __init__.py
    text_plain.py
    text_html.py
    pdf.py          # optional; may raise NotImplementedError if deps missing
```

### 3.1 Why a separate package from `fabric.world`

- `polisyos.fabric.world` is **World Graph infrastructure** (facts/events/materialize/query).
- `polisyos.fabric.docs` is a **domain subsystem** operating on document bytes/text and producing:
  - CAS artifacts (`fabric.doc.*`)
  - typed world objects (`DocMeta`, `DocFragment`, `WorldEvent`)
  - world facts/events via `fabric.world.store`

This separation keeps infra stable while allowing the docs pipeline to evolve independently.

---

## 4) Public API (Phase 12) — stable surface for producers

### 4.1 Public entrypoints

Expose these functions from `polisyos.fabric.docs.__init__`:

```python
def ingest_doc_bytes(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    source: DocSourceSpec,
    raw_bytes: bytes,
    mime: str,
    options: DocIngestOptions | None = None,
    segment_name: str | None = None,
) -> DocIngestResult: ...

def normalize_doc(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    options: DocNormalizeOptions | None = None,
    segment_name: str | None = None,
) -> DocNormalizeResult: ...

def structure_doc(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    options: DocStructureOptions | None = None,
    segment_name: str | None = None,
) -> DocStructureResult: ...

def chunk_doc(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    options: DocChunkOptions | None = None,
    segment_name: str | None = None,
) -> DocChunkResult: ...
```

### 4.2 Why `doc_meta_artifact_id` is the “handle”

Phase 12 must not depend on DuckDB/Kùzu for read-path. Without a DB, the only stable reference we always have is:

- CAS artifact id of `DocMeta` (the latest meta snapshot for a doc.version)

Therefore:

- All steps after ingestion take `doc_meta_artifact_id` to load the latest `DocMeta` and proceed.
- (Optional future extension) allow passing `doc_version_id` and resolving it via a world query API.

---

## 5) Types (`types.py`) — inputs, options, results (implementation-level)

### 5.1 `DocSourceSpec` (pipeline input; not a World model)

`DocSourceSpec` is a convenience input. It is NOT stored as a world node directly.

Recommended fields:

- identity (exactly one required):
  - `canonical_url: str | None`
  - `official_id: str | None`
  - `source_locator: str | None` (fallback; will map to `DocMeta.official_id`)
- metadata:
  - `license: str` (required; maps to `DocMeta.license`)
  - `retrieved_at: datetime | None` (default now UTC; maps to `DocMeta.retrieved_at`)
  - `jurisdiction: str | None` (maps to `DocMeta.jurisdiction`)
  - `language: str | None` (maps to `DocMeta.language`)
  - `source_type: str | None` (stored into `DocMeta.props["source_type"]`)
  - `title: str | None` (stored into `DocMeta.props["title"]`)
  - `publisher: str | None` (stored into `DocMeta.props["publisher"]`)

**Repo constraint**: `DocMeta` (IR) allows only one of `canonical_url` or `official_id`.  
Mapping rule (Phase 12):

1. if `canonical_url` provided → set `DocMeta.canonical_url`
2. else if `official_id` provided → set `DocMeta.official_id`
3. else if `source_locator` provided → set `DocMeta.official_id = source_locator`

Store extra identity hints (e.g. both URL and official id) into `DocMeta.props`.

### 5.2 Options (all deterministic; no runtime timestamps inside options)

#### `DocIngestOptions`

- `raw_kind: str = "fabric.doc.raw"` (CAS kind)
- `enforce_max_bytes: int | None` (optional guardrail)
- `agent_id: str = "prov.agent.fabric_docs"`
- `activity_id: str = "prov.activity.fabric_docs.ingest"`

#### `DocNormalizeOptions`

- `normalized_kind: str = "fabric.doc.normalized"`
- decoding:
  - `encoding_order: list[str] = ["utf-8", "utf-8-sig", "latin-1"]`
  - `errors: str = "strict"` (if strict fails for all, fallback to "replace" deterministically)
- text normalization:
  - `normalize_newlines: bool = True` (CRLF/CR → LF)
  - `strip_trailing_whitespace: bool = False` (default False to keep offsets stable)
  - `collapse_blank_lines: bool = False` (default False)
- html:
  - `html_extract_mode: Literal["visible_text_v1"] = "visible_text_v1"`

#### `DocStructureOptions`

- `structure_kind: str = "fabric.doc.structure"`
- `algorithm: Literal["anchors_v1"] = "anchors_v1"`
- `max_heading_len: int = 160`
- `min_section_chars: int = 200` (drop tiny sections)
- `include_full_document_anchor: bool = True` (always true for MVP)

#### `DocChunkOptions`

- `chunks_kind: str = "fabric.doc.chunks"`
- `algorithm: Literal["char_chunks_v1"] = "char_chunks_v1"`
- `chunk_size_chars: int = 2000`
- `overlap_chars: int = 200` (must be `< chunk_size_chars`)
- `min_chunk_chars: int = 200`
- `boundary: Literal["fixed", "paragraph"] = "fixed"`

### 5.3 Result types

Use frozen dataclasses or Pydantic models with:

- `doc_source_id: str` (WorldID)
- `doc_version_id: str` (WorldID)
- `raw_ref: str` / `normalized_ref: str | None` / `structure_ref: str | None` / `chunks_ref: str | None`
- `doc_meta_artifact_id: str` (ArtifactID string)
- `world_event_id: str` and `world_event_artifact_id: str`
- `world_segment_manifest: FactSegmentManifest`
- per-step additional fields:
  - `structure_doc`: `structure_ref`, `fragment_ids`
  - `chunk_doc`: `chunks_ref`, `chunk_fragment_ids`

---

## 6) Artifact kinds (`fabric.doc.*`) — required in Phase 12

Phase 12 introduces these new CAS kinds (data-plane artifacts; not world store artifacts):

- `fabric.doc.raw` — raw bytes (media_type = input MIME)
- `fabric.doc.normalized` — JSON: canonical extracted text + stats + normalization parameters
- `fabric.doc.structure` — JSON: anchors/sections + algorithm parameters
- `fabric.doc.chunks` — JSON: chunk set (deterministic ranges) + algorithm parameters

**Important**: World objects remain separate kinds and are already implemented:

- `fabric.world.doc_meta` (typed `DocMeta`)
- `fabric.world.doc_fragment` (typed `DocFragment`)
- `fabric.world.event` (typed `WorldEvent`)

---

## 7) Offsets & locator semantics (must be consistent everywhere)

### 7.1 Offset convention for `FragmentLocator.offset_start/offset_end`

Phase 12 standardizes:

- offsets are **0-based**
- `offset_start` is **inclusive**
- `offset_end` is **exclusive**

So the fragment text is reconstructed as:

```python
fragment_text = normalized_text[offset_start:offset_end]
```

This convention must be recorded in:

- `fabric.doc.structure` artifact (`"range_semantics": "python_slice"`)
- `fabric.doc.chunks` artifact

### 7.2 `DocFragment.text_hash` policy in Phase 12 (CAS-safe MVP)

Repo contract requires `DocFragment.text_hash` to be an `ArtifactID` string.

Phase 12 MVP policy:

- set `DocFragment.text_hash = DocMeta.normalized_ref`

Rationale:

- avoids exploding CAS by storing full fragment text blobs per fragment
- fragment reconstruction is possible from `(normalized_ref, locator)`
- fragment identity is still stable via `doc_fragment_id(doc_version_id, locator, text_hash)`

> Future (Phase 12.x / 13): optionally introduce `fabric.doc.fragment_text` blobs and set `text_hash` to those (citation-grade quote integrity).

---

## 8) Step 1 — Ingestion (`ingestion.py`): raw bytes → `DocMeta` + world facts + `WorldEvent`

### 8.1 Input

- `DocSourceSpec source`
- `raw_bytes: bytes`
- `mime: str` (required)

### 8.2 Strict steps (normative)

1. **Persist raw bytes into CAS**

```python
raw_ref = cas.put_bytes(
    raw_bytes,
    opts=PutOptions(kind="fabric.doc.raw", media_type=mime, schema=SchemaInfo(...)),
)
raw_artifact_id = str(raw_ref.artifact_id)   # "sha256:<hex>"
```

1. **Derive world ids (strictly per IR)**

```python
doc_source_id = doc_source_id(canonical_url=..., official_id=...)
doc_version_id = doc_version_id_from_raw_artifact(raw_artifact_id=raw_artifact_id)
```

1. **Build `DocMeta` (IR contract)**

Populate:

- ids: `doc_source_id`, `doc_version_id`
- identity: `canonical_url` XOR `official_id`
- fields: `retrieved_at`, `mime`, `license`, optional `jurisdiction`, `language`
- refs: `raw_ref=raw_artifact_id`, all other refs initially `None`
- `props`: extra metadata (source_type/title/publisher/source_locator etc), **no floats**

1. **Persist `DocMeta` through World Store**

```python
meta_ref = persist_doc_meta(cas, meta)
meta_artifact_id = str(meta_ref.artifact_id)
```

1. **Create `WorldEvent` (audit)**

Phase 12 maps stages to existing IR event kinds:

- ingestion stage → `EventKind.FETCH_DOC`

WorldEvent payload:

- `event_kind = EventKind.FETCH_DOC`
- `agent = ProvAgent(agent_id=options.agent_id, agent_type=SYSTEM, label="Fabric Docs")`
- `activity = ProvActivity(activity_id=options.activity_id, activity_type=FETCH_DOC, label="Ingest doc bytes", started_at=now, ended_at=now)`
- `inputs = []` (bytes are in-memory; optional input: an artifact containing `DocSourceSpec`)
- `outputs` MUST include:
  - `WorldObjectRef(artifact_id=raw_artifact_id)`
  - `WorldObjectRef(artifact_id=meta_artifact_id)`
  - `WorldObjectRef(world_id=doc_source_id)`
  - `WorldObjectRef(world_id=doc_version_id)`
- `evidence_ref`: optional (recommended: evidence bundle referencing raw artifact)
- `provenance_ref`: optional (may be `None` in MVP)

Compute `event_id` via `world_event_id_from_payload(payload_without_event_id)` (existing helper) and construct `WorldEvent(event_id=...)`.

Persist through World Store:

```python
event_ref = persist_world_event(cas, event)
event_artifact_id = str(event_ref.artifact_id)
```

1. **Emit World facts (strict provenance profiles)**

- semantic facts: `stable_world_provenance_v1()`
  - `emit_doc_meta_facts(meta, meta_artifact_id=meta_artifact_id, provenance=stable_prov)`
- event/audit facts: `event_world_provenance_v1(event_id)`
  - `emit_world_event_facts(event, event_artifact_id=event_artifact_id, provenance=event_prov)`

1. **Write a World fact segment**

```python
facts = stable_facts + event_facts
manifest = write_world_fact_segment(facts, fact_log_root=fact_log_root, segment_name=segment_name or "doc_ingest")
append_world_segment_index(manifest, fact_log_root=fact_log_root)
```

### 8.3 Idempotency expectations

- same `raw_bytes` → same `raw_artifact_id` → same `doc_version_id`
- semantic facts for `doc.source`, `doc.version`, `doc.has_version` dedupe by `fact_id`
- each call produces a new segment; events may be new (by started_at/ended_at)

---

## 9) Step 2 — Normalize (`normalize.py`): raw → `fabric.doc.normalized` + update `DocMeta.normalized_ref` + `WorldEvent`

### 9.1 Inputs

- `doc_meta_artifact_id` (ArtifactID string)

### 9.2 Strict steps (normative)

1. Load `DocMeta` from CAS and validate ids:

- `DocMeta.model_validate(payload)`
- `validate_doc_meta_ids(meta)` (World Store validator)

1. Load raw bytes from CAS via `meta.raw_ref`.

2. Choose backend by MIME:

- `text/plain` → `backends.text_plain.normalize_plain_text_v1`
- `text/html` → `backends.text_html.normalize_html_visible_text_v1`
- otherwise:
  - if `mime` starts with `text/` → treat as plain text
  - else raise `DocUnsupportedMimeError` (MVP)

1. Produce **normalized text** deterministically:

Plain text v1:

- decode using `encoding_order` sequentially (strict)
- if all strict decodes fail → decode using first encoding with `errors="replace"` (deterministic fallback)
- normalize newlines if enabled (`\r\n`/`\r` → `\n`)

HTML v1 (stdlib-only):

- decode as above
- parse HTML with `html.parser.HTMLParser`
  - ignore text inside `<script>` and `<style>`
  - convert block boundaries (`p`, `div`, `br`, `li`, headings) into `\n`
  - collapse runs of whitespace to single spaces **inside lines** (optional; if done, document it)
- normalize newlines

1. Persist normalized artifact:

Store a JSON object in CAS:

```json
{
  "schema_version": "1.0",
  "algorithm": "normalize_v1",
  "input_mime": "...",
  "text": "...",
  "stats": { "char_count": 123, "line_count": 7 },
  "options": { ... }   // deterministic, no floats
}
```

`normalized_ref = <artifact_id of this JSON>`

1. Update `DocMeta`:

- create a new `DocMeta` instance with identical ids + raw_ref + identity fields
- set `normalized_ref` to the new normalized artifact id
- do not change `props` except if adding deterministic info (recommended: keep props stable)

Persist `DocMeta` again → `meta_artifact_id_2`

1. Emit world facts:

- semantic: `emit_doc_meta_facts(meta2, meta_artifact_id=meta_artifact_id_2, stable_prov)`
- event: create `WorldEvent(event_kind=NORMALIZE_DOC, inputs=[doc_version_id, raw_ref], outputs=[normalized_ref, meta_artifact_id_2])`
  - emit via `emit_world_event_facts(..., event_prov)`

1. Write segment: `segment_name="doc_normalize"` (or default).

### 9.3 Idempotency expectations

- If normalization is deterministic and options identical:
  - `normalized_ref` must be stable (CAS dedup)
  - updated `DocMeta` must be stable (CAS dedup)
  - semantic facts must dedupe; only events may grow on repeated calls

---

## 10) Step 3 — Structure (`structure.py`): anchors → `fabric.doc.structure` + `DocFragment` (anchors) + `WorldEvent`

### 10.1 Inputs

- `doc_meta_artifact_id` (must refer to a meta with `normalized_ref != None`)

### 10.2 Structure artifact (`fabric.doc.structure`) — canonical JSON shape

Store:

```json
{
  "schema_version": "1.0",
  "algorithm": "anchors_v1",
  "range_semantics": "python_slice",
  "doc_version_id": "docv....",
  "normalized_ref": "sha256:....",
  "options": { ... },
  "anchors": [
    {
      "anchor_kind": "heading" | "section",
      "anchor_path": "h1:1/h2:3" | null,
      "offset_start": 0,
      "offset_end": 1234,
      "title_hint": "..."
    }
  ]
}
```

### 10.3 Anchor extraction algorithm (MVP v1)

The algorithm must be deterministic and produce valid ranges.

Minimum requirements:

- always produce at least one anchor covering the full document if text non-empty
- anchors must satisfy:
  - `0 <= offset_start <= offset_end <= len(text)`
  - `(offset_end - offset_start) >= min_section_chars` unless it is the full-document anchor

Recommended heuristics (v1):

- If normalized artifact has `input_mime` `text/html`:
  - emit heading anchors based on detected heading lines in the normalized text
    - strategy A (simplest): during HTML extraction, prefix heading lines with `"\n# "` or `"\n## "` and then detect `^#+` in normalized text.
    - strategy B (more direct): track heading offsets in the HTML parser (preferred if implemented).
- For plain text:
  - detect heading-like lines:
    - numbered: `^\\s*\\d+(\\.\\d+)*[)\\.]\\s+\\S`
    - ALLCAPS short lines (length <= max_heading_len, has letters, ratio of uppercase high)

In MVP, it is acceptable to produce:

- only the full-document anchor for plain text if no headings detected

### 10.4 Fragment emission (anchors → `DocFragment`)

For each anchor:

- Build `FragmentLocator`:
  - `anchor_kind = AnchorKind.HEADING` or `AnchorKind.SECTION`
  - include offsets; include `anchor_path` if you have a stable scheme
- Set `DocFragment.text_hash = meta.normalized_ref` (Phase 12 policy; §7.2)
- Compute `fragment_id` via `doc_fragment_id(doc_version_id, locator, text_hash)`
- `quote_preview`: deterministic preview from the fragment text:
  - `preview = fragment_text.strip().replace("\\s+", " ")[:240]` (no randomness)
- Persist each `DocFragment` via `persist_doc_fragment(cas, fragment)` to get `fragment_artifact_id`
- Emit semantic facts via `emit_doc_fragment_facts(fragment, fragment_artifact_id=...)` (stable provenance)

### 10.5 Update `DocMeta.structure_ref`

- persist the `fabric.doc.structure` artifact → `structure_ref`
- re-persist `DocMeta` with `structure_ref=structure_ref` → `meta_artifact_id_3`
- emit `emit_doc_meta_facts(meta3, meta_artifact_id_3, stable_prov)` to update `doc.version` meta pointer

### 10.6 Structure `WorldEvent`

Create `WorldEvent(event_kind=STRUCTURE_DOC)`:

- inputs:
  - `WorldObjectRef(world_id=doc_version_id)`
  - `WorldObjectRef(artifact_id=normalized_ref)`
- outputs:
  - `WorldObjectRef(artifact_id=structure_ref)`
  - `WorldObjectRef(artifact_id=meta_artifact_id_3)`
  - `WorldObjectRef(world_id=<fragment_id>)` for each created fragment

Persist event + emit event facts (event provenance).

### 10.7 Segment write

Write one segment for the structure call containing:

- doc meta facts (stable)
- doc fragment facts for all created anchors (stable)
- world event facts (event provenance)

---

## 11) Step 4 — Chunking (`chunking.py`): deterministic chunks → `fabric.doc.chunks` + `DocFragment` (chunks) + `WorldEvent`

### 11.1 Chunk-set artifact (`fabric.doc.chunks`) — canonical JSON shape

```json
{
  "schema_version": "1.0",
  "algorithm": "char_chunks_v1",
  "range_semantics": "python_slice",
  "doc_version_id": "docv....",
  "normalized_ref": "sha256:....",
  "options": { "chunk_size_chars": 2000, "overlap_chars": 200, ... },
  "chunks": [
    {
      "offset_start": 0,
      "offset_end": 2000,
      "fragment_id": "frag....",
      "text_len": 2000,
      "text_preview": "..."    // optional; short
    }
  ]
}
```

### 11.2 Chunking algorithm (MVP v1)

Deterministic fixed-window chunking:

- validate: `0 < overlap_chars < chunk_size_chars`
- step = `chunk_size_chars - overlap_chars`
- for `start` in `range(0, len(text), step)`:
  - `end = min(start + chunk_size_chars, len(text))`
  - if `end - start < min_chunk_chars`: break
  - yield chunk `[start, end)`
  - if `end == len(text)`: break

Paragraph-aware mode (`boundary="paragraph"`) may be implemented as a deterministic refinement:

- adjust `end` to the nearest paragraph break (`\\n\\n`) within a bounded window
- MUST NOT introduce non-determinism; all tie-breakers must be explicit

### 11.3 Chunk fragments (`DocFragment`)

For each chunk range:

- `FragmentLocator(anchor_kind=AnchorKind.CHUNK, offset_start, offset_end, anchor_path=None)`
- `text_hash = meta.normalized_ref` (Phase 12 policy)
- `fragment_id = doc_fragment_id(...)`
- persist fragment, emit fragment facts

### 11.4 Update `DocMeta.chunks_ref`

- persist chunk-set artifact → `chunks_ref`
- re-persist `DocMeta` with `chunks_ref=...` → `meta_artifact_id_4`
- emit doc meta facts to update `doc.version` meta pointer

### 11.5 Chunk `WorldEvent`

`WorldEvent(event_kind=CHUNK_DOC)`:

- inputs: `doc_version_id`, `normalized_ref`
- outputs: `chunks_ref`, `meta_artifact_id_4`, chunk fragment ids

Write segment: meta facts + chunk fragment facts + event facts.

---

## 12) Format support roadmap (MVP-first, repo-realistic)

### 12.1 MVP v1 (Phase 12 required)

- `text/plain` (always)
- `text/html` (stdlib-only simplified)

### 12.2 PDF (explicitly optional)

Because repo has no PDF dependencies, Phase 12 policy:

- keep `backends/pdf.py` as an optional backend that:
  - either raises `DocUnsupportedMimeError` with a clear “install extra deps” message
  - or is implemented behind an optional dependency group (future)

PDF support should not block Phase 12 completion.

---

## 13) Tests (mandatory deliverables)

Create `policy-engine/tests/unit/fabric/test_docs_pipeline_phase12.py`.

### 13.1 Unit: determinism & invariants

- `test_ingest_same_bytes_same_doc_version_id`
  - ingest same bytes twice (fixed `retrieved_at`)
  - assert `doc_version_id` equal
  - assert `raw_ref` equal
- `test_structure_offsets_are_valid`
  - structure a small doc
  - assert each fragment locator has valid offset semantics and `end >= start`
- `test_chunking_is_deterministic`
  - chunk twice with same options
  - assert returned chunk fragment ids identical

### 13.2 Integration: end-to-end materialization smoke

Use tmp_path:

1. create `cas = FileSystemCAS(tmp_path/"cas")`
2. run pipeline: ingest → normalize → structure → chunk
3. materialize via `materialize_world_duckdb_from_fact_log(tmp_path, db, cas)`
4. assert:

   - `SELECT COUNT(*) FROM world.doc_sources` == 1
   - `SELECT COUNT(*) FROM world.doc_versions` == 1
   - `SELECT normalized_ref, structure_ref, chunks_ref FROM world.doc_versions` are not null
   - `SELECT COUNT(*) FROM world.doc_fragments` > 0
   - `SELECT COUNT(*) FROM world.world_events` >= 4
   - `world.world_edges` contains `doc.has_version` and `doc.has_fragment`

### 13.3 Regression: idempotent semantics, growing history

Run normalize/structure/chunk twice with identical options:

- `world.doc_versions` stays 1 row (same PK)
- `world.doc_fragments` count stays constant
- `world.world_events` count increases (new audit events)

---

## 14) Definition of Done (Phase 12)

1. `polisyos.fabric.docs` package exists with modules listed in §3.
2. Pipeline functions exist (§4) and only write to world via `polisyos.fabric.world.store`.
3. CAS contains `fabric.doc.*` artifacts for raw/normalized/structure/chunks.
4. World facts are emitted so that DuckDB materialization shows:

   - doc source/version rows
   - fragment rows for structure+chunks
   - events for each step
5. All new tests in §13 pass.

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 0 citation/world ID determinism and Phase 4 observation/interoperability bridge                                                  |
| Contract tests      | `tests/contract/test_world_abi_contract.py`, `tests/unit/fabric/test_docs_pipeline.py`, `tests/unit/fabric/test_world_materialization.py`              |
| Schema snapshots    | `schemas/snapshots/ir/doc_meta.schema.json`, `schemas/snapshots/ir/doc_fragment.schema.json`, `schemas/snapshots/ir/world_event.schema.json` |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                       |
