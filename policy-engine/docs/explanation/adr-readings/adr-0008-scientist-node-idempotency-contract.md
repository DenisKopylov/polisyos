# English reader translation of ADR-0008: Scientist node idempotency contract

Document type: English reader translation (informational derivative)  
Source pin: `af387828fbf27dce6dec8665286180df0dd10d1c`  
Source of truth: `docs/adr/0008-scientist-node-idempotency-contract.md`

This page translates the decision text in the [source ADR](../../adr/0008-scientist-node-idempotency-contract.md), whose SHA-256 is
`953e844fc73d93e7ebf216069fa4eb5d7eb853ff202e45c156285a0a33c6359c`.
The generated ADR index reports the source status as `accepted` at the source
pin. This derivative does not ratify or revise the decision and does not
establish that the decision was implemented.

- **Date:** 2026-02-06
- **Status in source:** Accepted
- **Roadmap label:** ADR-003

## Context

The Scientist DAG includes costly and unstable operations (Foundry
compile/execute, Scholar/Fabric/Lex integration). When a run was retried or
restarted after a failure, the system repeated nodes that had already
succeeded, increasing execution cost and time.

## Decision

1. Add a run-scoped idempotency key for each DAG node:
   - `node_id` (including its version);
   - `run_id`;
   - canonical snapshot of `state_reads`;
   - `bind_params`.
2. Implement a CAS-backed `NodeResultCache`:
   - store `ok` outcomes as `scientist.node_outcome`;
   - store the index entry as `scientist.node_cache_entry`.
3. Integrate the cache with `WorkflowExecutor`:
   - cache hit: `NODE_CACHE_HIT`;
   - cache store: `NODE_CACHE_STORE`;
   - fail-open bypass: `NODE_CACHE_BYPASS`.
4. Restore the cache index when restarting the same `run_id`, by replaying
   `NODE_CACHE_STORE` from trace JSONL.
5. Do not cache outcomes with status `fail`.
6. Add CI guards:
   - `tools/quality/diagnostics/check_state_reads.py`;
   - `tools/quality/diagnostics/check_scientist_node_version_bump.py`.

## Consequences

### Advantages

1. Retrying the same run does not duplicate successful node work.
2. This provides a practical foundation for checkpoint / resume (Phase 8).
3. The `Node` protocol remains compatible.
4. Auditability improves through trace events.

### Disadvantages

1. Key generation and cache lookup / storage add overhead.
2. Updating `state_reads` and `component_id` versions requires discipline.
3. CAS storage grows with `NodeOutcome` / cache-entry artifacts.

## Alternatives

1. Cache by the hash of the entire `ExperimentState`: rejected (excessive
   invalidation).
2. Add decorators to every node: rejected (invasive and difficult to scale).
3. Cache at the ports (`FoundryPort`, `ScholarPort`): rejected (partial
   coverage).
