# Adapters (`polisyos.scientist.adapters`)

`adapters` implements the bridge between the Scientist workflow runtime and
external execution/data systems without routing direct Foundry/Fabric calls
through nodes.

## Role in the system

- **Depends on:** `core.contracts`, `core.security`, `foundry`, `fabric`
- **Used by:** `scientist.workflows`, built-in data/compile/simulate nodes
- The package isolates compile/execute and snapshot/materialization protocols behind typed ports.

## Key concepts

- **DefaultFoundryPort** — compile/execute bridge to the Foundry API.
- **DefaultFabricPort** — converts `DataViewRequest` into the snapshot/artifact surface.
- **Derived security artifacts** — TEE attestations and SBOMs can be published through the adapter path.
- **Workflow injection** — adapters are injected into `ExecutionContext` rather than hard-coded in nodes.

## Public API

- `DefaultFoundryPort`
- `DefaultFabricPort`

Details: [Reference →](../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-04-03
- Python modules: 3
- Exports: 2
- The README follows the shared template; the API surface remains compact and stable.
