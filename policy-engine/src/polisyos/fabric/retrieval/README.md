# Retrieval (`polisyos.fabric.retrieval`)

`retrieval` - resolve+execute layer that turns a `DataNeed` into fetch plans,
previews, full fetches and promotion signals.

## Role in System

- **Depends on:** `polisyos.fabric.catalog`, `polisyos.fabric.connectors`
- **Used by:** data-access tooling and runtime consumers that need metric-driven fetches
- Sits between deterministic fast-lane resolution and live exploration.

## Key Concepts

- **Fast lane** - deterministic catalog/source-binding resolution.
- **Explore lane** - bounded live discovery when fast lane is insufficient.
- **Execution** - preview gates, full fetches and fallback chains.
- **Promotion** - candidate promotion queue with optional persistence.

## Public API

| Type/Function | Description |
|---|---|
| `RetrievalService` | Main resolve/discover/execute service. |
| `FetchExecutor` | Executes fetch plans with preview/full gating. |
| `ExploreLaneDiscovery` | Live discovery helper. |
| `ExploreLaneLimits` | Limits for live discovery budgets. |
| `DiscoverOutcome` | Resolve/discover result wrapper. |
| `ResolveOutcome` | Resolve result wrapper. |
| `ExecuteOutcome` | Execute result wrapper. |

→ Full reference: [docs/reference/fabric/index.md](../../../../docs/reference/fabric/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 4 Python files
- Exports: 9
