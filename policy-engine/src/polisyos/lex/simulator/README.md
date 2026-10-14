# Simulator (`polisyos.lex.simulator`)

`polisyos.lex.simulator` performs what-if analysis of `NormPack` changes:
mutation, diff, and impact analysis before changes enter the main policy pipeline.
This is a legal sandbox for comparing baseline and proposed norm bundles.

## Role in the system

- **Depends on:** `polisyos.lex.normpack`, `polisyos.core.governance`, `polisyos.ir.loading.norm_pack`
- **Used by:** policy-design review, governance validation, and explicit norm-change analysis
- The package separates legal what-if analysis from the production assembly/evaluation path.

## Key concepts

- **Deterministic mutation** — `NormPackMutator` creates a new `pack_id` and mutation trace for reproducible sandbox runs.
- **Structured diff** — `diff_norm_packs()` computes `added/removed/modified/unchanged` plus field-level deltas.
- **Impact analysis** — `NormImpactAnalyzer` runs governance passes on old/new packs and aggregates compliance transitions.
- **Persistence surface** — with `persist=True`, `lex.norm_diff` and `lex.norm_impact_report` are published.
- **Report models** — `NormImpactReport`, `ComplianceDelta`, and `AffectedKPI` define the human-facing result surface.

## Public API

| Type/Function                                                                | Description                                            |
| ---------------------------------------------------------------------------- | ------------------------------------------------------ |
| `NormPackMutator`                                                            | Deterministic mutation builder for baseline `NormPack` |
| `MutationIntent`                                                             | Structured description of requested norm changes       |
| `diff_norm_packs()`                                                          | Compute structured diff between old and new packs      |
| `NormDiff`, `NormChange`, `NormChangeType`                                   | Diff result contracts                                  |
| `NormImpactAnalyzer`                                                         | Run governance-based impact analysis over pack deltas  |
| `NormImpactReport`, `ComplianceDelta`, `ComplianceTransition`, `AffectedKPI` | Final impact-report models                             |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 6 Python files
- Exports: 12 symbols in `__init__.py`
- Notable delta: package remains stable, but README is now aligned with the shared template and explicit about diff/impact contracts
