# Data Forge

`polisyos.data_forge` is the experimental build-time facade for asset-centric
data preparation and governed artifact publication.

- Last updated: 2026-10-17

## Public Surface

- `polisyos.data_forge`
- `polisyos.data_forge.read_api`
- `polisyos.data_forge.read_api.legal`
- `polisyos.data_forge.read_api.ukraine`

The public __version__ value is owned by the package root and tested against
the installed policy-engine distribution metadata; no private version module
is part of the supported import surface.

`polisyos.data_forge.read_api` exposes the pure byte-derived `GenerationBasis` producer and `build_generation_basis()` alongside the existing legal read contracts. It hashes caller-provided member bytes to produce a deterministic basis digest; it performs no file access and does not assert persisted-basis currentness. `polisyos.data_forge.read_api.legal.ThresholdAtom` remains candidate evidence.

The Ukraine read API owns the strict candidate payload types, contract-to-model registry, and role map for the three D4 source JSON contracts (governance request, identity-resolution cohort, and selected calibration splits). The same DataForge-owned model registry is used by the D4 producer and C5b source reader. `read_ukraine_json_snapshot()` still controls whether a payload is a conformant typed candidate, profileless raw snapshot candidate, or raw-only unknown profile; these types establish no producer authority, currentness, or promotion eligibility. The D3/S1 source group remains a separate complete group in Scientist orchestration.

The experimental Ukraine read API also exposes a versioned observation-period
projection. Its aligned bounds and dispositions, the D2/D3 consumer behavior,
legacy limitations, and the remaining reader-recovery boundaries are described
in the [read API README](read_api/README.md#ukraine-observation-periods).
The projection does not establish source authority or currentness.

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

Legal claim-to-source admission uses one shared relation owner.

The runtime-safe `polisyos.data_forge.read_api.legal` facade re-exports the
canonical typed source-relation refusal and disposition contracts by identity.
Lex and runtime consumers use that facade without changing the `search_candidate`
disposition or `verification_missing` status or implying that relation
verification has been established. Until an
independent verifier receipt binds the complete SPO claim to selected source
bytes, extracted claims remain `search_candidate`; an exact quotation establishes
text occurrence only. The authenticated Runtime Lex search can return those
candidate rows with the typed `legal_relation_refusal` status
`verification_missing`. Neither candidate results nor quote presence establish
entailment, legal validity, issuer authority, custody, or currentness. Existing
graphs are not rewritten in place; rebuild them through the ordinary producer
or graph builder to recompute candidate tiers.

## Exception ownership

The four generic exceptions exported from `polisyos.data_forge` are defined by the
Data Forge kernel in `kernel/__init__.py`. Legal corpus exceptions are defined with
the legal domain contracts in `domains/legal/contracts.py`; they remain distinct
from the runtime Lex exception classes. The internal `polisyos.data_forge.errors`
module has been removed after migrating repository consumers. Import the generic
names from the public Data Forge root and legal corpus names from the legal
contract owner. Previously pickled exception objects name their original module. No package-level pickle compatibility promise is declared for this unlisted module; deployments that persist such objects need an explicit migration or compatibility decision before adopting this move.

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
The Catalog read facade also exposes `read_wvs_indicator_registry(path)`: it returns
a typed mapping for present local bytes, `None` only for a missing file, and raises
`WVSIndicatorRegistryReadError` for malformed supplied content. It delegates to the same
content-snapshot parser used by batch readers; this local schema check establishes no
external authority, custody, or production currentness.

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

### Finite read API routes

`read_api/surface_routes.py` owns the finite module routes and summaries used by both the lazy
`read_api` facade and its surface helpers. The authority source-closure reader follows those same
literal routes and distinguishes module-valued lazy exports from symbol re-exports.
