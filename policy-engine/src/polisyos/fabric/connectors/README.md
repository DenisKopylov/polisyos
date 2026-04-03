# Connectors (`polisyos.fabric.connectors`)

`connectors` - protocol foundation and runtime registry for fetching external data
sources with reliability, validation, cache and profile-driven execution policy.

## Role in System

- **Depends on:** `polisyos.ir.connectors`, `polisyos.core.components`
- **Used by:** `fabric.ingestion`, `fabric._connector_bridge`, `fabric.retrieval`
- Owns the fetch surface for external APIs and the policy layer that chooses how sources should run.

## Key Concepts

- **Protocol core** - `SourceConnector`, `BaseConnector`, request/result and health types.
- **Registry and discovery** - runtime registration, entry-point discovery and connection pooling.
- **Reliability layers** - cache, resilience, validation and capability checks.
- **Profiles** - `SourceProfile` and `SourceExecutionPolicy` normalize source behavior.
- **Production sources** - `sources/__init__.py` exports 14 production connectors plus HTTP helpers.
- **Built-in profiles** - `profiles/builtin_profiles.py` currently contains 32 profile definitions.
- **Async-aware fetch** - recent source updates expand async fetch and SDMX-style paths.

## Public API

| Type/Function | Description |
|---|---|
| `SourceConnector` | Base fetch protocol for data sources. |
| `BaseConnector` | Common implementation base. |
| `FetchRequest` | Fetch request model. |
| `FetchResult` | Fetch result model. |
| `ConnectorRegistry` | Registry for connector implementations. |
| `discover_connectors()` | Discovers built-in and explicit connectors. |
| `SourceProfile` | Reusable source endpoint configuration. |
| `SourceExecutionPolicy` | Normalized runtime policy derived from a profile. |
| `resolve_connection_config()` | Converts a profile into connector connection config. |
| `resolve_execution_policy()` | Converts a `SourceProfile` into runtime policy. |

→ Full reference: [docs/reference/fabric/index.md](../../../../docs/reference/fabric/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 125 Python files
- Exports: 110
- Production connectors: 14
- Built-in profiles: 32
