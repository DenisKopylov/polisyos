# Dependency Upgrade Regression

Related how-to: [Installation](../how-to/install.md). Related reference:
[Configuration](../reference/configuration.md).

> Используйте этот runbook, когда regression появилась после upgrade Python,
> Node, `uv.lock`, `pnpm-lock.yaml`, npm package, PyPI dependency или
> optional extra.

Owner: `@platform-owners`
Last tested: `2026-04-17` against current dependency-platform and acceptance-audit references.
Evidence path: `docs/reference/dependency-platform.md`; `docs/archive/reports/platform-acceptance.md`; `ops/ci/templates/workflows/arch.yml`
Rollback path: revert the offending dependency or lockfile delta, restore the previous supported toolchain baseline, and freeze further bumps in that family until triage is complete.

## Symptom

- `polisyos-tools workspace doctor` или `polisyos-tools workspace verify` внезапно падают после dependency
  change;

- backend или frontend тесты ломаются без изменения product logic;
- появляются import/runtime/type errors, которых не было до bump;
- lockfile freshness и generated contract checks начинают расходиться между CI
  и локальной машиной.

## Likely Causes

- несовместимый transitive bump в `uv.lock` или `pnpm-lock.yaml`;
- dependency требует другой baseline, чем текущие Python `3.14.x` или Node
  `22.x`;

- upgrade изменил schema/OpenAPI/frontend generated surfaces;
- новый пакет изменил performance footprint, serialization или optional extras;
- lockfile перегенерирован не тем инструментом или не на supported baseline.

## Timeline Capture Expectations

Зафиксируйте сразу:

- UTC timestamp первого failing check;
- PR / commit SHA, где впервые появилась regression;
- какие файлы менялись:
  `pyproject.toml`, `uv.lock`,
  `frontend/runtime-dashboard/package.json`,
  `pnpm-lock.yaml`,
  `.python-version`, `.nvmrc`;

- полный список failing commands и их exit codes;
- первый known-good commit и первый known-bad commit;
- если regression user-facing, приложите affected dashboard/API surface.

## First Triage Steps

1. Подтвердите baseline и workspace состояние:

   ```bash
   cd policy-engine
   uv run polisyos-tools workspace doctor
   ```

2. Покажите, что именно менялось в dependency surface:

   ```bash
   git diff -- \
     policy-engine/pyproject.toml \
     policy-engine/uv.lock \
     policy-engine/.python-version \
     policy-engine/.nvmrc \
     policy-engine/frontend/runtime-dashboard/package.json \
     policy-engine/pnpm-lock.yaml
   ```

3. Разделите regression по поверхности:

   ```bash
   cd policy-engine
   uv run polisyos-tools workspace verify --backend-only
   uv run polisyos-tools workspace verify --frontend-only
   ```

4. Если failure contract-related, прогоните canonical checks отдельно:

   ```bash
   cd policy-engine
   uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check
   uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py
   corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify
   ```

5. Если regression явно вызвана одним bump, попробуйте pin rollback в ветке и
   подтвердите, что green state возвращается.

## Rollback / Mitigation

- откатите offending dependency или lock refresh в PR, если root cause ещё не
  подтверждён;

- заморозьте дальнейшие bump-ы этой dependency family до postmortem;
- если затронут runtime/control-plane surface, не продвигайте релиз дальше
  staging/promotion gate;

- если нужен partial mitigation, добавьте upper bound или feature flag, а не
  ad hoc локальный workaround у одного разработчика.

## Escalation Owner

- primary: `@platform-owners`;
- supporting: owner того subsystem, где проявилась regression
  (`@runtime-owners`, `@frontend-owners`, `@foundry-owners`, `@fabric-owners`);

- если regression ломает release gate, incident commander тоже
  `@platform-owners`.

## Follow-up Checklist

- зафиксирован offending package и exact version delta;
- добавлен regression test или contract check;
- добавлен/обновлён version constraint, если проблема системная;
- если поменялся contributor path, обновлены docs в
  [Installation](../how-to/install.md);

- если affected surface user-facing, обновлены release notes и upgrade notes;
- если bump был automated, настроен denylist/ruleset для повторной волны.

## Blameless Postmortem

### What Went Well

- какой check первым дал правдивый signal;
- что помогло быстро сузить blast radius;
- какие guardrails сработали до production.

### What Went Poorly

- где dependency drift оставалась неявной;
- какие сигналы были noisy, duplicated или опоздали;
- где owner map или docs оказались недостаточно точными.

### Action Items

Заполните по итогам инцидента.

| Action item                                                                | Owner                    | Due date   | Status |
| -------------------------------------------------------------------------- | ------------------------ | ---------- | ------ |
| Add or tighten regression coverage for the failing dependency path         | `@platform-owners`       | YYYY-MM-DD | open   |
| Document package-specific pin/compatibility rule if the failure can repeat | affected subsystem owner | YYYY-MM-DD | open   |
| Update upgrade policy / allowlist / denylist for the dependency family     | `@platform-owners`       | YYYY-MM-DD | open   |
