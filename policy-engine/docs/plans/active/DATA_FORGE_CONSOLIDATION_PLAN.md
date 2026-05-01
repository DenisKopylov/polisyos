---
title: Data Forge Consolidation Plan
status: active
owner: team-data-forge
created: 2026-04-18
last_verified: 2026-04-29
stability: draft
execution_status: hold_until_npa_processing_complete
---

# Data Forge Consolidation Plan

This is the active implementation plan for completing the Data Forge
consolidation. The temporary freeze-safe work has already created the initial
Data Forge foundation and shadow/read surfaces. The plan below restores the
original full consolidation intent: physically move offline data preparation
into `polisyos.data_forge`, retire legacy god-files and compatibility shims,
and make `polisyos.data_forge.read_api` the stable runtime consumption surface.

Execution is intentionally paused until the NPA corpus processing run is fully
complete and the owner explicitly starts the post-processing cutover. This
document is planning-only until that signal is given.

The long-form historical analysis remains in
`docs/DATA_FORGE_CONSOLIDATION_PLAN.md`; repository-wide rules live in
`docs/plans/active/REPOSITORY_SOTA_PLAN.md`.

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

## Execution Hold

Current operational state: NPA processing is finishing but is not yet declared
complete. Until the owner says the processing is complete and asks to start
implementation, this plan must not trigger code movement, cloud runner changes,
Lex entrypoint changes, or compatibility shim removal.

Start the post-processing cutover only after all of the following are true:

1. Queue 2 `shard_4` and Queue 3 Waves 1 through 5 have completed.
2. Merge, QC, publication, and backup checks have passed.
3. The production revision, artifact roots, manifest schemas, output layouts,
   resume markers, and clean/resume semantics are recorded.
4. A baseline old-vs-new replay or differential strategy is documented for
   Legal/Lex, shared batch infrastructure, and Ukraine sharding-adjacent paths.
5. The owner explicitly says to begin execution.

Before that start signal, allowed work is limited to plan edits, review,
inventory, and non-mutating verification.

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
- `domains/catalog` asset mirror, per-source module design, source/readiness
  shadow reader, read API, and baseline/candidate fixtures.
- `domains/ukraine` non-Lex scaffolding/read APIs for source/demography/static
  aging artifacts, plus shadow fixtures. NPA sharding, Lex manifests, and cloud
  runners remain untouched.
- `read_api/*` lazy surfaces and tests proving that importing
  `polisyos.data_forge.read_api` or its surface modules does not eagerly load
  `domains/*`, `kernel/*`, or legacy runtime packages.
- Targeted Data Forge tests under `tests/data_forge/`.

This baseline is not a cutover. Legacy production entrypoints remain live until
their explicit migration phase.

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
   `architecture/public_surface.toml`.
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
5. No `architecture/complexity_exceptions.toml` burn-down before the replacement
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
| 0 | Post-processing cutover readiness | Pending owner start signal | Record production revision, artifact roots, manifest schemas, output layouts, clean/resume semantics, merge/QC evidence, and replay inputs. No code cutover starts before this is complete. |
| 1 | Shared kernel cutover | Planned | Move shared batch infrastructure from `batch_common` and `batch_snapshot` into `data_forge.kernel/*`; wire compatibility shims; prove old-vs-new manifest/snapshot behavior; then burn down shared-batch exceptions. |
| 2 | Academic completion | Partially scaffolded | Move remaining academic batch/QC/benchmark/SKG read surfaces into `domains/academic`; keep legacy imports as shims; publish schema contracts; burn down academic complexity exceptions after tests pass. |
| 3 | Catalog completion | Partially scaffolded | Replace `core_sources_ingest.py` with per-source modules in `domains/catalog`; migrate source registry/harvest/normalize/observations/publish surfaces behind compatibility shims; burn down catalog exception. |
| 4 | Legal cutover | Shadow adapter exists | Move Lex batch logic into `domains/legal`; replay completed NPA outputs; compare manifests, claims, QC, caches, resume markers, and publish artifacts; switch cloud/job entrypoints only after differential checks pass; burn down `lex/batch/*` exceptions. |
| 5 | Ukraine completion | Non-Lex scaffold exists | Move Ukraine pipeline into `domains/ukraine`; split `ukraine_data/builders.py`; only then integrate any sharding-adjacent logic with Legal/Data Forge after Lex dependencies are clear and replayed. |
| 6 | Read API consolidation | Partially scaffolded | Keep lazy `read_api/*` surfaces as the only runtime API; migrate runtime consumers from old read facades in small scoped patches; add import-contract tests; do not perform a broad global import rewrite. |
| 7 | Schema, quality, and observability hardening | Planned | Fill out schema registry migrations, quality differential/drift harnesses, OTel trace propagation, SLO definitions, ArtifactRef coverage, and consumer contracts for each migrated domain. |
| 8 | Shim sunset | Planned | Remove compatibility shims only after `architecture/migration_shims.toml` sunset gates pass, downstream imports are clean, release notes exist, and rollback path is documented. |

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

### Phase 1: Shared Kernel Cutover

Move reusable batch primitives into `data_forge.kernel`:

- manifest read/write/validation;
- stage/publish manifest compatibility;
- snapshot finalize/transaction/Merkle/time-travel;
- file hashing and atomic commit helpers;
- QC/quality contracts;
- config and secret contracts;
- test harnesses.

Compatibility shims must keep `polisyos.batch_common` and
`polisyos.batch_snapshot` importable until all consumers are migrated. Burn down
exceptions only after old-vs-new tests prove behavior parity.

### Phase 2: Academic Completion

Complete the academic migration:

- migrate academic batch assets into `domains/academic`;
- move benchmark/QC/read-only SKG access behind `read_api.academic`;
- publish academic schema contracts;
- add old-vs-new fixtures for readiness and artifact hashes;
- keep `polisyos.academic` compatibility shims until runtime consumers are
  migrated;
- burn down academic exceptions in `architecture/complexity_exceptions.toml`.

### Phase 3: Catalog Completion

Replace the catalog god-file shape:

- split `core_sources_ingest.py` into per-source modules;
- migrate source registry contracts to `domains/catalog`;
- migrate harvest/normalize/observation/publish paths behind the source-module
  asset model;
- keep `polisyos.datasets` compatibility shims until downstream consumers are
  migrated;
- add differential tests for table counts, readiness, source summaries, and
  publish artifacts;
- burn down the `core_sources_ingest.py` exception.

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

### Phase 5: Ukraine Completion

Complete Ukraine only after Legal sharding dependencies are explicit:

- move non-Lex source/demography/static-aging builders into `domains/ukraine`;
- split `ukraine_data/builders.py` into focused modules;
- preserve old `polisyos.ukraine_data` imports as shims during migration;
- integrate any NPA sharding-adjacent functionality only after Legal cutover
  confirms manifest and shard semantics;
- add differential tests for source summaries, demographic targets, static
  aging inputs, and any sharding-adjacent artifacts.

### Phase 6: Read API Consolidation

The read API is already lazy and split by domain. The remaining work is
consumer migration:

- migrate runtime consumers to `polisyos.data_forge.read_api.*` in scoped
  patches;
- add import-contract tests proving runtime packages do not import
  `data_forge.domains` or `data_forge.kernel`;
- keep old read facades alive as shims until downstream consumers are clean;
- avoid broad automatic global import rewrites.

### Phase 7: Schema, Quality, And Observability Hardening

Complete the cross-cutting production layer:

- artifact schemas under `schemas/artifacts/`;
- manifest schemas under `schemas/manifests/`;
- schema evolution/migration checks;
- differential and drift test harnesses per domain;
- OTel traces and ArtifactRef trace metadata;
- SLO definitions under `ops/observability/slo/`;
- consumer contracts for Fabric/runtime packages.

### Phase 8: Shim Sunset

Remove compatibility shims only when:

- `architecture/migration_shims.toml` sunset conditions pass;
- import-linter and package-boundary checks are clean;
- release notes and rollback notes exist;
- tests cover the new read API and old shim removal;
- complexity exceptions are either removed or re-owned with a new sunset.

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
9. No migrated god-file remains in `architecture/complexity_exceptions.toml`
   without a new owner, reason, and sunset.
10. Legal and cloud cutover have replay/differential evidence against completed
    NPA outputs.
11. Shim sunset gates pass and old import paths are either removed or explicitly
    documented as stable public compatibility surfaces.

## Do Not Start Yet

This plan is ready for post-processing execution, but execution remains on hold.
The next implementation step is Phase 0, and it begins only after the owner says
the NPA processing has completed and asks to start the cutover.
