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

Do not add new modules under `polisyos.scientist.replay.backend`. The retired legacy module
is a Phase 4.4 compatibility shim for `polisyos.scientist.replay.backend` and
sunsets on 2026-11-30.

Tests live under `tests/unit/scientist/replay`.
