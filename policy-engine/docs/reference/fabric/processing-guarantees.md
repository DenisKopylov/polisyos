# Fabric Processing Guarantees

Related plan: [FABRIC_BEST_IN_CLASS_PLAN.md](../../plans/active/FABRIC_BEST_IN_CLASS_PLAN.md).
Related ADR: [0133 Fabric Streaming and Scale Semantics](../../adr/0133-fabric-streaming-scale-semantics.md).

Phase 8 makes Fabric explicit about what each runtime path can promise. The
contract is intentionally conservative: a path only claims `exactly_once_narrow`
when input offsets, state updates, and output writes are committed atomically
and the proof reference is recorded.

## Guarantee Labels

| Label | Meaning | Typical Fabric path |
| ----- | ------- | ------------------- |
| `batch_atomic` | A batch publishes CAS/manifest outputs atomically at artifact boundaries. | Batch ingestion and world materialization |
| `at_least_once` | Events may be reprocessed and no dedupe contract is claimed. | Transitional stream adapters |
| `at_least_once_with_dedupe` | Events may be reprocessed, but dedupe keys and a retention window are visible. | `stream.jsonl` and generic streaming paths |
| `effectively_once` | Replays converge through idempotency and replay retention, without one atomic external transaction. | Future hardened stream/CDC adapters |
| `exactly_once_narrow` | Input, state, and output commits are atomically proven for a bounded adapter. | None by default |
| `replay_only` | Runtime does not claim online delivery guarantees; replay evidence is the contract. | Offline historical sources |

## Source Contract Fields

Every production `SourceContract` now carries a `processing` block with:

| Field | Purpose |
| ----- | ------- |
| `guarantee` | Honest processing guarantee enum |
| `idempotency.key_fields` | Dedupe/idempotency key policy |
| `idempotency.dedupe_window_seconds` | Visible dedupe window |
| `idempotency.replay_retention_days` | Replay retention tied to source retention |
| `out_of_order.handling` | Explicit wait, reorder, watermark, drop, or quarantine behavior |
| `cdc_schema_changes` | Additive, breaking, and metadata-only handling |
| `backpressure` | Bounded runtime response when buffers exceed limits |
| `atomicity_proof` | Required proof block for `exactly_once_narrow` |

Generated evidence:

| Artifact | Purpose |
| -------- | ------- |
| `schemas/fabric/processing_guarantee.schema.json` | Schema for processing guarantee contracts |
| `schemas/snapshots/fabric/source_contracts_v2.json` | SourceContract snapshot including processing guarantees |
| `tools/quality/validation/fabric_processing_guarantees.py` | CI/report gate for guarantee honesty |

## Runtime Semantics

Streaming runtime persists the effective processing contract into stream chunks,
windows, checkpoints, cursors, and CDC schema-change events. Out-of-order rows
are counted explicitly and late rows are dropped or quarantined according to the
contract rather than silently reshaping window results.

CDC schema changes are classified as:

| Compatibility | Rule |
| ------------- | ---- |
| `metadata_only` | Field set is unchanged |
| `compatible_additive` | Existing fields remain and new fields are added |
| `incompatible_breaking` | Previously visible fields disappear |
| `unknown` | Fallback for unsupported comparisons |

Breaking schema changes follow the declared contract action: `fail_closed`
raises before the changed rows are published, while `quarantine` writes DLQ
evidence and keeps those rows out of the happy-path stream chunk/window outputs.

Distributed execution adapters (`dask`, `ray`, `celery`) fail closed unless the
partition plan carries lineage, quality, access classification, and replay or
non-replayable evidence. This keeps scale-out execution from bypassing Fabric
trust metadata.

## Benchmarks

Fabric benchmark reports include:

| Metric | Requirement |
| ------ | ----------- |
| `latency_quantiles_ms.p50/p95/p99` | Present for ingestion, stream, materialization, and query paths |
| `peak_memory_bytes` | Captured with `tracemalloc` |
| `correctness_counters` | Rows, windows, CDC events, partitions, segments, or query results |

Validation:

```bash
uv run python tools/quality/validation/fabric_processing_guarantees.py --check
uv run pytest tests/fabric/data_plane/test_processing_guarantees.py tests/fabric/data_plane/test_benchmarks.py -q
```
