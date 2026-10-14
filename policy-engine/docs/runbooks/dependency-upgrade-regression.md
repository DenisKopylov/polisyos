# Dependency Upgrade Regression

Related how-to: [Installation](../how-to/install.md). Related reference:
[Configuration](../reference/configuration.md).

> Use this runbook when a regression appears after upgrading Python,
> Node, `uv.lock`, `pnpm-lock.yaml`, an npm package, a PyPI dependency, or
> optional extra.

Owner: `@platform-owners`
Historical validation receipt (as recorded by this page): `2026-04-17` — dependency-platform and acceptance-audit references available at that time; this is not a fresh validation.
Evidence path: `docs/reference/dependency-platform.md`; `docs/archive/reports/platform-acceptance.md`; `ops/ci/templates/workflows/arch.yml`
Rollback path: revert the offending dependency or lockfile delta, restore the previous supported toolchain baseline, and freeze further bumps in that family until triage is complete.

## Symptom

- `polisyos-tools workspace doctor` or `polisyos-tools workspace verify` unexpectedly fails after a dependency
  change;

- Backend or frontend tests fail without a change to product logic;
- Import, runtime, or type errors appear that were absent before the bump;
- Lockfile freshness and generated contract checks start to diverge between CI
  and a local machine.

## Likely Causes

- An incompatible transitive bump in `uv.lock` or `pnpm-lock.yaml`;
- The dependency requires a different baseline from the current Python `3.14.x` or Node
  `22.x`;

- The upgrade changed schema, OpenAPI, or generated frontend surfaces;
- A new package changed performance footprint, serialization, or optional extras;
- The lockfile was regenerated with the wrong tool or on an unsupported baseline.

## Timeline Capture Expectations

Record these details immediately:

- The UTC timestamp of the first failing check;
- The PR or commit SHA where the regression first appeared;
- Which files changed:
  `pyproject.toml`, `uv.lock`,
  `apps/runtime-dashboard/package.json`,
  `pnpm-lock.yaml`,
  `.python-version`, `.nvmrc`;

- The complete list of failing commands and their exit codes;
- The first known-good commit and the first known-bad commit;
- If the regression is user-facing, attach the affected dashboard or API surface.

## First Triage Steps

1. Confirm the baseline and workspace state:

   ```bash
   cd policy-engine
   uv run polisyos-tools workspace doctor
   ```

2. Show exactly what changed in the dependency surface:

   ```bash
   git diff -- \
     policy-engine/pyproject.toml \
     policy-engine/uv.lock \
     policy-engine/.python-version \
     policy-engine/.nvmrc \
     policy-engine/apps/runtime-dashboard/package.json \
     policy-engine/pnpm-lock.yaml
   ```

3. Classify the regression by surface:

   ```bash
   cd policy-engine
   uv run polisyos-tools workspace verify --backend-only
   uv run polisyos-tools workspace verify --frontend-only
   ```

4. If the failure is contract-related, run the canonical checks separately:

   ```bash
   cd policy-engine
   uv run --extra ml python tools/quality/diagnostics/gen_schema.py --check
   uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
   corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify
   ```

5. If one bump clearly caused the regression, try rolling back the pin on a branch and
   confirm that the green state returns.

## Rollback / Mitigation

- Revert the offending dependency or lock refresh in the PR if the root cause is not yet
  confirmed;

- Freeze further bumps in this dependency family until the postmortem;
- If the runtime or control-plane surface is affected, do not promote the release beyond
  the staging or promotion gate;

- If partial mitigation is needed, add an upper bound or feature flag instead of
  an ad hoc local workaround for one developer.

## Escalation Owner

- primary: `@platform-owners`;
- Supporting: the owner of the subsystem where the regression appeared
  (`@runtime-owners`, `@frontend-owners`, `@foundry-owners`, `@fabric-owners`);

- If the regression breaks the release gate, the incident commander is also
  `@platform-owners`.

## Follow-up Checklist

- The offending package and exact version delta were recorded;
- A regression test or contract check was added;
- A version constraint was added or updated if the issue is systemic;
- If the contributor path changed, the docs in
  [Installation](../how-to/install.md);

- If the affected surface is user-facing, release notes and upgrade notes were updated;
- If the bump was automated, a denylist or ruleset was configured to prevent another wave.

## Blameless Postmortem

### What Went Well

- Which check first provided a truthful signal;
- What helped narrow the blast radius quickly;
- Which guardrails worked before production.

### What Went Poorly

- Where dependency drift remained implicit;
- Which signals were noisy, duplicated, or late;
- Where the owner map or docs were not precise enough.

### Action Items

Complete this section after the incident.

| Action item                                                                | Owner                    | Due date   | Status |
| -------------------------------------------------------------------------- | ------------------------ | ---------- | ------ |
| Add or tighten regression coverage for the failing dependency path         | `@platform-owners`       | YYYY-MM-DD | open   |
| Document package-specific pin/compatibility rule if the failure can repeat | affected subsystem owner | YYYY-MM-DD | open   |
| Update upgrade policy / allowlist / denylist for the dependency family     | `@platform-owners`       | YYYY-MM-DD | open   |
