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
