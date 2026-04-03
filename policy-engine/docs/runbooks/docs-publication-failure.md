# Docs Publication Failure

Related docs: [Home](../index.md), [Reference](../reference/index.md),
the repository documentation program plan.

> Используйте этот runbook, когда docs pipeline не может собрать, проверить или
> опубликовать site через `docs-pages`.

## Symptom

- `uv run --extra docs python -m mkdocs build --strict` падает локально или в CI;
- workflow `Docs Pages` не деплоит `github-pages`;
- docs accuracy / broken-link / nav issue ломает publish path;
- опубликованный docs site stale относительно `main`, хотя code CI green.

## Likely Causes

- broken nav path или missing file in `mkdocs.yml`;
- broken relative links, missing reference page или moved doc;
- docs page описывает несуществующую command/API surface;
- docs build зависит от Python/dev tooling, который не был synced;
- `workflow_run` publish path не стартует из-за состояния upstream `CI`.

## Timeline Capture Expectations

Зафиксируйте:

- failing local command или workflow step;
- `Docs Pages` run URL / run ID и related upstream `CI` run;
- commit SHA и список changed docs/nav files;
- затронутый раздел: tutorials, how-to, reference, explanation, runbooks;
- impact: publish blocked полностью или site stale частично.

## First Triage Steps

1. Воспроизведите build локально:

   ```bash
   cd policy-engine
   uv sync --frozen --extra dev
   uv run --extra docs python -m mkdocs build --strict
   ```

2. Если проблема про factual drift, прогоните docs accuracy checker:

   ```bash
   cd policy-engine
   uv run --extra docs python tools/validation/check_docs_accuracy.py --repo-root .
   ```

3. Проверьте `mkdocs.yml` nav и наличие всех referenced files.
4. Если publish path запускался через `workflow_run`, убедитесь, что upstream
   `CI` действительно был `success` на `main`.
5. Если stale site already published, определите: это build failure,
   upload-pages-artifact failure или deploy-pages failure.

## Rollback / Mitigation

- если broken docs change очевиден, откатите его или подготовьте minimal fix PR;
- если build ломает nav drift, временно снимите broken entry только вместе с
  replacement page или redirect note;
- если publish blocked, но source docs критичны для incident response,
  распространите temporary internal link to rendered artifact or PR preview;
- не публикуйте site с `--strict` выключенным как permanent workaround.

## Escalation Owner

- primary: `@docs-owners`;
- platform for CI/publish plumbing: `@platform-owners`;
- subsystem owner joins, если docs failure вызван contract drift в его area.

## Follow-up Checklist

- root cause classified: content drift, nav drift, tooling drift, publish plumbing;
- docs accuracy or link-check coverage updated, если нужно;
- publish freshness expectation re-documented;
- runbook, landing page или nav updated if discoverability was poor.

## Blameless Postmortem

### What Went Well

- что быстро локализовало failure: local build, CI step, accuracy checker;
- насколько reproducible оказался build locally;
- как быстро удалось вернуть docs publish.

### What Went Poorly

- где docs source-of-truth был размытым;
- какие changes дошли до `main` без local validation;
- какие stale docs увеличили operator risk.

### Action Items

| Action item | Owner | Due date | Status |
|---|---|---|---|
| Strengthen the check that should have caught the docs failure earlier | `@docs-owners` | YYYY-MM-DD | open |
| Fix the nav/content/tooling gap that blocked publication | affected owner | YYYY-MM-DD | open |
| Improve docs pipeline observability or ownership routing | `@platform-owners` | YYYY-MM-DD | open |
