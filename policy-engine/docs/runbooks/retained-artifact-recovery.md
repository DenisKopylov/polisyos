# Retained Artifact Recovery

Related reference: [Retention and Recovery Policy](../reference/operations/retention-and-recovery.md).
Related runbook: [Replay or Restore Workflow](replay-or-restore.md).
Related Fabric reference: [Fabric Data Plane](../reference/fabric/data-plane.md).

> Используйте этот runbook, когда нужно восстановить retained operational
> artifact family: CI diagnostics, benchmark outputs, replay/state bundles,
> audit packages, local snapshots или cold-tier archives.

Owner: `@platform-owners`
Last tested: `2026-04-17` against the current retention policy and restore drill evidence.
Evidence path: `docs/reference/operations/retention-and-recovery.md`; `docs/archive/reports/platform-acceptance-manual.md`; `docs/archive/reports/platform-acceptance.md`
Rollback path: freeze cleanup on the affected artifact family, preserve surviving copies, and restore only from a retained bundle that still has its required sidecars and hashes.

Freshness: 2026-04-17.

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
- Fabric connector fixture, quarantine record, CDC event, quality report,
  lineage graph, or schema-governance evidence was produced but not retained
  with its manifest or lookup key.

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
- for Fabric: connector id, dataset id, schema id/version, profile id,
  artifact kind, quarantine reason, CDC event kind, or lineage graph id.

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

### Fabric retained families

| Family                       | Lookup key                                                                       | Validation                                                                                           |
| ---------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Connector recorded fixtures  | fixture path under `tests/unit/fabric/connectors/sources/fixtures/` plus connector id | source-specific connector tests and record/replay tests                                              |
| Connector contract snapshots | contract id and schema id/version                                                | `polisyos-tools connectors check-contracts --check` and `tools/ci/check_fabric_schema_registry.py --check` |
| Data-plane replay bundles    | connector id, dataset id, replay ref, cursor/checkpoint key                      | `tests/unit/fabric/data_plane/test_record_replay.py`                                                      |
| Quarantine/DLQ records       | `artifact_id`, reason, source, schema version                                    | `tests/unit/fabric/data_plane/test_quarantine.py` and `list_quarantine_records()`                         |
| CDC schema-change events     | CAS artifact kind `fabric.cdc_schema_change` and stream dataset id               | `tests/unit/fabric/data_plane/test_streaming_runtime.py`                                                  |
| Quality reports              | metric id, run id, profile, `DataFitnessReport` payload                          | `tests/unit/fabric/test_quality_indicators.py`                                                            |
| Lineage graphs               | graph id such as `graph.lineage.test` or production graph id                     | `tests/unit/fabric/test_lineage.py` and OpenLineage export validation                                     |

### Useful commands

Verify docs/site rebuild class:

```bash
cd policy-engine
uv run --extra docs python -m mkdocs build --strict
```

Inspect legacy archive payload and report:

```bash
cd policy-engine
uv run python tools/ops/runtime/archive_legacy_runs.py --runs-root runs --archive-dir _build/.tmp/legacy_runs_archive
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
uv run pytest tests/unit/scientist/engine/test_checkpoint.py tests/unit/scientist/engine/test_checkpoint_gc.py
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

- если bundle integrity не подтверждена, stop restore и переключайтесь на
  другую retained copy;

- если evidence family missing, freeze destructive cleanup на affected surface
  до завершения gap analysis;

- если source family оказалась wrongly discardable, promote surviving copy в
  longer retention class до завершения postmortem;

- если restore drill failed on clean workspace, treat it как operational defect
  и открывайте remediation до следующего retention purge.

- если Fabric artifact family восстановлена из replay, сохраните связь между
  новым artifact id и original incident/ref, чтобы lineage не выглядела как
  independent source.

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
- Fabric schema-governance evidence, quarantine report, quality report, or
  lineage export regenerated only from trusted source state.

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

| Action item                                                                        | Owner              | Due date   | Status |
| ---------------------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Correct retention class or restore drill coverage for the affected artifact family | affected owner     | YYYY-MM-DD | open   |
| Backfill missing manifest, checksum, or evidence sidecars where feasible           | `@platform-owners` | YYYY-MM-DD | open   |
| Update recovery docs so retained-artifact restore is executable by non-authors     | `@platform-owners` | YYYY-MM-DD | open   |
