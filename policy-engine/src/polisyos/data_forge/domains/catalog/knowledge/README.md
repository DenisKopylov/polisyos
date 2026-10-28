# Catalog Knowledge (`polisyos.data_forge.domains.catalog.knowledge`)

`polisyos.data_forge.domains.catalog.knowledge` is the read-only discovery and
transportability layer over the dataset catalog built by the batch pipeline.

## Role in System

- **Depends on:** the DuckDB/HNSW artifacts materialized by
  `data_forge.domains.catalog.batch`.
- **Used by:** `fabric.retrieval`, `scientist`, and dataset discovery tooling.
- **Boundary function:** keeps dataset search and transportability scoring read-only.

## Key Concepts

- **Hybrid search** - `DatasetCatalogGraph` combines text and vector retrieval.
- Each query result carries `search_mode` and `vector_refusal_code` independently of the
  optional score explanation. `search_mode="vector"` denotes the vector-enabled hybrid path;
  `search_mode="text"` keeps text matches as candidates and carries the selected-generation or
  encoder refusal reason when vector admission is unavailable. Deterministic lookup results that
  did not run a search leave both fields unset.
- Query rows and the atomic response also carry `query_generation_context`, with an explicit
  `selected`, `absent`, `refused`, or `unknown` state. A selected context includes the persisted
  generation/profile and the live reader encoder profile checked for that query, including the
  content identity used by the compatibility check. The identity describes loaded encoder assets;
  it does not prove executable `encode` behavior, trusted provider ownership, ranking quality, or
  policy authority. Legacy list callers cannot preserve status for empty results; use the atomic
  response where query-local context matters.
- `DatasetCatalogGraph.search_datasets_with_status` returns one `DatasetSearchResponse` envelope
  containing the rows and mode/refusal from that same query, so a vector refusal remains visible
  when text fallback finds no rows. `DatasetCatalogGraph.search_datasets` and the direct
  `KnowledgeToolkit.search_datasets` method retain their legacy list return. The registered
  `search_datasets` knowledge tool uses the envelope bridge and serializes `results`,
  `search_mode`, `vector_refusal_code`, `limitation_code`, and `query_generation_context` together.
  A missing catalog or legacy reader without per-query status reports a limitation and unknown
  query context instead of an unqualified empty result.
- Measurement-root artifacts and semantic benchmark runs preserve status from the same query
  envelope; they do not reconstruct it from the graph's last-query diagnostic metrics. A v2
  semantic benchmark run carries query-local status and generation context while v1 serialization
  remains unchanged.
- **Dataset registry** - `DatasetRegistry` resolves datasets for canonical variables and P*(Z) estimates. Its private K_ref prepared reader exposes the complete ordered alignment projection in bounded batches under one read-only transaction; Runtime computes the existing full profile before replaying rows for edge derivation.
- **Proxy resolution** - `proxy_resolver.py` builds fallback chains when direct observations are missing.
- **Variable alignment** - `variable_alignment.py` maps canonical SKG variables onto dataset variables.
- **Derivation catalog selection** - `derivation_catalog_selection.py` strictly loads
  purpose-addressable family policies and evaluates candidates against exact metric/canonical
  owner edges plus rights, alignment, binding, and completeness evidence.
- **Semantic epoch overlay** - `CatalogAcquisitionOverlay` keeps operational
  ordinals distinct from semantic epoch identity, records a complete native
  membership relation for every baseline-union table, and exposes rows only
  after a separately persisted production receipt activates the pending
  admission. Legacy/null stamps and incomplete physical membership remain
  audit-visible but fail closed for read visibility and positive chronology. New framed
  semantic receipts persist the exact profile of their Core serializer, and activation
  re-reads that selected profile and payload before writing an active state. A historical
  manifest without Core CanonInfo is not retagged, restamped, or activated. A child ref without
  a profile selector can still read its actual default view unchanged when that manifest carries
  the declared Core profile.

## Registered Tool JSON Migration

The registered search_datasets tool returns a DatasetSearchResponse object with a results array and query-local status fields. This wire result is distinct from the legacy list returned by direct Python search_datasets methods. Registered-tool consumers must migrate to the object envelope; see [the migration guide](../../../../../../docs/migration/e02-catalog-search-datasets-envelope.md) and [the rollout runbook](../../../../../../docs/runbooks/catalog-search-datasets-envelope-rollout.md).

## Public API

- `DatasetCatalogGraph`
- `DatasetRegistry`
- `proxy_resolver`
- `variable_alignment`
- `derivation_catalog_selection`
- `types.py`
- `store.py`
- `search.py`

## Current State

- Last updated: 2026-10-14
- Data Forge Phase 8 physically removed the old `polisyos.datasets` namespace;
  this package is now the canonical implementation owner.
- `variable_alignment.py` now normalizes against both the academic canonical seed and the runtime canonical registry.
- The read-only store still opens DuckDB in `read_only=True` mode and falls back to text-only search if the vector index is unavailable.


Semantic epoch statements use the Core epoch contract's declared codec registry. Acquisition
owner snapshots and member rows retain framed epoch bytes; L5 and Lex owner rows use canonical
JSON, while L5 registry files retain exact raw JSON bytes. Fresh finalization resolves supported
content refs through selected manifest profiles. Profileless owner references remain typed
owner projection; it is not silently reselected from CAS or upgraded to authority.

Catalog acquisition uses the same expected-role boundary for its framed owner snapshot and native
member rows. The adapter validates source kind/media and exact row bytes before selected CAS writes,
then rereads the frame, canon, and selected manifest profile.

The native membership snapshot binds every receipt ref to its frozen passport row. Candidate refs
must match the passport's exact ref and content hash, then resolve to the registered candidate
statement in CAS before the semantic denominator can be emitted. Profileless owner projections are
not promoted to authority, and unresolved or legacy passport state remains unresolved.


The runtime validates the complete Catalog acquisition snapshot against strict row, passport, and
stamp schemas before copying it into the task CAS. Passport content hashes are recomputed from the
frozen passport mapping; matching owner-supplied hash fields alone are insufficient. For a bound
current-v2 passport, the owner row must also carry and match its epoch and passport identity, epoch
ref, stamp hash, full stamp, and prepared ref before snapshot or member CAS writes. The producer's
source facts are part of that same prewrite decision: both row-presence flags must be true, activation
must be pending or active, and the receipt operational epoch must equal the owner-row epoch. Historical
v1 rows remain explicitly legacy-unresolved; the adapter does not fabricate missing carriers or
promote them. A historical or unresolved passport remains limited and is never upgraded by this check.


## Protected semantic epoch activation readback

`CatalogAcquisitionOverlay.activate_semantic_epoch` sends the selected production-receipt ref
through Core `load_verified_epoch_statement` before it creates an activated receipt or opens the
activation transaction. This checks the exact receipt kind/media, selected Core epoch profile,
absent artifact schema, framed bytes, and the seven direct `epoch_production_input` edges declared
by the producer's typed receipt fields. A schema-bearing or input-edge-tampered selected view is
refused through the existing `OverlayAdmissionError` boundary without changing overlay state.
Activation retains its existing requirement for a selected production-receipt ref. That requirement
applies to the activation receipt itself; child refs inside it may lack a selector and still resolve
their actual default manifest when it carries the declared Core profile. The reader preserves such
child refs unchanged. This path does not synthesize selectors, retag bytes, or validate the separate
`owner_denominator_receipt_refs` evidence vector. Core CanonInfo confirms the declared serialization
codec only; it establishes no
IR law, denominator validity, currentness, or epoch authority.


### Fixed static measurement-unit conversions

The acquisition overlay can recompute a non-identity field lift only when the binding names `fixed_multiplicative` with `fabric://units/fixed-multiplicative/v1`. It reuses Fabric's existing `Unit` parser and fixed unit definitions, records the executor version, exact raw/canonical units, resolved multiplier, binding identity, and a digest of the used definitions plus the complete pinned v1 basis in the content-bound admission projection and in a nullable JSON column on the existing observation-provenance owner table. The v1 parser snapshots Fabric's existing 60 standard units, 33 prefixes, and 11 exponent glyphs into immutable maps; any current-map drift from that full basis fails closed before conversion. A fresh owner read recomputes the definition evidence and compares every persisted row before exposing the projection. It rewrites the consumer condition unit to the canonical unit before persistence. The executor refuses dimensionless, incompatible, currency/rate, population, offset, unknown, unregistered, and factor-one semantically distinct pairs. Identity bindings retain their existing path. This local arithmetic records no owner assignment, population, source-time, or institutional measurement authority.


### Guarded variable availability

`DatasetCatalogStore.variable_availability_counts` reads the actual metric-binding,
observation and dataset-metrics predicates inside the existing content-identity
`read_session`. The context yields its actual read-only connection so Runtime
consumers can keep a complete profile reconstruction inside the same guard.
It includes bindings with absent source labels. The returned
counts establish catalog presence only; they do not ground an effect, license
acquisition, or confer source authority. The identity guard scans baseline and
configured overlay bytes in 1 MiB chunks before and after a logical read. Its
CPU/I/O cost is linear in those files and needs profile-specific admission.
`identify_read_sources` and `read_source_identity` expose the same immutable
baseline/overlay tuple to selected-source consumers. A visible `.wal` sidecar
refuses with `catalog_read_source_checkpoint_required`; checkpoint/close its
native owner before retrying. The reader never deletes or repairs the sidecar.
The existing before/after guard is not an atomic filesystem custody transaction;
a hostile writer that substitutes and restores bytes between all checks is
not excluded. Such writers require an immutable snapshot/transaction owner.


The guarded source/session failures are `CatalogReadSourceError`, preserving
`CatalogSelectionError` ancestry and exact code/detail. Consumers propagate
this whole family, including future owner codes, instead of testing only the
old `catalog_read_session_` spelling. A constructor source swap is typed
`catalog_read_source_changed_while_opening` with its old detail retained.
The reader closes an opened connection if its post-open identity check fails.

Escaped native DuckDB query/backend errors also use this typed read-source
family (`catalog_read_native_query_unavailable`); a closed backend is ERROR,
not evidence of zero observations. The original driver exception is retained
as the cause.

Selected Catalog source failures retain their typed cause at initial content
identity construction and throughout persisted Fabric capture. The public
acquisition owner alone classifies the forwarded failure; unrelated optional
capture failures retain their prior fallback. Empty native sources are errors,
not unavailable variable counts. This does not establish atomic file custody.
