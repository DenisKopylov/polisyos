---
title: Data Forge Consolidation Plan
status: active
owner: team-data-forge
created: 2026-04-18
last_verified: 2026-04-18
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

| Module | Purpose |
|--------|---------|
| `kernel/pipeline/assets.py` | `AssetKey`, `AssetSpec`, `AssetGroup`, `PartitionSpec` |
| `kernel/pipeline/materialize.py` | `@asset`, materialization planner/executor |
| `kernel/pipeline/partitions.py` | time/hash/composite partitions |
| `kernel/pipeline/config/` | pydantic-settings profile composition |
| `kernel/pipeline/schemas/` | versioned schema registry and migration rules |

## Lakehouse Snapshot Semantics

Decision source: ADR-0122.

Publishing is atomic and addressable:

| Module | Purpose |
|--------|---------|
| `kernel/snapshot/transactions.py` | all-or-nothing asset group publish |
| `kernel/snapshot/commit.py` | write-then-rename atomic commit |
| `kernel/snapshot/merkle.py` | Merkle root for complete snapshot identity |
| `kernel/snapshot/time_travel.py` | resolve artifact at `(snapshot_id, logical_ts)` |
| `kernel/snapshot/retention.py` | HOT/WARM/COLD/EPHEMERAL retention and GC |

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

| Field | Meaning |
|-------|---------|
| `uri` | logical `polisyos://...` identifier |
| `sha256` | content hash |
| `producer` | module/function that materialized the artifact |
| `producer_version` | code/model/lockfile version tuple |
| `trace_id`, `span_id` | OTel trace linkage |
| `config_hash` | materialization config hash |
| `owner` | accountable team |
| `license` | artifact license |
| `pii_level` | `none`, `low`, `medium`, `high` |
| `retention_class` | `hot`, `warm`, `cold`, `ephemeral` |
| `freshness_sla_seconds` | freshness contract |
| `schema_id`, `schema_version` | schema registry identity |

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

| Module | Purpose |
|--------|---------|
| `expectations.py` | declarative expectations over any artifact |
| `differential.py` | old-vs-new pipeline diff tests with tolerances |
| `drift.py` | distribution drift between snapshots |
| `consumer_contracts.py` | Fabric/runtime minimum requirements |

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

| Phase | Deliverables |
|-------|--------------|
| 0 | Create `data_forge` skeleton, asset kernel, schema registry skeleton, import contracts, public surface entry |
| 1 | Move shared batch infrastructure into `kernel/*`; remove `batch_common` and `batch_snapshot` entries from `architecture/complexity_exceptions.toml` when split |
| 2 | Move academic domain into `domains/academic`; burn down academic entries in `architecture/complexity_exceptions.toml` |
| 3 | Move catalog domain into `domains/catalog`; replace `core_sources_ingest.py` exception with per-source modules |
| 4 | Move legal batch into `domains/legal`; burn down `lex/batch/*` exceptions |
| 5 | Move Ukraine pipeline into `domains/ukraine`; split `ukraine_data/builders.py` exception |
| 6 | Split old read facades into `read_api/*`; remove runtime imports of domain internals |
| 7 | Remove compatibility shims after `migration_shims.toml` sunset gates pass |

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
