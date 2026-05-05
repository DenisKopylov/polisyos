# ADR 0133: Fabric Streaming and Scale Semantics

## Status

Accepted

## Date

2026-04-28

## Context

Fabric now spans batch ingestion, CDC/schema-change detection, replay,
streaming windows, world materialization, and optional distributed execution.
Those paths do not have one universal delivery guarantee. Claiming
exactly-once broadly would be misleading because most adapters do not commit
source offsets, Fabric state, and output artifacts in one atomic transaction.

## Decision

Fabric will expose a processing guarantee contract on every production source
and relevant runtime artifact. The allowed labels are:

- `batch_atomic`
- `at_least_once`
- `at_least_once_with_dedupe`
- `effectively_once`
- `exactly_once_narrow`
- `replay_only`

`exactly_once_narrow` is only valid when a contract carries proof references
showing atomic input-offset, state-update, and output-write commits. Generic
streaming defaults to `at_least_once_with_dedupe`.

The contract also carries:

- idempotency and dedupe key policy;
- dedupe window and replay retention;
- out-of-order handling;
- CDC schema-change compatibility handling;
- backpressure policy;
- optional atomicity proof.

Distributed execution adapters must fail closed unless the partition plan
carries lineage, quality, access classification, and replay or explicit
non-replayable evidence.

## Consequences

Source contracts become the first place operators can see dedupe windows,
replay retention, and processing guarantees. Streaming artifacts, checkpoints,
and CDC events repeat the effective processing contract so replay and audits do
not depend on out-of-band knowledge.

Scale-out is supported, but distributed adapters cannot be used as a shortcut
around Fabric trust metadata. Future adapters can upgrade to
`effectively_once` or `exactly_once_narrow` only with explicit proof artifacts.

## Validation

- `tools/quality/validation/fabric_processing_guarantees.py --check`
- `tests/unit/fabric/data_plane/test_processing_guarantees.py`
- `tests/unit/fabric/data_plane/test_benchmarks.py`
- `tests/unit/fabric/data_plane/test_orchestrator.py`

## Concrete impact

- `src/polisyos/fabric/processing_guarantees.py` defines the guarantee model.
- SourceContract v2 snapshots include processing, dedupe, replay retention,
  out-of-order, CDC, and backpressure policy.
- Streaming artifacts/checkpoints carry the effective processing contract.
- Distributed ingestion validates lineage, quality, access, and replay metadata
  before scale-out adapters execute.
- Benchmark reports expose p50/p95/p99 latency, memory, and correctness
  counters.

## Related Decisions

- [ADR-0021: Connector Schema Contracts and StoragePort Boundary](0021-connector-schema-contracts-and-storage-port.md)
- [ADR-0122: Lakehouse Snapshot Semantics](0122-lakehouse-snapshot-semantics.md)
- [ADR-0123: ArtifactRef Governance Metadata](0123-artifact-ref-governance.md)
