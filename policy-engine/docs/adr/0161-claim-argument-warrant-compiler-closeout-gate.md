# ADR-0161: Claim Argument, Warrant Reliability, And Compiler Closeout Gate

## Status

Accepted

## Date

2026-05-16

## Context

Pass 1A diagnostics found that final claims can be minted without data refs,
method refs, legal norm refs, objective refs, numerical semantics, portfolio
refs, or typed blockers. The honest diagnostics substrate can prove whether
evidence is runtime-owned, but the claim compiler still needs a policy-domain
contract for when a claim is allowed to exist as a serious case node.

A later design review also found that a Policy Design Case must be an explicit
assurance case: evidence refs are not enough. A claim needs an argument and a
warrant that explain why the evidence supports the claim, under which
assumptions, against which rebuttals, and with which deficits.

The repository also contains `src/polisyos/berl`, a bounded explanation
reliability layer with explanation bundles, validation thresholds, empirical
reliability bounds, and local infidelity diagnostics. When explanations affect
reviewer trust or claim acceptance, those reliability bounds should be part of
the warrant record.

## Decision

1. The claim compiler may mint a serious major claim only as a Policy Design
   Case assurance node with required refs or typed blockers.
2. A major claim records claim id, assurance-case node id, policy concept refs,
   legal norm refs, source/data refs, Scholar literature refs or literature
   deficits, method refs, evidence portfolio refs, independence-map refs,
   multiverse/specification-curve refs, disconfirming evidence refs, synthesis
   report refs, objective/tradeoff refs, uncertainty refs, numerical semantics
   refs, and implementation/monitoring refs when in scope.
3. A major claim records an argument strategy and warrant explaining why those
   refs support the claim, what assumptions are needed, where the claim applies,
   and which limitations remain.
4. Rebuttals, counter-evidence, requester-capture challenge results,
   single-line-evidence deficits, unresolved assurance deficits, and blockers
   are first-class claim-adjacent records.
5. BERL explanation reliability evidence is required when an explanation or
   warrant is used to support reviewer trust, automated claim acceptance, or
   user-facing confidence. The record includes the relevant explanation bundle,
   validation result, empirical bound, local infidelity diagnostic when
   applicable, and threshold decision.
6. The claim compiler must not backfill missing producer evidence from prose,
   dashboard state, static inventory, or bundle-local files.
7. Scorecard and readiness gates must fail when a major claim has evidence refs
   but lacks argument, warrant, rebuttal/counter-evidence assessment, accepted
   assurance deficit, or required BERL reliability evidence.
8. Claims in exploratory or research profiles may carry accepted deficits, but
   those deficits must be visible to downstream surfaces and cannot be upgraded
   silently to governed or production authority.

## Consequences

Positive:

- Final claims become auditable reasoning objects instead of decorated prose.
- Reviewers can challenge the warrant, not only the underlying evidence refs.
- Counter-evidence and deficits remain visible instead of being smoothed into a
  recommendation.
- BERL reliability bounds reduce overtrust in explanation-shaped outputs.

Negative:

- The compiler must carry more structured inputs and blockers.
- Some currently useful narrative outputs will lose serious-run authority until
  their warrants and deficits are explicit.
- BERL thresholds need governance because explanation reliability can affect
  claim acceptance and human review behavior.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- claim argument and warrant schema;
- claim-to-portfolio, claim-to-synthesis, claim-to-norm, claim-to-source,
  claim-to-method, claim-to-objective, and claim-to-uncertainty refs;
- rebuttal, counter-evidence, assurance-deficit, and blocker records;
- BERL explanation reliability refs for applicable warrants;
- claim compiler checks that reject missing producer evidence and prose
  backfill;
- scorecard/readiness checks for unsupported claim, evidence-without-argument,
  missing BERL reliability evidence, hidden counter-evidence, and silent
  promotion of research deficits.

## Related Decisions

- Extends: ADR-0129 Scientist Claim Ledger.
- Extends: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Extends: ADR-0153 Diagnostic SLOs, Assurance Case, And Attestation.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Related: ADR-0160 Evidence Portfolio, Independence Map, Multiverse, And
  Synthesis.
