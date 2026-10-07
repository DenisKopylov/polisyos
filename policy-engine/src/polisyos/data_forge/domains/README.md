# Data Forge Domains (`polisyos.data_forge.domains`)

Owner: `team-data-forge`
Last updated: 2026-05-05

## Purpose

`polisyos.data_forge.domains` hosts builtin Data Forge domain packages for
academic, catalog, legal, and Ukraine data build pipelines.

## Public API

The stable runtime import surface is `polisyos.data_forge.read_api`. Domain
packages are build-time implementation unless registered through
`polisyos.data_forge_domains`.

## Internal Layout

| Path | Role |
| --- | --- |
| `academic/` | Academic literature and knowledge build pipelines. |
| `catalog/` | Source catalog build, curation, and registry materialization. |
| `legal/` | Legal corpus extraction and normalization. |
| `ukraine/` | Ukraine data domain build surfaces. |

The internal catalog resource owner `catalog/_resources.py` resolves the four
curated defaults authored under `data/dataset_catalog`. Source checkouts retain
those original paths; unpacked installations use exact Hatch projections in the
private catalog `_resources/` directory. Raw observations and mutable batch
outputs remain external. The nested runtime function
`polisyos.data_forge.read_api.catalog.catalog_default_resource_path` is an additive
`public_experimental` facade contract: one canonical function, four allowed names,
a durable `Path`, and `ValueError` for other names. Explicit loader paths still
override defaults; the provider remains internal and no root export is added.
See [catalog defaults](../../../../docs/reference/data-forge/catalog-default-resources.md).

## Extension Points

External domains use the `polisyos.data_forge_domains` entry-point group and
must ship a small offline materialization smoke test.

## Tests

Use `tests/unit/data_forge/` and domain-local test subtrees under that root.

## Operability Links

- `docs/reference/fabric/source-platform.md`
- `docs/reference/fabric/product-api-integration.md`
- `architecture/extension_points.toml`

## Known Shims/Deprecations

Domain package moves or source registry changes require migration notes and
fixture compatibility tests before old paths are removed.
