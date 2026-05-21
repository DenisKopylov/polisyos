# ADR-0163: Lifecycle, DDM, Ex-Post Outcomes, And Calibration

## Status

Accepted

## Date

2026-05-18

## Context

The Policy Design Case SDD adds a constraint that policy decisions are not
one-shot artifacts. A best-in-class policy system must know whether earlier
claims held up, how a case was revised, whether it was superseded or withdrawn,
and how the system's forecasts calibrated over time.

The repository already contains continuous governance, reissue, DDM,
degradation, readiness, incident, root-cause, calibration, backtesting, and
memory-contamination surfaces. Without an ADR, later implementation could
silently treat these surfaces as optional reports instead of binding them into
case authority.

Historical cases also need append-only lifecycle semantics. Ex-post learning
must not rewrite the original publication authority, contaminate unrelated
runs, or let a weak historical track record excuse a weak current case.

## Decision

1. Every published or governed Policy Design Case has an append-only lifecycle
   ledger. Lifecycle events include draft, ready_for_review, approved,
   published, amended, superseded, withdrawn, recalled, retracted, stale,
   contested, ex_post_under_review, confirmed, refuted, and inconclusive.
2. Lifecycle events reference the prior case state and the evidence that
   justified the transition. They never rewrite historical authority records,
   publication packets, claims, or approval events.
3. Governed and production cases require an implementation, monitoring, and
   evaluation record when a policy decision is intended to affect real-world
   outcomes. The record defines observation windows, indicators, trigger
   thresholds, data sources, review cadence, and responsible owners.
4. DDM shift, degradation, readiness, incident, and root-cause events are
   mandatory lifecycle evidence when monitoring is in scope for the authority
   profile. These events must reference the case, affected claims, affected
   evidence lines, and downstream readiness or publication status.
5. Ex-post outcome reassessment compares forecast claims, uncertainty ranges,
   implementation assumptions, realized outcomes, external shocks, and missed
   assumptions. The result is recorded as confirmation, refutation,
   supersession, inconclusive evidence, or an accepted data-deficit state.
6. Calibration is a case-system track-record ledger, not a substitute for the
   current case. It records prediction interval coverage, forecast bias,
   realized-versus-predicted effect error, reversal/retraction rates, and
   severe-miss causes by domain, jurisdiction, method family, data class,
   evidence mode, and authority profile.
7. Weak calibration may alter future evidence budgets, authority profile
   eligibility, reviewer escalation, or required uncertainty width, but it may
   not backfill missing evidence in the current case.
8. Learning records derived from ex-post reassessment must name scope,
   applicability, revocation conditions, and memory-contamination controls
   before they influence future runs.
9. Scorecard and readiness gates must fail when lifecycle, monitoring,
   DDM, ex-post, or calibration evidence is required by authority profile and
   is missing, stale, contradictory, or only narrative.

## Consequences

Positive:

- Published cases remain historically auditable while still supporting
  amendment, supersession, recall, and retraction.
- PolicyOS can learn from outcomes without pretending that a new observation
  was present at publication time.
- Calibration can constrain future high-authority runs in domains where the
  system has a weak track record.
- DDM and continuous governance become part of case authority rather than
  detached operational reports.

Negative:

- Publication creates long-lived monitoring obligations.
- Ex-post data may be incomplete, delayed, or confounded by implementation
  changes and external shocks.
- Calibration records can expose weak domains or method families, which may
  block high-authority reuse until remediation lands.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- case lifecycle event schemas and append-only transition checks;
- implementation, monitoring, and evaluation records;
- DDM monitoring bridge records for shift, degradation, readiness, incident,
  and root-cause evidence;
- ex-post outcome reassessment records;
- calibration ledger and calibration governance records;
- scorecard/readiness checks for missing monitoring plans, missing DDM events,
  stale lifecycle state, historical rewrite attempts, missing reassessment, weak
  calibration blockers, and learning-record contamination risk.

## Related Decisions

- Extends: ADR-0149 Effective Mode And Fallback Degradation Ledger.
- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Extends: ADR-0160 Evidence Portfolio, Independence Map, Multiverse, And
  Synthesis.
- Related: ADR-0154 Diagnostic Event Envelope And Runtime Log Contract.
- Related: ADR-0161 Claim Argument, Warrant Reliability, And Compiler Closeout
  Gate.
- Related: ADR-0162 Human Oversight, Publication, And External Audit Authority.
- Related: ADR-0164 Run Cost, Proportionality, And Evidence Budget Governance.
