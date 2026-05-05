# Replay or Restore Workflow

Related reference: [Fabric Data Plane](../reference/fabric/data-plane.md). Related
how-to: [Use Control Plane](../how-to/use-control-plane.md),
[Debug Failed Run](../how-to/debug-failed-run.md).

> Используйте этот runbook, когда нужно восстановить record/replay session,
> checkpoint-backed workflow progress, snapshot manifest или retained archive.

Owner: `@platform-owners`
Last tested: `2026-04-17` against current replay/checkpoint regressions and retained-artifact references.
Evidence path: `docs/reference/operations/retention-and-recovery.md`; `docs/archive/reports/platform-acceptance-manual.md`; `tests/unit/fabric/data_plane/test_record_replay.py`
Rollback path: stop destructive restore steps, preserve the current broken head or replay bundle, and switch to another trusted retained copy or documented replay source.

## Symptom

- `replay_ref` не воспроизводится или даёт другой результат, чем исходный run;
- `record_mode` отработал, но fixtures/session не удаётся прочитать из CAS;
- checkpoint resume path broken, current head corrupted или missing;
- archived runs/snapshots/audit packages не удаётся восстановить для анализа.

## Likely Causes

- CAS artifact отсутствует, повреждён или был удалён вне retention policy;
- replay session записан, но fixture layout не совпадает с expected connector
  manifest;

- checkpoint head указывает на artifact из другой workflow definition;
- snapshot/archive существует, но нет manifest/report/sha256 для верификации;
- restore делался без фиксации exact run ID, replay ref или archive hash.

## Timeline Capture Expectations

Зафиксируйте:

- `run_id`, `job_id`, `replay_ref`, `checkpoint_ref`, `snapshot_root` или
  `archive_sha256`;

- UTC время начала restore/replay attempt и кем он запущен;
- desired outcome: reproduce incident, recover active run, restore audit package,
  restore legacy runs;

- exact retained source: CAS, local snapshot, cold archive, CI artifact;
- whether original issue is deterministic or intermittent.

## First Triage Steps

1. Если проблема в data-plane replay, подтвердите, что `replay_ref` или
   `record_ref` вообще существует и относится к нужному connector manifest.
2. Если restore идёт через control plane, проверьте request path, где
   `replay_ref` dispatch-ится в `run_replay_mode(...)`.
3. Для checkpoint recovery сначала проверьте current head, а потом payload, а
   не наоборот.
4. Для archived runs используйте archive report вместе с tarball, не один файл
   без другого.

### Useful commands

Finalize snapshot manifest:

```bash
cd policy-engine
uv run python -m polisyos.data_forge.kernel.snapshot.cli finalize --snapshot-root /path/to/snapshot
```

Archive legacy runs with report:

```bash
cd policy-engine
uv run python tools/ops/runtime/archive_legacy_runs.py --runs-root runs --archive-dir _build/.tmp/legacy_runs_archive
```

Record/replay regression coverage:

```bash
cd policy-engine
uv run pytest tests/unit/fabric/data_plane/test_record_replay.py
uv run pytest tests/unit/scientist/engine/test_checkpoint.py tests/unit/scientist/engine/test_checkpoint_gc.py
```

## Rollback / Mitigation

- если replay session corrupted, не удаляйте исходные fixtures до копии в cold
  archive;

- если checkpoint head corrupted, сохраняйте bad head отдельно перед repair;
- если archive mismatch найден, останавливайте restore и запрашивайте another
  retained copy вместо silent overwrite;

- если deterministic reproduction не получается, зафиксируйте это явно и
  переключитесь на timeline/lineage evidence, не продолжая “надеяться”.

## Escalation Owner

- primary: `@platform-owners`;
- supporting: `@fabric-owners` для ReplayStore/data plane,
  `@scientist-owners` для checkpoint/resume,
  affected owner для retained artifact family.

## Follow-up Checklist

- verified source of truth for the restored artifact family;
- retained copy re-hashed or otherwise validated;
- restore drill outcome documented: success, partial success, failure;
- retention policy updated, если artifact нужного класса не удалось найти;
- runbook or recovery tooling improved when restore required ad hoc reasoning.

## Blameless Postmortem

### What Went Well

- какой retained artifact оказался sufficient для recovery;
- сработала ли reproduction path без live dependency calls;
- какой manifest/report упростил restore.

### What Went Poorly

- где artifact sprawl мешал найти нужную копию;
- какие metadata или hashes отсутствовали;
- не был ли restore path понятен только автору системы.

### Action Items

| Action item                                                               | Owner              | Due date   | Status |
| ------------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Add or improve restore drill coverage for the failed artifact family      | `@platform-owners` | YYYY-MM-DD | open   |
| Close the metadata, manifest, or retention gap discovered during recovery | affected owner     | YYYY-MM-DD | open   |
| Update restore instructions so the next responder can repeat them         | `@platform-owners` | YYYY-MM-DD | open   |
