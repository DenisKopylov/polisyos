# ADR-0171: Review Effectiveness Telemetry Advisory First

## Status

Accepted

## Date

2026-05-22

## Context

Universal Policy Design Case execution needs to measure whether human review is
effective without turning early measurement into premature publication or
closeout authority.

The repository already has review and oversight primitives in
`src/polisyos/runtime/quality/human_review.py`, production approval packet
integration, human-review calibration reports, reviewer burden summaries,
override packet checks, producer/reviewer independence fields, and dashboard
projection. The missing decision is not whether review telemetry exists. The
missing decision is whether early review-effectiveness thresholds can block.

The research synthesis for C24 and FT-ADR-06 says they cannot. Review time,
override rate, dissent, no-delta reviews, and separation-of-duty failures are
measured signals first. Blocking consequences require longitudinal evidence and
a mature governed policy. Without this boundary, PolicyOS would recreate P04,
P05, P09, P10, and P13: warning-like measurement would become a hidden status
lattice, scorecard authority would be diluted, and review could become
ceremonial surveillance theater rather than effective oversight.

This ADR ratifies W0.F FT-ADR-06 from the Universal Policy Design Case
implementation plan.

Source traceability is repo-owned:

- raw ledger:
  `docs/research/universal-policy-design/deep-research-reports-105-146-combined.md`
- normalized synthesis:
  `docs/backlog/universal-policy-design-case-research-results-consolidation.md`
- research plan:
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md`
- implementation plan:
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md`
- W0.G source ownership:
  `docs/reference/policy-design-case-source-ownership.md`

## Decision

1. Review-effectiveness telemetry is collected from existing review metadata
   before it has blocking consequences.
2. The initial measured signals are:
   `review_time_seconds_average`, `review_time_seconds_median`,
   `low_time_review_count`, `override_rate`, `override_count`,
   `dissent_rate`, `dissent_count`, `no_delta_review_rate`,
   `no_delta_review_count`, `separation_of_duty_failure_rate`, and
   `separation_of_duty_failure_count`.
3. Threshold outcomes remain visible as `quality_signals` and
   `review_effectiveness_telemetry.threshold_status`, but they are advisory by
   default.
4. Advisory review-effectiveness telemetry is authoritative for measuring
   review behavior, future calibration, and reviewer-load observability. It is
   not authoritative for current-run closeout block, publication block, or
   claim-support downgrade.
5. Blocking is permitted only when a `HumanReviewEffectivenessPolicy` has:
   `maturity = mature_governed`, `blocking_enabled = true`, `policy_ref`, and
   `longitudinal_evidence_ref`.
6. Scorecard and closeout consumers must enforce the same boundary by treating
   advisory review telemetry as non-blocking even when measured thresholds
   fail.
7. Missing human-review artifacts, missing runtime refs, missing authority
   envelopes, or missing effective-oversight records remain separate closeout
   failures. This ADR demotes only early review-effectiveness telemetry, not
   provenance, record presence, or publication-oversight requirements.

## Structural Commitment

Runtime review reports must expose a `review_effectiveness_telemetry` object
with:

- `schema_version`;
- `adr_ref`;
- `threshold_status`;
- `posture`;
- `blocking_permitted`;
- `report_status_effect`;
- `policy`;
- `authority_boundary`;
- `measured_signals`;
- `advisory_signal_codes`;
- `blocking_signal_codes`.

The canonical producer is `build_human_review_calibration_report(...)` in
`polisyos.runtime.quality.human_review`. The public projection is
`human_review_public_export(...)`.

The consumer rule is:

```text
if review_effectiveness_policy permits blocking:
  report status follows threshold status
else:
  report status remains pass for review-effectiveness threshold failures
  threshold failures remain visible as advisory measurement
```

This is an `extend_existing` implementation over the existing human-review
calibration owner. It does not introduce a second review telemetry subsystem.

## Tuned Parameter

These values are governed configuration, not structural truth:

- review-time minimums;
- override-rate warning or failure cutoffs;
- dissent, no-delta, and change-request cutoffs;
- separation-of-duty failure cutoffs;
- rubber-stamp scoring weights;
- minimum sample size and observation window for maturity promotion;
- longitudinal evidence requirements;
- owner-specific reviewer-load or burden thresholds.

Changing these values does not require a new ADR if the advisory-first boundary
and maturity requirements remain unchanged. Promoting a threshold to blocking
requires governed config with owner, version, rollback path, and longitudinal
promotion evidence.

## Authority Boundary

Review-effectiveness telemetry may be authoritative for:

- which review events were measured;
- aggregate review time;
- override rate and override correctness;
- dissent and change-request rates;
- no-delta review rate;
- separation-of-duty failure rate;
- future review-policy calibration;
- reviewer burden and load observability.

Advisory review-effectiveness telemetry may not be authoritative for:

- current-run closeout block;
- publication block;
- claim-support downgrade;
- legal, data, method, participation, or evidence authority;
- replacing a required effective human-oversight record;
- replacing runtime provenance, authority envelope, CAS, or diagnostic-event
  evidence.

A mature governed policy may allow review-effectiveness threshold failures to
become closeout inputs only after the runtime report declares
`blocking_permitted = true`.

## Negative Laundering Test

Implementation must include a negative test where telemetry shows bad review
behavior but cannot block because policy maturity is still advisory:

- high override rate;
- low review time;
- no dissent;
- no-delta review;
- separation-of-duty failure;
- failed threshold signals.

The expected result is:

- `review_effectiveness_telemetry.threshold_status = fail`;
- `review_effectiveness_telemetry.posture = advisory`;
- every review-effectiveness quality signal has `blocking = false`;
- scorecard closeout remains unblocked when all non-telemetry authority
  evidence is valid.

The current tests are:

- `tests/unit/runtime/quality/test_human_review.py::test_review_effectiveness_telemetry_is_advisory_until_governed_policy_matures`
- `tests/unit/runtime/quality/test_scorecard.py::test_review_effectiveness_telemetry_cannot_block_without_mature_policy`

## Feature Flag / Advisory Posture

Initial posture is advisory:

- `HumanReviewEffectivenessPolicy.maturity = early_advisory`;
- `blocking_enabled = false`;
- missing `policy_ref` or `longitudinal_evidence_ref` prevents blocking even if
  an operator accidentally sets `blocking_enabled = true`.

The promotion posture is governed blocking:

- `maturity = mature_governed`;
- `blocking_enabled = true`;
- `policy_ref` points to the governed policy version;
- `longitudinal_evidence_ref` points to calibration or corpus evidence
  supporting the threshold.

No feature flag may bypass the maturity and evidence checks.

## Revision Path

A new ADR is required to:

- remove the advisory-first default;
- allow review-effectiveness telemetry to block without longitudinal evidence;
- change the authority meaning of advisory telemetry;
- let telemetry replace effective human-oversight records;
- let review telemetry downgrade claim support directly;
- remove the `policy_ref` or `longitudinal_evidence_ref` requirement for
  blocking.

Config changes are sufficient to tune thresholds, scoring weights, sample-size
requirements, owners, and observation windows when the advisory-first boundary
remains intact.

## Affected E Tasks

This ADR unblocks:

- E19 Self-FMEA, Soft-Gate, Review, And Complexity Controls, for
  review-effectiveness telemetry collection.

It constrains:

- E3 closeout readers, because advisory telemetry cannot become closeout
  authority before maturity;
- E5 dashboard and export surfaces, because public projections must show the
  signal as advisory unless blocking is permitted;
- E20 calibration, because longitudinal evidence is the promotion path;
- E22 semantic evaluation, because negative tests must include review telemetry
  laundering attempts.

## Validation

The ADR itself is validated by docs lifecycle gates:

```bash
uv run pytest tests/repo_quality/tools/test_docs_lifecycle.py tests/repo_quality/tools/test_docs_gate.py -q
```

Runtime behavior is validated by:

```bash
uv run pytest tests/unit/runtime/quality/test_human_review.py -q
uv run pytest tests/unit/runtime/quality/test_scorecard.py::test_review_effectiveness_telemetry_cannot_block_without_mature_policy -q
```

## Capability Reality And Pattern Pass

Reuse classification: `extend_existing`. The existing human-review calibration
report, production approval packet checks, scorecard, and public export are
the correct owners. This ADR extends them with advisory-first
review-effectiveness telemetry instead of creating a parallel review subsystem.

Relevant anti-patterns:

- P04 status lattice gap: failed review-effectiveness thresholds must not
  become hidden closeout blockers before a mature governed policy exists.
- P05 authority dilution: telemetry measures review behavior; it cannot replace
  required oversight records or producer evidence.
- P09 warning lifecycle gap: advisory signals must remain visible with posture,
  policy, and blocking metadata.
- P10 semantic adequacy gap: tests must prove bad review behavior is measured
  without blocking in advisory mode.
- P13 governance gravity: early telemetry remains measurement and calibration
  evidence until longitudinal data justifies stronger consequences.
- P15 LLM speculation laundering: summaries of review quality cannot replace
  measured review events or governed policy evidence.

Existing anti-pattern found: human-review quality signals already existed, but
without a ratified maturity boundary they could be treated as blocking status
too early. That was a `status lattice` and `authority boundary` risk.

Target correct pattern: review-effectiveness telemetry is measured and exposed
immediately, every signal carries blocking metadata, and closeout/publication
blocking is permitted only with `mature_governed` policy plus policy and
longitudinal evidence refs.

Missing capability labels after this ADR and W0.F bridge:
`surface_missing` for broader dashboard/API exposure and `semantic_test_missing`
for future E22 semantic packs. The current producer and scorecard consumers
cover the advisory-not-blocking negative, while E19/E22 still need their wider
runtime-quality and semantic-evaluation surfaces.

Acceptance signal: later work can cite ADR-0171, collect review time, override,
dissent, no-delta, and separation-of-duty telemetry, and prove threshold
failures cannot block without a mature governed policy.

## Consequences

Positive:

- Review telemetry becomes visible without premature gates.
- E19 can collect longitudinal evidence immediately.
- Scorecard consumers enforce the same authority boundary as the producer.
- Missing provenance and missing oversight records remain hard failures.
- Future threshold promotion has a clear governance and rollback path.

Negative:

- Operators may see severe advisory review signals that do not block yet.
- Dashboards and exports must explain advisory posture without hiding risk.
- Mature blocking policy requires real longitudinal evidence before promotion.

## Concrete impact

This ADR requires implementation work to introduce or update:

- `HumanReviewEffectivenessPolicy`;
- `review_effectiveness_telemetry` in human-review calibration reports;
- advisory `blocking = false` review-effectiveness quality signals by default;
- mature governed blocking behavior behind policy maturity and evidence refs;
- public export of telemetry posture and authority boundary;
- scorecard regression tests proving advisory telemetry cannot block;
- docs explaining that review-effectiveness telemetry differs from required
  human-review provenance and oversight records.

## Related Decisions

- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Extends: ADR-0162 Human Oversight, Publication, And External Audit
  Authority.
- Extends: ADR-0163 Lifecycle, DDM, Ex-Post Outcomes, And Calibration.
- Extends: ADR-0165 Formal Policy Case And Substrate Invariant Specs.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0154 Diagnostic Event Envelope And Runtime Log Contract.
- Related: ADR-0164 Run Cost, Proportionality, And Evidence Budget Governance.
