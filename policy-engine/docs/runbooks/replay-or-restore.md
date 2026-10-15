# Replay or Restore Workflow

Related reference: [Fabric Data Plane](../reference/fabric/data-plane.md). Related
how-to: [Use Control Plane](../how-to/use-control-plane.md),
[Debug Failed Run](../how-to/debug-failed-run.md).

> Use this runbook when you need to restore a record/replay session,
> checkpoint-backed workflow progress, a snapshot manifest, or a retained archive.

Owner: `@platform-owners`
Historical validation receipt (as recorded by this page): `2026-04-17` — replay/checkpoint regression and retained-artifact evidence available at that time; this is not a fresh validation.
Evidence path: `docs/reference/operations/retention-and-recovery.md`; `docs/archive/reports/platform-acceptance-manual.md`; `tests/unit/fabric/data_plane/test_record_replay.py`
Rollback path: stop destructive restore steps, preserve the current broken head or replay bundle, and switch to another trusted retained copy or documented replay source.

## Symptom

- A `replay_ref` cannot be replayed or produces a different result from the original run;
- `record_mode` completed, but fixtures or a session cannot be read from CAS;
- The checkpoint-resume path is broken, or the current head is corrupted or missing;
- Archived runs, snapshots, or audit packages cannot be restored for analysis.

## Likely Causes

- The CAS artifact is missing, corrupted, or was deleted outside the retention policy;
- A replay session was recorded, but its fixture layout does not match the expected connector
  manifest;

- The checkpoint head points to an artifact from a different workflow definition;
- A snapshot or archive exists without a manifest, report, or SHA-256 for verification;
- The restore was attempted without recording the exact run ID, replay reference, or archive hash.

## Timeline Capture Expectations

Record:

- `run_id`, `job_id`, `replay_ref`, `checkpoint_ref`, `snapshot_root`, or
  `archive_sha256`;

- The UTC time when the restore or replay attempt started and who started it;
- desired outcome: reproduce incident, recover active run, restore audit package,
  restore legacy runs;

- exact retained source: CAS, local snapshot, cold archive, CI artifact;
- whether original issue is deterministic or intermittent.

## First Triage Steps

1. If the issue is in data-plane replay, confirm that `replay_ref` or
   `record_ref` exists and belongs to the intended connector manifest.
2. If restoration goes through the control plane, inspect the request path where
   `replay_ref` is dispatched to `run_replay_mode(...)`.
3. For checkpoint recovery, inspect the current head first, then the payload,
   not the other way around.
4. For archived runs, use the archive report together with the tarball, not one file
   without the other.

### Useful commands

Finalize snapshot manifest:

```bash
cd policy-engine
uv run python -m polisyos.data_forge.kernel.snapshot.cli finalize --snapshot-root /path/to/snapshot
```

Archive legacy runs with report:

```bash
cd policy-engine
uv run python tools/ops_runners/runtime/archive_legacy_runs.py --runs-root runs --archive-dir _build/.tmp/legacy_runs_archive
```

Record/replay regression coverage:

```bash
cd policy-engine
uv run pytest tests/unit/fabric/data_plane/test_record_replay.py
uv run pytest tests/unit/scientist/orchestration/engine/test_checkpoint.py tests/unit/scientist/orchestration/engine/test_checkpoint_gc.py
```

## Rollback / Mitigation

- If the replay session is corrupted, do not delete the original fixtures before copying them to a cold
  archive;

- If the checkpoint head is corrupted, preserve the bad head separately before repair;
- If an archive mismatch is found, stop the restore and request another
  retained copy instead of silently overwriting it;

- If deterministic reproduction is not possible, record that explicitly and
  switch to timeline or lineage evidence instead of continuing to “hope”.

## Escalation Owner

- primary: `@platform-owners`;
- Supporting: `@fabric-owners` for ReplayStore and the data plane,
  `@scientist-owners` for checkpoint/resume,
  and the affected owner for the retained artifact family.

## Follow-up Checklist

- verified source of truth for the restored artifact family;
- retained copy re-hashed or otherwise validated;
- restore drill outcome documented: success, partial success, failure;
- Update the retention policy if an artifact in the required class could not be found;
- runbook or recovery tooling improved when restore required ad hoc reasoning.

## Blameless Postmortem

### What Went Well

- Which retained artifact was sufficient for recovery;
- Whether the reproduction path worked without live dependency calls;
- Which manifest or report simplified the restore.

### What Went Poorly

- Where artifact sprawl made the right copy hard to find;
- Which metadata or hashes were missing;
- Whether the restore path was understandable only to the system author.

### Action Items

| Action item                                                               | Owner              | Due date   | Status |
| ------------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Add or improve restore drill coverage for the failed artifact family      | `@platform-owners` | YYYY-MM-DD | open   |
| Close the metadata, manifest, or retention gap discovered during recovery | affected owner     | YYYY-MM-DD | open   |
| Update restore instructions so the next responder can repeat them         | `@platform-owners` | YYYY-MM-DD | open   |
