# Ukraine method-contract consumer residual — owner decision

Stage 1 decision, before execution or source changes. Lane: `codex/owner-residuals`.
Merge base: `cc74d65813d7bb1259a0f82f6c3cc8b131661a97`.
Row: `foundry-ukraine-method-contract-consumer-residual`.

## Decision and ownership

**Route the remaining workflow-consumer obligation to team-scientist, with
team-foundry retaining the existing contract producer and method signatures.**
Do not manufacture twelve consumers in the Foundry data-plane owner, and do not
reopen the completed relocation Task 3 to add them. The existing panel route is
preserved; verifying its boundary does not close the other twelve rows.

The named original consumer is
`scientist_causal_full.run_causal_evaluation`, implemented by
`RunCausalEvaluationNode.execute`. The original allowed evidence is the completed
Task 3 in `docs/superpowers/plans/2026-08-27-data-forge-relocation-repairs.md`:
its interface requires explicit selection and its Step 4 connects only
`d2_panel_observational`. The corresponding journal's **Foundry method-contract
residual ledger**, and its explicit registration signal for this row, enumerate
one exercised workflow consumer and twelve `consumer_missing` entries.
This is the row's residual, not a missing Foundry method-input producer.

The routing request is **Ukraine selected method-input workflow consumers**:
team-scientist must appoint the actual orchestration consumers, decide the
method/contract combinations that each workflow can execute, and either wire
those routes or declare their scope with a reason. Team-foundry supplies the
existing DTO/signature contract and correctness review. The architect must
register and allocate this named work: this lane has not established an active
implementation task with that exact closure. Do not treat this prose name as a
registered task ID or a discharged deferral.

Related work is not a substitute destination. `PDD-004 — Trace Foundry Method
Selection` in `docs/backlog/production-data-e2e-diagnostic-backlog.md` is a
**diagnostic** task whose acceptance is identifying the stopping boundary.
Phase 5C in the active-draft
`docs/plans/active/POLICYOS_POLICY_EVIDENCE_CAPABILITY_GRAPH_PLAN.md` consumes
method contract targets for **selection** (survival, panel, microsim and dynamic
treatment); it does not appoint the twelve execution consumers.

## Complete starting-state denominator

The lane-wide source-derived checker is the existing
`src/polisyos/runtime/quality/production_invocation.py`; the root owns its full
receipt and independently derived Git/AST cross-check under
`docs/superpowers/journals/residuals/census/raw/`. The complete denominator at the
merge base is **2,654 tracked `src/**/*.py` files**. No absence claim is derived
from a name query or one sampled file.

An independent row trace parsed each of those 2,654 tracked Python files with
`ast.parse`, walking `FunctionDef` and `AsyncFunctionDef` as well as imports,
references and string constants. Its search vocabulary came from the actual
producer: `load_ukraine_foundry_intake`, `materialize_method_contract`,
`ukraine_foundry_method_selection`, the selected contract and bundle state keys,
and their exported state-key constants. Every discovered semantic consumer was
then read to distinguish a selected-input reader from another use of the same
DTO. The row's denominator is independently recoverable by AST-enumerating the
`contract_specs` tuple in `load_ukraine_foundry_intake`; Stage 2 will reconcile
that exact set with the real intake's CAS bundle and each persisted contract.

| All thirteen producer contract keys | Stage-1 observed residual |
| --- | --- |
| `d1_multiplex_network` | `consumer_missing` |
| `d1_trade_network` | `consumer_missing` |
| `d1_trade_network_causal` | `consumer_missing` |
| `d1_distress_network` | `consumer_missing` |
| `d1_distress_network_causal` | `consumer_missing` |
| `d1_public_service_network` | `consumer_missing` |
| `d1_public_service_network_causal` | `consumer_missing` |
| `d2_panel_observational` | existing explicit panel workflow route |
| `d2_dynamic_treatment` | `consumer_missing` for this selected-input route |
| `d2_microsim_survey` | `consumer_missing` |
| `d2_survival` | `consumer_missing` for this selected-input route |
| `d2_panel_econometric` | `consumer_missing` |
| `d3_microsim_survey` | `consumer_missing` |

These labels describe the missing route from the emitted Ukraine contract,
not absence of the DTO or of all methods for its family. Delivered adjacent
mechanisms were explicitly considered:

- `TemporalInterventionSequenceCompiler._resolve_dynamic_treatment_data` in
  `scientist/nodes/builtins/causal/run_causal_contract_execution.py` consumes
  `TemporalDTRTask` payloads and observation-plane manifests, with
  `RunCausalContractExecutionNode.execute` reading `params.temporal_dtr_tasks`.
  It does not read the selected Ukraine bundle/state slot.
- `SurvivalModelAdapter.run` and `_materialize_survival_contract` in
  `scientist/methods/advanced.py` consume `C7AdvancedInputs.survival_contract`.
  Their existence refutes a broad survival-producer absence sentence; it does
  not establish the required Ukraine selected-contract handoff.
- `verify_staged_foundry_input_state` and `_verified_method_input_refs` in
  `runtime/quality/workspace/foundry_consumption.py` replay the sole intake into
  a fresh CAS, bind the complete selected-input ancestry and recorded panel
  input, and reject mismatched lineage. This is an existing exact reader and
  verification consumer, not twelve new method executors.
- `_materialize_recorded_method_input` in `runtime/quality/data_forge_binding.py`
  and `_load_observational_data` in the causal-evaluation node materialize
  recorded panel inputs and observation envelopes, respectively. Typed
  compatibility does not by itself carry a
  Ukraine selection to those consumers.

## Production caller and persisted reader, named before code

No new source mechanism is proposed. The existing producer's direct non-test
caller is `BindFoundryInputsNode.execute` through `_load_ukraine_intake` in
`src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py`.
Its consumer only sets `observational_data_ref` and `causal_method_fqn` when the
explicit key is `d2_panel_observational`; this is the stopping boundary for the
remaining selected inputs.

`causal_full_workflow_spec` registers `scientist.node_bind_foundry_inputs@1.0.0`
and `scientist.node_run_causal_evaluation@2.0.0` with the evaluation node depending
on binding. Builtins are registered by
`scientist.nodes.components.builtin_node_components`; `scientist.api.run_experiment`
selects this workflow through `scientist.orchestration.workflows.builder`.
The non-test external caller is the Runtime NL pipeline's call to
`scientist.api.run_experiment` in
`src/polisyos/runtime/http/services/control/nl_pipeline.py`. The run-lifecycle
service also calls that API. These are existing runtime service callbacks;
they are not a standalone `main()` exposed only by a module path.

**Command registration:** this row's consumer is a registered Scientist DAG
node, not a separate `polisyos-tools` command. A second CLI executor would bypass
the workflow owner. HTTP framework dispatch and callback/receiver resolution
are the invocation checker's registered blind spot (also recorded in
`docs/superpowers/journals/producers/verification/COMPLETION.md`, **Static
invocation model limits**). The static audit alone cannot establish that a real
request selects this Ukraine configuration. This routing decision makes no new
HTTP reachability/complete-runtime claim; the successor owner must provide the
real request witness before claiming each consumer wired.

Persistence is owned by `load_ukraine_foundry_intake` in
`src/polisyos/foundry/data_plane/bindings.py`: all thirteen validated method DTOs
are CAS artifacts with `verified_stage_output` and `verified_stage_receipt`
lineage. The strict bundle maps each key to its exact contract/artifact/receipt,
with `authority_purpose=method_input_transport` and forbidden uses
`governance_admissibility` and `method_validity`. The causal evaluator reads the
selected CAS bytes and passes selected-contract, bundle and intake references
into `run_job`; the workspace verification reader independently replays and
binds that closure.

## Stage 2 targeted verification and red/removal plan

Commit this decision before running the following witness or changing any
source. No source changes are authorized by this row's routing decision. Existing
source in the closed relocation task and closed GY consumer work remains byte
unchanged. Any removal probe acts on a compiled function **in the test process**,
never on its tracked source file, and is discarded when the process exits.

Every test is an exact node. AST enumeration of the complete named test files,
including async declarations, found 5 test functions in
`test_bindings_multiscale.py`, 9 in `test_bind_foundry_inputs_node.py`, 15 in
`test_run_causal_evaluation.py`, and 31 in
`test_workspace_foundry_consumption.py`; these are definition counts, not a
claim about parametrized pytest item counts. Only these planned nodes run:

1. `tests/unit/foundry/data_plane/test_bindings_multiscale.py::test_load_ukraine_foundry_intake_content_binds_and_validates_all_method_contracts`
   — real owner ingestion, all thirteen persisted refs, exact CAS readback,
   typed limitations and source-mutation isolation.
2. `tests/unit/foundry/data_plane/test_bindings_multiscale.py::test_load_ukraine_foundry_intake_fails_closed_on_one_corrupted_method_artifact`
   — the changed stage output refuses for `content hash mismatch`.
3. `tests/unit/foundry/data_plane/test_method_contract_materialization.py::test_materialize_method_contract_rejects_mismatched_fqn`
   — valid dynamic-treatment payload with a false contract FQN refuses for
   `contract target mismatch`.
4. `tests/unit/foundry/data_plane/test_method_contract_materialization.py::test_materialize_method_contract_round_trips_deterministically`
   — the compatible payload is admitted and round-trips through the actual DTO.

**Removal probe:** AST-select only the `target.contract_fqn != spec.contract_fqn`
refusal from `materialize_method_contract`, compile that single function in its
existing module globals, install it at the public facade in the isolated test
process, and run node 3 unchanged. The expected result is `DID NOT RAISE` because
the fake identity has been admitted, not a collection/import/dependency error.
Run node 3 again in a clean process to establish restoration. The retained raw
receipt records the selected AST predicate and before/after function-source
hashes; tracked source hashes must agree before/after the entire probe.

Root writes and retains deciding command outputs and census readbacks under the
gitignored `docs/superpowers/journals/residuals/ukraine/raw/`, then cites the
compact results in the single completion journal. Gates run as the only command
in their invocation. There is no directory-wide test or new checker.

## Pattern pass and acceptance

Relevant patterns: P01/P02 (a selectable DTO is not a workflow consumer), P05/P15
(execution and transport do not confer validity authority), P27/P28 (reuse the
existing producer and preserve completed work), P29/P32/P33 (semantic corruption
and unchanged-negative removal), P35 (all thirteen contracts and complete Python
denominator), P37/P38 (a static path or familiar type name is not a measured
request/call handoff).

The condition “the selected contract reaches an execution consumer” is currently
`recomputed` for the source's panel-only branch, and `not_established` as a fresh
live-request property in this lane. The bundle's residual labels are producer
annotations and cannot prove absence by themselves. The independent state-key,
DTO and callback trace is what bounds the routing finding. A dynamic-treatment
method elsewhere in a file is the concrete divergent case for the proxy
“matching DTO implies Ukraine workflow consumption.”

Acceptance for this lane is an honest **routed-to-another-owner** verdict with
all thirteen source/CAS identities reconciled and negative/removal receipts for
the preserved intake boundary. Acceptance for the routed owner is separate:
each consumer it claims must demonstrate explicit scoped selection → existing
producer → persisted method input → actual workflow execution → exact persisted
result reader, reject fake/absent/incompatible inputs for their own reasons, and
turn an unchanged negative red when that admission/call is removed. Do not
silently promote the twelve residuals on the strength of the one panel witness.

Incidental findings go to their named destinations: the AST invocation model's
callback limitation stays with the runtime-quality invocation-checker owner;
the task-allocation gap goes to the architect and team-scientist; generic
Foundry target selection stays in capability-graph Phase 5C. None is absorbed
into this lane. No governed epoch transition is proposed for this row.
