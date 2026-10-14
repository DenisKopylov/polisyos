# Benchmark Regression Triage

Related how-to: [Run Benchmarks](../how-to/run-benchmarks.md). Related reference:
[Foundry](../reference/foundry/index.md).

> Use this runbook when a benchmark suite regresses in
> quality, latency, stability, comparator completeness, or release-gate results.

Owner: `@foundry-owners`
Historical validation receipt (as recorded by this page): `2026-04-17` — benchmark and release-gate evidence surfaces available at that time; this is not a fresh validation.
Evidence path: `docs/reference/scientist/reliability-scorecard.md`; `docs/archive/reports/platform-release-canary.md`; `ops/ci/templates/workflows/perf.yml`
Rollback path: stop promotion, preserve baseline and candidate reports, then roll back or pin the change that introduced the confirmed regression.

## Symptom

- Smoke or extended benchmark reports show a lower pass rate;
- The release summary or comparator matrix worsens for a suite or circuit;
- Benchmark JSON output differs between two otherwise identical runs without
  a justified nondeterminism note;

- The regression appears in local validation, the nightly pack, or release review.

## Likely Causes

- A change to Foundry, Scientist, or Fabric logic degraded factual metrics;
- A dependency or toolchain bump changed numerics, runtime cost, or JIT behavior;
- The baseline snapshot is stale or was replaced without an explicit record;
- A comparator, ablation, or shadow-evidence path is no longer complete;
- The regression comes from data or fixture drift rather than model quality.

## Timeline Capture Expectations

Record:

- The suite ID, circuit, mode, profile, and report path;
- The baseline report and candidate report;
- commit SHA, environment, seed/profile if relevant;
- regression type: pass rate, latency, NaN rate, comparator completeness,
  release gate, memory/cost;

- Whether the regression was detected locally, in the nightly pack, or during release review.

## First Triage Steps

1. Rerun the failing suite with the canonical registry-backed runner:

   ```bash
   cd policy-engine
   uv run polisyos-tools benchmarks run-all --circuit <suite-or-circuit> --mode smoke
   ```

2. If the regression appears performance-specific, run a narrow pytest path
   or a benchmark-specific test next to the suite family.
3. Compare generated JSON reports, not only the console summary.
4. Check whether any of these changed at the same time:

   - dependency upgrades;
   - schema/contract refresh;
   - replay/data fixture drift;
   - observability or instrumentation overhead.
5. If the regression becomes visible to users only after aggregation, rebuild the release summary
   and comparator-completeness results; do not draw a conclusion from one suite alone.

## Rollback / Mitigation

- If the regression is severe and confirmed, do not promote the candidate to release;
- If a recent merge caused the regression, revert the offending change or
  temporarily pin the feature flag or profile;

- If only one benchmark family regressed, limit the blast radius and do not
  stop unrelated work without evidence;

- If the baseline is stale, update it only after explicit
  review and recording the rationale.

## Escalation Owner

- primary: `@foundry-owners`;
- Supporting: the owner of the affected subsystem surface
  (`@scientist-owners`, `@fabric-owners`, `@platform-owners`).

## Follow-up Checklist

- The regression was confirmed by a rerun on the canonical runner;
- Baseline and candidate artifacts were preserved;
- The root cause was classified as code, data, dependency, tooling, or baseline drift;
- benchmark registry / release summary / docs updated if expectations changed;
- added targeted regression coverage if blind spot was discovered.

## Blameless Postmortem

### What Went Well

- Which suite or metric first exposed the regression;
- What helped locate the source quickly;
- How reproducible the benchmark path was.

### What Went Poorly

- Where suite semantics or report formats were unclear;
- Which baseline assumptions were not recorded explicitly;
- Whether benchmark drift was confused with expected product evolution.

### Action Items

| Action item                                                             | Owner              | Due date   | Status |
| ----------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Add focused regression coverage for the failing benchmark path          | `@foundry-owners`  | YYYY-MM-DD | open   |
| Clarify benchmark baseline or report interpretation if it was ambiguous | affected owner     | YYYY-MM-DD | open   |
| Update release review policy if the regression should block sooner      | `@platform-owners` | YYYY-MM-DD | open   |
