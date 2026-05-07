# Broken Contract Generation

Related how-to: [Manage Schemas](../how-to/manage-schemas.md). Related reference:
[Schemas](../reference/schemas.md), [REST API](../reference/api/index.md).

> Используйте этот runbook, когда contract freshness или generation path
> расходятся между backend, committed snapshots, OpenAPI и frontend fixtures.

Owner: `@platform-owners`
Last tested: `2026-04-17` against current schema, OpenAPI, frontend-contract, and docs build checks.
Evidence path: `docs/reference/quality-gates.md`; `schemas/runtime_api_v1.openapi.json`; `docs/archive/reports/platform-acceptance.md`
Rollback path: revert the unintended contract change or regenerate all affected artifacts and docs in one change set before promotion.

## Symptom

- `uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check` падает;
- `uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py` сообщает drift;
- `corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify`
  ломается;
- `mkdocs build --strict` или docs pages ссылаются на устаревший API shape;
- CI на ABI/OpenAPI/frontend contracts краснеет после seemingly innocent change.

## Likely Causes

- изменили Pydantic contract, route response, schema model или generated client,
  но не обновили committed artifacts;

- backend route и frontend fixture были изменены независимо;
- OpenAPI snapshot или schema snapshots собирались на stale workspace;
- runtime contract change прошёл без обновления docs/reference surface;
- additive-looking change на деле нарушил compatibility policy.

## Timeline Capture Expectations

Зафиксируйте:

- failing command и точное сообщение;
- commit SHA, authoring area и changed files;
- какой authoritative source считается источником истины:
  Python models, runtime routes, generated frontend fixtures или schema
  snapshots;

- какой snapshot/file drift detected первым;
- был ли change уже опубликован в docs или попал в release candidate.

## First Triage Steps

1. Прогоните все три canonical checks отдельно:

   ```bash
   cd policy-engine
   uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check
   uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
   corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify
   ```

2. Отделите source drift от generated drift:

   - если упал только schema check, смотрите `schemas/snapshots/**`;
   - если упал только runtime API check, смотрите `runtime/http` и committed
     OpenAPI snapshot;
   - если упал frontend contracts path, смотрите runtime client/fixtures и
     dashboard expectations.

3. Сверьте docs surface:

   ```bash
   cd policy-engine
   uv run --extra docs python -m mkdocs build --strict
   ```

4. Если change intended, регенерируйте artifacts canonical path-ом и убедитесь,
   что diff ожидаемый, а не побочный.

## Rollback / Mitigation

- если drift непреднамеренный, откатите contract-affecting change до последнего
  green SHA;

- если change намеренный, не merge-ите его без regenerated artifacts и docs
  updates в том же change set;

- если frontend и backend разошлись, временно удерживайте deploy до выравнивания
  обеих сторон;

- если compatibility нарушена, инициируйте ADR/contract review вместо
  молчаливого force-refresh.

## Escalation Owner

- primary: `@platform-owners`;
- supporting: owner изменённой boundary surface
  (`@runtime-owners`, `@frontend-owners`, `@ir-owners`, `@core-owners`).

## Follow-up Checklist

- определён authoritative source для каждого drifted artifact;
- regenerated artifacts вошли в тот же change set;
- обновлены reference/how-to docs, если behavior surface changed;
- добавлен test or gate, который раньше не ловил этот тип drift;
- для breaking change обновлена compatibility narrative.

## Blameless Postmortem

### What Went Well

- какой freshness check первым показал правду;
- что позволило быстро отличить intended change от accidental drift;
- где source-of-truth оказался однозначным.

### What Went Poorly

- где граница ownership была размытой;
- какая contract surface оказалась слишком implicit;
- почему docs or client drift дошли так далеко.

### Action Items

| Action item                                                       | Owner              | Due date   | Status |
| ----------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Add a stronger freshness gate for the missed drift pattern        | `@platform-owners` | YYYY-MM-DD | open   |
| Update docs and generation instructions for the affected boundary | affected owner     | YYYY-MM-DD | open   |
| Tighten compatibility review for the contract family if needed    | `@platform-owners` | YYYY-MM-DD | open   |
