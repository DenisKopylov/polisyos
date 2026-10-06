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

## Checkpoint publication

The checkpoint filename now selects one immutable UUID generation through an
atomic JSON pointer. The pointer binds the complete snapshot bytes; that
snapshot keeps state, completed frontier and original per-node history in the
same generation. NumPy state and history sidecars carry content, shape and
dtype bindings. Readers resolve the selected generation once. State and
original history share one structural encoder: the complete logical
root and path distinguish their arrays even when user state contains
history-like keys. Relative checkpoint paths are normalized to their owning
directory before publication. Concurrent writers hold the same per-checkpoint
filesystem lock through publication and rollback, and remove only their own
unpublished generation after a failed save.

Snapshot files, sidecars and their directories are fsynced before the pointer
is replaced. If the final pointer-directory fsync fails after replacement,
`CheckpointPublicationUncertainError` reports uncertainty and preserves the
visible generation. Callers must inspect or retry that outcome; it is not a
durable-success acknowledgement. A process killed before pointer replacement
leaves the previous selection readable; a process killed after replacement
leaves a complete new selection, with durability still unacknowledged.

Existing direct-JSON checkpoint files remain readable under their original
content-binding and execution-identity checks. Consumers must use
`ChainCheckpoint.load()` rather than read state fields from the pointer file.
Generation reclamation is not implemented: successful and interrupted orphan
generations remain on disk. This protocol assumes a local filesystem with
flock, atomic replacement and directory fsync. It does not establish power-loss
behavior, protection from hostile filesystem mutation, or Scientist workflow
recovery.
