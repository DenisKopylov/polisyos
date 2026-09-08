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
# Observation route constraints

`MethodRouteConstraint` is a candidate search constraint. It does not certify a
manifest, observed data, or method validity. The selector rechecks every allowed
method against its actual input contract and preserves the native value-output
gate. The runtime manifest owner derives the constraint from source; direct raw
nested manifests refuse rather than becoming empty hints. An explicit requested
method cannot escape the allowed route.

Cross-component consumers import `MethodRouteConstraint` and
`method_accepts_input_contract` through the stable `polisyos.foundry` facade.
The facade lazily exposes these exact existing owner objects; it adds no wrapper,
parser, evidence authority, or change to this internal implementation's maturity.

Selector context v4 binds the complete effective constraint. Selection receipt v2
retains its existing shape and authority labels. Prior context hashes remain
historical; replay requiring current semantics recomputes the v4 context from source.
