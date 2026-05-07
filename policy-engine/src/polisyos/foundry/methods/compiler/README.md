# Foundry Method Compiler

`polisyos.foundry.methods.compiler` owns method compilation, slot layout, and
hot-reload cache invalidation.

## Home

- `__init__.py` is the canonical `MethodCompiler` and `CompilationCache` API.
- `plan_optimizer.py` turns method DAGs into backend-aware execution plans.
- `layout.py` owns slot-family layout manifests used by compile-time contracts.
- `specialization.py` builds deterministic specialization keys for compiled variants.
- `hot_reload.py` owns source watching and generation invalidation helpers.

## Authoring Rules

- Keep compilation deterministic and keyed by explicit specialization state.
- Do not register methods from compiler code; registration belongs in
  `selection/registry.py` and catalog family bootstrap modules.
- Optional runtime integrations must degrade gracefully when dependencies are
  unavailable.
