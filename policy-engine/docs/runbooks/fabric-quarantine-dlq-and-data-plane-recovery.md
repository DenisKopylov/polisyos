# Fabric Quarantine/DLQ And Data-Plane Recovery

Related reference: [Fabric Data Plane](../reference/fabric/data-plane.md),
[Fabric Lineage](../reference/fabric/lineage.md), and
[Retention and Recovery Policy](../reference/operations/retention-and-recovery.md).
Related runbooks: [Cache Rebuild Storm](cache-rebuild-storm.md),
[Retained Artifact Recovery](retained-artifact-recovery.md), and
[Replay or Restore Workflow](replay-or-restore.md).

> Use this runbook when Fabric ingestion creates unexpected quarantine/DLQ
> records, streaming/checkpoint recovery stalls, or a connector data-plane
> recovery path risks losing source evidence.

Owner: `@fabric-owners`
Last tested: `2026-04-17` against current quarantine, streaming, record/replay, and lineage regression coverage.
Evidence path: `docs/reference/fabric/data-plane.md`; `tests/fabric/data_plane/test_quarantine.py`; `tests/fabric/data_plane/test_streaming_runtime.py`; `tests/fabric/data_plane/test_record_replay.py`
Rollback path: stop destructive reprocessing, preserve quarantine/checkpoint artifacts, roll back the connector/profile/schema change if it caused the incident, and replay only from retained CAS-backed inputs.

Freshness: 2026-04-17.

## Symptom

- quarantine or DLQ counts spike for one connector, source profile, stream, or
  dataset family;

- valid-looking rows are quarantined after a schema, transform, or unit change;
- poison stream messages repeat across retries and block downstream
  materialization;

- cursor or checkpoint recovery replays the same window without making forward
  progress;

- downstream world tables, quality reports, or lineage graphs disagree with the
  expected reprocess result.

## Likely Causes

- connector contract or source profile changed without compatible schema
  migration evidence;

- transform logic started producing non-finite, malformed, or untyped values;
- stream dedupe keys, offsets, or checkpoint state drifted from the retained
  replay bundle;

- a quarantine reprocessor was not registered for the affected source prefix;
- CAS payload, quarantine index, lineage edge, or generated schema sidecar was
  restored without the matching manifest or evidence path.

## Timeline Capture Expectations

Record these details before reprocessing or cleanup:

- connector id, dataset id, profile id, schema id/version, and source prefix;
- quarantine `artifact_id` values and aggregate report counts;
- stream session id, checkpoint key, offsets, dedupe keys, and CDC event kind;
- first bad deploy, profile change, schema snapshot, or source upstream change;
- affected downstream artifacts: world table, materialization snapshot, lineage
  graph, quality report, Scientist input snapshot, or runtime read path.

## First Triage Steps

1. Freeze destructive cleanup for the affected connector or stream family.
2. Capture the current quarantine report and copy the incident artifact ids into
   the timeline.
3. Confirm whether the issue is isolated to fetch, transform, schema
   compatibility, streaming, or materialization.
4. Run the narrow regression checks before reprocessing:

```bash
cd policy-engine
uv run pytest tests/fabric/data_plane/test_quarantine.py -q
uv run pytest tests/fabric/data_plane/test_streaming_runtime.py -q
uv run pytest tests/fabric/data_plane/test_record_replay.py -q
uv run pytest tests/fabric/test_lineage.py tests/fabric/test_quality_indicators.py -q
```

1. If the incident followed a schema or contract change, run the schema
   governance checks before accepting new snapshots:

```bash
cd policy-engine
uv run python tools/connectors/check_contracts.py --check
uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out .tmp/fabric-schema-governance.json
```

## Quarantine / DLQ Triage

| Check                | What to verify                                                                                      |
| -------------------- | --------------------------------------------------------------------------------------------------- |
| Record list          | `list_quarantine_records()` returns stable records for the affected source prefix.                  |
| Report shape         | `build_quarantine_report()` groups by reason, source, and downstream impact.                        |
| Payload integrity    | `load_quarantine_payload()` can read each raw payload from CAS without digest mismatch.             |
| Reprocessor coverage | `register_quarantine_reprocessor()` exists for the affected source prefix before replay.            |
| Replay output        | `reprocess_quarantine_records()` emits new result artifacts and does not mutate historical records. |

If payload integrity fails, stop here and switch to
[Artifact Corruption Recovery](artifact-corruption-recovery.md). If retained
sidecars are missing, switch to
[Retained Artifact Recovery](retained-artifact-recovery.md).

## Data-Plane Recovery Triage

| Check                      | What to verify                                                                        |
| -------------------------- | ------------------------------------------------------------------------------------- |
| Cursor/checkpoint state    | checkpoint keys match the stream session and retained replay bundle.                  |
| Dedupe behavior            | repeated windows do not create duplicate world facts or duplicate quarantine records. |
| CDC compatibility          | schema-change events have corresponding compatibility evidence.                       |
| Lineage continuity         | new artifacts preserve input refs from original quarantine/checkpoint state.          |
| Downstream materialization | world snapshots and quality reports rebuild from trusted source state only.           |

For stuck streaming recovery, prefer pausing the source profile, preserving the
checkpoint, and replaying a bounded window over deleting cursor state.

## Rollback / Mitigation

- roll back the connector/profile/schema change that caused valid records to
  enter quarantine;

- pause the affected stream or reduce source concurrency if poison messages are
  causing repeated checkpoint recovery;

- keep historical quarantine records immutable and write corrective reprocess
  artifacts instead of editing old payloads;

- restore from retained CAS-backed inputs when the quarantine index or
  checkpoint state is corrupted;

- block downstream promotion until lineage, quality, and schema compatibility
  evidence agree with the recovered state.

## Escalation Owner

- primary: `@fabric-owners`;
- supporting: `@platform-owners` for CAS/retention/signing failures;
- supporting: `@runtime-owners` when runtime read paths or control-plane jobs
  are degraded;

- supporting: `@scientist-owners` when a Scientist workflow consumed affected
  snapshots.

## Follow-up Checklist

- incident timeline includes connector/profile/schema ids and affected artifact
  refs;

- quarantine report, schema-governance evidence, and lineage export are attached
  to the incident record;

- a regression test or fixture covers the failing fetch/transform/stream window;
- recovery produced new artifacts linked to original inputs rather than
  rewriting historical evidence;

- docs or connector authoring guidance were updated if the incident exposed a
  missing procedure.

## Blameless Postmortem

### What Went Well

- which evidence artifact made the bad source, transform, or checkpoint obvious;
- whether quarantine preserved enough payload context for safe replay;
- whether lineage made downstream impact analysis fast.

### What Went Poorly

- whether owners had to infer connector ids, schema ids, or source prefixes from
  raw logs;

- whether checkpoint recovery required ad hoc state edits;
- whether the reprocessor or schema gate was missing for the affected family.

### Action Items

| Action item                                                              | Owner            | Due date   | Status |
| ------------------------------------------------------------------------ | ---------------- | ---------- | ------ |
| Add or repair the missing quarantine/stream regression fixture           | `@fabric-owners` | YYYY-MM-DD | open   |
| Backfill schema-governance or lineage evidence for the affected recovery | `@fabric-owners` | YYYY-MM-DD | open   |
| Improve operator visibility for the affected source prefix or checkpoint | `@fabric-owners` | YYYY-MM-DD | open   |
