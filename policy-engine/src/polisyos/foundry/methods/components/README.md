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

The state/history codec supports JSON values and non-object NumPy arrays.
Every mapping, including mappings nested in lists, must use string keys and
must not use the reserved `__npy_ref__` array tag as a user key. Unsupported
mapping forms fail before the pointer is published, preserving the previously
selected checkpoint. No Python mapping-key coercion is treated as a faithful
roundtrip.

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

## Checkpoint execution identity

Checkpoint-bound execution resolves the actual registry classes once. A registry
replacement during a producer does not substitute another implementation into
the remaining suffix. The effective digest includes the current class and
payload/result callback source, immutable captured values, current ABI, compiled
bindings and requirements, parameters, initial state and seed. Registering an
unrelated method does not change this identity.

For artifact-backed identity, supply `artifact_store=` to the executor and a
`CheckpointArtifactContext` to `execute(artifact_context=...)`. Its fields are
`input_refs`, `config_refs`, `origin_ref`, `dependency_refs` and occurrence-keyed
`cache_refs`. Every declared `ArtifactRef` must select an explicit manifest
profile. The guarded store reads its bytes and selected manifest, and the
checkpoint reconciles content, type and the canonical profile independently
before cold execution or resume. Ambient tenant/cell, declared acquisition
origin/config/dependencies/cache references and selected backend versions and
configuration join state, completed frontier and original history in the same
immutable checkpoint generation. The owning method source/ABI and ambient scope
are checked immediately before and after each actual dispatch; a changed identity
raises `CheckpointIdentityError` before a checkpoint acknowledges that result.
Large CAS payloads are read once per cold/resume validation, not once per node.

The declaration is a lineage premise. It grants no read permission, decodes no
input, and does not assert that a declared cache artifact materializes a node's
output. Callers still supply the actual initial state; both it and the refs are
bound. The guarded store decides authorization. Strict identity supports
inspectable classes/functions with immutable scalar/tuple captures and versioned
imported modules. The shared artifact identity projection also binds runtime
class helper functions, static/class methods, property accessors and immutable
record field values. Unknown source, mutable captures, unsupported wrapped or
dynamic descriptors, and unavailable declared runtime
versions, missing selected views and invalid occurrence cache refs fail before
dispatch. Mutable external effects and hostile environment mutation are outside
this profile. Operational checkpoint frequency and persistence-error policy do
not change numerical identity.

`artifact_context=None` retains a limited request/source profile. It does not
establish artifact, tenant or acquisition authority; unavailable mutable captures
remain explicitly unbound. Checkpoints created before the source-identity profile
cannot be resumed as that new profile and must be recomputed. Both profiles refuse
an incompatible effective request rather than silently reuse the old prefix;
partial graph recomputation is not implemented here. This is Foundry checkpoint
validation, not Scientist cache restoration or public generation-route acceptance.
