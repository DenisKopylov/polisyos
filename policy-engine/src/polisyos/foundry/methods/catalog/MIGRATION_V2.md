# Foundry V2 Migration Note

Foundry V2 completes the breaking cleanup of the old method surface.

## What was removed

- `bootstrap_registry` no longer exists in either `polisyos.foundry.methods` or `polisyos.foundry.methods.discovery`.
- Deep shim modules such as `polisyos.foundry.methods.<domain>.<module>` have been removed.
- The deprecated shim `polisyos.foundry.methods.catalog.causal.scm` has been removed.
- Aggregate-wrapper FQNs are no longer registered as first-class methods.

## What to use instead

- For bootstrap/runtime: `polisyos.core.components.bootstrap.build_components_index(...)` and `polisyos.foundry.methods.components.bridge.bootstrap_method_registry_from_components(...)`.
- For the public flat API:
  - `from polisyos.foundry.methods.causal import SyntheticControlMethod`
  - `from polisyos.foundry.methods.optimization import ResourceLP`
  - `from polisyos.foundry.methods.econometrics import PanelData`
- For canonical modules: `polisyos.foundry.methods.catalog.<domain>.<module>`.

## Common migrations

- `polisyos.foundry.methods.causal.protocols`
  -> `polisyos.foundry.methods.catalog.causal.protocols`
- `polisyos.foundry.methods.optimization.lp`
  -> `polisyos.foundry.methods.optimization`
- `polisyos.foundry.methods.econometrics.panel`
  -> `polisyos.foundry.methods.econometrics`
- `bootstrap_registry(...)`
  -> `build_components_index(...)` + `bootstrap_method_registry_from_components(...)`

## New invariant

The `methods/catalog/*` catalog is the single source of truth for:

- canonical FQN;
- registration;
- capability matrix;
- migration/authoring guidance.

Phase 1A removes empty package placeholders
`methods/{bayesian,causal,dependence,econometrics,microsim,ml,network,optimization,spatial}/`.
The flat domain API is now implemented by single-file facade modules
`methods/<domain>.py`; these are not packages, so deep legacy imports beneath
`methods.<domain>` remain non-importable.
