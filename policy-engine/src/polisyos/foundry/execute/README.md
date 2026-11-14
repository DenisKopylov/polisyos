# Foundry execution

This package executes selected compiled programs against CAS-backed inputs and
persists their numerical results. Use the public `polisyos.foundry.execute`
facade; `_internal/` contains the shared graph, patch and snapshot owners.

## Entry points and owners

| Entry point | Responsibility |
| --- | --- |
| `execute(store, request)` | Resolve an `ExecuteRequest`, run the compiled plan, apply its delta and persist a `SimulationResult` plus derived artifacts. |
| `admit_execution_source()` / `admit_execution_source_bounded()` | Reopen a saved result and reconcile its selected execution-input basis. Admission of source facts is separate from current permission or publication authority. |
| `execute_semantic_horizon_step()` | Run one explicitly selected semantic horizon step through the existing predecessor/input reconciliation. |
| `prepare_program_graph_method_calls()` | Prepare supported, held NumPy method calls without running their numerical kernels; actual execution uses the same preparation owner. |
| `prepare_program_graph_mechanism_calls()` | Prepare supported mechanism calls through their actual factory and override path. |
| `load_stored_selected_method_input_occurrences()` | Read stored method-input occurrences against their original graph and execution records. |

Start with [api.py](api.py) for request and result modes,
[model_input_requirements.py](model_input_requirements.py) for input preflight,
[the graph owner](_internal/graph/README.md) for dispatch/capture, and
[the binding owner](../data_plane/bindings.py) for source-to-argument replay.
State and delta persistence live in `_internal/snapshots/` and
`_internal/patching/`; the method ABI and backend dispatch remain under
[methods](../methods/README.md).

## Selected method inputs

A model that declares input ports uses a closed input map. Each actual ABI input
must resolve to its selected registered source; missing, extra, foreign or
state-shadowing values refuse before the method runs. Graph 0.3 maps ABI-local
names to registered source slots, so different instances need not share a
variable name. The supported mapped runtime source is `registry_slot`;
`method_output` transfer still refuses until its persisted producer/consumer
bridge is composed.

Foundry input-bindings profile 1.4 carries the selected scalar method values.
The consumer reopens their semantic manifest, source/derivation chain and NPY
bytes, then records the actual argument identity in the method-execution
bundle. A selected value is an argument, not an implicit new `GlobalState`
field. The NumPy encoder preserves declared float64 without enabling JAX x64.
Shapes, units, Decimal error bounds and the actual registered ABI remain part
of admission; scalar broadcast is not inferred.

Patch-emitting methods also require explicit state outputs and the registered
patch-target contract. An empty output list permits no state writes. The
period-flow accounting consumer uses the declared period total without an
extra time multiplier. Contracted stock updates refuse when their declared
numerical precision cannot be represented by the destination state dtype.
This is candidate arithmetic, not a claim about empirical causality or cash
financing.

## Results, readers and unfinished profiles

Inspect `ExecuteResult.ok`, notes and artifact refs together. Unsupported runtime
mechanisms can return a failed result; malformed or unresolved inputs can raise
a typed refusal before execution. Preserve that distinction in API consumers.
A diagnostic `ProgramGraphExecutionObserver` sees actual held calls but cannot
supply their results or grant authority.

Selected single-step results carry `execution_source_status="single_step_basis"`.
Historical profileless results remain an explicit `legacy_profileless` read
mode. Feedback results can remain `feedback_uncomposed`; semantic selected
bindings with feedback currently refuse with
`foundry_input_bindings_semantic_feedback_not_established`. A feedback trace or
prepared call must not be described as a composed selected-input result.

Snapshot 2.4 and bindings 1.5 have versioned contracts and bounded component
readers, but their persistent-state, temporal/vector and feedback orchestration
must be qualified through the actual caller before being claimed complete.
Old artifacts are read under their own profiles and are not rewritten using
current method definitions. Keep current grants, expiry, quota and selected-use
checks with their Runtime owners.

See [retained-artifact recovery](../../../../docs/runbooks/retained-artifact-recovery.md)
for missing payload/profile evidence and the [E02 work plan](../../../../../E02-WORK-PLAN.md)
for the current composition and verification boundaries.
