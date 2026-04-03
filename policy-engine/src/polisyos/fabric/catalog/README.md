# Catalog (`polisyos.fabric.catalog`)

`catalog` - metric-level data contracts and curated source bindings for deterministic
resolve across the Fabric layer.

## Role in System

- **Depends on:** `polisyos.ir.connectors`
- **Used by:** `fabric.retrieval`, `fabric.connectors`, governance/security flows
- Defines the canonical contract IDs and the mapping from metrics to source bindings.

## Key Concepts

- **Data contracts** - canonical metric definitions with granularity and PII tiers.
- **Source bindings** - curated `metric -> dataset/profile` mappings.
- **Hash-locked validation** - detects drift between requested and stored contracts.
- **Fast lane resolve** - deterministic resolution before live discovery is needed.

## Public API

| Type/Function | Description |
|---|---|
| `DataContract` | Canonical metric contract. |
| `DataContractRegistry` | Registry for contract records. |
| `MetricBinding` | Hash-locked metric binding. |
| `SourceBinding` | Curated source binding. |
| `SourceBindingRegistry` | Registry for source bindings. |
| `FastLaneResolver` | Deterministic resolver for metric requests. |
| `MetricSearcher` | Search helper for contract discovery. |
| `load_contract_collection()` | Loads curated contract collections. |

→ Full reference: [docs/reference/fabric/index.md](../../../../docs/reference/fabric/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 8 Python files
- Exports: 20
