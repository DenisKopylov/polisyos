# Docs Publication Failure

Related docs: [Home](../index.md), [Reference](../reference/index.md),
the repository documentation program plan.

> Use this runbook when the documentation pipeline cannot build, validate, or
> complete publication-ready validation through the repository-tracked documentation gate.

Owner: `@docs-owners`
Historical validation receipt: `2026-04-17` — at that time, the strict MkDocs build, docs-accuracy check, and published QA ledger were used. This is not a fresh validation.
Evidence path: `docs/reference/documentation-inventory.md`; `docs/reference/quality-gates.md`; `.github/workflows/abi.yml`; `.github/workflows/docs-pages.yml`
Rollback path: revert or minimally fix the docs/nav/config change that broke publish, restore a strict green build, and only then republish.

## Symptom

- `uv run --extra docs python -m mkdocs build --strict` fails locally or in CI;
- docs quality or publication workflow (`.github/workflows/abi.yml` or
  `.github/workflows/docs-pages.yml`) fails;
- A docs accuracy, broken-link, or navigation issue breaks the publish path;
- The published docs site is stale relative to `main` even though code CI is green.

## Likely Causes

- A broken navigation path or missing file in `mkdocs.yml`;
- Broken relative links, a missing reference page, or a moved document;
- A docs page describes a command or API surface that does not exist;
- The docs build depends on Python or development tooling that was not synchronized;
- The `workflow_run` publish path does not start because of the upstream `CI` state.

## Timeline Capture Expectations

Record:

- The failing local command or workflow step;
- The `Documentation` run URL or run ID and the related upstream `CI` run;
- The commit SHA and list of changed documentation or navigation files;
- The affected section: tutorials, how-to, reference, explanation, or runbooks;
- The impact: publication is fully blocked or the site is partially stale.

## First Triage Steps

1. Reproduce the build locally:

   ```bash
   cd policy-engine
   uv sync --frozen --extra docs --extra runtime --extra ml
   uv run polisyos-tools validation check-docs-gate --repo-root . --base-ref origin/main
   ```

2. If the problem appears to be a content or navigation failure, narrow reproduction to a
   strict MkDocs build:

   ```bash
   cd policy-engine
   uv run --extra docs python -m mkdocs build --strict
   ```

3. If the problem concerns factual drift, run the docs-accuracy checker:

   ```bash
   cd policy-engine
   uv run polisyos-tools validation check-docs-accuracy --repo-root .
   ```

4. Check `mkdocs.yml` navigation and confirm that all referenced files exist.
5. If the documentation gate ran as a PR check, compare the failing diff with
   the expected docs-sensitive scope and confirm that changed-file rules did not
   miss a required evidence update.
6. If a stale site was already published, determine whether this is a build failure,
   an upload-pages-artifact failure, or a deploy-pages failure.

## Rollback / Mitigation

- If the documentation change is clearly broken, revert it or prepare a minimal fix PR;
- If a navigation change breaks the build, temporarily remove the broken entry only with
  a replacement page or redirect note;

- If the publication gate is blocked but source docs are critical for incident response,
  share a temporary internal link to the rendered artifact or PR preview;

- Do not publish the site with `--strict` disabled as a permanent workaround.

## Escalation Owner

- primary: `@docs-owners`;
- platform for CI/publish plumbing: `@platform-owners`;
- The subsystem owner joins if the documentation failure was caused by contract drift in their area.

## Follow-up Checklist

- root cause classified: content drift, nav drift, tooling drift, publish plumbing;
- Docs-accuracy or link-check coverage was updated if needed;
- publish freshness expectation re-documented;
- The runbook, landing page, or navigation was updated if discoverability was poor.

## Blameless Postmortem

### What Went Well

- What quickly localized the failure: local build, CI step, or the accuracy checker;
- How reproducible the local build was;
- How quickly documentation publishing was restored.

### What Went Poorly

- Where the documentation source of truth was unclear;
- Which changes reached `main` without local validation;
- Which stale docs increased operator risk.

### Action Items

| Action item                                                           | Owner              | Due date   | Status |
| --------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Strengthen the check that should have caught the docs failure earlier | `@docs-owners`     | YYYY-MM-DD | open   |
| Fix the nav/content/tooling gap that blocked publication              | affected owner     | YYYY-MM-DD | open   |
| Improve docs pipeline observability or ownership routing              | `@platform-owners` | YYYY-MM-DD | open   |
