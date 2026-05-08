---
title: Data Forge Consolidation Plan
status: active
owner: team-data-forge
created: 2026-04-18
last_verified: 2026-05-02
stability: stable
execution_status: phase8_legacy_data_forge_shims_removed
---

# Data Forge Consolidation Plan

This is the active implementation plan for completing the Data Forge
consolidation. The temporary freeze-safe work has already created the initial
Data Forge foundation and shadow/read surfaces. The plan below restores the
original full consolidation intent: physically move offline data preparation
into `polisyos.data_forge`, retire legacy god-files and compatibility shims,
and make `polisyos.data_forge.read_api` the stable runtime consumption surface.

Phase 0 cutover readiness is complete and recorded in
`docs/plans/active/DATA_FORGE_CUTOVER_READINESS.md`. Phase 1 through Phase 7
completed the implementation-owner moves, and Phase 8 removed the legacy
academic, catalog, Ukraine, shared-kernel, and snapshot compatibility packages.

The long-form historical analysis remains in
`docs/plans/archive/DATA_FORGE_CONSOLIDATION_PLAN_ROOT_LEGACY.md`; repository-wide rules live in
`docs/plans/accepted/REPOSITORY_SOTA_PLAN.md`.

Key Data Forge decisions are fixed by ADR-0112 through ADR-0114 and ADR-0122
through ADR-0125. This plan may refine implementation sequence, but it must not
redefine snapshot, ArtifactRef, LLM, or quality semantics without updating the
corresponding ADR.

## Goal

Move offline acquisition, normalization, publishing, and batch preprocessing
from:

- `polisyos.academic`
- `polisyos.datasets`
- `polisyos.ukraine_data`
- `polisyos.batch_common`
- `polisyos.batch_snapshot`
- `polisyos.lex.batch`

into:

```text
src/polisyos/data_forge/
```

Runtime packages consume prepared artifacts through stable contracts and
`polisyos.data_forge.read_api`, not through domain or pipeline internals.

## Execution Status

Current operational state: NPA processing is complete and the accepted Lex
artifacts under `production_data/lex_current_20260501` are sufficient for the
completed Legal cutover. Phase 1 shared-kernel, Phase 2 academic, Phase 3
catalog, Phase 4 legal, Phase 5 Ukraine, Phase 6 read API, and Phase 7
schema/quality/observability work are implemented. Phase 8 physically removed
`polisyos.academic`, `polisyos.datasets`, `polisyos.ukraine_data`,
`polisyos.batch_common`, `polisyos.batch_snapshot`, and the old Lex offline
`batch`/`corpus` paths.

## Current Repository Baseline

As of 2026-04-29, the repository already contains an additive Data Forge
baseline:

- `src/polisyos/data_forge/_version.py`, `errors.py`, `py.typed`, and public
  package/read_api facades.
- `kernel/*` skeleton for asset contracts, materialization metadata,
  partitions, config contracts, schema registry/evolution/migration stubs,
  ArtifactRef governance, hashing, snapshot transactions/Merkle/finalize
  helpers, quality checks, and golden testing.
- `domains/legal` read-only Lex shadow adapter and differential fixtures.
- `domains/academic` asset mirror, readiness summary, shadow reader, read API,
  and baseline/candidate fixtures.
- `domains/catalog` asset mirror, full source-module registry mirror,
  per-source harvest/normalize/observation/publish contracts, catalog schema
  registry contracts, benchmark/QC/readiness readers, source/readiness shadow
  reader, read API, and baseline/candidate fixtures.
- `domains/ukraine` non-Lex scaffolding/read APIs for source/demography/static
  aging artifacts, plus shadow fixtures. NPA sharding, Lex manifests, and cloud
  runners remain untouched.
- `read_api/*` lazy surfaces and tests proving that importing
  `polisyos.data_forge.read_api` or its surface modules does not eagerly load
  `domains/*`, `kernel/*`, or legacy runtime packages.
- Targeted Data Forge tests under `tests/unit/data_forge/`.
- Phase 1 shared-kernel cutover: manifest, hashing, atomic IO, snapshot,
  quality, config/secret, runtime pacing, and migration test-harness contracts
  live under `data_forge.kernel`; the old shared-kernel compatibility packages
  were removed in Phase 8.
- Phase 2 academic completion: academic batch-stage asset contracts,
  readiness/benchmark/QC readers, schema contracts, artifact-hash differential
  tests, and read-only SKG inspection live behind `read_api.academic`.
- Phase 3 catalog completion: catalog source registry contracts, all checked-in
  catalog source modules, per-source asset/stage contracts, schema contracts,
  readiness/benchmark/QC readers, and old-vs-new catalog fixture checks live
  behind `read_api.catalog`; the legacy datasets compatibility package was
  removed in Phase 8.
- Phase 4 legal cutover: legal batch runtime modules now live under
  `data_forge.domains.legal.batch`, corpus preprocessing lives under
  `data_forge.domains.legal.corpus`, and the old Lex offline paths were
  removed. Cloud runner imports point at Data Forge; legal shadow comparisons
  cover manifests, claims, claim summaries, QC, benchmark summaries,
  cache/resume markers, and publish artifacts.
- Phase 7 hardening: concrete ArtifactRef/domain-artifact/trace metadata
  schemas live under `schemas/artifacts/`; raw/stage/publish manifest schemas
  live under `schemas/manifests/`; schema evolution/migration checks, drift
  harnesses, OTel trace metadata helpers, Data Forge SLOs, and Fabric/runtime
  read-API-only consumer contracts are covered by targeted tests.

Legacy production/domain entrypoints remain live until their explicit migration
phase. The implemented Phase 1 through Phase 4 work preserved compatibility
imports.

## Target Layout

```text
src/polisyos/data_forge/
|-- __init__.py
|-- _version.py
|-- errors.py
|-- kernel/
|   |-- pipeline/
|   |-- io/
|   |-- harvest/
|   |-- transform/
|   |-- extraction/
|   |-- index/
|   |-- quality/
|   |-- snapshot/
|   |-- schemas/
|   `-- testing/
|-- domains/
|   |-- academic/
|   |-- catalog/
|   |-- ukraine/
|   `-- legal/
|-- read_api/
|   |-- __init__.py
|   |-- surfaces.py
|   |-- academic.py
|   |-- catalog.py
|   |-- legal.py
|   `-- ukraine.py
`-- py.typed
```

Rules:

1. `domains/*` may import `kernel/*`.
2. `domains/*` may not import sibling domains.
3. Runtime packages may import only `polisyos.data_forge.read_api`.
4. `kernel/*` remains internal unless explicitly listed in
   `architecture/public_surface/contract.toml`.
5. Legacy package entrypoints remain as compatibility shims only until their
   sunset gates pass.

## Non-Negotiable Cutover Invariants

During the full consolidation, preserve these invariants:

1. No production artifact schema changes without a schema registry version,
   migration/evolution rule, and old-vs-new comparison.
2. No cloud job import switch until replay/differential checks pass for the
   affected domain.
3. No removal of old entrypoints until compatibility shims have test coverage,
   migration owner, and sunset gate.
4. No runtime import from `polisyos.data_forge.domains` or
   `polisyos.data_forge.kernel` outside Data Forge itself.
5. No `architecture/exceptions/complexity.toml` burn-down before the replacement
   module is complete and protected by tests.
6. No broad global import rewrite. Each import migration must be scoped to the
   phase and verified by targeted tests.

## Asset-Centric Model

The primary object is an asset, not a stage. A stage is only a materialization
function.

```python
@asset(
    key=AssetKey("academic", "works", "normalized"),
    deps=[AssetKey("academic", "works", "raw")],
    partitions=DailyPartition(),
    io=DuckDBTableIO("ac_works"),
    schema=NormalizedWorkSchema,
    freshness_sla=timedelta(days=7),
    retention=RetentionClass.LONG,
    owner="team-data-forge",
)
async def ac_works_normalized(ctx, raw: Works) -> Works:
    ...
```

Required kernel modules:

| Module                           | Purpose                                                |
| -------------------------------- | ------------------------------------------------------ |
| `kernel/pipeline/assets.py`      | `AssetKey`, `AssetSpec`, `AssetGroup`, `PartitionSpec` |
| `kernel/pipeline/materialize.py` | `@asset`, materialization planner/executor             |
| `kernel/pipeline/partitions.py`  | time/hash/composite partitions                         |
| `kernel/pipeline/config/`        | pydantic-settings profile composition                  |
| `kernel/pipeline/schemas/`       | versioned schema registry and migration rules          |

## Lakehouse Snapshot Semantics

Decision source: ADR-0122.

Publishing is atomic and addressable:

| Module                            | Purpose                                         |
| --------------------------------- | ----------------------------------------------- |
| `kernel/snapshot/transactions.py` | all-or-nothing asset group publish              |
| `kernel/snapshot/commit.py`       | write-then-rename atomic commit                 |
| `kernel/snapshot/merkle.py`       | Merkle root for complete snapshot identity      |
| `kernel/snapshot/time_travel.py`  | resolve artifact at `(snapshot_id, logical_ts)` |
| `kernel/snapshot/retention.py`    | HOT/WARM/COLD/EPHEMERAL retention and GC        |

Published artifacts use logical URIs such as:

```text
polisyos://academic/skg@<snapshot_id>
```

Local filesystem paths are cache hints only.

## Schema Registry

Decision source: ADR-0114.

Data Forge publication boundaries use a versioned schema registry:

```text
kernel/pipeline/schemas/
|-- registry.py
|-- evolution.py
|-- codegen.py
`-- migrations.py
```

Compatibility modes:

- `BACKWARD`
- `FORWARD`
- `FULL`

CI must fail when a schema-visible change lacks an evolution rule or a
migration from the previous version.

## ArtifactRef Governance

Decision source: ADR-0123.

Published artifact references include:

| Field                         | Meaning                                        |
| ----------------------------- | ---------------------------------------------- |
| `uri`                         | logical `polisyos://...` identifier            |
| `sha256`                      | content hash                                   |
| `producer`                    | module/function that materialized the artifact |
| `producer_version`            | code/model/lockfile version tuple              |
| `trace_id`, `span_id`         | OTel trace linkage                             |
| `config_hash`                 | materialization config hash                    |
| `owner`                       | accountable team                               |
| `license`                     | artifact license                               |
| `regeneration_command`        | canonical command or review path to reproduce  |
| `pii_level`                   | `none`, `low`, `medium`, `high`                |
| `retention_class`             | `hot`, `warm`, `cold`, `ephemeral`             |
| `freshness_sla_seconds`       | freshness contract                             |
| `schema_id`, `schema_version` | schema registry identity                       |

## OTel-First Telemetry

Decision source: ADR-0116.

Traces, metrics, and logs flow through OpenTelemetry first. JSONL, Prometheus
textfile, and summary files are exporters/fallbacks, not the canonical telemetry
API.

Required behavior:

1. W3C trace context propagates across stages, retries, and LLM calls.
2. `trace_id` and `span_id` are written to stage manifests and ArtifactRefs.
3. CI validates that Data Forge SLO definitions exist under
   `ops/observability/slo/`.

## Quality System

Decision source: ADR-0125.

`kernel/quality/` includes:

| Module                  | Purpose                                        |
| ----------------------- | ---------------------------------------------- |
| `expectations.py`       | declarative expectations over any artifact     |
| `differential.py`       | old-vs-new pipeline diff tests with tolerances |
| `drift.py`              | distribution drift between snapshots           |
| `consumer_contracts.py` | Fabric/runtime minimum requirements            |

Golden tests remain, but differential and drift tests are required for
LLM-extracted or embedding-derived assets.

## Config And Secrets

Pipeline config uses pydantic-settings plus profile composition:

```text
kernel/pipeline/config/
|-- base.py
|-- profiles/
|   |-- base.yaml
|   |-- prod_full.yaml
|   |-- preflight.yaml
|   `-- dev.yaml
|-- compose.py
`-- schema.py
```

Secrets use a protocol, not direct env reads:

```python
class SecretBackend(Protocol):
    def get(self, name: str) -> str | None: ...
```

Backends: env, dotenv, GCP Secret Manager, Vault, file-mounted secrets. All
secrets are redacted or hashed before logs, telemetry, or manifests.

## LLM Idempotency

Decision source: ADR-0124.

LLM extraction requires:

1. Cache key over messages, model, temperature, seed, response schema hash, and
   provider version.
2. Idempotency keys per batch record.
3. Dead-letter queue for poison-pill records.
4. Prompt registry with prompt version in lineage.
5. Per-prompt eval sets with precision/recall regression gates.

## Phase Plan

The implementation order below is the full consolidation order after the NPA
processing completion gate passes.

| Phase | Name | State | Deliverables |
| ----- | ---- | ----- | ------------ |
| 0 | Post-processing cutover readiness | Completed | `DATA_FORGE_CUTOVER_READINESS.md` records production revision, accepted Lex artifact root, output inventory, QC/benchmark evidence, schemas/layouts, clean/resume semantics, replay inputs, rollback checkpoints, and owner sign-off. |
| 1 | Shared kernel cutover | Completed; shims removed | Shared batch infrastructure from `batch_common` and `batch_snapshot` now lives in `data_forge.kernel/*`; old shared-kernel shims were physically removed; manifest/snapshot behavior is covered by targeted tests. |
| 2 | Academic completion | Completed; shims removed | Academic batch/OpenAlex/SKG/knowledge implementation now lives under `domains/academic`; `read_api.academic` exposes Data Forge-owned symbols; `polisyos.academic` was physically removed; academic complexity exceptions are burned down. |
| 3 | Catalog completion | Completed; shims removed | Catalog batch/knowledge/metrics implementation now lives under `domains/catalog`; source registry and checked-in source modules live in Data Forge; `read_api.catalog` exposes Data Forge-owned symbols; `polisyos.datasets` was physically removed; the legacy `core_sources_ingest.py` exception and `_core_sources_ingest_runtime.py` shape are burned down. |
| 4 | Legal cutover | Completed; old Lex offline paths removed | Legal batch runtime lives under `domains/legal/batch`; corpus preprocessing lives under `domains/legal/corpus`; cloud runner imports point at Data Forge; legal shadow/differential fixtures cover manifests, claims, claim summaries, QC, benchmark summaries, cache/resume markers, and publish artifacts; `lex/batch/*` complexity exceptions are burned down. |
| 5 | Ukraine completion | Completed; shims removed | Ukraine source adapters, manifests, models, resources, server/orchestrator/CLI, and production builders now live under `domains/ukraine`; `ukraine_data/builders.py` is split into focused Data Forge builder modules for common primitives, source/observation stages, demography, calibration, and release; `polisyos.ukraine_data` was physically removed; sharding-adjacent pre-shard summary semantics are explicit and covered by differential fixtures; the old builders complexity exception is burned down. |
| 6 | Read API consolidation | Implemented | Lazy `read_api/*` surfaces are the runtime-facing API; scoped runtime consumers now route through `polisyos.data_forge.read_api.*`; import-contract tests prove runtime does not import Data Forge domain/kernel internals or legacy read facades directly. |
| 7 | Schema, quality, and observability hardening | Implemented | Concrete artifact/manifest schemas, schema evolution and migration checks, domain drift harnesses, OTel ArtifactRef trace metadata helpers, SLO definitions, and Fabric/runtime read-API-only consumer contracts are covered by targeted tests. |
| 8 | Shim sunset | Completed for Data Forge and old Lex offline paths | Runtime/tool consumers were moved off legacy shims, obsolete import exceptions were burned down, release/rollback notes exist, and targeted tests enforce that the academic, datasets, Ukraine, batch_common, batch_snapshot, Lex batch, and Lex corpus directories are absent. |

## Phase Details

### Phase 0: Post-Processing Cutover Readiness

Create `docs/plans/active/DATA_FORGE_CUTOVER_READINESS.md` before code
cutover begins. It must include:

- exact production revision used for final NPA processing;
- Queue 2 and Queue 3 completion evidence;
- merge/QC/publication evidence;
- artifact root inventory;
- production manifest/schema/output-layout inventory;
- clean/resume/cache/idempotency behavior notes;
- replay fixtures or copied completed outputs for Legal, shared snapshot, and
  Ukraine sharding-adjacent checks;
- rollback checkpoints and owner sign-off.

Implementation status as of 2026-05-02:

- The production readiness gate is recorded in
  `docs/plans/active/DATA_FORGE_CUTOVER_READINESS.md`.
- The accepted immutable Lex artifact root is
  `production_data/lex_current_20260501`, with completed QC, benchmark,
  DuckDB graph, and normative-claim export artifacts.
- Owner sign-off accepts the Lex root for replay evidence even though the
  benchmark report still records advisory/readiness failures for reference
  resolution and temporal-current-safety thresholds.

### Phase 1: Shared Kernel Cutover

Move reusable batch primitives into `data_forge.kernel`:

- manifest read/write/validation;
- stage/publish manifest compatibility;
- snapshot finalize/transaction/Merkle/time-travel;
- file hashing and atomic commit helpers;
- QC/quality contracts;
- config and secret contracts;
- test harnesses.

Compatibility shims were allowed until all consumers migrated. They are now
removed, and canonical snapshot usage goes through
`polisyos.data_forge.kernel.snapshot.cli`.

Implementation status as of 2026-05-02:

- `kernel.pipeline.manifests` owns raw/stage/publish manifest IO,
  compatibility dataclasses, manifest reads, and artifact checksum validation.
- `kernel.io` owns hashing, JSONL hashing, path helpers, and atomic file/commit
  helpers.
- `kernel.snapshot` owns snapshot finalize, transaction, commit, Merkle,
  retention, and time-travel contracts.
- `kernel.quality` owns QC and Phase-0 quality contracts.
- `kernel.pipeline.config` owns profile and secret-provider contracts.
- `kernel.runtime` owns thermal pacing contracts.
- `kernel.testing` owns golden and differential comparison harnesses.
- `polisyos.batch_common` and `polisyos.batch_snapshot` were removed after
  consumers and tests moved to Data Forge kernel imports.

### Phase 2: Academic Completion

Complete the academic migration:

- migrate academic batch assets into `domains/academic`;
- move benchmark/QC/read-only SKG access behind `read_api.academic`;
- publish academic schema contracts;
- add old-vs-new fixtures for readiness and artifact hashes;
- remove `polisyos.academic` compatibility shims after runtime consumers are
  migrated;
- burn down academic exceptions in `architecture/exceptions/complexity.toml`.

Implementation status as of 2026-05-02:

- `domains.academic.batch`, `domains.academic.openalex`,
  `domains.academic.knowledge`, and `domains.academic.trust` own the former
  `polisyos.academic` implementation modules.
- `domains.academic.batch_assets` declares the legacy academic stage graph as
  Data Forge asset contracts without importing legacy academic implementation.
- `domains.academic.schemas` publishes high-level academic asset schemas and
  per-stage batch schemas in a Data Forge schema registry.
- `domains.academic.quality` loads academic benchmark, QC, readiness, and
  artifact-hash summaries from completed outputs.
- `domains.academic.skg` inspects SKG DuckDB artifacts in read-only mode and
  tolerates placeholder or unreadable fixture artifacts.
- `read_api.academic` lazily exposes Data Forge-owned academic contracts,
  readers, batch config, SKG types, canonical variables, runtime canonical
  registry helpers, and edge synthesis without importing legacy academic
  implementation.
- `polisyos.academic` was physically removed in Phase 8.
- Targeted Phase 2 tests cover asset planning, schema registry coverage,
  readiness/hash old-vs-new fixtures, SKG inspection, and import safety.

### Phase 3: Catalog Completion

Replace the catalog god-file shape:

- split `core_sources_ingest.py` into per-source modules;
- migrate source registry contracts to `domains/catalog`;
- migrate harvest/normalize/observation/publish paths behind the source-module
  asset model;
- remove `polisyos.datasets` compatibility shims after downstream consumers are
  migrated;
- add differential tests for table counts, readiness, source summaries, and
  publish artifacts;
- burn down the `core_sources_ingest.py` exception.

Implementation status as of 2026-05-02:

- `domains.catalog.batch`, `domains.catalog.knowledge`, and
  `domains.catalog.metrics_map` own the former `polisyos.datasets`
  implementation modules.
- `domains.catalog.source_modules` declares source-owned harvest, normalize,
  observation, and publish asset contracts.
- `domains.catalog.sources.*` splits the checked-in source registry into
  per-family source modules while preserving source order and run-profile
  semantics.
- `domains.catalog.registry` loads and validates the legacy
  `source_registry.yaml` without importing `polisyos.datasets`.
- `domains.catalog.schemas` publishes base catalog schemas and per-source
  stage schemas in a Data Forge schema registry.
- `domains.catalog.quality` loads catalog benchmark, QC, readiness, and
  artifact-hash summaries from completed outputs.
- `read_api.catalog` lazily exposes Data Forge-owned catalog contracts,
  readers, source registry helpers, Dataset Catalog Graph, proxy resolution,
  and variable-alignment helpers.
- `polisyos.datasets` was physically removed in Phase 8.
- The legacy `_core_sources_ingest_runtime.py` indirection is removed; the
  canonical entrypoint is `domains.catalog.batch.core_sources_ingest`.
- Targeted Phase 3 tests cover registry parity, source-module planning,
  per-source stage contracts, schema registry coverage, readiness/hash
  old-vs-new fixtures, source summaries, table-count deltas, publish artifact
  deltas, deleted-shim behavior, and complexity exception burn-down.

### Phase 4: Legal Cutover

Legal cutover starts only after Phase 0 sign-off.

Required sequence:

1. Copy completed NPA outputs into replay fixtures or point tests at immutable
   artifact roots.
2. Move Lex batch internals into `domains/legal` without changing behavior.
3. Compare old-vs-new outputs for manifests, claims, claim summaries, QC,
   benchmark summaries, cache/resume markers, and publish artifacts.
4. Switch local CLI/job entrypoints to compatibility shims.
5. Switch cloud entrypoints only after replay/differential results pass.
6. Burn down `lex/batch/*` exceptions and update import contracts.

Implementation status as of 2026-05-01:

- The accepted completed NPA output root is recorded as
  `tests/_data/data_forge/legal_shadow/accepted_artifact_root.json`, pointing
  at the local immutable root `production_data/lex_current_20260501/finalize`;
  CI-sized replay fixtures cover publish-manifest differential behavior.
- `polisyos.data_forge.domains.legal.batch` owns the moved Lex batch runtime
  modules.
- `polisyos.data_forge.domains.legal.batch` is the only local batch CLI,
  including `python -m polisyos.data_forge.domains.legal.batch`.
- Runtime job entrypoints consume `polisyos.data_forge.read_api.legal`.
- The cloud manifest runner and GCP preflight import the Data Forge legal batch
  runtime directly.
- The legal shadow adapter compares accepted Lex outputs for manifests, claims,
  claim summaries, QC, benchmark summaries, cache/resume markers, and publish
  artifacts, including `publish/manifest.json` itself.
- Import contracts and package boundaries forbid retired Lex offline imports.
- `lex/batch/*` complexity exceptions are burned down and covered by targeted
  Phase 4 tests; the import gate passes with Phase 4 compatibility exceptions
  registered in `architecture/imports/exceptions.toml`.

### Phase 5: Ukraine Completion

Complete Ukraine only after Legal sharding dependencies are explicit:

- move non-Lex source/demography/static-aging builders into `domains/ukraine`;
- split `ukraine_data/builders.py` into focused modules;
- remove old `polisyos.ukraine_data` imports after migration;
- integrate any NPA sharding-adjacent functionality only after Legal cutover
  confirms manifest and shard semantics;
- add differential tests for source summaries, demographic targets, static
  aging inputs, and any sharding-adjacent artifacts.

Implementation status as of 2026-05-01:

- `domains.ukraine.adapters`, `models`, `manifests`, `resources`, `server`,
  `orchestrator`, and `cli` own the former Ukraine production runtime modules.
- `domains.ukraine.builders` owns focused `common`, `sources`, `demography`,
  `calibration`, and `release` builder modules while preserving the accepted
  stage behavior.
- `domains.ukraine.static_aging` owns static-aging state composition; the lazy
  `read_api.ukraine` surface delegates to it.
- `domains.ukraine.sharding` records the post-Legal NPA pre-shard status,
  snapshot-label, deterministic shard assignment, summary loading, and
  differential contracts without importing Lex batch internals.
- `polisyos.ukraine_data` was physically removed in Phase 8.
- Targeted Phase 5 tests cover source summaries, demographic/static-aging
  inputs, pre-shard summary diffs, deleted-shim behavior, and complexity
  exception burn-down.

### Phase 6: Read API Consolidation

The read API is already lazy and split by domain. The remaining work is
consumer migration:

- migrate runtime consumers to `polisyos.data_forge.read_api.*` in scoped
  patches;
- add import-contract tests proving runtime packages do not import
  `data_forge.domains` or `data_forge.kernel`;
- keep old read facades alive as shims until downstream consumers are clean;
- avoid broad automatic global import rewrites.

Implementation status as of 2026-05-01:

- Runtime Lex pipeline execution and search consumers route through
  `polisyos.data_forge.read_api.legal` instead of importing Legal/Lex read
  internals directly.
- `read_api.legal.search_legal_knowledge_graph` provides a small read-only
  DuckDB graph search surface without importing the old Lex knowledge facade;
  that old facade remains available for non-runtime downstream users.
- `tests/unit/data_forge/test_phase6_read_api_consolidation.py` enforces lazy
  `read_api` imports, no eager `domains/*` or `kernel/*` imports, and no direct
  runtime imports of Data Forge internals or legacy read facades.
- No broad automatic import rewrite was performed; migration stayed scoped to
  the runtime consumer found in the control service.

### Phase 7: Schema, Quality, And Observability Hardening

Complete the cross-cutting production layer:

- artifact schemas under `schemas/artifacts/`;
- manifest schemas under `schemas/manifests/`;
- schema evolution/migration checks;
- differential and drift test harnesses per domain;
- OTel traces and ArtifactRef trace metadata;
- SLO definitions under `ops/observability/slo/`;
- consumer contracts for Fabric/runtime packages.

Implementation status as of 2026-05-02:

- `schemas/artifacts/` contains ArtifactRef, ArtifactTraceMetadata, and
  domain-artifact schemas covering governance, trace, quality, differential, and
  drift metadata.
- `schemas/manifests/` contains raw, stage, and publish manifest schemas
  compatible with the shared-kernel manifest writers.
- `kernel.schemas.evolution` evaluates schema-visible additions, removals, and
  type changes; uncovered breaking changes raise `SchemaCompatibilityError`.
- `kernel.schemas.migrations` plans and applies deterministic version-to-version
  migration paths.
- `kernel.testing.drift` compares domain metric drift for academic, catalog,
  legal, and Ukraine gates; differential/golden harnesses remain available in
  the same package.
- `kernel.observability` reads the current OTel span context, emits ArtifactRef
  trace metadata, and can bind trace IDs plus trace labels onto ArtifactRefs;
  shared-kernel raw/stage/publish manifest writers can persist `trace_id` and
  `span_id` when given a `TraceContext` while preserving legacy payload shape
  when omitted.
- Data Forge SLO objectives include schema-evolution and domain-drift violation
  rates and validate against `schemas/ops/slo.schema.json`.
- Import/package-boundary contracts explicitly keep Fabric and runtime packages
  on `polisyos.data_forge.read_api` rather than Data Forge internals.

### Phase 8: Shim Sunset

Remove compatibility shims only when:

- `architecture/shims.toml` sunset conditions pass;
- import-linter and package-boundary checks are clean;
- release notes and rollback notes exist;
- tests cover the new read API and old shim removal;
- complexity exceptions are either removed or re-owned with a new sunset.

Implementation status as of 2026-05-02:

- Data Forge legal, academic, and catalog batch modules no longer import
  `polisyos.batch_common`; they use shared-kernel manifest/runtime/quality/IO
  helpers directly.
- Fabric retrieval source-policy lookup now reads the Data Forge catalog source
  registry instead of `polisyos.datasets.batch.source_registry`.
- Foundry release acceptance now loads Ukraine release manifests through
  `polisyos.data_forge.read_api.ukraine`.
- Ukraine operational builder tools and the `ukraine-data` console entrypoint
  now target Data Forge Ukraine modules.
- Scientist, IR, Foundry, cloud, research, and Ukraine pre-shard consumers that
  still used removed legacy/offline packages now route through
  `polisyos.data_forge.read_api.*` or Data Forge-owned CLI modules.
- Scientist Ukraine real-history backtest metadata now uses a Data Forge-owned
  Ukraine contract marker instead of `polisyos.ukraine_data`.
- Import-policy exceptions for Data Forge legal batch to `batch_common`, Fabric
  retrieval to `datasets`, and Foundry release acceptance to `ukraine_data`
  are removed.
- Release notes and rollback notes live under `docs/migration/`.
- `tests/unit/data_forge/test_phase8_shim_sunset.py` guards the migrated consumers,
  the removed exceptions, the documented rollback path, deleted directory
  assertions, and the canonical academic/catalog/legal/Ukraine test import
  paths.
- `polisyos.academic`, `polisyos.datasets`, `polisyos.ukraine_data`,
  `polisyos.batch_common`, `polisyos.batch_snapshot`, and old Lex offline
  `batch`/`corpus` paths were removed from source, public surface inventory,
  package boundaries, and migration shims.

## Import And Boundary Contracts

Required checks:

1. `import-linter` proves Data Forge domains are independent.
2. Runtime packages import only `polisyos.data_forge.read_api`.
3. `read_api` package import remains lazy and does not load `domains/*` or
   `kernel/*`.
4. Legacy imports are allowed only in compatibility shims and targeted tests.
5. No sibling-domain imports inside `domains/*`.

## Acceptance Criteria

The plan is complete when:

1. All offline data preparation lives in `polisyos.data_forge`.
2. Legacy packages are compatibility shims or removed according to sunset gates.
3. Runtime packages import only `polisyos.data_forge.read_api`.
4. Published snapshots are atomic and have Merkle roots.
5. ArtifactRefs include governance metadata and OTel trace IDs.
6. Generated schemas and frontend types are drift-checked.
7. Golden, differential, and drift tests pass for each migrated domain.
8. Each migrated domain publishes artifact schemas under `schemas/artifacts/`
   and manifest schemas under `schemas/manifests/`.
9. No migrated god-file remains in `architecture/exceptions/complexity.toml`
   without a new owner, reason, and sunset.
10. Legal and cloud cutover have replay/differential evidence against completed
    NPA outputs.
11. Shim sunset gates pass and old import paths are either removed or explicitly
    documented as stable public compatibility surfaces.

## Execution Status

The post-processing execution hold has been lifted by owner direction. Phase 0
readiness and Phases 1 through 7 are implemented. Phase 8 has completed the
physical academic/catalog implementation-owner move and is now in thin-shim
sunset mode until migration-shim deletion gates pass.
