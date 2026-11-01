# Scientist Replay

Replay owns deterministic re-execution, dead-letter replay, semantic diffs, and
replay verification reports for Scientist runs.

Use this hub for:

- deterministic replay planning, completeness, and verification contracts in
  `deterministic.py`;
- replay backend execution and dead-letter inspection;
- semantic diff models and comparators;
- replay verification reports and registries.

`polisyos.runtime.replay` is a compatibility facade over `deterministic.py`.
New first-party replay consumers use the Scientist-owned module directly.

The Runtime root retains its ten lazy exports; `runtime.replay` retains the twenty
identity-preserving compatibility aliases. No retirement of those exports is implied
by a successful source census. External callers remain unknown. Runtime's historical
`RunManifest` 1.0 reader is a different owner from Core's run manifest and
`runtime.quality.replay`; the source-qualified protocol-4 fixture under
`tests/fixtures/package_path_compatibility/` preserves one finite historical model
sample, not a production run corpus or a converter between those owners.

`replay --check-only` examines the real persisted dependency graph without executing
the backend. An ordinary replay executes its selected backend and persists its result.
Execution success is separate from verification: `VerificationMode.SKIP` returns
`passed=False` and `skipped=True`, and does not make a successful execution fail.
JSON and text CLI output expose the skip. Bit-exact mode compares result references;
it is not scientific validation. CI-bounded mode currently compares persisted metrics
against a finite, nonnegative relative tolerance. Its `confidence_level` must be a
finite value strictly between 0 and 1 and is not a calibrated statistical interval;
its result explicitly reports
`scientific_qualification=UNQUALIFIED` without a separate domain oracle. Numeric
agreement alone does not establish that scientific oracle. Scientist replay also
preserves the executor's actual terminal status and any produced refs: a failed or
unknown report, or an OK report with no output, is not successful replay under SKIP.

In JSON mode the CLI keeps library diagnostics on stderr and emits one JSON value
on stdout. Human-readable output retains the ordinary diagnostic behavior.

Replay first freezes one verified selected packet manifest/payload view. Its consumed
roles retain the exact manifest `InputRef` profiles through completeness, seed and
environment reads, Foundry/Scientist input construction, and original-result metric
comparison. Conflicting IDs, multiple profiles for one role, and partly selected
bindings refuse execution. ID-only legacy packets retain their bounded compatibility
reader with an explicit `legacy_payload_reference_profiles_not_established` warning;
check-only exposes the same limitation in `reason_codes`. This does not establish
the original producer's metadata view. Child traversals share a bounded remaining
node capacity and root-relative depth. Because overlapping descendants are not
credited before their traversal, a tight capacity can conservatively refuse a
shared DAG whose final union would fit; the refusal does not claim that union was
measured and exceeded the cap. Output ID strings
remain compatible, while `replay_artifact_refs` exposes the actual selected result
views for a fresh CAS reader. A selected original SimulationResult must pass the
existing Foundry execution-source admission, and its plan, bindings, registry and
effective seed must agree with the packet. Replay reuses that admitted request;
it does not reconstruct a weaker request after a source refusal. Without an admitted
original source, the bounded candidate route remains available and reports
`original_execution_source_not_established:legacy_candidate`. Even a packet with
exact input profiles can have this separate limitation. Its output ref remains
profileless and reports `replay_output_profile_not_established:simulation_result`,
rather than claiming stronger output custody from selected inputs alone.

To resume an explicitly chosen original workflow, supply `resume --workflow-ref
sha256:<workflow-id> --workflow-profile sha256:<manifest-profile>`. The pair identifies
the exact selected CAS view. The checkpoint owner verifies and reads its typed
`WorkflowSpec`, then checks the original functional fingerprint before dispatching the
residual workflow. A content ID alone, an unavailable profile, a changed functional
workflow, or simultaneous explicit workflow object/reference is refused. Omitting
the pair preserves the existing default-workflow compatibility route. A dry run only
inspects checkpoint metadata; it does not qualify workflow or execution admission.

All execution routes that call node retry share retained-source workflow intake:
`WorkflowExecutor`, `AsyncWorkflowExecutor`, the serialized `run_node_in_worker`
entry used by local/distributed workers, and public `replay_dead_letter`. An explicit
`ExperimentState.inputs["skg_source_snapshot"]` is resolved from the full profile-bound
CAS descriptor and chunk closure, materialized under the run, and recorded as a run
input before retry. Invalid explicit refs fail closed; they do not fall back to the
current live SKG path. Workers carry only the typed state ref across the existing wire
and reopen local CAS bytes through the store's verified member-read interface; an
attempt-scoped facade may delegate those reads but retains its write revocation. A live
prepared-reader handle remains local and is not transferred to a timeout worker. This
establishes local source replay only, not issuer authenticity, production currentness, or
scientific output dependence. Dead-letter schema `2.0` stores only the selected-profile ref to the
engine-owned `RunInvocationStarted` basis and its lineage edge; it never copies invocation params
into the DLQ payload. Replay re-reads the exact run-owner chain, verifies the basis and selected
`WorkflowSpec` under current CAS access, checks its alias and component identity, then binds the
persisted `NodeInvocation.params` to the replay node. It does not use current `ExperimentState.params`
as a substitute. Older schema `1.0` or unbound records remain listable but replay fails closed with
`dead_letter_dispatch_basis_not_established`; new direct retry callers without an owner-issued attempt
also persist an explicit `not_established` source status.

Tests live under `tests/unit/scientist/replay`.
