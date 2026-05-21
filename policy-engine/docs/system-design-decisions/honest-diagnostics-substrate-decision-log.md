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

### DL-HDS-0007 - strict xfail carry-forward for open red controls

- **Date**: 2026-05-15
- **Context**: Phase 1.10 requires every temporary HDS strict xfail exception to be named by a machine-readable registry entry and reviewed through the decision log while earlier red controls await runtime implementation.
- **Decision**: Allow only the registered `HDS-XFAIL-RED-CONTROLS` strict xfail budget for the current HDS red-control files; any increase or new path must add a new temporary exception tied to an invariant and revisit wave.
- **Affected ADR**: ADR-0147, ADR-0148, ADR-0149, ADR-0150, ADR-0152, ADR-0154, ADR-0155
- **Affected invariant id or phase id**: HDS-MCG-001; Phase 1.10
- **Owner**: team-architecture-governance
- **Reversibility**: reversible
- **Revisit trigger**: The referenced red controls pass without xfail, or any PR adds, moves, broadens, or increases a strict xfail in an HDS substrate test.
- **Revisit wave**: after Wave 2
- **Promotion status**: log_only_pending_revisit

### DL-HDS-0008 - Wave 4 operational closeout evidence

- **Date**: 2026-05-15
- **Context**: Wave 4 requires operational closeout evidence, not only local unit-test pass status. The implementation now requires a fresh serious canary bundle, `policyos.honest_diagnostics.wave4_closeout.v1`, and `check_wave4_operational_closeout.py` before the Wave 4 exit fence can be marked complete.
- **Decision**: Treat the fresh bundle's authority-bearing semantic binding ledger, decision artifact quality report, assurance case, diagnostic SLO report, attestation records, migration sandbox, and redacted public export projection as the Wave 4 closeout evidence set. The two-consecutive-weekly-baseline window is explicitly not a blocker for this closeout per implementation instruction; the report records it as `not_applicable_by_instruction`.
- **Evidence bundle path**: `_build/honest-diagnostics/rebaseline/wave-4`
- **Commands**: `uv run python tools/quality/validation/check_substrate_drift.py --repo-root .`; `uv run python tools/quality/validation/build_honest_diagnostics_coverage.py --repo-root . --output-dir _build/honest-diagnostics/rebaseline/wave-4`; `uv run python tools/quality/validation/check_wave4_operational_closeout.py --repo-root . --bundle-dir <fresh-serious-bundle> --ignore-weekly-baseline-window`
- **Affected ADR**: ADR-0152, ADR-0153
- **Affected invariant id or phase id**: Wave 4 Exit Fence; Phase 4.1; Phase 4.3A; Phase 4.4; Phase 4.5; Phase 4.6
- **Owner**: team-runtime-quality
- **Reversibility**: reversible
- **Revisit trigger**: Any Wave 4 closeout command fails, or any serious bundle uses legacy, projection-only, synthetic, stale, or missing evidence as authority.
- **Revisit wave**: Wave 5
- **Promotion status**: operational_closeout_required

### DL-HDS-0009 - Wave 6 authority envelope disposition

- **Date**: 2026-05-16
- **Context**: Wave 6 closeout binds authority envelope serialization to runtime CAS refs, diagnostic events, schema compatibility, same-input closure, effective mode, fallback/degradation, projection boundaries, and attested producer metadata.
- **Decision**: Close the Wave 1 open question by treating the runtime authority envelope plus CAS manifest and diagnostic event reconciliation as the production authority record.
- **Closes**: DL-HDS-0001
- **Affected ADR**: ADR-0147, ADR-0152, ADR-0155
- **Affected invariant id or phase id**: HDS-MCG-001; HDS-MCG-002; Wave 6
- **Owner**: team-runtime-quality
- **Reversibility**: superseded only by new ADR or accepted decision-log supersession
- **Revisit trigger**: Any final readiness run accepts a bundle-local path, projection, or static inventory row as runtime authority.
- **Revisit wave**: Wave 7
- **Promotion status**: retired

### DL-HDS-0010 - Wave 6 event-log boundary disposition

- **Date**: 2026-05-16
- **Context**: Wave 6 requires every selected serious runtime ref to reconcile to diagnostic events while dashboard projections remain projection-only evidence.
- **Decision**: Close the Wave 2 boundary question by assigning authority to append-only runtime diagnostic events and keeping dashboard-only metadata out of closeout authority.
- **Closes**: DL-HDS-0002
- **Affected ADR**: ADR-0150, ADR-0154
- **Affected invariant id or phase id**: HDS-MCG-001; HDS-MCG-020; Wave 6
- **Owner**: team-observability
- **Reversibility**: superseded only by new ADR or accepted decision-log supersession
- **Revisit trigger**: Event/CAS reconciliation fails or a dashboard projection is used as closeout authority.
- **Revisit wave**: Wave 7
- **Promotion status**: retired

### DL-HDS-0011 - Wave 6 legacy migration disposition

- **Date**: 2026-05-16
- **Context**: Wave 6 serious closeout keeps legacy-compatible payloads in migration sandbox outputs and requires authority-bearing runtime reports for closeout.
- **Decision**: Close the Wave 4 migration cutoff question by quarantining legacy evidence as diagnostic-only unless it is re-emitted with runtime authority metadata.
- **Closes**: DL-HDS-0003
- **Affected ADR**: ADR-0151
- **Affected invariant id or phase id**: HDS-MCG-001; HDS-MCG-003; Wave 6
- **Owner**: team-architecture
- **Reversibility**: superseded only by new ADR or accepted decision-log supersession
- **Revisit trigger**: A legacy bundle is promoted to serious authority without a new runtime CAS ref and compatible schema decision.
- **Revisit wave**: Wave 7
- **Promotion status**: retired

### DL-HDS-0012 - Wave 6 diagnostic SLO disposition

- **Date**: 2026-05-16
- **Context**: Wave 6 inspection and readiness require diagnostic SLO evidence in selected serious bundles and treat missing/stale diagnostic evidence as closeout blockers.
- **Decision**: Close the Wave 4 threshold question by binding SLO readiness to pass records emitted in the diagnostic SLO report and invariant proof harness.
- **Closes**: DL-HDS-0004
- **Affected ADR**: ADR-0153
- **Affected invariant id or phase id**: HDS-MCG-001; HDS-MCG-021; Wave 6
- **Owner**: team-assurance
- **Reversibility**: superseded only by new ADR or accepted decision-log supersession
- **Revisit trigger**: Diagnostic SLO evidence becomes stale or a closeout lane passes with missing diagnostic observations.
- **Revisit wave**: Wave 7
- **Promotion status**: retired

### DL-HDS-0013 - Wave 6 attestation disposition

- **Date**: 2026-05-16
- **Context**: Wave 6 requires attestation records for producer steps, public export, dashboard projection, approval packet, provider/model gateway, and prompt/tool/parser boundaries.
- **Decision**: Close the Wave 5 attestation expansion question by requiring trust-boundary attestation records in serious bundles and preserving semantic-binding failures as non-overridable blockers.
- **Closes**: DL-HDS-0005
- **Affected ADR**: ADR-0148, ADR-0149, ADR-0152, ADR-0153, ADR-0155
- **Affected invariant id or phase id**: HDS-MCG-001; HDS-MCG-008; Wave 6
- **Owner**: team-architecture-governance
- **Reversibility**: superseded only by new ADR or accepted decision-log supersession
- **Revisit trigger**: A serious bundle contains an unattested producer step, semantic binding gap, or non-overridable blocker bypass.
- **Revisit wave**: Wave 7
- **Promotion status**: retired

### DL-HDS-0014 - Wave 6 CI budget disposition

- **Date**: 2026-05-16
- **Context**: Wave 6 final validation runs are sequential to avoid local port and CAS contention while deterministic serious closeout remains non-live.
- **Decision**: Close the Wave 5 CI budget question by keeping dev smoke explicit through `--ci-smoke`, deterministic serious closeout through the canary matrix, and final coverage/anti-drift/readiness checks as separate sequential gates.
- **Closes**: DL-HDS-0006
- **Affected ADR**: ADR-0153, ADR-0155
- **Affected invariant id or phase id**: CI Tiers And Test Budget; Wave 6 Exit Fence
- **Owner**: team-quality-closeout
- **Reversibility**: superseded only by new ADR or accepted decision-log supersession
- **Revisit trigger**: Final validation timing or flakiness requires changing lane ownership, timeout budgets, or gate order.
- **Revisit wave**: Wave 7
- **Promotion status**: retired

### DL-HDS-0015 - Wave 6 strict xfail disposition

- **Date**: 2026-05-16
- **Context**: Wave 6 proof-harness, anti-drift, red-control, and coverage checks require zero due temporary exceptions for the honest diagnostics substrate.
- **Decision**: Close the Wave 2 strict xfail carry-forward by requiring every due HDS exception to be either removed, retired, or superseded by an explicit later-wave decision before closeout.
- **Closes**: DL-HDS-0007
- **Affected ADR**: ADR-0147, ADR-0148, ADR-0149, ADR-0150, ADR-0152, ADR-0154, ADR-0155
- **Affected invariant id or phase id**: HDS-MCG-001; Phase 1.10; Wave 6
- **Owner**: team-architecture-governance
- **Reversibility**: superseded only by new ADR or accepted decision-log supersession
- **Revisit trigger**: Any strict xfail budget increases, broadens, or carries past its revisit wave.
- **Revisit wave**: Wave 7
- **Promotion status**: retired

### DL-HDS-0016 - Wave 6 operational closeout disposition

- **Date**: 2026-05-16
- **Context**: Wave 6 promotes the closeout authority from Wave 4 operational evidence to the final deterministic matrix, evidence inspection, runtime/API/local/dashboard smokes, coverage, anti-drift, and readiness outputs.
- **Decision**: Close the Wave 4 operational closeout carry-forward by requiring final evidence paths in the Wave 6 plan before archiving.
- **Closes**: DL-HDS-0008
- **Affected ADR**: ADR-0152, ADR-0153
- **Affected invariant id or phase id**: Wave 6 Exit Fence; Phase 6.1; Phase 6.4
- **Owner**: team-runtime-quality
- **Reversibility**: superseded only by new ADR or accepted decision-log supersession
- **Revisit trigger**: Final closeout evidence is missing, stale, or fails inspection/readiness.
- **Revisit wave**: Wave 7
- **Promotion status**: retired
