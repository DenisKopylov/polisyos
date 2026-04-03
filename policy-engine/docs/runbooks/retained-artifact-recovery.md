# Retained Artifact Recovery

Related reference: [Retention and Recovery Policy](../reference/operations/retention-and-recovery.md).
Related runbook: [Replay or Restore Workflow](replay-or-restore.md).

> Используйте этот runbook, когда нужно восстановить retained operational
> artifact family: CI diagnostics, benchmark outputs, replay/state bundles,
> audit packages, local snapshots или cold-tier archives.

## Symptom

- требуемый retained artifact не находится в ожидаемом retention window;
- archive, audit package или snapshot найден, но checksum/report не сходится;
- restore drill не может воспроизвести артефакт на clean workspace;
- инцидент или audit blocked, потому что непонятно, что именно является source
  of truth для выбранной artifact family.

## Likely Causes

- artifact был ошибочно классифицирован как reproducible и удалён слишком рано;
- сохранён payload без manifest/report/checksum sidecars;
- restore path зависит от knowledge only-in-head вместо documented procedure;
- retained copy существует, но owner, storage tier или exact lookup key не
  были зафиксированы в incident timeline;
- local snapshot promoted в archive без проверки целостности и restoreability.

## Timeline Capture Expectations

Сразу зафиксируйте:

- artifact family и retention class (`R0`-`R4`);
- exact lookup key: `run_id`, `job_id`, `artifact_id`, `replay_ref`,
  `snapshot_root`, `archive_sha256`, CI run URL;
- UTC время начала restore attempt и owner, который его ведёт;
- expected outcome: reproduce, audit evidence, release evidence, incident
  analysis, operational resume;
- storage location: CI, CAS, local snapshot tree, compliance storage, cold
  archive;
- whether another retained copy exists.

## First Triage Steps

1. Определите, это recoverable artifact или merely reproducible output.
   Если семейство формально reproducible, сначала проверьте, не быстрее ли
   законно пересобрать его из source commit и lockfiles.
2. Проверьте retention class и owning team в
   [Retention and Recovery Policy](../reference/operations/retention-and-recovery.md).
3. Восстанавливайте family вместе с обязательными sidecars:
   audit package с provenance/signature, archive с report/hash, snapshot с
   manifest, replay bundle с connector context.
4. Если restore касается evidence или compliance, не редактируйте bundle
   in-place и не перепаковывайте его до верификации.

### Useful commands

Verify docs/site rebuild class:

```bash
cd policy-engine
uv run --extra docs python -m mkdocs build --strict
```

Inspect legacy archive payload and report:

```bash
cd policy-engine
uv run python tools/runtime/archive_legacy_runs.py --runs-root runs --archive-dir .tmp/legacy_runs_archive
```

Rebuild snapshot manifest for validation:

```bash
cd policy-engine
uv run python -m polisyos.batch_snapshot.cli finalize --snapshot-root /path/to/snapshot
```

Replay/checkpoint recovery regression coverage:

```bash
cd policy-engine
uv run pytest tests/fabric/data_plane/test_record_replay.py
uv run pytest tests/scientist/test_checkpoint.py tests/scientist/engine/test_checkpoint_gc.py
```

## Rollback / Mitigation

- если bundle integrity не подтверждена, stop restore и переключайтесь на
  другую retained copy;
- если evidence family missing, freeze destructive cleanup на affected surface
  до завершения gap analysis;
- если source family оказалась wrongly discardable, promote surviving copy в
  longer retention class до завершения postmortem;
- если restore drill failed on clean workspace, treat it как operational defect
  и открывайте remediation до следующего retention purge.

## Escalation Owner

- primary: `@platform-owners`;
- supporting: affected artifact-family owner;
- mandatory coordination: security/compliance owner для audit packages,
  provenance, signing evidence и other evidentiary bundles.

## Follow-up Checklist

- зафиксирован final source of truth по выбранной artifact family;
- checksum/report/manifest verified или explicitly marked missing;
- documented, было ли восстановление recovery или reproduction;
- retention class, owner и expiry assumptions обновлены, если были неверны;
- restore drill backlog пополнен, если восстановление потребовало ad hoc шагов.

## Blameless Postmortem

### What Went Well

- какой retention decision помог быстро найти нужную копию;
- какой sidecar или manifest сделал restore repeatable;
- где ownership и storage path были понятны без chat archaeology.

### What Went Poorly

- какая artifact family была классифицирована неверно;
- где missing checksums/manifests сломали доверие к restore;
- какая часть процедуры зависела от tacit knowledge.

### Action Items

| Action item | Owner | Due date | Status |
|---|---|---|---|
| Correct retention class or restore drill coverage for the affected artifact family | affected owner | YYYY-MM-DD | open |
| Backfill missing manifest, checksum, or evidence sidecars where feasible | `@platform-owners` | YYYY-MM-DD | open |
| Update recovery docs so retained-artifact restore is executable by non-authors | `@platform-owners` | YYYY-MM-DD | open |
