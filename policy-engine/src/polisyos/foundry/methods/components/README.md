# Foundry Method Components

`polisyos.foundry.methods.components` owns chain composition, component-backed
method promotion, and input/output materialization helpers.

## Home

- `composer.py` builds method DAGs and compiled chains.
- `bridge.py` promotes component-registry entries into method registrations.
- `consensus.py` owns cross-method consistency and misspecification diagnostics.
- `io.py` materializes bound inputs and dematerializes method outputs.
- `linker.py` resolves slot bindings and compatibility diagnostics.
- `merge_engine.py` owns deterministic state-delta merge helpers.
- `semantic_validator.py` validates cross-method chain semantics.
- `slot_schema.py` owns semantic slot labels and compatibility registration.

## Registration Boundary

`bridge.py` may call `selection.registry.MethodRegistry.register_lazy()` for
component-backed methods. Catalog family registration remains in
`catalog/*/_registry_boot.py`.

## Executor payload and checkpoint history

Sequential, async and checkpoint chain execution use the same compiled slot
bindings and input materializer. Node parameters merge in this order: compiled
static parameters, node dynamic parameters, then explicit per-node overrides.
The backend validates declared parameters; the execution seed stays a dispatcher
argument rather than becoming an undeclared method parameter.

Checkpoint resume restores original per-node outputs, slot outputs, timing,
backend, seed and result metadata before materializing a remaining bound node.
Absent original records remain absent: `ChainExecutionResult.history_complete`
is false and `missing_history_node_ids` identifies the completed occurrences
whose records are unavailable. An explicit incomplete checkpoint header or an
original `history_incomplete` warning also keeps history incomplete when all
rows are present. The reproducibility contract describes the
known records and carries the same incomplete-history status. Continuation
preserves the completed frontier and any known suffix records when it saves a
new checkpoint. A remaining binding that needs an unavailable producer record
fails with `MethodContractError` before its method is dispatched.

These contracts cover the Foundry chain executor. They do not implement
Scientist workflow recovery, public generation-route consumption, automatic
retry, or exactly-once external effects. Checkpoint inputs must retain the
effective compiled plan and request identity used for the original execution.
