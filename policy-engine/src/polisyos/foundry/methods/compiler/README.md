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

## Compiled chain context boundary

`MethodCompiler.compile_chain()` replays the canonical composer validation before
compilation. `CompiledChainExecutor.__call__()` replays it again and reconciles
the bound compiled method occurrences, signatures and static specialization with
that plan before executing. Unknown, erased or inconsistent validation refuses.
The executor exposes `warnings` and typed `validation_context` properties, so a
reusable handle retains the actual compiler limitations, including mode OFF.

The existing call contract still returns raw state. That raw value has no
`ChainExecutionResult` diagnostic envelope and must not be described as carrying
warnings or compiler provenance. Consumers needing a transferable contextual
result must retain the executor's diagnostic surface or use the heterogeneous
chain result API. A new raw-state diagnostic envelope and full DAG slot-routing
adaptation for compiled kernels are `surface_out_of_scope` for this compatible
companion; no such capability or custody claim is made. Compiler validation
proves current mechanical checks, not scientific or institutional authority.
