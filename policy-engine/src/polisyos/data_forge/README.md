# Data Forge

`polisyos.data_forge` is the experimental build-time facade for asset-centric
data preparation and governed artifact publication.

- Last updated: 2026-05-02

## Public Surface

- `polisyos.data_forge`
- `polisyos.data_forge.read_api`
- `polisyos.data_forge.read_api.legal`

The top-level package lazily exports build-time contracts for asset identity,
`ArtifactRef` governance, schema registry access, snapshot transactions,
quality checks, provenance manifests, and golden/differential migration tests.
`polisyos.data_forge.read_api` is the intended runtime import boundary and
keeps domain surfaces lazy: importing the facade does not load `domains/` or
`kernel/` internals. Laziness does not make every exported operation a read;
the facade currently also exposes producer/execution operations, including
legal `run_batch_pipeline`, academic `run_edge_synthesize`, and the existing
snapshot publisher/finalizer. Its pipeline binding lookup returns an immutable
role/surface pair from the canonical snapshot owner. The academic facade also
exposes the existing OpenAlex request/client types lazily for the explicitly
opted-in acquisition route; returned records remain candidate evidence.

The narrow boundary is not fully enforced. `architecture/packages/boundaries.toml`
allows Fabric to depend on `polisyos.data_forge.read_api` and forbids
`polisyos.data_forge.domains`, while `architecture/imports/policy.toml` allows
the broad `polisyos.data_forge` root. At documentation source snapshot `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`,
Fabric retrieval imported the private catalog helper
`_profile_input_coverage_currentness` from
`polisyos.data_forge.domains.catalog.batch.config`. The candidate source preserved
by this merge imports its Catalog operations through `read_api.catalog` instead.
That repaired import does not establish a uniformly enforced narrow matrix.


The Legal facade exposes a bounded local runtime-material owner; its exact model
revision, runtime bytes, source closure, and effective encode settings are
recomputed by the owner and do not select production sources or confer authority.
Domain implementation under `domains/` remains non-public.

## Role

Data Forge owns offline acquisition, normalization, and publishing of prepared
assets, and exposes runtime read APIs. The current `read_api` also exports
some execution-oriented producers, so it is not uniformly read-only.

Phase 1 shared-kernel cutover has moved reusable batch primitives into
`polisyos.data_forge.kernel`. The legacy `batch_common` and `batch_snapshot`
packages were removed in the Phase 8 shim sunset.

Phase 2 academic completion has moved academic batch asset contracts, schema
contracts, readiness readers, benchmark/QC readers, artifact-hash comparisons,
and read-only SKG inspection behind `polisyos.data_forge.read_api.academic`.
The legacy `polisyos.academic` package was removed in the Phase 8 shim sunset.

The academic read facade also exposes the existing `PreparedSKGRead` and
`PreparedSKGReadReceipt` contracts for engine cache-input preparation and current
read receipts. These are additive runtime-safe read exports of the canonical
SKG implementation; the facade keeps lazy loading and does not grant source
snapshot retention, filesystem authority or a new SKG algorithm. Existing
prepared-connection/key/query behavior remains owned by the academic producer.
Cross-package type-only consumers import these contracts through
`polisyos.data_forge.read_api.academic`, just as Catalog consumers import its
run-profile and source-registry contracts through `read_api.catalog`; each facade
resolves the canonical object rather than maintaining a parallel contract.

Phase 3 catalog completion has moved catalog source registry contracts,
per-source source-module planning, harvest/normalize/observation/publish asset
contracts, catalog schema contracts, readiness readers, benchmark/QC readers,
and publish-artifact differential checks behind
`polisyos.data_forge.read_api.catalog`. The legacy `polisyos.datasets` package
was removed in the Phase 8 shim sunset.

Phase 4 legal cutover moved Lex batch runtime modules into
`polisyos.data_forge.domains.legal.batch`. Phase 8 retired the old Lex batch
and corpus packages; cloud Lex runner imports now target the Data Forge legal
batch runtime directly.

Phase 8 removed the academic, catalog, Ukraine, shared-kernel, snapshot, and
old Lex offline compatibility packages. Release and rollback notes live under
`docs/migration/`.

W9.C snapshot finalization writes a durable
`data_forge_provenance_manifest.json` ledger for each official snapshot. The
ledger carries `corpus_id`, `data_hash`, `creation_time`, lineage refs, quality
gates, `builder_revision`, transform lineage, and claim requirement bindings;
runtime closeout consumes the companion binding report and fails closed when the
provenance manifest identity or transform lineage is absent.

## Where to Start

- Read the active plan:
  [`docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md`](/Users/deniskopylov/polisyos/policy-engine/docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md)

- Review the stable import contract in
  [`architecture/public_surface/contract.toml`](/Users/deniskopylov/polisyos/policy-engine/architecture/public_surface/contract.toml)

- Start runtime-safe consumption from `polisyos.data_forge.read_api`

## Source Of Truth

- Architecture contract:
  [`architecture/public_surface/contract.toml`](/Users/deniskopylov/polisyos/policy-engine/architecture/public_surface/contract.toml)

- Active implementation plan:
  [`docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md`](/Users/deniskopylov/polisyos/policy-engine/docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md)
