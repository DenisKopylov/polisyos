# ADR-0149: Effective Mode And Fallback Degradation Ledger

## Status

Accepted

## Date

2026-05-14

## Context

Production diagnostics found that serious lanes can be shaped by development
mode, local-control waivers, simulated providers, fixture overlays, generated
substitutes, optional refs, silent defaults, and fallback paths. These choices
can affect evidence while remaining invisible to scorecard, readiness,
approval, dashboard, or public artifacts.

Fallback is not an implementation detail when it changes authority. Mode,
fallback, degradation, simulation, fixture identity, and overlay state must be
runtime-owned evidence.

## Decision

1. Every serious run and canary lane must emit an effective mode ledger.
2. The mode ledger records requested execution profile, effective execution
   profile, canary kind, lane id, provider mode, model simulation mode, mock
   fallback allowed/used, fixture identity, data mode, production data root,
   manifest fingerprint, state-store backend, worker backend, local-control
   waiver, scorecard warn policy, evidence overlay mode, quarantine status, and
   signed exception identity when present.
3. Governed, production, research closeout, approval, and deterministic
   closeout fail when requested mode, effective mode, provider mode, canary
   kind, fixture identity, overlay mode, state-store backend, or warning policy
   disagree without an allowed-profile exception.
4. Every fallback, default, optionalization, simulation, overlay, projection,
   dependency degradation, or generated substitute that can affect evidence
   must emit a fallback/degradation ledger record.
5. The fallback/degradation ledger records event id, component, phase, trigger,
   primary path, fallback path, allowed profiles, actual profile, produced
   artifacts, affected claims, affected gates, severity, degradation kind,
   downstream impact, override policy, blocking status, owner, and next
   diagnostic command.
6. Fallback-produced evidence cannot silently satisfy production gates. It must
   be explicitly allowed for the active profile or produce a blocking
   degradation record.
7. Simulated provider evidence, fixture evidence, deterministic overlays, and
   bundle-generated substitutes are allowed only when their provenance is
   declared and the invariant registry permits them for that profile and gate.
8. Serious-profile warning acceptance is itself a mode policy. A `warn`
   scorecard may not satisfy closeout unless the lane is explicitly declared as
   non-production dev smoke.

## Consequences

Positive:

- The system can explain why a serious run used a degraded or simulated path.
- Fixture theater and mode leakage become detectable before closeout.
- Canary matrix, scorecard, readiness, approval, and dashboards can share one
  runtime-owned mode truth.
- Fallback decisions become reviewable, replayable, and bound to affected
  claims and gates.

Negative:

- Local and deterministic runs must carry more explicit mode metadata.
- Some current simulated or fixture lanes will become non-ready for serious
  closeout until they provide allowed-profile policies.
- Defaults that were previously convenient will become blockers when they
  affect production authority.

## Concrete impact

This ADR does not define an implementation plan. It requires future
implementation work to introduce or update:

- effective mode ledger schema;
- fallback/degradation ledger schema;
- allowed-profile policy registry;
- provider/model mode checks;
- scorecard, canary matrix, readiness, and approval checks that reject hidden
  mode or fallback divergence;
- negative tests for dev mode in production, simulated provider leakage,
  fixture overlay closeout, generated report substitution, optional ref
  acceptance, and warning scorecard acceptance in serious lanes.

## Related Decisions

- Extends: ADR-0097 Runtime Rate Limiting and Idempotency.
- Extends: ADR-0101 Runtime Audit Trail Model.
- Extends: ADR-0116 OTel-First Observability.
- Extends: ADR-RSR-0137 Production Data and Fixtures Classification.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0148 Serious Run State Machine And Phase Barriers.
- Related: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
