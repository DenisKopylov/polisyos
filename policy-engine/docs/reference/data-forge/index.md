# Data Forge reference

Owner: @data-forge-owners
Last updated: 2026-10-14
Source of truth: canonical implementation at repository pin `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; package boundaries are described in `policy-engine/src/polisyos/data_forge/README.md` and `policy-engine/src/polisyos/data_forge/domains/README.md`.

Data Forge builds and publishes domain assets and exposes selected runtime APIs
through `read_api`. At the source pin above, this index maps observed acquisition
and materialization paths, artifact and provenance contracts, canonicalization,
Fabric boundaries, runtime consumers, and documented gaps; it does not describe
a universal connector or always-running acquisition service. Start with [Current
data paths](current-data-paths.md) for those implementation routes and limits,
then use [Catalog default resources](catalog-default-resources.md) for packaged
configuration inputs.

| Reference | Covers |
| --- | --- |
| [Current data paths](current-data-paths.md) | Acquisition and materialization paths, artifact/provenance/schema/time contracts, canonicalization, Fabric boundaries, runtime consumers, and concrete gaps. |
| [Catalog default resources](catalog-default-resources.md) | Catalog-specific default resource behavior. |

## Lifecycle and import boundaries

Use [Current data paths](current-data-paths.md) to compare two related but distinct routes:
requirement-driven acquisition and its accepted N7 receipt, and domain-produced publish
manifests finalized as official snapshots for runtime consumption. An accepted N7 receipt is
not automatically converted into an official snapshot or `OfficialSnapshotAnswer`. Its local
`same_cycle_reentry` authority is not production-native epoch admission or durable production
re-entry; quality/readiness evidence also does not replace source-time or snapshot-freshness
checks. For curated packaged YAML, see [Catalog default resources](catalog-default-resources.md);
these are configuration inputs, not live observations.

Use the domain owners under `policy-engine/src/polisyos/data_forge/domains/*` as the implementation authority. The package `read_api` is the supported runtime entry surface; domain batch implementation modules are not the supported general runtime import surfaces. Selected side-effectful batch operations are exposed through `read_api`, including `run_edge_synthesize` from `policy-engine/src/polisyos/data_forge/read_api/academic.py` and `run_batch_pipeline` from `policy-engine/src/polisyos/data_forge/read_api/legal.py`. Those exports do not create a generic runtime batch contract. This reference documents observed behavior at the stated source pin, not a promise that every domain has the same producer or lifecycle.
