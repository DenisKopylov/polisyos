---
title: Honest Diagnostics Substrate Decision Log
status: active append-only log
owner: team-architecture
created: 2026-05-15
source_decision: honest-diagnostics-substrate.md
---

# Honest Diagnostics Substrate Decision Log

This log captures small implementation decisions and deferred open questions for
the honest diagnostics substrate. ADR 0147-0155 remain the stable architecture
layer. Entries here must not narrow those ADRs unless they are later promoted
through the ADR process.

## Append-Only Rule

Entries are append-only. Do not rewrite prior entries to change history. When a
decision changes, append a new entry that references the older entry and marks
the older decision as superseded in the new context.

Use the log for local, bounded, or reversible implementation choices. Promote a
decision to ADR when it changes cross-component contract semantics, public
evidence semantics, security/privacy posture, override policy, or compatibility
guarantees.

Quarterly, review accumulated entries and either promote, retire, or mark them
as superseded through a later entry.

## Append-Only Entry Template

Copy this template for new entries under `## Entries`.

```markdown
### DL-HDS-0000 - short decision title

- **Date**: YYYY-MM-DD
- **Context**: Why this decision is needed and what source question, phase, or incident raised it.
- **Decision**: The decision made, or the open question retained with the current constraint.
- **Affected ADR**: ADR-0147, ADR-0148, ADR-0149, ADR-0150, ADR-0151, ADR-0152, ADR-0153, ADR-0154, ADR-0155, or a subset.
- **Affected invariant id or phase id**: HDS invariant id, ADR decision bullet, phase id, or plan wave.
- **Owner**: team or role accountable for revisiting the entry.
- **Reversibility**: reversible, costly_to_reverse, or irreversible.
- **Revisit trigger**: Concrete event that forces review.
- **Revisit wave**: after Wave N, quarterly review, or immediate if violated.
- **Promotion status**: log_only_pending_revisit, needs_adr, promoted_to_ADR-XXXX, retired, or superseded_by_DL-HDS-XXXX.
```

## Imported Source Open Questions

Imported from
`docs/system-design-decisions/honest-diagnostics-substrate.md` on 2026-05-15:

1. Which substrate record becomes the primary CAS object for each run: one composite authority graph, separate ledgers, or both?
2. Should provenance vocabulary be one global enum or a registry-scoped enum with subsystem extensions?
3. Which blockers are categorically non-overridable, and which can accept a signed production exception?
4. Should dashboard projection source labels be part of the runtime API contract or dashboard-only rendering metadata?
5. How much historical bundle evidence should be migrated versus treated as legacy non-authoritative evidence?
6. Which ADRs should this design split into after review?
7. Which diagnostic SLIs are strong enough to quarantine production closeout?
8. Which evidence events must be never-sampled for serious runs?
9. Which semantic binding failures are non-overridable?
10. How should claim-argument-evidence cases be represented in CAS without duplicating scorecard logic?

## Entries

### DL-HDS-0001 - evidence authority envelope serialization details

- **Date**: 2026-05-15
- **Context**: Imports source open questions 1, 2, and 10 about the primary CAS authority record, provenance vocabulary scope, and claim-argument-evidence representation.
- **Decision**: Keep serialization details open until Wave 1 proves the authority envelope contract, then decide whether the CAS authority object is composite, ledger-based, or both.
- **Affected ADR**: ADR-0147, ADR-0152, ADR-0155
- **Affected invariant id or phase id**: HDS invariants 1 and 2; Phase 1.1; Phase 1.8
- **Owner**: team-runtime-quality
- **Reversibility**: reversible
- **Revisit trigger**: Wave 1 authority envelope, schema compatibility, source-truth, and proof-harness contracts exist with CAS/event reconciliation examples.
- **Revisit wave**: after Wave 1
- **Promotion status**: log_only_pending_revisit

### DL-HDS-0002 - event-log persistence boundary

- **Date**: 2026-05-15
- **Context**: Imports source open questions 4 and 8 about projection-source labeling and never-sampled serious-run evidence events.
- **Decision**: Keep the persistence boundary open until Wave 2 proves runtime event-log writes and phase barriers, then decide which labels belong in runtime API events versus dashboard-only metadata.
- **Affected ADR**: ADR-0150, ADR-0154
- **Affected invariant id or phase id**: HDS invariants 4 and 5; Phase 2.2; Phase 2.3
- **Owner**: team-observability
- **Reversibility**: reversible
- **Revisit trigger**: Wave 2 append-only event log, runtime phase barriers, and trace-linked diagnostic events are implemented and tested.
- **Revisit wave**: after Wave 2
- **Promotion status**: log_only_pending_revisit

### DL-HDS-0003 - legacy evidence migration cutoff

- **Date**: 2026-05-15
- **Context**: Imports source open question 5 about historical bundle evidence migration versus legacy non-authoritative quarantine.
- **Decision**: Treat migration cutoff policy as open until Wave 4 schema migration work proves which historical evidence can be upgraded without weakening serious closeout semantics.
- **Affected ADR**: ADR-0151
- **Affected invariant id or phase id**: HDS invariant 3; Phase 4.3; Phase 4.3A
- **Owner**: team-architecture
- **Reversibility**: reversible
- **Revisit trigger**: Wave 4 schema migration and migration sandbox produce compatibility evidence for legacy bundle classes.
- **Revisit wave**: after Wave 4
- **Promotion status**: log_only_pending_revisit

### DL-HDS-0004 - diagnostic SLO thresholds

- **Date**: 2026-05-15
- **Context**: Imports source open question 7 about which diagnostic SLIs are strong enough to quarantine production closeout.
- **Decision**: Keep threshold values open until Wave 4 assurance and SLO work can bind quarantine behavior to measured diagnostic reliability instead of guessed numbers.
- **Affected ADR**: ADR-0153
- **Affected invariant id or phase id**: HDS invariant 3; Phase 4.4; Phase 4.6
- **Owner**: team-assurance
- **Reversibility**: reversible
- **Revisit trigger**: Wave 4 assurance case, SLO registry, and attestation wiring expose measurable evidence completeness, trace continuity, stale-evidence rate, and blocker quality.
- **Revisit wave**: after Wave 4
- **Promotion status**: log_only_pending_revisit

### DL-HDS-0005 - attestation coverage expansion

- **Date**: 2026-05-15
- **Context**: Imports source open questions 3, 6, and 9 about non-overridable blockers, ADR split candidates, and non-overridable semantic binding failures.
- **Decision**: Keep attestation expansion open until Wave 5 adversarial controls prove which blockers and semantic failures require non-overridable attestations or ADR promotion.
- **Affected ADR**: ADR-0148, ADR-0149, ADR-0152, ADR-0153, ADR-0155
- **Affected invariant id or phase id**: HDS invariants 3 and 4; Phase 5.1; Phase 5.6
- **Owner**: team-architecture-governance
- **Reversibility**: reversible
- **Revisit trigger**: Wave 5 spoofing, partial-state, multi-tenant, replay-drift, resilience-lane, and metamorphic controls have produced blocker coverage evidence.
- **Revisit wave**: after Wave 5
- **Promotion status**: log_only_pending_revisit

### DL-HDS-0006 - CI tier budgets

- **Date**: 2026-05-15
- **Context**: Carries the Phase 0.5 open governance question for CI tier budgets from the implementation plan's CI Tiers And Test Budget section.
- **Decision**: Keep CI budget tuning open until Wave 5 shows the cost of adversarial controls, then decide whether fast-pr, integration-pr, nightly, and weekly-closeout budgets remain realistic.
- **Affected ADR**: ADR-0153, ADR-0155
- **Affected invariant id or phase id**: Phase 0.5; CI Tiers And Test Budget; Wave 5 exit fence
- **Owner**: team-quality-closeout
- **Reversibility**: reversible
- **Revisit trigger**: Wave 5 negative controls and proof-harness enforcement have stable timing data across fast-pr, integration-pr, nightly, and weekly-closeout lanes.
- **Revisit wave**: after Wave 5
- **Promotion status**: log_only_pending_revisit
