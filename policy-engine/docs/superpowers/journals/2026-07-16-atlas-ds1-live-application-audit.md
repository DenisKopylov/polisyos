---
title: Atlas DS1 Live Application Audit Journal
status: active
owner: team-design
created: 2026-07-16
branch: codex/atlas-ds0-source-of-truth
worktree: .worktrees/atlas-ds0
---

# Atlas DS1 Live Application Audit Journal

This is the one journal created for DS1. It records the audit checkpoints on
the isolated Atlas branch and never edits the DS0 or parallel GY journal.

## 2026-07-16 - Executable-spec checkpoint

- Continued from DS0 HEAD `1afee84f8` in `.worktrees/atlas-ds0` on
  `codex/atlas-ds0-source-of-truth`; the worktree was clean.
- Re-read, in order, Revision 2 of the Atlas master plan, the surface
  constitution, and `docs/brand/ATLAS_SOURCE_OF_TRUTH.md`.
- Re-read `CONTRIBUTING.md` and the failure/repair register before design.
- Confirmed the DS1 output is an exhaustive live-code map, not a sample or an
  implementation slice. Application, package, frontend, e2e, and runtime HTTP
  paths remain read-only.
- Chose one human report under `docs/reference/frontend/` and one real
  readiness-ledger instance under `architecture/atlas_surfaces/`. The report
  carries adoption verdicts and plan impact; the machine twin reuses the DS0
  readiness schema without extending its vocabulary.
- Defined full-denominator reconciliation and set-difference checks as closure
  gates. A discovered unit without a report and ledger row is a finding and
  blocks closure.

Next checkpoint: commit the DS1 executable plan, then begin recomputing the
inventory from the live tree.

## 2026-07-16 - Inventory and UI-estate checkpoint

- Recomputed the June denominators instead of inheriting them. Dashboard
  `src` is still exactly 908 TS/TSX and 136,827 physical LOC, while the full
  frontend zone is 944 TS/TSX and 145,033 LOC. The old 230-test number counted
  dashboard-source `.test` files and omitted 3 authored source specs, 17 e2e
  specs, and the CLI test.
- Expanded the route denominator to 32 declared objects, 29 effective URL
  patterns, and 22 leaf UI patterns. Recorded the redundant second `/` index
  route and the five leaf routes absent from browser axe coverage.
- Audited all 17 feature directories. `features/layout` is empty;
  collaboration, export, and onboarding have no outside production importer;
  these are disposition findings, not omissions.
- Reconciled 89 shared/UI implementation TSX files into 12 named families.
  No family meets the constitution's `stable` bar. The structural a11y test's
  allowlist omits `OperatorDiagnosticPanel`, making the current gate red by
  set difference; an isolated test command could not start because installed
  Vitest dependencies are absent, and no installation was attempted.
- Audited the reference shell's four button-switched views. It directly uses
  the package generated client, refuting the plan's dashboard-only consumer
  claim.
- Created the canonical report and froze stable IDs for routes, features, UI
  families, and reference-shell views. The application/runtime tree remained
  untouched and clean before report creation.

Next checkpoint: add the 89-operation bidirectional census, local statuses,
flags, transports, authorization matrix, and adjacent/evidence estates.
