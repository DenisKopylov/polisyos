# Plugins (`polisyos.foundry.plugins`)

`plugins` - domain-plugin layer over `agent_sim` for composable multi-domain
simulations and training flows.

## Role in System

- **Depends on:** `polisyos.foundry.agent_sim`, `polisyos.foundry.contracts`
- **Used by:** domain-specific simulation scenarios and plugin-driven orchestration
- Wraps low-level agent simulation into reusable domain plugins with composite execution.

## Key Concepts

- **DomainPlugin** - pluggable domain contract with state, mechanisms and rewards.
- **Composite execution** - `CompositeState` and `CompositeExecutor` combine several domains.
- **PolisySimulator** - high-level API for run/train/visualize workflows.
- **Discovery** - built-ins plus entry-point discovery and simple plugin scaffolding.
- **CLI** - `list`, `run`, `train`, `analyze` surfaces for local and scripted usage.

## Public API

| Type/Function | Description |
|---|---|
| `DomainPlugin` | Contract for a pluggable simulation domain. |
| `PluginRegistry` | Registry of available domain plugins. |
| `CompositeState` | Combined state across multiple domains. |
| `CompositeExecutor` | Cross-domain executor for composite runs. |
| `PolisySimulator` | High-level orchestration API. |
| `discover_plugins()` | Discovers built-in and entry-point plugins. |
| `auto_register_plugins()` | Registers built-in plugins automatically. |

→ Full reference: [docs/reference/foundry/index.md](../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 12 Python files
- Exports: 24
