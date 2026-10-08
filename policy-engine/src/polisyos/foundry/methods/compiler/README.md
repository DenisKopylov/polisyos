# Foundry Method Compiler

`polisyos.foundry.methods.compiler` owns method compilation and hot-reload
cache invalidation. Slot-layout types and builders belong to
`polisyos.ir.kernel.slots`.

## Home

- `__init__.py` is the canonical `MethodCompiler` and `CompilationCache` API.
- `plan_optimizer.py` turns method DAGs into backend-aware execution plans.
- `layout.py` retains the legacy import address for IR-owned slot-layout types
  and builders. First-party compiler callers import the IR owner directly.
- `specialization.py` builds deterministic specialization keys for compiled variants.
- `hot_reload.py` owns source watching and generation invalidation helpers.

## Layout Compatibility

`polisyos.foundry.methods.layout` is the direct Foundry compatibility facade;
`polisyos.foundry.methods.compiler.layout` is the legacy compatibility alias.
Both import the same three types and two builders directly from
`polisyos.ir.kernel.slots`. Neither address introduces a second layout owner
or requires a caller to traverse the other module.

Both nested addresses are internal under the
[public-surface contract](../../../../../architecture/public_surface/contract.toml).
Existing compatible callers can continue to use either address. Foundry owners
maintain these bindings; a separate tracked lifecycle decision must migrate
remaining callers and references, preserve the identity tests, and record
compatibility and release notes before removing either address. This change
sets no removal date and adds no public-stable entrypoint.

## Authoring Rules

- Keep compilation deterministic and keyed by explicit specialization state.
- Do not register methods from compiler code; registration belongs in
  `selection/registry.py` and catalog family bootstrap modules.
- Optional runtime integrations must degrade gracefully when dependencies are
  unavailable.
