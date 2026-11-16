# Foundry data plane

This package prepares and replays selected inputs for Foundry execution. Use
`polisyos.foundry.data_plane` for the exported binding helpers and the public
Foundry execute facade for dispatch; the graph executor owns capture and
consumption records.

| Owner | Responsibility |
| --- | --- |
| [bindings.py](bindings.py) | Resolve selected snapshots/manifests, materialize bindings and reopen their source facts. Fact replay alone does not admit a new use. |
| [selected_tensors.py](selected_tensors.py) | Encode bounded Decimal inputs with explicit dtype, shape and error limits; hash the actual tensor bytes. |
| [method_output_values.py](method_output_values.py) | Fresh-read a selected typed producer output and reconcile its actual consumer argument. |
| [entity_axis.py](entity_axis.py) | Reconcile candidate-scoped typed entity IDs and explicit vector alignment. |
| [selected_method_entity_vector.py](selected_method_entity_vector.py) | Reopen selected source IDs and values, reconstruct their fixed typed axis, and reconcile the aligned bytes with the persisted method-input NPY argument. |

## Direct entity-vector method inputs

The Core manifest 4.0 / Foundry input-bindings 1.5 path reopens the selected
source and typed axis, aligns candidate values, and reconciles the persisted
actual NPY tensor identity. See the [execute README](../execute/README.md#direct-entity-vector-method-inputs)
for candidate status, input bounds and authority limits.

## Method-output transfer

The composed method-output route remains bounded to PURE-to-PURE NumPy scalar
calls in the same graph invocation and step. The selected graph identifies the
earlier producer node and exact returned slot. Typed `MethodOutputPayload` 1.1
preserves its scalar bytes, dtype and producer ABI; `MethodExecutionBundle` 1.3 joins
that output occurrence to the actual consumer input hash. The reader reconciles
those refs and bytes rather than treating a matching value or execution order as
proof. Older payloads remain readable under their own profiles.

No implicit unit, dtype, shape or broadcast conversion is supplied. Cross-step,
array, patch-emitting, feedback and overlapping metric-transfer profiles remain
outside this bounded route; N5 retention and authority need their own admission.
The generic state-patch owner remains separate. Helpers do not schedule a method
or issue publication permission. See the [graph owner](../execute/_internal/graph/README.md)
for capture and [execution API](../execute/api.py) for result modes.

## Registered SQL semantic input composition

Foundry input-bindings payload schema 1.3 composes the selected registered SQL
admission with the existing resolved semantic-input manifest. The bounded route
requires the exact same selected snapshot, a one-step invocation, a schema 1.0
manifest with measurements and no derivations, and only `initial_state` ports
carried by `state_path`. Foundry reopens the selected SQL occurrence and source
edges while reconciling the bound state; it does not infer a method-input or
temporal transport. SQL method-inputs and step-qualified inputs remain on
their separate Foundry input-binding schema versions 1.4 and 1.5, respectively.

This composition preserves candidate-only meaning: it does not establish SQL
currentness, external source rights or publication authority. Existing
FoundryInputBindings payload versions remain readable under their own schemas;
the combined SQL-and-manifest path emits version 1.3 without rewriting prior
artifacts.

The bounded execution-source reader supports this same initial-state SQL 1.3
replay through its existing aggregate transfer budget. Its read-only view
charges selected manifests, JSON payloads and parent-bound state blobs through
Core receipts, including repeated transfers. The supported view caps every
semantic/registry JSON artifact at 4 MiB, depth 32 and 100,000 elements, with
512 KiB manifests, and state NPZ members at 16 MiB; the aggregate limit also
applies. Larger profiles refuse instead of reading through an unbounded
fallback. Legacy three-method bounded readers retain their structural API;
this new SQL replay requires the optional semantic-reader capability. These
checks do not replace C105's current-use permission check or grant authority.
