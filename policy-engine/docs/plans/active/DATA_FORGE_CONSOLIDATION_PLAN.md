---
title: Data Forge Consolidation Plan
status: active
owner: team-data-forge
created: 2026-04-18
last_verified: 2026-04-24
stability: draft
---

# Data Forge Consolidation Plan

This is the focused active implementation plan for Data Forge. The long-form
historical analysis remains in `docs/DATA_FORGE_CONSOLIDATION_PLAN.md`; the
repository-wide rules live in `docs/plans/active/REPOSITORY_SOTA_PLAN.md`.

Key Data Forge decisions are fixed by ADR-0112 through ADR-0114 and ADR-0122
through ADR-0125. This plan may refine implementation sequence, but it must not
redefine snapshot, ArtifactRef, LLM, or quality semantics without updating the
corresponding ADR.

## Scope

Move offline data acquisition and preprocessing from:

- `polisyos.academic`
- `polisyos.datasets`
- `polisyos.ukraine_data`
- `polisyos.batch_common`
- `polisyos.batch_snapshot`
- `polisyos.lex.batch`

into a single build-time package:

```text
src/polisyos/data_forge/
```

Runtime packages consume artifacts through stable contracts and
`data_forge.read_api`, not through pipeline internals.

Temporary constraint: as of 2026-04-24, the cloud Lex pipeline is processing the
NPA corpus. Queue 2 is finishing `shard_4`, and Queue 3 Wave 1 is active for
`shard_0` through `shard_4`; Queue 3 Waves 2, 3, 4, and 5 are still expected to
run. Until that run completes, Data Forge work uses a hybrid additive/domain
split plan:

1. Build new Data Forge foundations additively.
2. Allow non-Lex domain work that does not touch active cloud pipeline surfaces.
3. Freeze physical moves and behavior changes for the Lex production writer.
4. Return to the strict consolidation sequence after the run is complete.

## Temporary Lex Production Freeze

This freeze starts on 2026-04-24 and ends only after all of the following are
true:

1. Queue 2 `shard_4` has completed.
2. Queue 3 Waves 1 through 5 have completed.
3. Shard merge, QC, and publication checks have passed.
4. A cutover readiness note records the exact production source revision,
   artifact roots, and merge/QC evidence.

The freeze is event-gated, not calendar-gated. During this window, the current
Lex pipeline remains the production writer and Data Forge remains a shadow or
read-only consumer for legal artifacts.

Protected surfaces during the freeze:

- `src/polisyos/lex/batch/**`
- `src/polisyos/batch_common/**`
- `src/polisyos/batch_snapshot/**`
- `tools/ops/cloud/run_lex_from_manifest.py`
- `tools/ops/cloud/build_queue3_waves.py`
- `tools/ops/cloud/merge_shards.py`
- `tools/ops/cloud/prepare_shards.*`
- `tools/ops/ukraine_data/pre_shard_lex_corpus.py`
- `tools/cloud/**` compatibility wrappers used by cloud jobs
- production Lex output layouts, stage manifests, resume markers, cache keys,
  idempotency keys, and clean/resume semantics

Forbidden during the freeze:

1. Moving or renaming `polisyos.lex.batch`, `polisyos.batch_common`, or
   `polisyos.batch_snapshot`.
2. Rewriting active cloud runner imports from old paths to Data Forge paths.
3. Changing production manifest schemas, shard assignment semantics, output
   directory layout, cache keys, or cleanup/resume behavior.
4. Removing or tightening compatibility wrappers required by queued cloud jobs.
5. Burning down `lex/batch/*`, `batch_common`, or `batch_snapshot` complexity
   exceptions before the cutover gate.

Allowed during the freeze:

1. Create or extend `polisyos.data_forge` modules without switching production
   Lex jobs to them.
2. Build the asset kernel, schema registry skeleton, ArtifactRef models,
   snapshot contracts, config contracts, quality contracts, and test harnesses.
3. Add read-only or shadow legal adapters that inspect completed Lex artifacts
   without writing to production outputs.
4. Capture tiny legal goldens from local fixtures or completed shard outputs.
5. Migrate academic and catalog code when their public imports, tests, and
   compatibility shims remain stable.
6. Add Ukraine Data Forge scaffolding and read APIs, but defer any change that
   affects Lex NPA sharding, manifests, or cloud execution.
7. Add import/package-boundary checks in warning or allowlisted mode for paths
   still frozen by this section.

If a production Lex hotfix is required during the freeze, it must be narrowly
scoped, preserve existing import paths and artifact semantics, and be called out
in the cutover readiness note.

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

## Config and Secrets

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

## Phases

| Phase | Mode | Deliverables |
| ----- | ---- | ------------ |
| 0A | Freeze-safe foundation | Create `data_forge` skeleton, asset kernel contracts, schema registry skeleton, ArtifactRef models, snapshot contracts, import contracts, public surface entry, and Data Forge test harnesses. No protected Lex/shared paths move. |
| 0B | Shadow legal bridge | Add read-only legal shadow adapters and tiny golden/differential fixtures for completed Lex artifacts. Do not make cloud jobs import Data Forge legal code. |
| 0C | Non-Lex domain split | Move or mirror academic and catalog toward `domains/academic` and `domains/catalog` behind compatibility shims. Ukraine work is allowed only for scaffolding/read APIs that do not affect NPA sharding or active cloud execution. |
| 0D | Cutover readiness gate | After Queue 2 `shard_4` and Queue 3 Waves 1-5 pass merge/QC, record the production revision, artifact roots, manifest schemas, output layouts, and old-vs-new golden comparison. |
| 1 | Strict shared-kernel cutover | Move shared batch infrastructure into `kernel/*`; only then remove `batch_common` and `batch_snapshot` complexity exceptions when compatibility and tests pass. |
| 2 | Academic completion | Complete academic migration into `domains/academic`; burn down academic entries in `architecture/complexity_exceptions.toml`. |
| 3 | Catalog completion | Complete catalog migration into `domains/catalog`; replace `core_sources_ingest.py` exception with per-source modules. |
| 4 | Legal cutover | Move legal batch into `domains/legal`; switch cloud/job entrypoints after replay/differential checks; burn down `lex/batch/*` exceptions. |
| 5 | Ukraine completion | Move Ukraine pipeline into `domains/ukraine`; split `ukraine_data/builders.py` exception after Lex sharding dependencies are clear. |
| 6 | Read API consolidation | Split old read facades into `read_api/*`; remove runtime imports of domain internals. |
| 7 | Shim sunset | Remove compatibility shims after `migration_shims.toml` sunset gates pass. |

## Freeze-Safe Workstreams

The hybrid plan lets work proceed without waiting for the active Lex run:

| Workstream | Status During Freeze | Notes |
| ---------- | -------------------- | ----- |
| Data Forge kernel | Allowed | Additive contracts and tests only; no production writer switch. |
| Schema registry | Allowed | New Data Forge schema definitions may be added; production Lex manifest schemas remain unchanged. |
| ArtifactRef governance | Allowed | Model and validation work may proceed; production Lex manifests may be read, not rewritten. |
| Snapshot semantics | Allowed | Implement and test new transaction/Merkle/time-travel code against isolated fixtures. |
| Quality system | Allowed | Add golden, differential, and drift harnesses using fixtures or copied completed outputs. |
| Academic domain | Allowed | Migrate behind shims if public imports and tests stay stable. |
| Catalog domain | Allowed | Migrate behind shims if public imports and tests stay stable. |
| Ukraine domain | Partially allowed | Add scaffolding/read APIs; defer changes to NPA sharding, Lex manifests, and cloud runners. |
| Legal domain | Shadow only | Add read-only adapters and tests; defer physical move and writer switch. |
| Shared batch infra | Shadow only | Implement Data Forge equivalents; defer old import rewrites and exception burn-down. |

## Acceptance Criteria

1. `import-linter` proves Data Forge domains are independent.
2. Runtime packages import only `polisyos.data_forge.read_api`.
3. Published snapshots are atomic and have Merkle roots.
4. ArtifactRefs include governance metadata and OTel trace IDs.
5. Generated schemas and frontend types are drift-checked.
6. Golden, differential, and drift tests pass for each migrated domain.
7. Each migrated domain publishes artifact schemas under `schemas/artifacts/`
   and manifest schemas under `schemas/manifests/`.
8. No migrated god-file remains in `architecture/complexity_exceptions.toml`
   without a new owner, reason, and sunset.
9. During the Lex freeze, no protected production surface changes behavior or
   import path.
10. Legal and shared-batch cutover happens only after the cutover readiness gate
    records completed Queue 2/Queue 3 processing, merge/QC evidence, and
    old-vs-new replay or differential results.
