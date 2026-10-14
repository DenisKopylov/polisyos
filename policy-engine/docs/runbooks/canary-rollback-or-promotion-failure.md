# Canary Rollback or Failed Production Promotion

Related policy: [SLO and Error Budget Policy](../reference/operations/slo-error-budget.md).
Related how-to: [Deploy Runtime](../how-to/deploy-runtime.md).

> Use this runbook for a staged rollout, canary evaluation, or any
> production promotion gate. The repository release workflow runs a local
> health-probe canary against an installed release wheel before publishing a
> release; this is not a production deployment or environment canary. This
> runbook also covers manual environment approval and rollback procedures.

Owner: `@platform-owners`
Source of truth: `.github/workflows/release.yml` and `policy-engine/tools/ops_runners/release/run_release_canary.py`.
Repository source reviewed: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; source inspection only, no release workflow or runtime was executed.
Historical validation receipt (as recorded by this page): `2026-04-17` — canary and acceptance-rehearsal evidence available at that time; this is not a fresh validation.
Evidence path: `docs/archive/reports/platform-release-canary.md`; `docs/archive/reports/platform-acceptance-manual.md`; `docs/reference/operations/platform-acceptance-audit.md`
Rollback path: return traffic and config to the last known-good candidate before further investigation, then freeze further promotion until the root cause is understood.

## Symptom

- The release candidate fails a promotion checkpoint;
- Golden signals degrade after a limited rollout and the rollout stops;
- A rollback was triggered manually or automatically by an alert threshold;
- The production deployment succeeds technically, but the runtime or control-plane surface becomes
  worse than the baseline.

## Likely Causes

- Runtime or configuration drift between staging and production;
- A silent contract mismatch between the runtime and dashboard or operator tooling;
- A hidden dependency on the state store, auth, SBOM/signing, OPA, or a connector path;
- SLO burn begins to rise after rollout even though pre-release checks were green;
- The release candidate contains a migration and feature-flag combination that is not covered by the
  smoke path.

## Timeline Capture Expectations

Record at least:

- The candidate build ID, commit SHA, and release-note summary;
- The exact rollout start, hold, and rollback window in UTC;
- The checkpoint that failed: health, latency, errors, saturation, or manual sign-off;
- What was compared with the baseline;
- Who made the hold, rollback, or promotion decision;
- Which user-facing routes, jobs, or dashboards were affected.

## First Triage Steps

1. Confirm that the failure is related to promotion and not an older
   background incident.
2. Compare the candidate with the last known-good version across:

   - health/readiness;
   - runtime error rate;
   - DAG success rate;
   - control-plane queue/worker health;
   - frontend platform health.
3. Open the trusted dashboards:
   `executive-overview`, `slo-overview`, `scientist-agents`,
   `security-phase4`.
4. If the rollout is partial, record its scope: what percentage of traffic, users, or jobs
   has already received the candidate.
5. Check immediately for parallel failures in contracts, signing/SBOM,
   documentation publishing, or replay/state-restore paths.

## Rollback / Mitigation

- If the candidate degrades golden signals, rollback takes priority over finding
  the perfect root cause;

- Return to the last known-good artifact/configuration pair, not only the code;
- Freeze further promotion activity until the system is stable and the incident is reviewed;
- Security fixes and P0 restoration work remain exceptions during the freeze, but
  their scope must be minimal and explicitly recorded.

## Escalation Owner

- primary: `@platform-owners`;
- runtime evaluation: `@runtime-owners`;
- The affected subsystem owner joins after the rollback decision, not instead of it.

## Follow-up Checklist

- recorded candidate-vs-baseline comparison preserved;
- The root cause was classified as code, configuration, dependency, migration, or traffic shape;
- If rollback was manual, the manual steps are now documented;
- The release checklist was amended if a missing checkpoint allowed a bad candidate through;
- error-budget impact reflected in freeze/no-freeze decision.

## Blameless Postmortem

### What Went Well

- Which checkpoint stopped the bad promotion in time;
- How quickly the known-good state was restored;
- Whether ownership and decision rights were sufficient.

### What Went Poorly

- Where the rollout signal was ambiguous;
- Which staged checks did not reflect the real production path;
- Whether rollback steps depended too much on manual knowledge.

### Action Items

| Action item                                                 | Owner              | Due date   | Status |
| ----------------------------------------------------------- | ------------------ | ---------- | ------ |
| Add or tighten the missing promotion checkpoint             | `@platform-owners` | YYYY-MM-DD | open   |
| Reduce manual rollback steps for this release path          | `@platform-owners` | YYYY-MM-DD | open   |
| Add staging/prod parity coverage for the root-cause surface | affected owner     | YYYY-MM-DD | open   |
