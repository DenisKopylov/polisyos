# Retained Artifact Recovery

Related reference: [Retention and Recovery Policy](../reference/operations/retention-and-recovery.md).
Related runbook: [Replay or Restore Workflow](replay-or-restore.md).
Related Fabric reference: [Fabric Data Plane](../reference/fabric/data-plane.md).

> Use this runbook when you need to recover a retained operational
> artifact family: CI diagnostics, benchmark outputs, replay/state bundles,
> audit packages, local snapshots, or cold-tier archives.

Owner: `@platform-owners`
Historical validation receipt (as recorded by this page): `2026-04-17` — retention policy and restore-drill evidence available at that time; this is not a fresh validation.
Evidence path: `docs/reference/operations/retention-and-recovery.md`; `docs/archive/reports/platform-acceptance-manual.md`; `docs/archive/reports/platform-acceptance.md`
Rollback path: freeze cleanup on the affected artifact family, preserve surviving copies, and restore only from a retained bundle that still has its required sidecars and hashes.

## Symptom

- A required retained artifact cannot be found within the expected retention window;
- An archive, audit package, or snapshot was found, but its checksum or report does not match;
- A restore drill cannot reproduce an artifact in a clean workspace;
- An incident or audit is blocked because it is unclear which artifact is the source
  of truth for the selected family.

## Likely Causes

- An artifact was incorrectly classified as reproducible and deleted too early;
- A payload was retained without its manifest, report, or checksum sidecars;
- The restore path depends on knowledge held only in someone’s head instead of a documented procedure;
- A retained copy exists, but its owner, storage tier, or exact lookup key was not
  recorded in the incident timeline;

- A local snapshot was promoted to an archive without integrity and restoreability checks.
- Fabric connector fixture, quarantine record, CDC event, quality report,
  lineage graph, or schema-governance evidence was produced but not retained
  with its manifest or lookup key.

## Timeline Capture Expectations

Record these details immediately:

- The artifact family and retention class (`R0`–`R4`);
- exact lookup key: `run_id`, `job_id`, `artifact_id`, `replay_ref`,
  `snapshot_root`, `archive_sha256`, CI run URL;

- The UTC time when the restore attempt began and the owner leading it;
- expected outcome: reproduce, audit evidence, release evidence, incident
  analysis, operational resume;

- storage location: CI, CAS, local snapshot tree, compliance storage, cold
  archive;

- whether another retained copy exists.
- for Fabric: connector id, dataset id, schema id/version, profile id,
  artifact kind, quarantine reason, CDC event kind, or lineage graph id.

## First Triage Steps

1. Determine whether this is a recoverable artifact or merely reproducible output.
   If the family is formally reproducible, first check whether it is faster to
   rebuild it legitimately from the source commit and lockfiles.
2. Check the retention class and owning team in
   [Retention and Recovery Policy](../reference/operations/retention-and-recovery.md).
   The R0–R4 windows there are manual guidance, not a global TTL. For local
   `.polisyos` slots, use the per-slot contract; for remote artifacts, use the
   owning system's retention record.
3. Restore the family together with its required sidecars:
   the audit package with provenance/signature, the archive with report/hash, the snapshot with
   its manifest, and the replay bundle with connector context.
4. If the restore involves evidence or compliance, do not edit the bundle
   in place or repackage it before verification.

### Fabric retained families

| Family                       | Lookup key                                                                    | Validation                                                                                                 |
| ---------------------------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Connector recorded fixtures  | fixture path under `tests/_data/fabric/connectors/sources/` plus connector id | source-specific connector tests and record/replay tests                                                    |
| Connector contract snapshots | contract id and schema id/version                                             | `polisyos-tools connectors check-contracts --check` and `tools/ci/check_fabric_schema_registry.py --check` |
| Data-plane replay bundles    | connector id, dataset id, replay ref, cursor/checkpoint key                   | `tests/unit/fabric/data_plane/test_record_replay.py`                                                       |
| Quarantine/DLQ records       | `artifact_id`, reason, source, schema version                                 | `tests/unit/fabric/data_plane/test_quarantine.py` and `list_quarantine_records()`                          |
| CDC schema-change events     | CAS artifact kind `fabric.cdc_schema_change` and stream dataset id            | `tests/unit/fabric/data_plane/test_streaming_runtime.py`                                                   |
| Quality reports              | metric id, run id, profile, `DataFitnessReport` payload                       | `tests/unit/fabric/test_quality_indicators.py`                                                             |
| Lineage graphs               | graph id such as `graph.lineage.test` or production graph id                  | `tests/unit/fabric/test_lineage.py` and OpenLineage export validation                                      |

### Useful commands

Verify docs/site rebuild class:

```bash
cd policy-engine
uv run --extra docs python -m mkdocs build --strict
```

Inspect legacy archive payload and report:

```bash
cd policy-engine
uv run python tools/ops_runners/runtime/archive_legacy_runs.py --runs-root runs --archive-dir _build/.tmp/legacy_runs_archive
```

Rebuild snapshot manifest for validation:

```bash
cd policy-engine
uv run python -m polisyos.data_forge.kernel.snapshot.cli finalize --snapshot-root /path/to/snapshot
```

Replay/checkpoint recovery regression coverage:

```bash
cd policy-engine
uv run pytest tests/unit/fabric/data_plane/test_record_replay.py
uv run pytest tests/unit/scientist/orchestration/engine/test_checkpoint.py tests/unit/scientist/orchestration/engine/test_checkpoint_gc.py
```

Fabric schema and retained-artifact checks:

```bash
cd policy-engine
uv run polisyos-tools connectors check-contracts --check
uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json
uv run pytest tests/unit/fabric/data_plane/test_quarantine.py tests/unit/fabric/data_plane/test_streaming_runtime.py -q
uv run pytest tests/unit/fabric/test_quality_indicators.py tests/unit/fabric/test_lineage.py -q
```

## Rollback / Mitigation

- If bundle integrity is unconfirmed, stop the restore and switch to
  another retained copy;

- If an evidence family is missing, freeze destructive cleanup on the affected surface
  until the gap analysis is complete;

- If a source family was wrongly considered discardable, promote the surviving copy to a
  longer retention class until the postmortem is complete;

- If a restore drill failed in a clean workspace, treat it as an operational defect
  and open remediation before the next retention purge.

- If a Fabric artifact family was recovered from replay, preserve the link between
  the new artifact ID and the original incident/reference so its lineage does not appear to be an
  independent source.

## Escalation Owner

- primary: `@platform-owners`;
- supporting: affected artifact-family owner;
- Required coordination: the security/compliance owner for audit packages,
  provenance, signing evidence, and other evidentiary bundles.

## Follow-up Checklist

- The final source of truth for the selected artifact family was recorded;
- The checksum, report, or manifest was verified or explicitly marked missing;
- It was documented whether the operation was recovery or reproduction;
- Retention class, owner, and expiry assumptions were updated if they were wrong;
- The restore-drill backlog was updated if recovery required ad hoc steps.
- Fabric schema-governance evidence, quarantine report, quality report, or
  lineage export regenerated only from trusted source state.

## Blameless Postmortem

### What Went Well

- Which retention decision helped locate the right copy quickly;
- Which sidecar or manifest made the restore repeatable;
- Where ownership and storage paths were clear without searching through chat history.

### What Went Poorly

- Which artifact family was classified incorrectly;
- Where missing checksums or manifests undermined trust in the restore;
- Which part of the procedure depended on tacit knowledge.

### Action Items

| Action item                                                                        | Owner              | Due date   | Status |
| ---------------------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Correct retention class or restore drill coverage for the affected artifact family | affected owner     | YYYY-MM-DD | open   |
| Backfill missing manifest, checksum, or evidence sidecars where feasible           | `@platform-owners` | YYYY-MM-DD | open   |
| Update recovery docs so retained-artifact restore is executable by non-authors     | `@platform-owners` | YYYY-MM-DD | open   |
