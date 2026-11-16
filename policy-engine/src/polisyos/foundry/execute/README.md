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
| `create_program_graph_actuation_selection()` / `resolve_program_graph_actuation()` | Persist or replay a candidate-only whole-binding selection against the exact compiled graph, plan and lowered rows. |
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
variable name. Mapped inputs support `registry_slot` and persisted `method_output` sources.
Output transfer binds the exact producer call, retained output and consumer
argument; missing or foreign output evidence refuses.

Foundry input-bindings profile 1.4 carries selected scalar method values.
Profile 1.5 carries step-qualified scalar values for an explicit semantic
horizon. Execution requires complete horizon coverage and selects the exact
effective step; historical reading joins its actual predecessor snapshot.
The consumer reopens their semantic manifest, source/derivation chain and NPY
bytes, then records the actual argument identity in the method-execution
bundle. A selected value is an argument, not an implicit new `GlobalState`
field. The NumPy encoder preserves declared float64 without enabling JAX x64.
Shapes, units, Decimal error bounds and the actual registered ABI remain part
of admission; scalar broadcast is not inferred.

### Direct entity-vector method inputs

Resolved input manifest 4.0 carries step-qualified entity-vector selections;
Foundry input-bindings 1.5 persists their selected NPY values as method
arguments. Each selection retains its original model-input obligation and step
predecessor, model interface and port, selected source view, candidate meaning
and correspondence declarations, and typed entity-axis identity. Fresh
consumers reopen and replay those inputs before reconciling the stored argument
bytes against the aligned source values.

The source meaning and correspondence basis are candidate declarations. Source
meaning and `source_scope` remain `consumer_asserted`; source currentness,
empirical correctness and independent origin remain `not_established`. The
source layout is generic parallel JSON arrays: selected pointers identify
member IDs and numeric values without decoding a domain schema or time axis.
Entity IDs retain their string or integer type on a fixed canonical axis.

The direct vector port is bounded to a one-dimensional, `GLOBAL`, pathless
`DECIMAL` slot with a generic `amount` unit. Unit conversion is not applied and
the unit does not declare USD. Correspondence scales must be 1. The persisted
NumPy dtype follows the declared encoding; the current `generalized_gini@1.0`
fixture uses `float64`. The
selected-vector record keeps `tensor_value_sha256` for the actual NPY argument
separate from the axis-alignment digest. Core's
`selected_method_input_tensor_identity` accessor returns that tensor identity,
not the alignment digest. Foundry input-bindings 1.5 step rows must use one input
kind; mixed scalar/vector selections are unsupported. Vector preparation
requires the exact original pre-state and snapshot, with no pre-seeded selected
state. Scalar broadcast is not inferred.

The numerical fixture reuses `generalized_gini@1.0` with `nu=2`; it exercises
the generic bridge rather than a method-specific path. The existing
`MetricSpec` path `generalized_gini` captures the numeric value in
`MethodOutputPayload` 1.0, while the metric remains unavailable because its
registered metric law is missing. Output capture does not establish metric
meaning or authority.

The existing Foundry execute facade and stored-input readers are the consumer
surface; retained bindings, NPY values, execution bundles and argument hashes
support artifact and argument audits. No HTTP vector route is introduced. This
profile does not enable Runtime current-use/N5 vector admission,
selected-feedback vectors, feedback model-state inputs or new institutional
authority.

## Candidate policy actuation

[`actuation.py`](actuation.py) persists and replays a candidate selection;
the compiler-owned [binding resolver](../compile/actuation.py) reconciles each
LoweredIR row with its compiled mask/apply pair. Foundry reopens the selected
graph, plan, complete lowered-row inventory and parameter payloads, then checks
the exact source edges, row-to-mask/apply identity, selectors and ordered I/O.
Rows sharing a `binding_id` remain distinct; partial intervention groups refuse.

An absent `ExecuteRequest.actuation_selection_ref` (`None`) preserves legacy
all-applies behavior. A persisted selection with
`selected_intervention_ids=()` means an explicit empty baseline. During a
selected execution, only inactive `apply_mechanism` nodes are skipped; policy
selection does not disable the world-model method nodes or other graph work.
Method execution capture is required and keeps inactive apply nodes in the
planned occurrence denominator. The request uses schema 1.1; a returned
`FoundryExecutionInputBasis` uses schema 1.4 and binds the same selected ref.
Actuation selection with feedback execution is not supported. The artifact is
for candidate simulation only and grants no policy or execution authority.

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
mode. Direct selected-scalar bindings 1.4 support candidate feedback execution:
the returned SimulationResult 1.5 and execution basis 1.3 bind the original
request, final injected state, actual final graph invocation, mapped outputs,
selected argument identities and delta. Fresh readers reconcile those facts
under the matching numerical/backend profile, including JAX x64 configuration.
A nonconverged solve does not emit a successful SimulationResult. Existing
uncomposed feedback stays explicitly `feedback_uncomposed`; unsupported selected
profiles still refuse with `foundry_input_bindings_semantic_feedback_not_established`.
A feedback trace or prepared call alone is not a composed selected-input result.

Snapshot 2.4 has a real scalar model-state graph/API route. Scalar temporal
bindings 1.5 also reach actual step execution and cold-chain reading. Direct
entity-vector inputs use the bounded candidate path above; Runtime/N5
composition, temporal scalar-feedback, selected-feedback vectors and
model-state feedback remain separate and disabled.
Old artifacts are read under their own profiles and are not rewritten using
current method definitions. Keep current grants, expiry, quota and selected-use
checks with their Runtime owners.

Runtime's paired comparator profile V4 and paired request profile V5 are
authored and their unit checks pass; the hosted pair has not yet produced a
qualified complete result/frontier. This Foundry
candidate seam does not close the paired Runtime lane; see the [E02 work plan](../../../../../E02-WORK-PLAN.md)
for its current verification boundary.

See [retained-artifact recovery](../../../../docs/runbooks/retained-artifact-recovery.md)
for missing payload/profile evidence and the [E02 work plan](../../../../../E02-WORK-PLAN.md)
for the current composition and verification boundaries.
