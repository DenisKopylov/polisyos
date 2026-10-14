# Fabric

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-10-14
Owner: `@fabric-owners`
Source pin: `c35222b3dcf103338175cf300c5fe9487e6416f3`
Source of truth: `src/polisyos/fabric/**`, `src/polisyos/data_forge/read_api/**`,
  `architecture/imports/policy.toml`, `architecture/packages/boundaries.toml`,
  and the named tests below.
Evidence level: implementation and test behavior inspected at the source pin.
Test status: tests were inspected but not run in this documentation pass.
Test fixtures establish the named paths only; this page makes no claim of live
provider readiness, universal source completeness, or source truth.

## Fabric and Data Forge

`polisyos.fabric` owns runtime connector access and retrieval, Fabric evidence
and lineage artifacts, the data-plane modes, document and claim processing, and
world-store emission, materialization, and query helpers. Its stable package
facade is `src/polisyos/fabric/__init__.py`; subsystem responsibilities are
documented in the package READMEs and pages below.

Data Forge owns offline asset-oriented builds and publication. Runtime code
uses `polisyos.data_forge.read_api`; Fabric's allowed Data Forge dependency is
intended to be that read API, not `data_forge.kernel` or `data_forge.domains`.
`architecture/packages/boundaries.toml` declares that narrow package rule, but
`architecture/imports/policy.toml` allows Fabric the broader `data_forge` root.
There is also an observed source exception: `src/polisyos/fabric/retrieval/service.py`
imports `polisyos.data_forge.domains.catalog.batch.config._profile_input_coverage_currentness`
inside `_catalog_profile_plan_admission`. The declared narrow boundary is
therefore not the complete observed import picture.

The `read_api` name also does not mean every export is read-only:
`src/polisyos/data_forge/read_api/legal.py` exports `run_batch_pipeline`, and
`src/polisyos/data_forge/read_api/academic.py` exports `run_edge_synthesize`,
from domain batch modules. Treat the package boundary as the intended rule and
the imports above as exceptions requiring consolidation; this page does not
claim a fully enforced narrow matrix. See the
[Data Fabric explanation](../../explanation/data-fabric.md#fabric-and-data-forge)
for the conceptual build/runtime distinction.

## Artifact and workflow map

| Path | Inputs and producer | Persisted output and consumer | Evidence and boundary |
| --- | --- | --- | --- |
| Connector ingestion | `ConnectorManifestSpec` and `DatasetFetchSpec` drive a registered connector. It receives a `FetchRequest` and returns a `FetchResult`. | With CAS configured, `run_connectors_ingestion` stores fetched payload refs, a `ProvenanceCoreGraph`, and an `EvidenceBundleRef`. `run_orchestrated_ingestion` may wrap the bundle in a CAS `DataSnapshotRef`. | `tests/unit/fabric/connectors/test_integration.py` exercises connector ingestion with test connectors and CAS. `tests/unit/fabric/data_plane/test_orchestrator.py` stubs the ingestion producer and checks snapshot construction from a persisted evidence bundle. The snapshot builder selects the first bundle source as `data_ref`; it does not merge all sources into a dataset or emit a world fact. |
| Document and claim processing | `ingest_doc_bytes` accepts raw bytes plus `DocSourceSpec`; later stages normalize, structure, and chunk through explicit artifact refs. Claim extraction consumes an explicit normalized/chunked `DocMeta` artifact. | Document and claim stages persist artifacts, emit world facts/events, append fact-log segments, and can be materialized into world tables. | `tests/unit/fabric/test_docs_pipeline.py` covers bytes through document stages and DuckDB materialization. `tests/unit/fabric/test_claims_pipeline.py` covers claim persistence and materialization. These are specific pipelines, not a generic sink for every connector result. |
| Catalog-bound fetch custody | Fabric retrieval takes a `FetchPlan` bound against the Data Forge catalog read API and executes its selected connector request. | CAS stores the complete payload, catalog binding, and `FabricFetchReceipt`. `src/polisyos/runtime/quality/data_forge_binding.py` resolves the receipt and current fetch before emitting a measurement-root payload. | `tests/unit/fabric/test_retrieval_fetch_custody.py` covers receipt and payload custody. `tests/unit/runtime/quality/test_promotion_sequence.py::test_real_measurement_root_resolves_and_binds_into_n9` covers the bounded fixture-backed measurement-root consumer; `tests/unit/runtime/quality/test_promotion_sequence.py::test_n9_replays_current_measurement_source_at_admission` covers the admission recheck. The receipt authority is catalog selection and returned-result custody. |
| Prepared Data Forge assets | Offline domain builders publish typed assets through Data Forge's build and publication surfaces. | `ArtifactRef` carries the content hash, producer/version, config hash, owner, license, regeneration command, PII and retention classifications, freshness SLA, and schema identity. Runtime readers enter through `polisyos.data_forge.read_api`. | See `src/polisyos/data_forge/README.md`, `src/polisyos/data_forge/kernel/artifacts.py`, and `src/polisyos/data_forge/read_api/`. This is a separate asset lifecycle from a Fabric connector fetch. |

The world-store's retained `WorldSnapshot`/branch context is created from
materialized world state for world-query time travel. It is distinct from the
connector pipeline's CAS `DataSnapshot`, which points at an evidence bundle and
one primary source artifact. Neither snapshot type creates the missing generic
connector-result-to-world-fact bridge.

The runtime control service routes `run_data_ingestion` requests to full,
incremental, record/replay, or streaming modes and returns artifact references
when produced (`src/polisyos/runtime/http/services/control/run_lifecycle.py`).
The control API tests in `tests/unit/runtime/http/test_e2e_ingestion.py` patch
the ingestion producer; they establish request dispatch, not a live provider to
persisted result demonstration.

The SourceContract v2 fixture label also has a bounded meaning. The current
fixture builder in `tools/quality/validation/fabric_source_contracts.py`
generates schema-shaped sample rows and a `fabric://` request; these fixtures
are not captured responses from the named providers. A source-platform
`production_visible` label and fixture count therefore describe declared
contract artifacts, not live provider availability or source truth.

## Time, provenance, and trust

| Field or artifact | What it establishes | What it does not establish |
| --- | --- | --- |
| `FetchResult.fetched_at`, `source_updated_at`, and `version` | The typed connector result's fetch time, optional source-update time, and declared version. | An independent observation of when the provider changed its data or proof that its content is true. |
| `DocMeta.retrieved_at` | The document retrieval time carried by document metadata. | The document's legal or policy-effective time. |
| World fact `valid_time`; `WorldQueryRequest.as_of_valid_time` and `as_of_tx_time` | The fact's valid-time value and separate valid/transaction-time query selectors. | A single interchangeable timestamp for fetch, observation, validity, and storage. |
| `ProvenanceCoreGraph`, `EvidenceBundle`, and CAS `InputRef` links | The source, transform, and artifact relationships actually written by the producing path. | A complete lineage graph across producers that do not emit or bind those relationships. |
| `FabricFetchReceipt` and `resolve_persisted_fetch` | A catalog-bound plan, the persisted returned payload, and agreement with a current connector replay. | Historical proof that the original transport happened at its recorded time or scientific truth; the receipt docstring states these limits. |

`run_orchestrated_ingestion` writes a `fabric.quality_report` containing the
ingestion source, dataset count, and evidence notes. That report ref is useful
snapshot metadata; the wrapper does not run a full content-quality assessment.
Content checks are owned by the corresponding quality and connector-contract
paths.

## Demonstrated limits

- **`bridge_missing` for the generic connector-to-world-fact chain.** Connector
  ingestion produces an evidence bundle and, optionally, a data snapshot. The
  document and claim pipelines emit their own world facts and events. The
  presence of both APIs does not establish a general connector-result-to-world
  materialization bridge.
- **`semantic_test_missing` for automatic source-to-query lineage.**
  `tests/unit/fabric/test_lineage.py` builds the source, transform,
  materialization, claim, fact, and query nodes directly through
  `FabricLineageTracker`; it verifies graph trace and impact behavior, not that
  operational connector and world-store producers automatically emit one
  complete graph.
- **Source truth remains unestablished by custody.**
  `resolve_persisted_fetch` explicitly says that a current-source comparison
  does not establish the historical transport occurrence or scientific truth.
  Caller-provided source and license labels, schema validity, checksums, and
  quality fields do not change that authority boundary.
- **Inventory status is not an end-to-end proof.** The generated
  `best-in-class-inventory.md` is report-only and records declared surfaces and
  presence checks. Its `implemented` label does not establish automatic
  source-to-query lineage, live provider readiness, or a generic source-to-world
  consumer chain.

## Reference pages

| Page | Responsibility |
| --- | --- |
| [Connectors](connectors.md) | Connector protocol, registration, source families, and schema contracts. |
| [Profiles](profiles.md) | Source profiles, execution policies, and runtime configuration. |
| [Data plane](data-plane.md) | Ingestion modes, cursors, replay, quarantine, streaming, and orchestration. |
| [Schema compatibility](schema-compatibility.md) | Connector schema evolution and governance snapshots. |
| [Lineage](lineage.md) | Provenance graph node and trace APIs. |
| [Quality](quality.md) | Quality indicators, validation, and fitness reports. |
| [Observability and governance](observability-governance.md) | SLI/SLO, access, audit, and retention surfaces. |
| [Source platform](source-platform.md) | Source contracts, scorecards, and conformance surfaces. |
| [Time travel](time-travel.md) | Snapshot reads, valid and transaction time, and branch behavior. |
| [Processing guarantees](processing-guarantees.md) | Batch, streaming, replay, and CDC guarantee contracts. |
| [Discovery intelligence](discovery-intelligence.md) | Catalog search, source bindings, and entity-resolution helpers. |
| [Product/API integration](product-api-integration.md) | Runtime routes, downstream payloads, and compatibility bridges. |
| [Best-in-class inventory](best-in-class-inventory.md) | Report-only inventory and its validation boundary. |

## Stable Fabric facade

`polisyos.fabric` exposes `run_connectors_ingestion`, `fabric_get_data`,
`execute_world_query`, `query_world_table`, `query_claims`, and `query_events`.
The orchestrated fetch-to-snapshot entrypoint is
`polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion`.
Catalog-bound retrieval and persisted fetch resolution live under
`polisyos.fabric.retrieval`; they are separate from the root compatibility
fetch helper.

## Evidence anchors

- `tests/unit/fabric/connectors/test_integration.py` — connector fetch and CAS
  evidence-bundle behavior using test connectors.
- `tests/unit/fabric/data_plane/test_orchestrator.py` — optional snapshot
  construction from an evidence bundle.
- `tests/unit/fabric/test_docs_pipeline.py` and
  `tests/unit/fabric/test_claims_pipeline.py` — document/claim artifacts and
  world materialization.
- `tests/unit/fabric/test_retrieval_fetch_custody.py` and
  `tests/unit/runtime/quality/test_promotion_sequence.py` — catalog-bound fetch
  custody, fixture-backed measurement-root consumption, and admission recheck.
- `tests/unit/fabric/test_lineage.py` — explicit lineage graph trace and impact
  semantics.
