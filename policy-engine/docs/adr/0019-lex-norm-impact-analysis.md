# ADR-0019: Lex Norm Impact Analysis API (Phase 13)

## Status

Proposed

## Context

Phase 13 requires a deterministic "law-change simulator" for what-if analysis:

- mutate a baseline `NormPack`
- compare old/new packs structurally
- re-run selected governance passes
- produce a machine-readable impact report and persist it in CAS

The existing Lex and Governance modules already provide:

- stable `NormPack` IR contract
- pass-level execution via `PassContext`
- CAS persistence and provenance-ready references

but no dedicated impact-analysis API.

## Decision

Introduce `polisyos.lex.simulator` with:

1. `NormPackMutator` + `MutationIntent` for deterministic mutations and intent tracking.
2. `diff_norm_packs()` producing structured `NormDiff`.
3. `NormImpactAnalyzer` orchestrating:

   - structural diff
   - pass replay (`legal`, `safety`)
   - compliance delta classification
   - impact report assembly + CAS persistence
4. CLI command:
   `polisyos lex impact <old_ref> <new_ref> [--passes ...] [--profile ...]`

Artifacts:

- `lex.norm_diff`
- `lex.norm_impact_report`

Typed refs added to `core.contracts.lex`:

- `NormDiffRef`
- `NormImpactReportRef`

## Consequences

### Positive

- Fast policy-law what-if analysis without full simulation reruns.
- Deterministic mutation IDs and explicit mutation intent metadata.
- Native integration with CAS/replay/audit pipelines.

### Negative

- Additional maintenance surface in Lex module.
- KPI impact inference remains heuristic in Phase 13.

## Alternatives Considered

1. Rebuild full norm pipeline for each scenario: rejected due high cost and slow UX.
2. JSON patch only: rejected due poor semantic readability for policy analysts.
