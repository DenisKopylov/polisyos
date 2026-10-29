# Fabric (`polisyos.fabric`)

`polisyos.fabric` is the repository's data-fabric layer: connector-backed
acquisition, document and claim pipelines, data-plane orchestration,
provenance, retrieval, and world materialization.

- Last updated: 2026-10-25

## Purpose

Use `polisyos.fabric` for several related but separately bridged surfaces:
connector-backed acquisition, document and claim production, and world
materialization/query. Connector ingestion persists payload and provenance
artifacts and can emit evidence bundles or snapshots. Those artifacts do not
automatically become document claims or world facts/tables; the document/claim
producers and world materializers have their own inputs and write paths. No
generic connector-to-world materialization bridge is established by the
connector receipt or snapshot alone. Follow the relevant subpackage README for
the path in use; the [data-fabric explanation](../../../docs/explanation/data-fabric.md)
maps the current bridges and their gaps.

## Where to Start

- Start with [connectors/README.md](./connectors/README.md) when adding,
  registering, validating, or debugging a data source.

- Start with [data_plane/README.md](./data_plane/README.md) for batch, record,
  replay, streaming, CDC, quarantine, and semantic-diff flows.

- Start with [docs/README.md](./docs/README.md),
  [claims/README.md](./claims/README.md), and [world/README.md](./world/README.md)
  for the document-to-world pipeline.

- Start with [retrieval/README.md](./retrieval/README.md) and
  [catalog/README.md](./catalog/README.md) for metric discovery, fetch planning,
  and semantic catalog behavior.

- Use [tests/unit/fabric/README.md](../../../tests/unit/fabric/README.md) to find the
  focused validation suite for the area you are changing.

## Public API

| Entrypoint                              | Description                                                                                          |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `run_connectors_ingestion()`            | Main ingestion entrypoint for connector-backed runs.                                                 |
| `fabric_get_data()`                     | Compatibility bridge used by upper layers that need synchronous fetch access.                        |
| `execute_world_query()`                 | Read-only world-query entrypoint over Fabric materializations.                                       |
| `query_world_table()`                   | Convenience helper for direct world-table reads.                                                     |
| `query_claims()` / `query_events()`     | Helpers for claim and world-event query paths.                                                       |
| `WorldQueryRequest` / `WorldQueryError` | Request and error surface for governed world queries.                                                |
| `FabricFetchReceipt`                    | Typed custody receipt for a catalog-bound fetch and its persisted payload.                           |
| `CatalogRegistrySchemaError`            | Typed refusal when supplied catalog-registry input is malformed or makes discovery incomplete.       |
| `file_lock()` / `atomic_write_json()`   | Existing filesystem lock and atomic metadata writer, reused by durable runtime admission accounting. |
| `world`                                 | Lazy-loaded `polisyos.fabric.world` subpackage for lower-level write and materialization helpers.    |

`polisyos.fabric.__all__` is the stable public facade. Catalog and semantic
discovery surfaces live under `polisyos.fabric.catalog` and are linked from the
retrieval README rather than being part of the root facade contract. The scoped
runtime annotation contract for selected facade callables and class fields is
documented in [Fabric runtime annotation compatibility](../../../docs/reference/fabric/runtime-annotations.md); it does not add facade exports or make annotations evidence of source authority.
`fabric_get_data` continues probing independent providers after an unselected provider has a malformed
registry; if no provider matches and any registry probe failed, it raises the typed
`CatalogRegistrySchemaError` refusal instead of reporting absence. A selected WVS
provider validates its supplied local registry before issuing HTTP. This does not
establish external source authority or currentness.

## Semantic Groups
Supported subpackage routes include `polisyos.fabric.api`, `polisyos.fabric.connectors`, `polisyos.fabric.docs`, `polisyos.fabric.ingestion`, and `polisyos.fabric.retrieval`.
The temporary product evidence-path bridge remains at the documented module route `polisyos.fabric.product_integration` with its existing 2026-11-30 sunset. Registering that route does not add adapter names to the stable root `__all__` or extend the sunset.
Ingestion and retrieval names remain typed operational contracts; their presence does not grant source authority or establish a successful fetch.


- [`api.py`](api.py) and [`__init__.py`](__init__.py) own the stable lazy root
  facade and public-surface helper metadata.
- [`_internal/`](_internal/) contains post-cleanup private helpers. Do not
  deep-import it from callers outside Fabric.
- [`_adapters/`](_adapters/) contains Fabric adapters over canonical
  cross-cutting interfaces such as `polisyos.core.observability`.
- [`ingestion/`](ingestion/) owns ingestion runtime semantics and provider
  resolution; connector-specific ingestion entrypoints live under
  [`connectors/ingestion/`](connectors/ingestion/).
- [`trust/`](trust/) owns trust comparison helpers and trust-envelope adapters.
- [`quality/`](quality/) owns quality indicators, safety guardrails, fitness
  reports, and processing-guarantee contracts.
- [`evidence/`](evidence/) owns evidence bundles, decision-data envelopes, and
  fact writing.
  `evidence/non_data_acquisition.py` extends that plane with persisted candidate
  object intake, independent verifier admission and re-entry receipts. Candidate,
  vocabulary and receipt writes now select one explicit Core canonical profile;
  their reader binds the selected bytes to the exact owner kind, media type,
  schema and strict payload DTO before recomputation. Historical profileless
  artifacts are refused and must be regenerated through the producer.
  `evidence/ceiling_relations.py` owns the eight explicit non-data ceiling relations
  registered in `evidence/ceiling_vocabulary.json`; unknown fields and identities
  fail closed. Same-stream row growth cannot resolve a missing non-data object.
  The verifier port permits an independently owned GY-AS1 oracle; that battery and
  institutional authority are outside this implementation.
  `evidence/acquisition_assurance.py` is the non-test synthetic assurance caller:
  it executes AQ1 intake, persisted receipt verification and demanding-owner
  re-entry. `tools.quality.validation.check_gy_acquisition_assurance` grades the
  immutable corpus through a separately authored isolated oracle. Reference
  terminal knowledge remains distinct from AQ1 process state; the battery grants
  no institutional authority or general real-world completeness.
- [`identity/`](identity/) owns dataset and segment manifest identity.
- [`numerics/`](numerics/) owns finite-number and numerical-stability helpers.
- [`data_plane/`](data_plane/) owns shape/time semantics plus orchestration,
  replay, streaming, quarantine, and semantic-diff flows.
- [`config/`](config/) owns Fabric-local configuration models.
- [`world/`](world/) owns world materialization, world store, and query helpers.
- Connector-facing code lives under [`connectors/`](connectors/) and
  [`connectors/sources/`](connectors/sources/README.md).

## Extension Points

- External connectors use the `polisyos.fabric_connectors` entry-point group
  declared in
  [architecture/extension_points.toml](../../../architecture/extension_points.toml).
- Builtin connector components register through the connector component loader
  and source contracts documented in
  [connectors/sources/README.md](connectors/sources/README.md).
- Use [connectors/sources/AUTHORING.md](connectors/sources/AUTHORING.md) for
  source-adapter naming, fixture, and version-policy rules.

## Depends On / Depended On By

- Declared dependencies include `polisyos.common`, `polisyos.core`,
  `polisyos.ir`, and `polisyos.data_forge.read_api`. The intended Data Forge
  boundary is the read API, but it is not fully enforced: the import policy
  allows the broad `polisyos.data_forge` root, while Fabric retrieval currently
  imports the private `polisyos.data_forge.domains.catalog.batch.config` module
  in `src/polisyos/fabric/retrieval/service.py` (the package boundary declares
  domain imports forbidden). Treat this as a declared/observed boundary
  mismatch, not proof of a narrow enforced matrix.

- Depended on by: `polisyos.runtime.http.services.control`,
  `polisyos.scientist`, `polisyos.scholar`, `polisyos.lex`, and any code that
  reads materialized world state or connector-backed data contexts.

## Common Commands

Run from the repository root (`policy-engine/`).

- `rg --files src/polisyos/fabric | sort`
  Survey the package map before following imports. Smoke-tested on 2026-04-17.

- `rg -n "run_connectors_ingestion\|fabric_get_data\|execute_world_query" src/polisyos/fabric`
  Jump to the root facade and bridging entrypoints. Smoke-tested on 2026-04-17.

- `uv run python -m polisyos.fabric.data_plane.cli --help`
  Inspect the package-local quarantine/report CLI exposed inside Fabric.
  Smoke-tested on 2026-04-17.

## Tests

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/unit/fabric/test_docs_pipeline.py tests/unit/fabric/test_claims_pipeline.py tests/unit/fabric/test_retrieval_service_catalog.py tests/unit/fabric/test_world_store.py -q`
  Cross-package Fabric smoke suite. Smoke-tested on 2026-04-17.

- `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json`
  Connector contract compatibility gate. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric -q`
  Full Fabric suite. Conceptual in this README refresh; not run in this pass.

## Operability Links

- [Fabric component SLO](../../../ops/components/fabric/slo.yaml)
- [Fabric component runbooks](../../../ops/components/fabric/runbooks.md)
- [Fabric observability and governance](../../../docs/reference/fabric/observability-governance.md)
- [Fabric quarantine and data-plane recovery runbook](../../../docs/runbooks/fabric-quarantine-dlq-and-data-plane-recovery.md)
- [CAS/OPA outage runbook](../../../docs/runbooks/cas-opa-outage.md)

## Known Shims/Deprecations

- Active Fabric facade-cleanup shims are registered in
  [architecture/shims.toml](../../../architecture/shims.toml) with owner
  `team-fabric` and sunset `2026-12-31`.
- Legacy compatibility imports such as `polisyos.fabric.evidence.decision_data` and
  `polisyos.fabric._adapters.observability` are bridged through documented re-export
  aliases to the semantic groups above. Newly retired cleanup paths now import
  directly from their semantic groups, such as
  `polisyos.fabric.quality.processing_guarantees` and
  `polisyos.fabric.world.query`.
- New public imports must be added to `api.py`, the generated public-surface
  reference, and compatibility policy before old import paths are retired.

## Reference Docs

- [Fabric reference index](../../../docs/reference/fabric/index.md)
- [Fabric connectors reference](../../../docs/reference/fabric/connectors.md)
- [Fabric data-plane reference](../../../docs/reference/fabric/data-plane.md)
- [Fabric runtime annotation compatibility](../../../docs/reference/fabric/runtime-annotations.md)
- [Fabric lineage reference](../../../docs/reference/fabric/lineage.md)
- [Connector CONTRIBUTING guide](../../../docs/connectors/CONTRIBUTING.md)
- [Add data source](../../../docs/how-to/add-data-source.md)
- [Manage generated artifacts](../../../docs/how-to/manage-generated-artifacts.md)
- [Fabric tests map](../../../tests/unit/fabric/README.md)


Evidence boundaries also validate present input structure before normalizing it:
source-selection consumers refuse malformed supplied report fields and validate
the complete consumed source-row map and record-list shape; the scorecard intake
refuses a malformed non-null trace while preserving absent and explicit-null
optionality. A present malformed outer source-family expectation now adds a
blocking issue instead of falling back to the report's own expectation; missing,
null, and valid-empty external intent still leave the report expectation as a
candidate consistency constraint only. Required source facets are checked by
their declared contract kind: rights require nonblank text, while every
reference facet must yield a recognized textual ref. Symbolic field refs and
CAS refs remain valid; an unknown-key map or scalar without a ref is missing.
The non-data acquisition consumer requires a persisted receipt ref before
readback, and the registered ceiling relation resource is parsed through its
strict owner shape. These checks do not establish institutional authority or
source currentness.

## Explicit selected Federation capture

`fabric_get_data(..., federation=FederationFetchRequest(...))` opts into the
existing Federation owner using explicit ordered connector/dataset or held-parent
selections. Default None keeps the ordinary single-connector route. The existing
planner can prepare selections; no hidden ranking or authority is introduced.

The first supported profile is **captured rows only**. Source EOF/completeness,
currentness and query fulfillment are not established. False has_more, no token
and a matching row_count do not prove EOF. A page_size is a hard bound on every actual source capture and the final
composed output, never an EOF assertion. A connector may treat it as a hint or
per-page setting; an over-bound returned frame is refused rather than silently
sliced. An actual SQL LIMIT may still capture one row from a larger table. Nonempty filters/date scope and max_staleness are refused
before fetch for every source kind. Held parents are exact whole captures; a
parent exceeding a new page bound is refused rather than silently re-sliced.
The upper-layer opt-in supports one unfiltered table metric with no additional
query scope/aggregation/access/cursor request. Other scopes need an actual
reconciliation owner, not a request-key or marker proof.

The producer persists the kernel derivation and a bounded selected
`acquisition.json` receipt in its new owned output directory. The receipt binds
frozen request/source/order/root context, selected kernel member digests and
typed consumer-asserted observation/capture claims. `freeze_federation_request` freezes independent
intent before callbacks. The real `DefaultFabricPort` consumer passes that
context and independently held root to `reopen_federated_fetch_result`; it does
not select from the returned root/ref/observations alone. It reconciles the fresh
selected kernel request/source members and receipt against the independent
constructor and current DataViewRequest. A different valid derivation Q cannot
be labeled as requested P; mutable return data or observations are ignored.
One shared fresh capture intake replays actual kernel bytes and rechecks every
source row bound, aggregate output bound and all immutable declared leaf trust
preferences against frozen intent. A callback cannot bypass those predicates by
constructing a valid artifact directly.
Receipt provenance, capture origin and observation claims remain
consumer_asserted; matching self-selected hashes does not authenticate a
connector fetch. Selected stored bytes/counts and software replay are recomputed.
The aggregate verification time/duration describe the actual software readback,
not an authenticated connector-capture time. No institutional evidence follows.

Kernel parents do not carry the bridge's separately selected fetch/warning
history. Bare selected-parent inputs therefore have explicit unavailable
observation/quality history, `fetches_scope=fresh_connector_fetches_only`, and
warning flags that persist to the snapshot. An empty fresh-fetch list is not a
claim of zero parent warnings. The kernel's immutable fresh whole-leaf declared
trust projection is reused; a carrier's metadata/attrs cannot replace it.

All opt-in Core data/schema/quality/warning/snapshot emissions receive a bounded
actual CAN.2 encode/decode semantic preflight and fresh selected readback. The
data comparator checks every row/key/scalar, while schema keeps column order and
dtypes, including zero rows. Null normalization uses exactly R4's encode_scalar
equivalence and preserves null keys (`exclude_none=False`). A byte roundtrip is
not the equality oracle. Data outside the exact supported row profile raises
`FederationSnapshotProjectionError` before Core data publication: signed zero,
native-tag-like row mappings and nanosecond timestamp loss are counterexamples,
not a reserved-name blacklist. Ordinary finite primitive rows/nulls remain
useful; datetime values require a separately admitted bounded owner projection
and reader, rather than hand-written native tags. No CAN.3 dependency or writer-fence bypass is
introduced. Full-range lossless snapshot support requires an agreed versioned
row envelope/reader across existing consumers or another accepted Core profile;
this proposal does not invent that wire rollout. The public selected kernel
route itself can retain these values even when this snapshot profile refuses.

The existing selected WarningsBundle carries the request-bound candidate audit;
DataSnapshot input edges bind warnings_ref. Quality remains UNVERIFIED,
completeness0 is only a lower bound, and freshness/query fulfillment stay unknown.
No aggregate evidence_ref is fabricated from incompatible Federation refs.
Keep actual output/held-parent/acquisition bytes available; hashes alone do not
deliver them. No HTTP/export endpoint, sovereign subsystem or new IR family is
introduced. Root owns composition, public/generated companions and runtime
qualification; this RAW proposal supplies no G acceptance or criterion closure.

A same-intent synthetic selected capture can still be constructed without any
connector call. This profile admits only its conditional captured-row candidate,
labels the origin/observations consumer_asserted, and keeps quality UNVERIFIED;
it never stamps such content independently reconciled or connector-reported.
A stronger origin handshake should reuse the existing catalog-bound
FabricFetchReceipt/resolve_persisted_fetch owner with separately held request,
payload and receipt selectors. That integration is not established on this
explicit direct-registry path and is not invented here.

The Federation opt-in compiles its complete supported query profile before the
legacy dataset resolver or any callback. A request ID is never a substitute for
the single explicit nonblank metric on this route. Every fresh source and held
parent is admitted against frozen captured-row bounds even when an inner JOIN
produces fewer rows.

No admitted dataset-shape/workflow basis exists in this captured-candidate
profile. Column names remain schema, not repeated-survey evidence. The FED
snapshot/audit therefore carry shape and workflow basis `not_established`;
legacy name-derived definite shape and routing notes are withheld on this route.
The default single-connector behavior is unchanged. A future shape projection
requires an independently admitted typed design basis, not a column-name rule.

Source collection and partial source-scope evidence projections reuse the private
`ingestion/_source_evidence_schema.py` helper. They preserve the selected persisted
manifest's typed `artifact_schema` and refuse a missing schema before derived writes;
this check does not establish source provenance or currentness.
