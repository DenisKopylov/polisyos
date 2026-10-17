# E2.9 (Phase 17) — Lex NormPack assembly v1.0: assemble applicable NormPacks from corpus/claims (IR contract)

Repo snapshot date: 2026-02-04

> Historical snapshot note: Repository-state statements describe the dated snapshot above; phase labels and completion criteria belong to that historical plan. They do not establish current E02 status or end-to-end functionality.

## 0) Phase goal

Lex gains the ability to assemble an **applicable** `NormPack` (the IR contract from `polisyos.ir.loading.norm_pack`) for a given `LegalContext` / `NormPackBuildRequest`:

- `jurisdiction` (required)
- `as_of` date/time (required, ISO)
- `domain/topic` (optional, MVP = simple filtering)

**Sources of norms**:

1. **Legal corpus** (Phase 16 / E2.8): `DocMeta` + `ProvisionIndexV1` (provisions represented as `doc.fragment`).
2. **Claims** from those provisions through the existing claims write path (Phase 13 / E2.6).
3. **Trust + conflict resolution** (Phase 14): `detect_conflicts`/`resolve_conflicts` from `polisyos.fabric.claims`.

**Result**:

- CAS `NormPack` artifact (content-addressed)
- `WorldEvent(kind=assemble_norm_pack)`
- at minimum, world facts: an **artifact node** for the NormPack + **PROV edges** through the event (and optionally additional domain edges).

> Important: Phase 17 does not introduce a separate Lex store. Everything is stored as CAS artifacts + facts/events in the Fabric World Graph.

---

## 1) Repository context (what already exists)

### 1.1. Lex Corpus (Phase 16 / E2.8)

Existing contract artifacts and API:

- `lex.corpus.provision_index` (`polisyos.data_forge.domains.legal.corpus.ProvisionIndex`, v1.0)
  - file: `policy-engine/src/polisyos/data_forge/domains/legal/corpus/index.py`
  - built by `build_legal_structure(...)`, which stores a list of provisions:
    - `fragment_id` (WorldID `frag.sha256_...`)
    - `anchor_path` + offsets (python slice semantics)
    - `props["lex_kind"]` (article/point/...)
- `lex.corpus.version_index` (`polisyos.data_forge.domains.legal.corpus.VersionIndex`, v1.0)
  - file: `policy-engine/src/polisyos/data_forge/domains/legal/corpus/versioning.py`
  - the selection policy is already defined in Lex (`lex.versioning_v1.effective_range_then_published_at`)
- `resolve_active_version(...)` — deterministically selects the active version for `as_of` (date semantics)

Lex already uses the World Graph:

- world nodes (`doc.source`, `doc.version`, `doc.fragment`) + edges (`doc.has_version`, `doc.has_fragment`)
- world events (`fetch_doc`, `structure_doc`, `validate`, …)

### 1.2. Fabric Claims (Phase 13 / E2.6)

Existing write path:

- `extract_claims_from_doc(...)` (chunks → claims)
- `normalize_claims(...)`
- `detect_conflicts(...)`, `resolve_conflicts(...)`

Claims are IR contracts (`polisyos.ir.world.claim.Claim`), stored as `fabric.world.claim` and indexed in world projections (`world.claims`, `world.claim_citations`, …).

### 1.3. IR NormPack (Phase 3)

The `NormPack` contract already exists:

- `policy-engine/src/polisyos/ir/norm_pack.py`:
  - `NormPack(pack_id, jurisdiction, effective_date, norms[], metadata)`
  - `NormRule(norm_id, provision_refs[], rule_type, description, applicability, backend_metadata, …)`
  - `NormRef(provision_id, citations[])` (`provision_id` may be a `fragment_id` in the MVP)

---

## 2) Scope and deliverables (code/docs)

### 2.1. New Lex NormPack assembly package (Phase 17)

New package (recommended location):

```text
policy-engine/src/polisyos/lex/normpack/
  __init__.py
  policies.py
  select_sources.py
  extract_norm_claims.py
  applicability.py
  assemble_pack.py
```

Tests:

```text
policy-engine/tests/unit/fabric/test_normpack_phase17.py
```

Documentation:

```text
policy-engine/docs/contracts/E2_9_LEX_NORMPACK_ASSEMBLY_V1_0.md
```

### 2.2. Supporting changes outside the deliverables (required for the MVP)

To satisfy the “separate `extractor_id`” requirement and ensure correct trust scoring:

1. **Add an extractor** to `polisyos.fabric.claims.backends`:

- new backend file (example):
  - `policy-engine/src/polisyos/fabric/claims/backends/lex_norm_regex_v1.py`
- registration in `_EXTRACTOR_REGISTRY`:
  - key: `"lex.norm_extractor.regex_v1"`

1. **Add extractor reliability** to the conflict policy:

- `policy-engine/src/polisyos/fabric/claims/conflicts/policies.py`
  - `extractor_reliability["lex.norm_extractor.regex_v1"] = Decimal("0.80")` (or another value; see §9.3)

1. Optionally, export a high-level API from `polisyos.lex.api`:

- `assemble_norm_pack(...)` as a facade over `polisyos.lex.normpack.assemble_pack`.

---

## 3) Input contract (MVP): `NormPackBuildRequest`

### 3.1. Where to define it

Define in `policy-engine/src/polisyos/lex/normpack/types.py`:

- `NormPackBudgets`
- `NormPackBuildRequest`
- `NormPackBuildResult` (output contract)

> NormPack request/result contracts belong to the NormPack owner; the stable `polisyos.lex` facade re-exports its supported names.

### 3.2. Fields and semantics

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class NormPackBudgets:
    max_docs: int | None = None
    max_provisions: int | None = None
    max_claims: int | None = None

@dataclass(frozen=True)
class NormPackBuildRequest:
    jurisdiction: str
    as_of: str                      # ISO date/datetime
    domain: str | None = None
    doc_source_ids: list[str] | None = None  # manual whitelist; None => "all in corpus"

    selection_policy_id: str = "lex.versioning_v1.effective_range_then_published_at"
    conflict_policy_id: str = "policy.conflicts.default_v1"
    trust_policy_id: str = "policy.trust.default_v1"  # MVP: informational/metadata-only

    budgets: NormPackBudgets = NormPackBudgets()
```

#### Normalization (required for determinism)

When assembling:

- `jurisdiction_norm = jurisdiction.strip().casefold()`
  - **requirement**: `jurisdiction_norm` must match `ID_PATTERN` (`^[a-z][a-z0-9_.-]*$`).
- `as_of_norm = normalize_as_of(as_of)`
  - accepts `YYYY-MM-DD` or an ISO datetime and returns `YYYY-MM-DD`
  - Phase 17 semantics = `date_inclusive` (as in `lex.corpus.versioning.resolve_active_version`)
- `domain_norm = domain.strip().casefold()` or `None`
  - **requirement**: if not `None`, it must match `ID_PATTERN`.
- `doc_source_ids`:
  - if set: deduplicate + sort (string order) + validate against `ID_PATTERN`

#### Budget validation

Each budget field:

- `None` = unlimited
- otherwise, `>= 0`
- `0` is allowed and means “select nothing”; in this case assembly should be short-circuited:
  - `max_docs=0` => `selected_doc_versions=[]` => NormPack with no norms (or a policy error, see below)
  - `max_provisions=0` => `selected_fragments=[]` => NormPack with no norms
  - `max_claims=0` => `claims=[]` => NormPack with no norms

Recommended MVP policy: **do not fail**; return an empty NormPack + warning.

---

## 4) Output contract (MVP): `NormPackBuildResult`

Recommended structure (frozen dataclass):

```python
@dataclass(frozen=True)
class SelectedDocVersion:
    doc_source_id: str
    doc_version_id: str
    doc_meta_artifact_id: str
    selection_policy_id: str
    used_version_index_artifact_id: str | None
    explanation: list[str]

@dataclass(frozen=True)
class NormPackBuildResult:
    request: NormPackBuildRequest
    jurisdiction_norm: str
    as_of_norm: str
    domain_norm: str | None

    selected_doc_versions: list[SelectedDocVersion]
    selected_fragment_ids: list[str]

    claim_set_artifact_ids: list[str]
    norm_claim_ids: list[str]

    conflict_set_ids: list[str]
    conflict_resolution_artifact_ids: list[str]
    trust_assessment_ids: list[str]

    norm_pack_artifact_id: str
    norm_pack_world_id: str

    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest

    warnings: list[str] = field(default_factory=list)
```

Principle: `NormPackBuildResult` must provide a complete input/output audit trail without requiring a DB read.

---

## 5) NormPack assembly pipeline (strict sequence)

The following is the normative description of the Phase 17 algorithm. The implementation should be as mechanical and deterministic as possible.

### 5.0. General determinism rules

At every step:

- every set of IDs must be:
  - `sorted(set(...))` (string ordering)
  - truncated by budgets **after** sorting
- all lists in CAS payloads (`claim_set`, `norm_pack.metadata`, …) must be sorted stably.
- do not include runtime fields (timestamps, random IDs) in `NormPack` or `NormRule` payloads.
  - write runtime/audit information to `WorldEvent` instead (unique events per run are allowed).

### 5.1. Step 1 — Select sources (document sources + versions)

#### 5.1.1. Input

- `NormPackBuildRequest`
- `cas: FileSystemCAS`
- `fact_log_root: Path`
- optionally, `db: SimulationDB` — used only to speed up queries; the algorithm must not depend on a DB being present.

#### 5.1.2. How to obtain candidate `doc_source_ids`

1. If `request.doc_source_ids is not None`:
   - `doc_source_ids = sorted(set(request.doc_source_ids))`
   - additionally, filter by `jurisdiction` (see below)

2. If `request.doc_source_ids is None` (the “all corpus documents” mode):
   - the MVP implementation must work without DuckDB, using the fact log:
     - read manifests through `polisyos.fabric.world.store.load_world_fact_manifests(fact_log_root)`
     - read parquet columns `subject_id,predicate_id,object_value,target_id,tx_time,fact_id` (at minimum)
     - collect all `subject_id` values where `predicate_id == "world.kind"` and `object_value == "doc.source"`
   - then apply the “Lex corpus documents” filter:
     - each `doc_source_id` must have versions (`world.rel.doc.has_version`)
     - at least one version must have a `DocMeta` where:
       - `meta.props["lex"]["corpus"] == "lex.corpus"` (set by `lex.corpus.ingest_v1`)
     - if this filter is too expensive for the MVP, a “best effort” approach is allowed:
       - select `doc_source_id` values that have `official_id` and/or `canonical_url` (through projections, if a DB is available)

3. After obtaining `doc_source_ids`:
   - sort
   - apply `budgets.max_docs` (if set)

#### 5.1.3. Filter by jurisdiction

Goal: only documents from the relevant jurisdiction enter NormPack assembly.

Normative MVP filter:

- A document is considered to belong to `request.jurisdiction_norm` if the **active-version metadata** contains:
  - `DocMeta.jurisdiction` (case-insensitive) == `request.jurisdiction_norm`, or
  - `DocMeta.props["lex"]["jurisdiction"]` (case-insensitive) == `request.jurisdiction_norm`

If `DocMeta` has no jurisdiction, allow the document (permissive MVP) and add a warning:

- `warning:doc_jurisdiction_missing:<doc_source_id>`

#### 5.1.4. Select the active version for `as_of`

Algorithm for each `doc_source_id`:

1. **Primary path**: use existing Lex versioning:
   - call `polisyos.lex.api.resolve_active_version(...)`
   - strategy:
     - `ActiveVersionStrategy(fact_log_root=fact_log_root)` (so it works beyond `Path(cas.root).parent`)
   - if `selected_doc_version_id is not None` is returned:
     - accept it
     - save `selected_doc_meta_artifact_id`
     - save `used_version_index_artifact_id`

2. **Required fallback path**: if `resolve_active_version` is not ready (no version-index pointer):
   - extract `doc_version_ids` from world facts:
     - find all edge facts with `predicate_id == world.rel.doc.has_version` for `subject_id==doc_source_id`
   - find the “latest DocMeta artifact” for each `doc_version_id`:
     - take `world.artifact_id` facts for `subject_id==doc_version_id`
     - select the record with max `(tx_time, fact_id)` (as in `lex.corpus.versioning._latest_object_by_subject`)
   - load `DocMeta` for each candidate and extract temporal fields:
     - `effective_from = meta.props["lex"]["effective_from"]` (ISO date/datetime string)
     - `effective_to   = meta.props["lex"]["effective_to"]`
     - `published_at   = meta.props["lex"]["published_at"]`
   - apply active-version selection:
     - `as_of_date = normalize_as_of(as_of)` as a `date`
     - a candidate is active if:
       - `effective_from <= as_of_date` and
       - `effective_to is None or as_of_date <= effective_to`
     - use a deterministic, documented tie-break:
       - `effective_from` (desc, None = date.min)
       - `published_at` (desc, None = date.min)
       - `doc_version_id` (asc)
   - if none are active by effective range:
     - fall back to `published_at <= as_of_date` (tie-break: `published_at` descending, `doc_version_id` ascending)
   - if there are no published candidates:
     - fall back to `(doc_meta_artifact_id, doc_version_id)` in deterministic order (as in `resolve_active_version`)

Output for Step 1:

- `selected_doc_versions: list[SelectedDocVersion]`
- sort all lists by `doc_source_id`

### 5.2. Step 2 — Select provisions (fragments/provisions)

#### 5.2.1. Preconditions (Lex readiness)

For each selected `doc_meta_artifact_id`, the following must hold:

- `DocMeta.normalized_ref != None` (otherwise offsets cannot be used)
- `DocMeta.props["lex"]["provision_index_ref"]` exists

If the provision index is missing, raise `LexNotReadyError`:

- “run `polisyos.data_forge.domains.legal.corpus.build_legal_structure` for this doc_version”

#### 5.2.2. Load the provision index

- `ProvisionIndexV1 = polisyos.data_forge.domains.legal.corpus.index.load_provision_index(cas, provision_index_ref)`
- validate:
  - `index.doc_version_id == meta.doc_version_id`
  - `index.doc_source_id == meta.doc_source_id`

#### 5.2.3. Filter by domain/topic (MVP, no ML)

If `request.domain_norm is None`:

- take provisions using the rules below, without additional filtering

If `request.domain_norm` is set:

- use `polisyos.lex.normpack.policies.DOMAIN_KEYWORDS`:
  - `DOMAIN_KEYWORDS[domain] = [kw1, kw2, ...]` (lowercase/casefolded)
- include a provision if:
  - a keyword appears in `ProvisionEntryV1.citation_label.casefold()`, or
  - a keyword appears in the provision-text preview (see below)

The provision-text preview must be deterministic:

- load normalized text once per document version
  - `normalized_text = load_json_artifact(cas, meta.normalized_ref)["text"]`
- preview = `normalized_text[offset_start:offset_end]`, then:
  - collapse whitespace → single spaces
  - `.casefold()`
  - length limit: first 500–1000 characters (policy)

#### 5.2.4. Provision kinds to include (MVP)

For the MVP, we recommend:

- base included kinds: `{"article", "point", "subpoint"}`
- include `paragraph` and `part` according to policy flags (see `policies.py`)

#### 5.2.5. Budgets

Apply `budgets.max_provisions` **globally**, after deterministic sorting.

Normative provision ordering:

1. `doc_version_id`
2. `provision.anchor_path`
3. `fragment_id`

> This prevents document order from having a “random” effect on which provisions fit within the limit.

Output for Step 2:

- `selected_fragment_ids: list[str]` (`frag.*`)
  - sorted and unique
- an in-memory “provision selection report” for Step 3:
  - for each `fragment_id`: offsets, `doc_version_id`, `provision_key`, `anchor_path`, `citation_label`, kind

### 5.3. Step 3 — Extract normative claims from provisions

#### 5.3.1. Requirements

- use the existing CAS/world write path (as in Fabric Claims)
  - `persist_claim`, `emit_claim_facts`, `persist_world_event`, `emit_world_event_facts`, `write_world_fact_segment`
- use an extractor ID **separate** from the usual extractors (for example, `regex_numeric_v1`):
  - `extractor_id = "lex.norm_extractor.regex_v1"` (Phase 17 ABI)
- every claim must have required citations to `doc.fragment` (the provision’s `fragment_id`).

#### 5.3.2. Extractor backend contract

The extractor implements the `ClaimExtractorFn` interface from `polisyos.fabric.claims.backends`:

```python
def extract(
    *,
    ctx: ChunkContext,
    meta: DocMeta,
    normalized_text: str,
    options: ClaimExtractOptions,
) -> list[ClaimCandidate]: ...
```

The MVP “regex_v1” parser must be fully deterministic and offline.

Recommended MVP format inside provision text (no LLM):

- the line starts with `norm:` (or `claim:`), followed by:
  - `predicate_id` (`ID_PATTERN` or a string normalized through `canonicalize_id`)
  - optional `(subject_text)`
  - then `=` or `>=`/`<=`/`>`/`<`
  - then `value` and optionally `[unit]`

Example (for fixtures and regression tests):

```text
Стаття 1...
norm: roads.lane_width_min_m >= 3.5 [m]
norm: roads.max_speed_kmh <= 50 [km]
```

English gloss: “Article 1...” (the source-text placeholder above is preserved verbatim).

#### 5.3.3. Convert `ClaimCandidate` → `Claim` (Lex layer)

Important: Phase 17 requires normalization of `jurisdiction/domain/validity`.
Because `polisyos.fabric.claims.extraction._candidate_to_claim` in Phase 13 does not populate these fields,
the Phase 17 conversion must live in `polisyos.lex.normpack.extract_norm_claims`.

Normative conversion rules:

- `predicate_id`:
  - `canonicalize_id(candidate.predicate_id)` (required)
- `subject_id`:
  - if `candidate.subject_id` is set and valid → use it
  - otherwise use a stable ID: `lex.norm` (`ID_PATTERN`)
  - **do not** default to `doc_source_id` (otherwise `conflict_key` will not group norms across documents)
- `value_text`:
  - `.strip()`; if empty => drop candidate + warning
- `value_decimal/unit_id`:
  - `unit_id = canonical_unit(...)` (if set)
  - numeric parsing:
    - if the extractor computes `value_decimal` → use it
    - otherwise `None` (allowed for definition/boolean norms)
- `citations`:
  - exactly one minimum citation:
    - `minimal_doc_citation(meta, fragment_id=<ctx.fragment_id>)`
  - additional citations are allowed only if deterministic and free of runtime props
- `jurisdiction`:
  - `request.jurisdiction_norm`
- `domain`:
  - `request.domain_norm` (may be `None`)
- `valid_from/valid_to`:
  - from `DocMeta.props["lex"].effective_from/effective_to` if available
  - conversion:
    - `YYYY-MM-DD` => `datetime(YYYY,MM,DD, tz=UTC)`
    - `datetime ISO` => parse to aware datetime in UTC
- `qualifiers`:
  - only stable data affecting `conflict_key` and `claim_id`
  - **do not** include runtime counters/trace IDs
- `props`:
  - Lex metadata that does not affect `claim_id` may be stored:
    - `{"lex": {"provision_key": ..., "anchor_path": ..., "extractor_id": ...}}`
- `confidence`:
  - MVP: a fixed value (for example, `Decimal("0.6")`) or `candidate.confidence`

Then:

- compute `claim_id` strictly through `claim_id_from_payload(...)`
- validate with `validate_claim_id(claim)`

#### 5.3.4. Dedup + budgets

Deduplicate by `claim_id`:

- if there is a duplicate:
  - keep the higher `confidence`
  - if confidence is equal, break ties by `(predicate_id, value_text, unit_id)` (ascending)

`budgets.max_claims`:

- apply after sorting the final deduplicated claims by `claim_id`
- if the list is truncated by the limit, emit a warning:
  - `warning:max_claims_truncated:<kept>/<total>`

#### 5.3.5. Persist + WorldEvent (claims extract)

For each claim:

- `persist_claim(cas, claim)` → `claim_artifact_id`
- `emit_claim_facts(claim, claim_artifact_id, stable_world_provenance_v1())`

Recommended `claim_set` (per doc_version):

- kind: `lex.norms.claim_set` (or `fabric.claims.claim_set`, with `stage="lex_norm_extract_v1"`)
- payload includes:
  - `extractor_id`
  - `doc_meta_artifact_id`
  - `doc_source_id/doc_version_id`
  - `provision_index_artifact_id`
  - `selected_fragment_ids`
  - `claims[]` (sorted by `claim_id`; contains `claim_artifact_id`)

WorldEvent for the step:

- `event_kind = EventKind.EXTRACT_CLAIMS`
- `agent_id = "prov.agent.lex_norms"`
- `activity_id = "prov.activity.lex_norms.extract"`
- `props.pipeline = "lex.normpack.extract_norm_claims_v1"`
- inputs:
  - doc_meta_artifact_id (artifact)
  - normalized_ref (artifact)
  - provision_index_artifact_id (artifact)
  - selected fragments (world ids)
- outputs:
  - claim_set_artifact_id (artifact)
  - claim ids (world ids)

### 5.4. Step 4 — (Recommended) Normalize claims

Run `polisyos.fabric.claims.normalize_claims(...)` for each `claim_set`.

Why:

- canonicalize predicate IDs and unit IDs
- canonical numeric `value_text`
- build `prov.was_derived_from` edges (new claim → old claim)

Important:

- use **normalized claim IDs** for subsequent NormPack assembly
- save `normalized_claim_set_artifact_ids` in the result

### 5.5. Step 5 — Trust scoring + conflict detection/resolution

Call:

```python
resolve_conflicts(
  cas=cas,
  fact_log_root=fact_log_root,
  db=db_or_none,
  conflict_set_ids=None,
  claim_ids=<normalized_claim_ids>,
  claim_set_artifact_ids=<normalized_claim_set_artifact_ids>,
  policy_id=request.conflict_policy_id,
)
```

Use Phase 14 results as-is:

- update `ConflictSet` artifacts with `resolution` (`winner_claim_id`, `confidence`, `rationale`, `resolution_artifact_id`)
- create `TrustAssessment` for:
  - doc versions
  - claims
  - conflict sets

### 5.6. Step 6 — Canonical claims set

Build the set of canonical claims for the NormPack:

1. load each `ConflictSet` (from `conflict_set_artifact_ids`) and collect `member_claim_ids`
2. winner claim id = `resolve_result.winner_by_conflict_set[conflict_set_id]`
3. canonical_claim_ids =
   - all winners
   - - all `claim_ids` that do not belong to any `conflict_set`

4. sort `canonical_claim_ids`

### 5.7. Step 7 — Convert claims → IR `NormRule` → IR `NormPack`

#### 5.7.1. Map Claim → NormRule (MVP, as mechanical as possible)

For each canonical claim:

- `norm_id`:
  - MVP: `norm_id = claim.claim_id` (1:1, deterministic)
- `rule_type`:
  - MVP default: `RuleType.OBLIGATION`
  - if the extractor/props marks negation (`must_not`) — `RuleType.PROHIBITION`
- `description`:
  - a stable string, for example:
    - `"{predicate_id} {value_text} [{unit_id}]"` (`unit_id` is optional)
- `provision_refs`:
  - for each citation with `fragment_id`:
    - `NormRef(provision_id=<fragment_id>, citations=[citation])`
  - sort `provision_refs` by `provision_id`
- `applicability`:
  - at minimum:
    - `jurisdiction.any_of=[request.jurisdiction_norm]`
    - `time.valid_from/valid_to` from `claim.valid_from/valid_to` (if present; ISO)
  - leave everything else empty (MVP)
- `backend_metadata`:
  - record at minimum:
    - `predicate_id`
    - `value_text`, `value_decimal`, `unit_id`
    - `source_claim_id`
    - `conflict_set_id` (if the claim won a conflict set)
    - `trust_score`/`trust_tier` (from `TrustAssessment`, if found)
    - `extractor_id` (if available in the `claim_set` payload)

#### 5.7.2. Sorting NormRules (deterministic)

Because `NormRule` has no separate `predicate_id` field, define ordering during assembly:

- `rule_sort_key = (claim.predicate_id, applicability_key, norm_id)`

Where `applicability_key` is a deterministic key:

- `sha256(canonical_json(NormRule.applicability.model_dump()))[:32]` (hex string)

#### 5.7.3. NormPack payload

Fields:

- `jurisdiction = request.jurisdiction_norm`
- `effective_date = request.as_of_norm` (YYYY-MM-DD)
- `norms = sorted NormRules`
- `pack_id`:
  - a deterministic ID derived from:
    - normalized request (jurisdiction/as_of/domain)
    - selection_policy_id/conflict_policy_id/trust_policy_id
    - the list of `selected_doc_version_ids` (sorted)
    - the list of `canonical_claim_ids` (sorted)
    - algorithm versions (`extractor_id` + conflict resolver versions)
  - recommended: compute through `stable_world_id_from_canon(prefix="normpack", payload=...)`
- `metadata` (required, deterministic):
  - `selection_policy_id`
  - `conflict_policy_id`
  - `trust_policy_id`
  - `domain` (if set)
  - `source_doc_version_ids` (sorted)
  - `source_doc_source_ids` (sorted)
  - `source_fragment_ids` (sorted; may be truncated by budgets)
  - `algorithm_versions`:
    - `norm_claim_extractor_id`
    - `claims_normalize_version` (if applied)
    - `conflict_trust_algorithm_version`
    - `conflict_resolution_algorithm_version`
  - `budgets` + `actual_counts`
  - `warnings` (sorted)

### 5.8. Step 8 — Persist NormPack + WorldEvent(kind=assemble_norm_pack)

#### 5.8.1. Persist NormPack (CAS)

Normative kind:

- `lex.norm_pack` (recommended)

SchemaInfo:

- `SchemaInfo(name="polisyos.ir.NormPack", version="1.0")` (or equivalent, but it must be fixed in code)

Inputs (PutOptions.inputs):

- include the artifacts from which the NormPack was derived:
  - provision_index_artifact_ids
  - claim_set_artifact_ids (extract + normalize)
  - conflict_resolution_artifact_ids
  - optionally, `trust_assessment_artifact_ids` (useful)

#### 5.8.2. World facts (minimum)

Semantic facts (stable provenance):

- create a world node for the NormPack as an artifact node:
  - `norm_pack_world_id = artifact_id_to_world_id(prefix="artifact", artifact_id=norm_pack_artifact_id)`
  - facts:
    - `world.kind="artifact"`
    - `world.artifact_id="<sha256:...>"`

#### 5.8.3. WorldEvent: assemble_norm_pack

WorldEvent:

- `event_kind = EventKind.ASSEMBLE_NORM_PACK`
- `agent_id = "prov.agent.lex_normpack"`
- `activity_id = "prov.activity.lex_normpack.assemble"`
- `activity_type = ProvActivityType.ASSEMBLE_NORM_PACK`
- `props` includes:
  - pipeline id/version: `"lex.normpack.assembly_v1"`
  - normalized request fields
  - policy IDs
  - counts (docs/provisions/claims/conflicts/rules)

Event inputs (WorldObjectRef):

- selected doc versions (world ids)
- selected fragments (world ids)
- norm claim ids (world ids)
- conflict_set ids (world ids)
- trust assessment ids (world ids)
- claim_set artifacts / provision_index artifacts / resolution artifacts (artifact ids)

Event outputs:

- `WorldObjectRef(world_id=norm_pack_world_id)`
- optionally, conflict set IDs (world IDs) as “secondary outputs”

Write the event artifact through `persist_world_event`, and facts through `emit_world_event_facts(..., event_world_provenance_v1(event_id))`.

#### 5.8.4. Segment write

Phase 17 facts are written to the world fact log:

- `write_world_fact_segment(facts, fact_log_root, segment_name="lex_normpack_assemble_<suffix>")`
- `append_world_segment_index(manifest, fact_log_root)`

---

## 6) Idempotency and reproducibility

### 6.1. What must be idempotent

On repeated assembly with the same request and input subgraph:

- `norm_pack_artifact_id` must match (CAS = content-addressed)
- `pack_id` inside the NormPack must match (if the payload is deterministic)
- the set of `norm_id` values must match
- `NormRule` ordering must match

### 6.2. What may be non-idempotent (audit)

- a new `WorldEvent` may be created (new `event_id`) because it includes `started_at/ended_at`.
- audit facts (PROV edges) may be added.

Important: semantic facts must use `stable_world_provenance_v1()` (as in Phase 13/16) so repeated emission does not create new `fact_id` values for the same assertions.

---

## 7) Phase 17 files (module responsibilities + connections)

### 7.1. `polisyos/lex/normpack/policies.py`

Contains:

- ID constants:
  - `DEFAULT_SELECTION_POLICY_ID`
  - `DEFAULT_CONFLICT_POLICY_ID`
  - `DEFAULT_TRUST_POLICY_ID` (MVP informational)
  - `DEFAULT_EXTRACTOR_ID = "lex.norm_extractor.regex_v1"`
  - `NORM_PACK_KIND = "lex.norm_pack"`
- domain filters:
  - `DOMAIN_KEYWORDS: dict[str, list[str]]`
  - `DEFAULT_INCLUDED_PROVISION_KINDS: set[str]`
- algorithm versions:
  - `ASSEMBLY_PIPELINE_ID = "lex.normpack.assembly_v1"`
  - `NORM_CLAIM_EXTRACT_PIPELINE_ID = "lex.normpack.extract_norm_claims_v1"`

### 7.2. `polisyos/lex/normpack/select_sources.py`

Contains:

- `normalize_as_of(...)` (ISO → date)
- `select_doc_sources(...)`:
  - implements Step 1.2 (all documents vs. whitelist)
- `select_active_doc_versions(...)`:
  - implements Step 1.4 (primary `resolve_active_version` + fallback)
- output type `SelectedDocVersion` (or import from `polisyos.lex.normpack.types`)

### 7.3. `polisyos/lex/normpack/extract_norm_claims.py`

Contains:

- provision → `ChunkContext` conversion
- call the extractor backend (`get_extractor`)
- convert `ClaimCandidate` → `Claim` (with jurisdiction/domain/validity)
- persist claims + emit facts
- persist claim_set per doc_version (extract stage)
- optionally, call `normalize_claims`
- returns:
  - claim_set_artifact_ids
  - claim_ids (raw + normalized)
  - event IDs + segment manifests (if separate events are used)

### 7.4. `polisyos/lex/normpack/applicability.py`

Contains:

- `build_norm_applicability(...)`:
  - `NormApplicability(jurisdiction.any_of=[...], time window from claim, …)`
- `applicability_key(...)`:
  - stable hash key for sorting
- optionally, `applies_to_context(...)`:
  - MVP: check jurisdiction + time window

### 7.5. `polisyos/lex/normpack/assemble_pack.py`

Contains:

- `assemble_norm_pack(...)` — end‑to‑end orchestrator:
  - Step 1–8
- `claims_to_norm_rules(...)`:
  - mapping + sorting (Step 7)
- `persist_norm_pack(...)`:
  - CAS put_json + inputs
- `emit_norm_pack_world_facts(...)`:
  - artifact node facts (stable provenance)
- `emit_norm_pack_assemble_event(...)`:
  - WorldEvent(kind=assemble_norm_pack) + facts + segment

### 7.6. `polisyos/lex/normpack/__init__.py`

Public facade:

- re-export `NormPackBuildRequest/Result` + `assemble_norm_pack` (or `build_norm_pack`)

---

## 8) Tests (required): `test_normpack_phase17.py`

Location: `policy-engine/tests/unit/fabric/test_normpack_phase17.py`

### 8.1. Unit tests

1. **Deterministic mapping Claim → NormRule**

- the same input Claim (identical fields, including citations) must produce the same `NormRule.model_dump()`.
- verify:
  - `norm_id` is stable (for example, equal to `claim_id`)
  - `provision_refs` have stable ordering
  - `backend_metadata` has no runtime fields

1. **Sorting deterministic**

- assemble 3–5 claims in different orders
- ensure `NormPack` rules are sorted identically (by predicate/applicability/`norm_id`)

### 8.2. Integration test (end-to-end)

Fixture:

- two legal documents from one jurisdiction (`UA:LAW-A`, `UA:LAW-B`), both structured (Phase 16)
- provisions contain `norm:` lines extracted by the regex extractor
- one pair of norms conflicts (for example, `roads.max_speed_kmh <= 50` vs `<= 60`)

Steps:

1. call `ingest_legal_doc_bytes` for each version
2. call `build_legal_structure` for each
3. call `build_version_index` (optional; or test fallback selection)
4. call `assemble_norm_pack` with `jurisdiction="ua", as_of="2025-06-01", domain="roads"`
5. `materialize_world_duckdb_from_fact_log(tmp_path, db, cas)`

Assert:

- the NormPack artifact exists in CAS:
  - `cas.has(ArtifactID(norm_pack_artifact_id)) == True`
- `world.world_events` contains an event:
  - `event_kind == 'assemble_norm_pack'` (or activity_id == `prov.activity.lex_normpack.assemble`)
- citations in `NormRule`s point to existing `doc.fragment` IDs:
  - for every `CitationRef.fragment_id`, verify that it exists in `world.doc_fragments`
- a conflict is resolved by a deterministic winner:
  - repeating assembly with the same input subgraph returns the same `norm_pack_artifact_id`
  - the winning claim ID is stable (for example, lower/higher score; tie-break by lexicographic `claim_id`)

---

## 9) Policies, defaults, and extensibility

### 9.1. Selection policy

By default:

- `lex.versioning_v1.effective_range_then_published_at` (already used in Phase 16)

Phase 17 must:

- preserve `selection_policy_id` in `NormPack.metadata`
- never guess selection rules; follow the policy strictly

### 9.2. Conflict policy

By default:

- `policy.conflicts.default_v1` (Phase 14)

Phase 17 must:

- pass `conflict_policy_id` to `resolve_conflicts(policy_id=...)`
- preserve the policy ID/version in `NormPack.metadata` and `event.props`

### 9.3. Trust policy

MVP:

- preserve `trust_policy_id` as an informational metadata field
- perform actual trust scoring inside the Phase 14 conflict policy

Recommended extension (v1.1+):

- separate `trust_policy_id` and `conflict_policy_id` in the Phase 14 API

### 9.4. Domain/topic

MVP:

- `domain` affects provision selection only (Step 2)
- a list of domain keywords in `policies.py` is allowed

In the future (v2):

- `domain` may affect:
  - predicate-registry selection
  - ontology normalization (`subject_id`/`object` selectors)
  - backend selection for `backend_exprs`

---

## 10) Definition of Done (Phase 17)

Phase 17 is considered complete when:

1. Lex can assemble an applicable `NormPack` from its own corpus for a given date and jurisdiction:
   - input: `NormPackBuildRequest`
   - output: CAS artifact `lex.norm_pack` + `WorldEvent(kind=assemble_norm_pack)` + a world-facts segment

2. Assembly uses:
   - active-version selection by `as_of`
   - provision selection from `lex.corpus.provision_index`
   - norm-claim extraction with required citations to `doc.fragment`
   - conflict resolution (Phase 14) with a deterministic winner

3. The required Phase 17 tests exist (unit + integration); see §8.

## D1-L4 Historical Plan Links

| Link type           | Anchor as recorded in this dated plan                                                                                                                                           |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 0 norm/citation determinism and Phase 5 governance contract handoff                                                                                                   |
| Contract tests      | `tests/contract/test_applicability_contract.py`, `tests/unit/fabric/test_normpack.py`, `tests/unit/fabric/test_conflicts.py`                                                      |
| Schema snapshots    | `schemas/snapshots/ir/norm_pack.schema.json`, `schemas/snapshots/ir/norm_ref.schema.json`, `schemas/snapshots/ir/norm_rule.schema.json`, `schemas/snapshots/ir/claim.schema.json` |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                                                            |

The table is a historical plan-link inventory, not a current test-execution receipt. The exact test-file bindings are:

- `tests/contract/test_applicability_contract.py` — current-base file SHA-256 `91c8d621560258f7d77e2950a68b509403ac824082a4d52efc3d314656b32820` at HEAD `901f90e7c622b5c850bad1fe3dddf9bb4694501c`.
- `tests/unit/fabric/test_normpack.py` — historical `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` bytes SHA-256 `0f645bc86c821f655079be4cbdc4b305acbb8fb58e4d8e61fab6bce8224bc8c6`; R4 modified candidate postimage SHA-256 `bd1d986d94d52a08982b3f321bbb4344418dba8276b363c41526c8cadb07904f`. The R4 focused candidate test command did not select this module, so it is not reported as an R4 execution result.
- `tests/unit/fabric/test_conflicts.py` — current-base file SHA-256 `0ce5ea319c8efeb1f69b0cbaa81bfa9d1eed9303ce4ecbb79f91ec54531113bf` at HEAD `901f90e7c622b5c850bad1fe3dddf9bb4694501c`.

The `tests/unit/fabric/test_normpack_phase17.py` filename in §8 is a dated plan target absent from the current base and R4 candidate overlay. This document does not claim that target ran or exists as a current module.
