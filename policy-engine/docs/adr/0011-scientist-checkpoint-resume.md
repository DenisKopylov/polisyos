# ADR-0011: Scientist DAG Checkpoint/Resume

## Status

Accepted

## Context

Scientist DAG runs can be long-running. Before this change, a process crash could lose progress.
Idempotency (ADR-0008) exists but cache recovery depended on trace continuity.

## Decision

Implement checkpoint/resume at the engine layer with CAS-backed immutable snapshots and an atomic mutable head pointer per run.

### Key choices

1. Store full `ExperimentState` snapshots after successful node completion.
2. Persist checkpoint artifacts in CAS (`kind=scientist.checkpoint`).
3. Track latest checkpoint through `runs/<run_id>/checkpoint_head.json` with atomic replace and directory fsync.
4. Add workflow compatibility guard using `workflow_fingerprint` (sha256 of canonical `WorkflowSpec`).
5. Add resume cache warm-up from checkpoint metadata (`cache_entry_refs`) to avoid redundant node execution when trace is truncated.
6. Add local concurrency guard via `runs/<run_id>/run.lock` (`fcntl.flock`).

## Consequences

### Positive

- Crash recovery from latest checkpoint.
- Lower redundant compute during resume (cache warm-up from checkpoint metadata).
- Deterministic workflow-compatibility validation.
- Concurrent run/resume prevention on the same host filesystem.

### Negative

- Additional write overhead per successful node.
- New mutable files in run directory (`checkpoint_head.json`, `run.lock`).

## Related

- ADR-0008: Scientist node idempotency contract.
- ADR-0009: Decision packet replay protocol.
