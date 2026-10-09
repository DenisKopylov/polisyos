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

| Type/Function                | Description                                 |
| ---------------------------- | ------------------------------------------- |
| `DataContract`               | Canonical metric contract.                  |
| `DataContractRegistry`       | Registry for contract records.              |
| `MetricBinding`              | Hash-locked metric binding.                 |
| `SourceBinding`              | Curated source binding.                     |
| `SourceBindingRegistry`      | Registry for source bindings.               |
| `FastLaneResolver`           | Deterministic resolver for metric requests. |
| `MetricSearcher`             | Search helper for contract discovery.       |
| `load_contract_collection()` | Loads curated contract collections.         |
| `build_source_contract_requirement_bindings()` | Classifies SourceContract candidates against compiled `DataRequirementSpec` rows. |

→ Full reference: [docs/reference/fabric/index.md](../../../../docs/reference/fabric/index.md)

## Current State

- Last updated: 2026-05-23
- Files: 9 Python files
- Exports: 21

## Runtime Catalog Selection

Catalog-backed `DataResolveRequest` calls require an explicit
`catalog_run_profile`, or a profile selected by the runtime container's
configuration. A request may repeat the configured profile; a conflicting
request is rejected with HTTP 422. If neither is supplied, an executable
catalog source is refused with `catalog_run_profile_unresolved`; the runtime
does not assume `prod_full`. The same selected value is carried through the
natural-language retrieval and N6 acquisition paths. Selecting a run profile
controls source eligibility only; it does not establish production
currentness.
