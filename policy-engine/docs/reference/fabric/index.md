# Fabric

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Selected Python runtime annotation boundaries are documented in [Fabric runtime annotation compatibility](runtime-annotations.md); that page does not widen the supported facade set.

Freshness: 2026-10-14
Owner: `@fabric-owners`
Source pin: `78a7b7b9cdab2b16e9d4ecd56c15bece38728f3b`
Source of truth: `src/polisyos/fabric/**`, `src/polisyos/data_forge/read_api/**`,
  `src/polisyos/data_forge/README.md`, `src/polisyos/data_forge/kernel/artifacts.py`,
  `src/polisyos/runtime/http/services/control/run_lifecycle.py`,
  `src/polisyos/runtime/quality/data_forge_binding.py`,
  `architecture/imports/policy.toml`, `architecture/packages/boundaries.toml`,
  `architecture/public_surface/contract.toml`,
  `architecture/public_surface/inventory.json`, `docs/reference/public-surface.md`,
  `tests/unit/fabric/connectors/test_integration.py`,
  `tests/unit/fabric/connectors/test_protocol_compliance.py`,
  `tests/unit/fabric/connectors/test_source_contract_v2.py`,
  `tests/unit/fabric/data_plane/test_orchestrator.py`,
  `tests/unit/fabric/test_claims_pipeline.py`, `tests/unit/fabric/test_docs_pipeline.py`,
  `tests/unit/fabric/test_lineage.py`, `tests/unit/fabric/test_retrieval_fetch_custody.py`,
  `tests/unit/runtime/http/test_e2e_ingestion.py`,
  `tests/unit/runtime/quality/test_promotion_sequence.py`,
  `tests/repo_quality/tools/test_fabric_source_contracts.py`
Evidence level: implementation and test behavior inspected at the source pin.
Test status: tests were inspected but not run in this documentation pass.
Test fixtures establish the named paths only; this page makes no claim of live
provider readiness, universal source completeness, or source truth.

## Fabric and Data Forge

Fabric owns runtime connector access and retrieval, evidence/lineage artifacts,
document and claim processing, data-plane modes, and world-store helpers; Data
Forge owns offline asset builds and publication, with selected runtime reads
through `polisyos.data_forge.read_api`. This map follows the implementation and
selected tests listed above; tests were inspected, not run, and fixture evidence
is bounded to the named paths. Fixtures do not establish live provider
readiness, universal source completeness, or source truth. Start with the
artifact map below for observed producers, persisted outputs, consumers, and
test evidence; use [Current data paths](../data-forge/current-data-paths.md) for
the Data Forge asset lifecycle and the [Data Fabric explanation](../../explanation/data-fabric.md#fabric-and-data-forge)
for the conceptual boundary.

## Artifact and workflow map

| Path | Inputs and producer | Persisted output and consumer | Evidence and boundary |
| --- | --- | --- | --- |
| Connector ingestion | `ConnectorManifestSpec` and `DatasetFetchSpec` drive a registered connector. It receives a `FetchRequest` and returns a `FetchResult`. | With CAS configured, `run_connectors_ingestion` stores fetched payload refs, a `ProvenanceCoreGraph`, and an `EvidenceBundleRef`. `run_orchestrated_ingestion` may wrap the bundle in a CAS `DataSnapshotRef`. | `tests/unit/fabric/connectors/test_integration.py` exercises connector ingestion with test connectors and CAS. `tests/unit/fabric/data_plane/test_orchestrator.py` stubs the ingestion producer and checks snapshot construction from a persisted evidence bundle. The snapshot builder selects the first bundle source as `data_ref`; it does not merge all sources into a dataset or emit a world fact. |
| Document and claim processing | `ingest_doc_bytes` accepts raw bytes plus `DocSourceSpec`; later stages normalize, structure, and chunk through explicit artifact refs. Claim extraction consumes an explicit normalized/chunked `DocMeta` artifact. | Document and claim stages persist artifacts, emit world facts/events, append fact-log segments, and can be materialized into world tables. | `tests/unit/fabric/test_docs_pipeline.py` covers bytes through document stages and DuckDB materialization. `tests/unit/fabric/test_claims_pipeline.py` covers claim persistence and materialization. These are specific pipelines, not a generic sink for every connector result. |
| Catalog-bound fetch custody | Fabric retrieval takes a `FetchPlan` bound against the Data Forge catalog read API and executes its selected connector request. | CAS stores the complete payload, catalog binding, and `FabricFetchReceipt`. `src/polisyos/runtime/quality/data_forge_binding.py` resolves the receipt and current fetch before emitting a measurement-root payload. | `tests/unit/fabric/test_retrieval_fetch_custody.py` covers receipt and payload custody. `tests/unit/runtime/quality/test_promotion_sequence.py::test_real_measurement_root_resolves_and_binds_into_n9` covers the bounded fixture-backed measurement-root consumer; `tests/unit/runtime/quality/test_promotion_sequence.py::test_n9_replays_current_measurement_source_at_admission` covers the admission recheck. The receipt authority is catalog selection and returned-result custody. |
| Prepared Data Forge assets | Offline domain builders publish typed assets through Data Forge's build and publication surfaces. | `ArtifactRef` carries the content hash, producer/version, config hash, owner, license, regeneration command, PII and retention classifications, freshness SLA, and schema identity. Runtime readers enter through `polisyos.data_forge.read_api`. | See `src/polisyos/data_forge/README.md`, `src/polisyos/data_forge/kernel/artifacts.py`, and `src/polisyos/data_forge/read_api/`. This is a separate asset lifecycle from a Fabric connector fetch. |

## Boundary and custody details

The stable Fabric package facade is `src/polisyos/fabric/__init__.py`; subsystem
responsibilities are documented in the package READMEs and pages below. The
intended Fabric dependency on Data Forge is the narrow `read_api`, not
`data_forge.kernel` or `data_forge.domains`. `architecture/packages/boundaries.toml`
declares that rule, while `architecture/imports/policy.toml` allows the broader
`data_forge` root. One observed exception is
`src/polisyos/fabric/retrieval/service.py`, which imports
`polisyos.data_forge.domains.catalog.batch.config._profile_input_coverage_currentness`
inside `_catalog_profile_plan_admission`; the declared rule is not the complete
observed import picture.

The `read_api` name does not guarantee that every export is read-only:
`src/polisyos/data_forge/read_api/legal.py` exports `run_batch_pipeline`, and
`src/polisyos/data_forge/read_api/academic.py` exports `run_edge_synthesize`
from domain batch modules. Treat the package boundary as the intended rule and
the imports above as exceptions requiring consolidation; this page does not
claim a fully enforced narrow matrix. See the
[Data Fabric explanation](../../explanation/data-fabric.md#fabric-and-data-forge)
for the conceptual build/runtime distinction.

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

Read connector identity at each boundary. A connector class and its
`connector_id` identify an adapter declaration; a SourceContract has its own
`contract_id` and names a `connector_id`. The separate
`validate_source_conformance_v2` path compares a SourceContract's declared
connector ID with the connector metadata's qualified ID and, when set, checks
that the connector class ID is represented. `tests/repo_quality/tools/test_fabric_source_contracts.py`
asserts zero conformance errors for the generated set. The checker and test
source were inspected, not run, for this page. This is bounded declaration-level
identity evidence; it does not establish native or stable facade resolution,
provider readiness, or the family-level mapping measured by the inventory. The
[best-in-class inventory](best-in-class-inventory.md) therefore remains
`partial` for `source.entrypoint_coverage.direct_import_families`.

## How to read evidence and capability state

These artifacts answer different questions; none is a substitute for the next
producer or consumer in a workflow.

| Evidence layer | What the inspected path establishes | What remains unestablished | Follow the source change in |
| --- | --- | --- | --- |
| Connector declaration and contract | Source declares the adapter, `connector_id`, profile and schema/quality metadata; a separate conformance checker compares generated SourceContracts with connector metadata. | Live provider reachability, provider-backed fixture provenance, the inventory's family-level mapping, or source truth. Conformance-test execution for this page is not established. | [Connectors](connectors.md), [source platform](source-platform.md), and [schema compatibility](schema-compatibility.md); inspect `tests/unit/fabric/connectors/test_protocol_compliance.py`, `tests/unit/fabric/connectors/test_source_contract_v2.py`, and `tests/repo_quality/tools/test_fabric_source_contracts.py`. |
| Persisted connector result | With CAS configured, connector ingestion stores payload artifacts and a provenance graph, then returns an `EvidenceBundleRef`; the optional `DataSnapshot` points at the bundle's first source artifact. | A merge of every connector result into a world dataset, or a generic downstream consumer of that snapshot. | [Data plane](data-plane.md) and `tests/unit/fabric/connectors/test_integration.py` / `tests/unit/fabric/data_plane/test_orchestrator.py`. |
| Catalog-bound retrieval | `FabricFetchReceipt` binds a selected catalog target to the returned persisted payload; the bounded measurement-root path resolves it and rechecks against a current fetch. | Historical transport occurrence at the recorded time or scientific truth of the result. | `src/polisyos/fabric/retrieval/custody.py`, `src/polisyos/runtime/quality/data_forge_binding.py`, and `tests/unit/fabric/test_retrieval_fetch_custody.py`. |
| Document and claim producers | Explicit document stages and claim extraction persist their own artifacts and emit their own world facts/events. | A generic bridge from connector results or snapshots into those producers. That end-to-end bridge is `bridge_missing`. | [Data plane](data-plane.md), [product/API integration](product-api-integration.md), and `tests/unit/fabric/test_docs_pipeline.py` / `tests/unit/fabric/test_claims_pipeline.py`. |
| Lineage and world query | Connector ingestion records fetch provenance and, when a transform applies, can merge its transform graph. `FabricLineageTracker` can represent later graph nodes. | Production call sites connecting materialized columns, claims, facts, and query results into one automatic source-to-query graph: `bridge_missing`; the end-to-end semantic test is also `semantic_test_missing`. | [Lineage](lineage.md), [time travel](time-travel.md), and `tests/unit/fabric/test_lineage.py`. |
| Runtime operation | Named unit tests exercise fixture-backed code paths; the ingestion HTTP test patches the producer. | Live provider readiness, deployed behavior, or a complete input-to-policy workflow. These are `not_established` by the inspected tests. | [Product/API integration](product-api-integration.md) and the specific producer/consumer tests linked on each reference page. |

Connector quality has the same evidence boundary. Source-supplied quality,
freshness, version, and update fields are typed inputs; local validators can
compute bounded indicators over returned data; and the orchestrator's
`fabric.quality_report` is metadata-only. None independently establishes
provider truth. See [quality](quality.md) for the distinction between computed
checks and the report attached during snapshot assembly.

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
- **`bridge_missing` for automatic cross-producer lineage, with
  `semantic_test_missing` as a secondary gap.**
  `tests/unit/fabric/test_lineage.py` builds the source, transform,
  materialization, claim, fact, and query nodes directly through
  `FabricLineageTracker`; it verifies graph trace and impact behavior, not that
  operational connector and world-store producers automatically emit one
  complete graph. The downstream producer call sites are absent, so the bridge
  itself is missing; `semantic_test_missing` records that no end-to-end test
  proves the intended bridge.
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

## Declared Fabric facade exports

`src/polisyos/fabric/__init__.py` declares a facade export list (`__all__`)
that includes `run_connectors_ingestion`, `fabric_get_data`,
`execute_world_query`, `query_world_table`, `query_claims`, and `query_events`.
These are declared names, not proof that the names resolve to native or stable
public exports. The [public-surface inventory](../public-surface.md) classifies
the package as `public_stable` but reports export resolution as
`unresolved_exports`; the resolved export set and its count remain unknown.
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
