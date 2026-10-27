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

## Calibration execution-stall alert

When CalibrationStuck fires, it means the oldest active calibration execution
has not completed an optimizer step for more than 30 minutes and that state
persisted through the alert's existing 30-minute firing hold. It is an
execution-progress signal, not a calibration-quality or convergence verdict.

The producer exports active count and oldest step age by optimizer and
environment. A fresh concurrent calibration does not reset the oldest run's
age. The collector removes a run from active state on both successful return
and failure, so a retained calibration-loss gauge alone cannot keep the alert
eligible. Metric labels intentionally omit execution IDs. Compare the
alert window and optimizer/environment labels with existing calibration.run
trace spans. Each span's calibration.run_id distinguishes an invocation during
trace inspection, but the aggregate metric does not identify which invocation
is oldest. If several matching runs could explain the series, leave attribution
unresolved. Inspect available spans' start index, convergence reason, and total
steps before escalating to @foundry-owners. This controlled signal does not
establish production calibration quality or SLO attainment.

## Scientist API workflow p99 latency

When the Scientist API p99 alert fires, use the existing alert and dashboard:

- Alert: SLO_DagLatencyP99High in ops/observability/prometheus/slo_alerts.yml.
- Panel: DAG Latency Distribution in ops/observability/grafana/dashboards/slo-overview.json.
- Select the alert environment and affected workflow_id values. Compare the alert's 5-minute recording window and 15-minute firing hold with the 30-minute SLI query and the 28-day objective window.

First confirm eligible histogram samples exist for measurement_scope=scientist_api. No series or zero eligible traffic is missing evidence, not a healthy p99. Record the alert time range, environment, workflow IDs, and dashboard query window before comparing against the 300-second threshold.

For a candidate slow run, follow its existing trace or request/run record. The API histogram has no executor-profile or helper label, so it cannot attribute time to the Common shared executor. Only attribute a Common wait when the actual Common call event is attached to the selected experiment.workflow root, or to a descendant whose full parent chain resolves to that root, and the call-time executor profile is recorded. A matching workflow ID or a simultaneous helper observation alone is not enough. If this joined evidence is unavailable, record the cause as unclassified and escalate to @scientist-owners and @core-owners with the alert window and missing evidence identified.

The controlled regression path is tests/unit/scientist/orchestration/engine/test_scientist_api_slo_scope.py. It exercises a source-controlled FanOut/Common workflow; it does not establish production causation, deployment-profile selection, or SLO attainment.

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
