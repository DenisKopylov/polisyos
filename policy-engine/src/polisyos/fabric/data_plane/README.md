# Data Plane (`polisyos.fabric.data_plane`)

`polisyos.fabric.data_plane` orchestrates ingestion modes, cursor lifecycle,
record/replay, streaming and CDC, quarantine, semantic diffs, and benchmark
reports.

Last updated: 2026-10-25.

## Purpose

Use this package when you need to control how Fabric ingestion executes without
changing connector contracts: batch, replay, and streaming modes live here, as
do the operational recovery surfaces for quarantine and schema-drift evidence.

## Where to Start

- Read [cli.py](./cli.py) and [modes.py](./modes.py) for the operational entry
  surfaces used by tooling and runtime services.

- Read [orchestrator.py](./orchestrator.py) and
  [cursor_store.py](./cursor_store.py) for the main ingestion and checkpoint
  lifecycle.

- Read [quarantine.py](./quarantine.py), [streaming.py](./streaming.py), and
  [semantic_diff.py](./semantic_diff.py) for recovery, CDC, and historical
  comparison logic.

- Follow downstream links to [../docs/README.md](../docs/README.md),
  [../claims/README.md](../claims/README.md), and
  [../world/README.md](../world/README.md) when you need the full pipeline.

## Documented Entrypoints

| Entrypoint                                                                        | Description                                                                 |
| --------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `run_orchestrated_ingestion()`                                                    | Main orchestration entrypoint.                                              |
| `run_batch_incremental()`                                                         | Incremental batch mode with cursor advancement.                             |
| `run_record_mode()` / `run_replay_mode()`                                         | Deterministic capture and replay flow.                                      |
| `run_streaming_windowed()`                                                        | Windowed streaming mode over connector-backed datasets.                     |
| `process_stream_dataset()`                                                        | Streaming runtime with checkpoint, dedupe, backpressure, and CDC artifacts. |
| `QuarantineRecord`, `list_quarantine_records()`, `reprocess_quarantine_records()` | CAS-backed poison-record storage and reprocessing API.                      |
| `compare_historical_rows()` / `persist_historical_semantic_diff_report()`         | Historical schema-evolution diff helpers.                                   |
| `python -m polisyos.fabric.data_plane.cli`                                        | Package-local CLI for quarantine report and replay operations.              |

This list includes supported facade names and documented direct-module routes.
`run_batch_incremental`, `run_record_mode`, `run_replay_mode`, and
`run_streaming_windowed` remain bounded compatibility routes at
`polisyos.fabric.data_plane.modes`; they are not exports from the supported
`polisyos.fabric.data_plane` facade. Their runtime `ConnectionConfig` annotations
are covered by [Fabric runtime annotation compatibility](../../../../docs/reference/fabric/runtime-annotations.md).
This documentation does not add facade exports.

The quarantine report/replay CLI stores its JSONL index beneath the CAS root. It
requires the indexed-store protocol, including a filesystem `Path` root and the
CAS operations used by quarantine records; stores without that capability are
refused before report or replay starts.

## Depends On / Depended On By

- Depends on: `polisyos.fabric.ingestion`, `polisyos.fabric.connectors`,
  `polisyos.fabric.world`, `polisyos.core.artifacts`, and cursor/replay
  storage helpers in this package.

- Depended on by: `polisyos.runtime.http.services.control`,
  `polisyos.scientist.feedback`, `polisyos.fabric.claims.normalize`, and
  `polisyos.fabric.world.store.quarantine`.

## Stream admission and recovery

`StreamRuntimeOptions` bounds source input rows and serialized bytes before
runtime batch materialization, retained window rows and serialized bytes, and
returned chunk/window/CDC references. Recovery admits saved state before source
rewind. A prospective window transition uses the same accumulator against
isolated containers before output publication; exceeding a cap raises
`StreamCapacityError` and preserves the persisted predecessor. These are
logical retention limits; connector allocation and process RSS are outside
their scope.

Dedupe retains exact configured event/version components in connector, dataset,
and partition scope for the policy's UTC ingestion horizon (86,400 seconds by
default). Checkpoints preserve first-ingestion times. Missing components,
legacy keys without persisted UTC times, and live-key overflow raise
`StreamDedupeUnsupported`; no entity-ID or payload-hash fallback or live-key
eviction occurs. The source owner must establish the key's event/version
semantics. The current default `_message_id` field is not proof of that supplier
contract, including connectors which synthesize it from offsets.

Declared stream-schema membership is checked per row against `FieldSpec` before
quarantine or publication, independently of neighboring rows and batch size.

## Common Commands

Run from the repository root (`policy-engine/`).

- `uv run python -m polisyos.fabric.data_plane.cli --help`
  Inspect the quarantine report and replay CLI. Smoke-tested on 2026-04-17.

- `rg -n "run_batch_incremental|run_record_mode|run_replay_mode|run_streaming_windowed" src/polisyos/fabric/data_plane`
  Jump to the execution-mode entrypoints. Smoke-tested on 2026-04-17.

- `rg -n "QuarantineRecord|build_quarantine_report|reprocess_quarantine_records" src/polisyos/fabric/data_plane`
  Jump to the quarantine surface and replay hooks. Smoke-tested on 2026-04-17.

## Test / Verification Commands

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/unit/fabric/data_plane/test_modes.py tests/unit/fabric/data_plane/test_orchestrator.py -q`
  Batch and orchestrator smoke suite. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric/data_plane/test_quarantine.py tests/unit/fabric/data_plane/test_streaming_runtime.py -q`
  Quarantine and streaming smoke suite. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric/data_plane -q`
  Full data-plane suite. Conceptual in this README refresh; not run in this
  pass.

## Reference Docs

- [Fabric data-plane reference](../../../../docs/reference/fabric/data-plane.md)
- [Fabric runtime annotation compatibility](../../../../docs/reference/fabric/runtime-annotations.md)
- [Fabric lineage reference](../../../../docs/reference/fabric/lineage.md)
- [Fabric time-travel reference](../../../../docs/reference/fabric/time-travel.md)
- [Cache rebuild storm runbook](../../../../docs/runbooks/cache-rebuild-storm.md)
- [Retained artifact recovery runbook](../../../../docs/runbooks/retained-artifact-recovery.md)
- [Artifact corruption recovery runbook](../../../../docs/runbooks/artifact-corruption-recovery.md)
- [Fabric tests map](../../../../tests/unit/fabric/README.md)

## Stream result and row boundaries

The registered streaming runtime and the legacy fetch adapter report the same
read-only summary to the manifest consumer. iter_record_batches() returns
batches of object rows because non-object values are intentionally preserved
for per-row quarantine. Frame-like inputs are recognized from the exact tabular
operations each adapter consumes; input row caps use the frame's actual index.
A local IndexedArtifactStore capability is required only when a row must be
persisted to the quarantine index. Clean rows continue through stores that do
not expose that local index.


## Source progress and event identity admission

`ingestion/source_progress.py` extends the canonical `SourceContract` owner with
an independently versioned `SourceProgressContract` v1. The host supplies readers
through `IngestionDependencies.source_progress_readers` or
`ControlRegistryProviders.source_progress_readers`; HTTP payloads cannot install
an oracle. Existing SourceContract v2 records, fields, snapshots and byte identities
stay unchanged. Only active owner contracts may authorize replay progress.

The bundled reader has exactly `finite_source_fixture` scope. Batch positive
admission requires a `file:` ConnectionConfig that resolves to the **actual same
owner replay history file**. The mode performs bounded file replay itself; it
does not call a live connector and compare that response to an unrelated file.
The complete physical history is capped at 8 MiB, enumerated, append-only and
source/schema/tenant bound. A network endpoint with matching visible A/B rows
cannot borrow that authority or advance its cursor. Live-provider completeness,
currentness, rights and production key meaning remain `not_established` until an
independent live owner verifier and its actual inputs exist.

Cursor intake resolves exact selected witness, source payload and evidence views,
recomputes the actual request key and reconciles provenance. Requests receive only
a verified predecessor before fetch/persistence. Conditional save compares that
same predecessor under the existing index lock. Bare legacy cursors do not
silently upgrade. Partial/failed results retain inspectable evidence and explicit
scope but do not create completed snapshots or input bindings. The common
`ingestion_is_complete` predicate also gates durable partition success/retry,
live-acquisition consumption and replay comparison; unknown statuses fail closed.

The finite batch profile currently binds one actual history file/dataset per
connector. Its two-source positive uses distinct connector IDs. It does not
certify two datasets of one connector with distinct history files: that requires
a dataset-aware actual transport selector or a genuinely multi-dataset owner file.
This is a declared finite-fixture limitation, never production source authority.

Complete finite batch results use `SourceCollection` v1: a plain JSON namespaced
collection of **all** actual source contributions. It does not infer a cross-source
join or union incompatible records. An empty A transport delta still contributes
A's complete state to a fresh Snapshot B. The materializer reconciles the entire
original EvidenceBundle source set, every persisted contribution/provenance and
its source witness. Foundry's real snapshot loader calls `load_source_collection`
to verify the same denominator before ordinary explicit source-path bindings.
Omitting a source or row while retaining declarations is a hard refusal. Both
complete collections and partial evidence projections preserve the persisted
evidence schema through `ArtifactManifest.artifact_schema`; a missing typed
schema fails before writing a derived artifact instead of inferring one from the
payload or Pydantic's `schema` method. The existing single-source live
acquisition cached-result format is unchanged; other multi-source snapshot
callers must provide a reconciled materializer.

Streaming proof is confined to the canonical EventStream JSONL file producer.
Its actual configured file must resolve to the owner-bound transport file, and
the complete physical file's logical key universe and partition are reconciled
before effects. Source-provided redelivery annotations may differ; event/version
identity does not become payload truth. Different files with identical bytes,
wrong partitions, inactive owners, missing keys and hidden actual keys cannot
activate dedupe. Finite processing is explicitly `replay_only`. Its retained
witness, limitations and selected input edge survive chunk/window/CDC artifacts,
the aggregate manifest/evidence and snapshot.

The horizon stores UTC first-acceptance times for 86,400 seconds and refuses live
key overflow before eviction. Two OS processes with an explicit injected UTC
clock prove replay-time semantics after execution, never elapsed wall time.
Readers-first compatibility accepts an old clock-profile-free checkpoint only
for explicitly disabled dedupe, no stored keys and the default system clock;
it remains `at_least_once`. Authority-bearing legacy state still needs admitted
migration, not a presence/shape upgrade.

The separate generated shapes are `schemas/fabric/source_progress.schema.json`
and `schemas/fabric/source_collection.schema.json`; each owner projection has a
corrupt-field drift control. Focused behavioral tests are `test_source_progress.py`,
B79/B80/B83 in `test_e02_c_streaming_oracle.py`, the two-process test in
`test_source_progress_processes.py`, actual HTTP headers in
`connectors/reference/test_rest_json.py`, partition/status controls in
`test_orchestrator.py` and `test_regression.py`, and the authorized served tests in
`tests/unit/runtime/http/test_source_progress_api.py`. Source review and schema
export alone are not runtime evidence or G acceptance.
