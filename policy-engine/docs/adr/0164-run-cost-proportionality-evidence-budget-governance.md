# ADR-0164: Run Cost, Proportionality, And Evidence Budget Governance

## Status

Accepted

## Date

2026-05-18

## Context

ADR-0160 requires a major empirical claim to use a predeclared evidence
portfolio, independence map, multiverse/specification curve, disconfirming
evidence, synthesis, and stopping rules unless the active profile accepts an
explicit deficit. That contract is incomplete without proportionality:
low-impact decisions should not spend unbounded compute or reviewer time, and
high-impact decisions should not claim maturity after a shallow run.

The Policy Design Case SDD names run cost, best-in-class benchmarking, human
team comparison, and decision-cycle proportionality as success criteria. The
repository already has runtime budgets, provider cost tracking, Foundry cost
and method-selection surfaces, Scientist budgets, and performance metrics that
can become the first implementation sources.

Without an ADR, later code could treat cost as an operations concern detached
from policy authority, or could use cost pressure to waive non-overridable
evidence duties.

## Decision

1. Serious policy runs require a run cost and proportionality record whenever
   they execute a Policy Design Case beyond exploratory draft authority.
2. The record names the decision risk, public-impact class, requested authority
   profile, evidence-depth expectation, compute budget, provider budget,
   elapsed-time budget, storage/audit budget, human-review burden,
   consultation burden when in scope, and expected marginal value of additional
   evidence.
3. Evidence portfolio design includes an evidence budget before producer
   execution. The budget defines candidate evidence depth, method diversity,
   multiverse breadth, severe-test expectations, stopping rules, and escalation
   triggers.
4. Spending beyond budget requires a runtime-linked change record. Finishing
   materially under budget requires either proof that stopping rules were met
   or an explicit assurance deficit visible to downstream surfaces.
5. Proportionality may scope optional evidence depth, but it cannot waive
   non-overridable substrate, producer, claim, publication, lifecycle, or
   formal-invariant duties required by the active authority profile.
6. Low-impact or research-profile runs may accept proportionality deficits only
   when the deficit names what was not done, why the authority profile permits
   it, and which downstream claims or publication states are blocked.
7. Best-in-class benchmarking records compare PolicyOS cost, cycle time,
   error rate, evidence depth, auditability, reversal rate, and calibration
   against matched expert human-team or historical baseline tasks when such
   benchmarks are in scope.
8. Scorecard and readiness gates must fail when cost/proportionality evidence
   is missing, hidden, mismatched to authority profile, used to waive a
   non-overridable duty, or inconsistent with the evidence portfolio and
   stopping-rule record.

## Consequences

Positive:

- Evidence depth becomes explainable relative to decision risk and public
  impact.
- Cost pressure produces explicit deficits instead of silent shortcuts.
- Benchmarking can show whether PolicyOS is better, faster, cheaper, or more
  auditable than expert human policy teams on matched tasks.
- Portfolio stopping rules become governance decisions rather than ad hoc
  compute limits.

Negative:

- Runs need additional planning records before expensive evidence collection.
- Benchmarking can reveal that PolicyOS is not yet best-in-class in a domain.
- Proportionality rules require careful authority-profile design so low-impact
  efficiencies do not leak into high-impact publication decisions.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- run cost and proportionality records;
- evidence-budget fields on portfolio design records;
- provider, compute, elapsed-time, storage, audit, reviewer, and consultation
  burden projections;
- budget change records and under-budget deficit records;
- best-in-class benchmarking records and baseline selection rules;
- scorecard/readiness checks for missing budget, over-budget without change
  authority, under-budget without stopping-rule proof, disproportional evidence
  depth, and prohibited cost-based waivers.

## Related Decisions

- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Extends: ADR-0157 Policy Intent Envelope, Capability Ledger, And Authority
  Profile Mapping.
- Extends: ADR-0160 Evidence Portfolio, Independence Map, Multiverse, And
  Synthesis.
- Related: ADR-0161 Claim Argument, Warrant Reliability, And Compiler Closeout
  Gate.
- Related: ADR-0163 Lifecycle, DDM, Ex-Post Outcomes, And Calibration.
- Related: ADR-0165 Formal Policy Case And Substrate Invariant Specs.
