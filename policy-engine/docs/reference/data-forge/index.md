# Data Forge reference

Owner: @data-forge-owners
Last updated: 2026-10-14
Source of truth: canonical implementation at repository pin `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; package boundaries are described in `policy-engine/src/polisyos/data_forge/README.md` and `policy-engine/src/polisyos/data_forge/domains/README.md`.

Data Forge builds and publishes domain knowledge artifacts, then exposes selected runtime APIs. It is not a universal source connector or an always-running acquisition service. The current implementation, its evidence, and the limits of its capability claims are mapped in [Current data paths](current-data-paths.md).

| Reference | Covers |
| --- | --- |
| [Current data paths](current-data-paths.md) | Acquisition and materialization paths, artifact/provenance/schema/time contracts, canonicalization, Fabric boundaries, runtime consumers, and concrete gaps. |
| [Catalog default resources](catalog-default-resources.md) | Catalog-specific default resource behavior. |

Use the domain owners under `policy-engine/src/polisyos/data_forge/domains/*` as the implementation authority. The package `read_api` is the supported runtime entry surface. Most domain batch pipelines remain build-time APIs, while selected runtime surfaces expose callable batch operations such as `run_edge_synthesize` from `policy-engine/src/polisyos/data_forge/read_api/academic.py` and `run_batch_pipeline` from `policy-engine/src/polisyos/data_forge/read_api/legal.py`. Those exports do not create a generic runtime batch contract. This reference documents observed behavior at the stated source pin, not a promise that every domain has the same producer or lifecycle.
