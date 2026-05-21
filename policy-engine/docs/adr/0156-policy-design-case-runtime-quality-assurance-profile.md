# ADR-0156: Policy Design Case Runtime Quality Assurance Profile

## Status

Accepted

## Date

2026-05-16

## Context

Pass 1A and Pass 1B diagnostics show that PolicyOS needs a primary policy
design object that can connect intent, concepts, legal authority, data,
literature, methods, options, claims, publication, and ex-post learning. The
system design decision in
`docs/system-design-decisions/policy-design-best-in-class-operating-model.md`
calls this object the Policy Design Case.

The repository already has a runtime assurance-case and quality substrate in
`src/polisyos/runtime/quality`, including `assurance_case.py`, authority
records, semantic binding, prompt/tool ledgers, performance budgets, approval,
human review, attestation, degradation, public export, metamorphic controls,
phase barriers, invariants, scorecards, schema compatibility, effective mode,
source-of-truth records, event logs, and replay.

If implementation plans create a second serious-run case object beside
`runtime/quality`, PolicyOS will split authority between the honest diagnostics
substrate and the policy-domain pipeline. That would recreate the ambiguity the
substrate was built to remove.

## Decision

1. The Policy Design Case is a runtime quality assurance-case profile, not a
   parallel report graph or a second serious-run authority object.
2. `src/polisyos/runtime/quality/assurance_case.py` and adjacent
   `runtime/quality` modules are the first implementation surface for the
   runtime-owned case authority.
3. Policy-domain records extend that runtime assurance case with policy
   semantics: intent, concept spine, legal authority, source evidence,
   Scholar literature evidence, method validity, evidence portfolios, options,
   objectives, tradeoffs, claims, publication, lifecycle, calibration, and
   ex-post evidence.
4. The case model must preserve assurance-case structure: claim, subclaim,
   argument, warrant, context, assumption, evidence, rebuttal, counter-evidence,
   assurance deficit, and residual uncertainty are distinct inspectable nodes.
5. The case must be mappable to SACM/CAE/GSN concepts. PolicyOS may keep an
   internal schema only if it has a documented export or mapping contract.
6. Every authority-bearing Policy Design Case record must remain compatible
   with the honest diagnostics substrate: CAS-addressed, runtime-event-linked,
   schema-versioned, tenant-scoped, effective-mode-aware, and readable by
   scorecard/readiness gates.
7. A new case package, schema family, or authority ledger that overlaps
   `runtime/quality` requires a later ADR with a rejected-reuse finding.

## Consequences

Positive:

- Serious policy runs have one authority chain from runtime event to case,
  scorecard, readiness, approval, and public export.
- Implementation plans can add policy semantics without weakening substrate
  invariants.
- External audit can reason about PolicyOS as a claim-argument-evidence system
  rather than a bundle of unrelated reports.
- Existing runtime quality work is reused instead of duplicated.

Negative:

- `runtime/quality` becomes a central architecture surface for both substrate
  and policy-domain work.
- Policy-domain schemas must respect substrate constraints even when that makes
  early implementation slower.
- The assurance-case mapping needs careful migration so existing diagnostic
  scorecards do not become policy-domain theory containers.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- Policy Design Case schema facets in or over `src/polisyos/runtime/quality`;
- assurance-case node mapping for claim, argument, warrant, evidence, rebuttal,
  counter-evidence, and deficit records;
- SACM/CAE/GSN mapping or exporter documentation;
- scorecard/readiness checks that reject policy claims with missing
  assurance-case structure;
- tests that fail when a parallel serious-run case object bypasses
  `runtime/quality`.

## Related Decisions

- Extends: ADR-0147 Production Evidence Authority Ordering.
- Extends: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Extends: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Extends: ADR-0153 Diagnostic SLOs, Assurance Case, And Attestation.
- Extends: ADR-0155 Production Invariant Registry And Ownership Contract.
- Related: ADR-0157 Policy Intent Envelope, Capability Ledger, And Authority
  Profile Mapping.
- Related: ADR-0161 Claim Argument, Warrant Reliability, And Compiler Closeout
  Gate.
