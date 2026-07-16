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

## 2026-07-16 - Contract, transport, and authority checkpoint

- Enumerated all 89 checked-in OpenAPI method/path operations: 45 reach a
  production surface, 7 stop at hook/client definitions, and 37 have no
  dashboard call. The reference shell consumes eight operations already in
  the 45-set through a second generated-client home.
- Found exactly 9 production `fetch` calls outside `src/api` in 5 files, not
  about 10 files. Lex has migrated to typed hooks. Recorded all sites and the
  tooling-only tenth call separately.
- Recorded 23 named + 24 inline UI-local status definitions. The three
  `DisputeStatus` definitions form two vocabularies; operational and
  authority-adjacent states are not namespaced cleanly.
- Confirmed all 12 canonical flag defaults are true, all four D5
  `consumer_missing` claims remain true, and three affected surfaces are live
  outside those flags. `/auth/me` remains a thirteenth permission-derived
  pseudo-source; unknown manifest keys are ignored.
- Audited SSE/WS, three worker modules, the service worker, both IndexedDB
  stores, query cache, all authority-looking local stores, raw telemetry, and
  Sentry. Collaboration REST/WS is phantom but its whole feature is orphaned;
  the review WS has an authentication bridge risk.
- Recomputed the unsafe-method denominator from server decorators: 29 POST,
  zero PUT/PATCH/DELETE, audited 29/29. None has an action-permission or
  step-up dependency. Recorded the late OPA resource binding, fixture identity
  reach, fail-open UI placeholder, 12-server/15-client permission delta, and
  self-asserted production approval chain.
- Completed all named P15/P05 surfaces, the browser-signing blast radius,
  cache policy, 23 red-first negative specifications, and DS3-DS18 Plan Impact
  Appendix. Corrected only the evidence-backed master-plan snapshot/scope
  statements.
- Populated the first real readiness ledger with 261 entries generated from
  the delimited report index. JSON Schema validation passed; report and ledger
  both contain 261 unique IDs with empty set differences. All 408 local links
  in the report/master check resolved at this checkpoint.

Next checkpoint: close the task-plan checklist, run independent ledger/content
checks, final link/fence/diff/clean-tree verification, and commit DS1 closeout.
