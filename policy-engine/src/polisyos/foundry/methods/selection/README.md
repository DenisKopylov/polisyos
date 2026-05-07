# Foundry Method Selection

`polisyos.foundry.methods.selection` owns method lookup, version resolution,
selection advice, registry persistence, and execution-history feedback.

## Home

- `registry.py` is the canonical method registration path.
- `resolution.py` owns version policies and semver helpers.
- `advisor.py` owns planner-facing ranking and recommendation APIs.
- `history.py` owns execution-history telemetry used by the advisor.
- `cache.py` owns registry persistence cache helpers.
- `cost_model.py` owns selection cost estimates and budgets.

## Registration Path

Builtin catalog families register through `catalog/*/_registry_boot.py` and
call `selection.registry.MethodRegistry.register()` or `register_lazy()`.
Component-backed methods enter through `components/bridge.py`, which also calls
`selection.registry.MethodRegistry.register_lazy()`.

Phase 5 extension work should attach external entry-point discovery to this
same registry path without moving registry ownership out of `selection/`.

