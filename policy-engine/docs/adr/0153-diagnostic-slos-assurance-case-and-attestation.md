# ADR-0153: Diagnostic SLOs, Assurance Case, And Attestation

## Status

Accepted

## Date

2026-05-14

## Context

The first honest-diagnostics ADRs define the authority chain, runtime state,
mode/fallback semantics, scorecard boundaries, schema compatibility, and
semantic binding. That is enough to start a substrate implementation slice, but
it does not fully define how PolicyOS will keep diagnostic honesty reliable
over years.

Large systems regress when diagnostics are treated as background tooling. A
monitoring failure, false pass, over-redaction, missing negative control, stale
postmortem action, or unverifiable producer step can put the organization back
into the same self-deception loop. The diagnostic substrate must therefore have
its own reliability, assurance, and attestation model.

## Decision

1. The diagnostic substrate has SLOs. Candidate SLIs include complete authority
   graph rate, required runtime-ref verification rate, trace continuity,
   provenance coverage, fallback ledger coverage, schema compatibility coverage,
   semantic binding coverage, operator time-to-root-cause, stale evidence rate,
   false-pass rate from negative controls, false-block rate from positive
   controls, and redaction coverage.
2. Production closeout may be quarantined or downgraded when diagnostic SLOs
   burn budget. Diagnostic reliability is a production dependency, not an
   optional metric.
3. Every observed self-deception failure mode becomes a diagnostic fitness
   function until explicitly retired by ADR. Fitness functions include positive
   controls, negative controls, spoofing tests, mutation tests, metamorphic
   tests, and expected failure codes.
4. Production-quality decisions should have an assurance-case view. The case
   records top-level claim, subclaims, argument strategy, evidence refs,
   assumptions, contexts, defeaters, residual uncertainty, confidence limits,
   non-overridable blockers, and reviewer attribution.
5. The assurance case is not a replacement scorecard. It is an explanation
   layer over the authority graph that shows why a production claim is
   supported, blocked, or out of scope.
6. Evidence-generating steps that affect serious closeout must be attestable
   when their trust boundary requires it. Attestation records expected
   materials, observed materials, expected products, observed products,
   functionary, producer key or identity, environment identity, isolation
   status, service-generated status, consumer verification, and tamper check
   status.
7. Diagnostic records must be privacy-safe. Redaction must protect secrets,
   hidden benchmark answers, provider credentials, sensitive legal/workflow
   payloads, and unsafe public data while preserving enough structure to
   diagnose authority.
8. This ADR defines the assurance layer. It is accepted architecture, but it
   does not require the first substrate implementation slice to complete all
   assurance features before authority/envelope/state/mode/fallback/schema
   foundations exist.

## Consequences

Positive:

- Diagnostic honesty becomes measurable and regressions become visible.
- Negative controls protect against the exact self-deception modes already
  observed in the system.
- Policy decisions can be explained as claim-argument-evidence cases instead
  of flat checklist passes.
- Producer trust, tamper resistance, redaction, and public export can be
  reasoned about without weakening the core authority chain.

Negative:

- The assurance layer adds ongoing maintenance burden.
- SLOs and fitness functions can initially increase visible failure volume.
- Attestation and redaction may raise storage, key-management, and retention
  complexity.
- The first implementation slice must preserve extension points even if it does
  not implement the full assurance layer.

## Concrete impact

This ADR does not define an implementation plan. It requires future
implementation work to introduce or update:

- diagnostic SLI/SLO definitions;
- diagnostic error-budget policy;
- fitness function registry;
- positive and negative control suites;
- assurance-case schema;
- diagnostic attestation records;
- privacy-safe redaction and public-export diagnostic contracts;
- checks for false-pass, false-block, missing negative control, stale
  postmortem action, unattested producer step, and redaction that either leaks
  protected data or removes diagnostic meaning.

## Related Decisions

- Extends: ADR-0006 SLO Definitions for Scientist DAG.
- Extends: ADR-0010 CAS Artifact Signing.
- Extends: ADR-0116 OTel-First Observability.
- Extends: ADR-0128 Hermetic Reproducibility.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0148 Serious Run State Machine And Phase Barriers.
- Related: ADR-0149 Effective Mode And Fallback Degradation Ledger.
- Related: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Related: ADR-0151 Evidence Schema Compatibility And Legacy Quarantine.
- Related: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.

