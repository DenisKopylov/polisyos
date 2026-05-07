# Fabric Connector Sources (`polisyos.fabric.connectors.sources`)

Owner: `team-fabric`
Last updated: 2026-05-05

## Purpose

`polisyos.fabric.connectors.sources` contains builtin source adapters for HTTP,
file, SQL, SDMX, CKAN, Socrata, World Bank, Eurostat, WVS, WHO, UNESCO, and
other connector families used by Fabric ingestion.

## Public API

The public extension contract is `polisyos.fabric_connectors` in
`architecture/extension_points.toml`. Builtin source modules are implementation
adapters unless exported through Fabric connector registries.

## Internal Layout

| Path | Role |
| --- | --- |
| `http_base.py`, `http_common.py` | Shared HTTP source behavior. |
| `_file_common.py`, `file_tabular.py`, `object_storage.py` | File and object-storage helpers. |
| `_contracts/` | Source-specific contract metadata. |
| `*_source.py` or provider modules | Builtin provider adapters. |

## Extension Points

External connectors must use the `polisyos.fabric_connectors` entry-point group
or the builtin component loader. Do not add ad hoc dynamic imports.

## Tests

Use `tests/unit/fabric/connectors/sources/` and connector contract tests under
`tests/unit/fabric/connectors/`.

## Operability Links

- `docs/reference/fabric/connectors.md`
- `docs/reference/fabric/source-platform.md`
- `docs/how-to/add-data-source.md`

## Known Shims/Deprecations

Provider rename or contract-version changes require an extension-point
compatibility entry and source-specific tests before removing old names.
